import cadquery as cq
import ezdxf
import math

# OCP Imports
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.GCPnts import GCPnts_QuasiUniformDeflection
from OCP.TopExp import TopExp
from OCP.TopAbs import TopAbs_EDGE, TopAbs_VERTEX

def generate_wire_code(filename):
    ext = filename.lower().split('.')[-1]
    if ext in ['step', 'stp']:
        edges = _load_step_edges(filename)
    elif ext == 'dxf':
        #edges = _load_dxf_edges(filename)
        raise NotImplementedError("DXF support is currently disabled due to stability issues. Please use STEP files for now.")
    else:
        raise ValueError("Unsupported format.")

    if not edges:
        raise ValueError("No geometry found.")

    ordered_edges = _sort_edges(edges)
    commands = _analyze_chain(ordered_edges)
    return _format_hybrid_code(commands, filename)

# --- LOADERS ---
def _load_step_edges(filename):
    try:
        model = cq.importers.importShape(fileName=filename, importType="STEP")
        return model.edges().vals()
    except Exception as e:
        raise ValueError(f"STEP Load Error: {e}")

def _load_dxf_edges(filename):
    try:
        doc = ezdxf.readfile(filename)
        msp = doc.modelspace()
    except Exception as e:
        raise ValueError(f"DXF Load Error: {e}")

    edges = []

    def to_vec(v):
        return cq.Vector(v[0], v[1], v[2])

    for entity in msp:
        try:
            prims = entity.virtual_entities()
        except:
            prims = [entity]

        for prim in prims:
            etype = prim.dxftype()

            if etype == 'LINE':
                p1 = to_vec(prim.dxf.start)
                p2 = to_vec(prim.dxf.end)
                
                if (p1 - p2).Length > 1e-5:
                    edges.append(cq.Edge.makeLine(p1, p2))

            elif etype in ['SPLINE', 'ARC', 'ELLIPSE']:
                try:
                    pts = list(prim.flattening(distance=0.1))
                    vecs = [to_vec(p) for p in pts]
                    
                    if len(vecs) > 1:
                        edges.append(cq.Edge.makeSpline(vecs))
                except Exception as e:
                    print(f"Skipping invalid curve: {e}")

    return edges

def _sort_edges(edges):
    from collections import defaultdict

    if not edges: return []
    adj = defaultdict(list)
    
    def get_key(v):
        return (round(v.x, 4), round(v.y, 4), round(v.z, 4))
    
    for e in edges:
        k1 = get_key(e.startPoint())
        k2 = get_key(e.endPoint())
        adj[k1].append(e)
        adj[k2].append(e)
    
    start_node_key = None
    for k, connected_edges in adj.items():
        if len(connected_edges) == 1:
            start_node_key = k
            break
            
    if start_node_key is None:
        start_node_key = get_key(edges[0].startPoint())

    sorted_chain = []
    visited = set()
    current_key = start_node_key
    
    while len(sorted_chain) < len(edges):
        candidates = adj[current_key]
        
        # Find the unvisited neighbor
        next_edge = None
        for e in candidates:
            if e not in visited:
                next_edge = e
                break
        
        if not next_edge:
            break
        s_key = get_key(next_edge.startPoint())
        e_key = get_key(next_edge.endPoint())
        
        if s_key != current_key:
            next_edge = next_edge.reverse()
            current_key = s_key 
        else:
            current_key = e_key 
            
        visited.add(next_edge)
        sorted_chain.append(next_edge)

    return sorted_chain

def _analyze_chain(edges):
    commands = []
    
    if not edges: return []

    current_type = None 
    current_points = []
    
    def flush():
        nonlocal current_points
        if current_points:
            # Dedupe logic
            clean = []
            for p in current_points:
                if not clean or clean[-1] != p:
                    clean.append(p)
            if len(clean) > 0:
                commands.append((current_type, clean))
            current_points = []

    for edge in edges:
        # Detect Type
        is_line = (edge.geomType() == "LINE")
        seg_type = "polyline" if is_line else "spline"
        
        # Determine points for this edge
        pts = []
        if is_line:
            pts.append(edge.startPoint())
            pts.append(edge.endPoint())
        else:
            # Discretize curve
            adaptor = BRepAdaptor_Curve(edge.wrapped)
            discretizer = GCPnts_QuasiUniformDeflection(adaptor, 0.1)
            if discretizer.IsDone():
                for i in range(1, discretizer.NbPoints() + 1):
                    p = discretizer.Value(i)
                    pts.append(cq.Vector(p.X(), p.Y(), p.Z()))

        # If type changed, flush the old buffer
        if seg_type != current_type:
            flush()
            current_type = seg_type
            current_points = pts
        else:
            # Same type, append points (skip first one if it matches last)
            if current_points and pts:
                if (current_points[-1] - pts[0]).Length < 1e-4:
                    current_points.extend(pts[1:])
                else:
                    current_points.extend(pts)
            else:
                current_points.extend(pts)
                
    flush() # Final flush
    return commands

def _format_hybrid_code(commands, filename):
    code_lines = []
    code_lines.append("cq.Workplane(cq.Wire.assembleEdges([")

    def vec_str(v):
        return f"cq.Vector({v.x:.3f}, {v.y:.3f}, {v.z:.3f})"

    def list_str(points):
        return "[" + ", ".join([vec_str(p) for p in points]) + "]"

    for i, (cmd_type, points) in enumerate(commands):
        # We need at least 2 points to make an edge
        if len(points) < 2: continue

        if cmd_type == "polyline":
            for j in range(len(points) - 1):
                p1 = points[j]
                p2 = points[j+1]
                # Filter microscopic segments that crash the kernel
                if (p1 - p2).Length > 1e-5:
                    line_code = f"cq.Edge.makeLine({vec_str(p1)}, {vec_str(p2)}),"
                    code_lines.append(line_code)

        elif cmd_type == "spline":
            spline_code = f"cq.Edge.makeSpline({list_str(points)}),"
            code_lines.append(spline_code)

    code_lines.append("]))")
    
    
    return " ".join(code_lines)