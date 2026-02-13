import cadquery as cq

# OCP Imports
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.GCPnts import GCPnts_QuasiUniformDeflection

def generate_wire_code(filename):
    """
    Reads a STEP file, extracts Wires, and generates 3D Edge Assembly code.
    """
    ext = filename.lower().split('.')[-1]
    if ext not in ['step', 'stp']:
        raise ValueError("Unsupported format. Use STEP.")

    wires = _load_step_wires(filename)

    if not wires:
        raise ValueError("No Wires found in STEP file. Ensure you exported a Wire/Path, not just loose edges.")

    code_segments = []
    
    for i, wire in enumerate(wires):

        edges = wire.Edges()
        
        commands = _analyze_chain(edges)
        
        block = _format_hybrid_code(commands)
        code_segments.append(block)

    return "\n\n".join(code_segments)


def _load_step_wires(filename):
    try:
        model = cq.importers.importShape(fileName=filename, importType="STEP")
        wires:cq.Workplane = model.wires()
        if (not wires or wires.size() == 0):
            print("No wires found in step file. Attempting to assemble edges into wires (not recommended, may produce incorrect results). Please export as a joined Wire/Curve in your CAD tool.")
            wires = cq.Workplane(cq.Wire.assembleEdges(model.edges().vals()))
        return wires.vals()
    except Exception as e:
        raise ValueError(f"STEP Load Error: {e}")

def _analyze_chain(edges):
    commands = []
    if not edges: return []

    current_type = None 
    current_points = []
    
    def flush():
        nonlocal current_points
        if current_points:
            clean = []
            for p in current_points:
                if not clean or clean[-1] != p:
                    clean.append(p)
            if len(clean) > 1:
                commands.append((current_type, clean))
            current_points = []

    for edge in edges:
        is_line = (edge.geomType() == "LINE")
        seg_type = "polyline" if is_line else "spline"
        
        pts = []
        if is_line:
            pts.append(edge.startPoint())
            pts.append(edge.endPoint())
        else:
            adaptor = BRepAdaptor_Curve(edge.wrapped)
            discretizer = GCPnts_QuasiUniformDeflection(adaptor, 0.1)
            if discretizer.IsDone():
                for i in range(1, discretizer.NbPoints() + 1):
                    p = discretizer.Value(i)
                    pts.append(cq.Vector(p.X(), p.Y(), p.Z()))

        if seg_type != current_type:
            flush()
            current_type = seg_type
            current_points = pts
        else:
            if current_points and pts:

                if (current_points[-1] - pts[0]).Length < 1e-4:
                    current_points.extend(pts[1:])
                else:
                    flush()
                    current_type = seg_type
                    current_points.extend(pts)
            else:
                current_points.extend(pts)
                
    flush()
    return commands

def _format_hybrid_code(commands):
    code_lines = []
    code_lines.append(f"cq.Workplane(cq.Wire.assembleEdges([")

    def vec_str(v):
        return f"cq.Vector({v.x:.3f}, {v.y:.3f}, {v.z:.3f})"

    def list_str(points):
        return "[" + ", ".join([vec_str(p) for p in points]) + "]"

    for i, (cmd_type, points) in enumerate(commands):
        if len(points) < 2: continue

        if cmd_type == "polyline":
            for j in range(len(points) - 1):
                p1 = points[j]
                p2 = points[j+1]
                if (p1 - p2).Length > 1e-5:
                    code_lines.append(f"    cq.Edge.makeLine({vec_str(p1)}, {vec_str(p2)}),")

        elif cmd_type == "spline":
            code_lines.append(f"    cq.Edge.makeSpline({list_str(points)}),")
    
    code_lines.append("]))")
    
    return "\n".join(code_lines)