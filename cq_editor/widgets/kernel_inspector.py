from PyQt5.QtWidgets import (QDockWidget, QTreeWidget, QTreeWidgetItem, 
                             QVBoxLayout, QWidget, QPushButton)
from PyQt5.QtCore import Qt
from ..mixins import ComponentMixin

import cadquery as cq


from OCP.AIS import AIS_Shape, AIS_Point
from OCP.Geom import Geom_CartesianPoint
from OCP.Prs3d import Prs3d_PointAspect
from OCP.Aspect import Aspect_TOM_PLUS, Aspect_TOM_O
from OCP.Quantity import (Quantity_Color, Quantity_NOC_GREEN, Quantity_NOC_BLUE, 
                          Quantity_NOC_RED, Quantity_NOC_YELLOW, Quantity_NOC_CYAN)
from OCP.BRepTools import BRepTools
from OCP.BRep import BRep_Tool

class KernelInspector(QWidget, ComponentMixin):
    name = "Kernel Inspector" 

    def __init__(self, parent=None):
        super(KernelInspector, self).__init__(parent)
        self.setWindowTitle("Kernel Inspector") 
        self.temp_objects = [] 
        

        container = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0,0,0,0)
        
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Property", "Value"])
        self.tree.setColumnWidth(0, 160)
        self.tree.setAlternatingRowColors(True)
        self.tree.itemClicked.connect(self.on_tree_click)
        
        self.btn = QPushButton("Analyze Selection")
        self.btn.clicked.connect(self.analyze)
        
        layout.addWidget(self.tree)
        layout.addWidget(self.btn)
        container.setLayout(layout)
        self.setLayout(layout)

    # --- REQUIRED FOR COMPONENT SYSTEM ---
    def menuActions(self):
        return {}

    def toolbarActions(self):
        return []
    # --------------------------------------
    def get_viewer(self):
        if self.parent() and hasattr(self.parent(), 'components'):
            return self.parent().components.get('viewer')
        if self.parent() and self.parent().parent() and hasattr(self.parent().parent(), 'components'):
             return self.parent().parent().components.get('viewer')
        return None

    def locate_context(self):
        vc = self.get_viewer()
        if not vc: return None
        
        if hasattr(vc, '_get_context'): return vc._get_context()
        if hasattr(vc, '_display'): return vc._display.Context
        if hasattr(vc, 'widget') and hasattr(vc.widget, 'display'): 
            return vc.widget.display.Context
        return None


    def analyze(self):
        ctx = self.locate_context()
        if not ctx: 
            print("Kernel Inspector: Could not locate OCP Context")
            return

        self.tree.clear()
        self.clear_highlight(ctx)
        
        selection = []
        ctx.InitSelected()
        
        while ctx.MoreSelected():
            try:
                ais_obj = ctx.SelectedInteractive()
                topo_shape = None


                if hasattr(ais_obj, "Shape"):
                    topo_shape = ais_obj.Shape()
                

                elif hasattr(ais_obj, "get"):
                    topo_shape = ais_obj.get().Shape()

                if topo_shape and not topo_shape.IsNull():
                    cq_shape = cq.Shape.cast(topo_shape)
                    self._unwrap_and_append(cq_shape, selection, ctx)
                else:
                    print("   -> Object has no geometry (Shape() method missing or returned Null).")

            except Exception as e:
                print(f"Error processing selection: {e}")

            ctx.NextSelected()

        if not selection:
            self.add_pair("Status", "Nothing Selected")
            return

        self.add_pair("Selection Count", str(len(selection)))
        
        for i, shape in enumerate(selection):
            label = f"{shape.ShapeType()}[{i}]"
            item = QTreeWidgetItem(self.tree, [label, " "])
            item.setData(0, Qt.UserRole, shape)  
            self.inspect_shape(shape, item)

    def _unwrap_and_append(self, cq_shape, selection, ctx):
        if cq_shape.ShapeType() == "Compound":
            solids = cq_shape.Solids()
            faces = cq_shape.Faces()
            wires = cq_shape.Wires()
            edges = cq_shape.Edges()
            vertices = cq_shape.Vertices()
            
            if len(solids) == 1: selection.append(solids[0])
            elif len(faces) == 1: selection.append(faces[0])
            elif len(wires) == 1: selection.append(wires[0])
            elif len(edges) == 1: selection.append(edges[0])
            elif len(vertices) == 1: selection.append(vertices[0])
            
            elif len(solids) > 1: selection.extend(solids)
            elif len(faces) > 1: selection.extend(faces)
            elif len(wires) > 1: selection.extend(wires)
            elif len(edges) > 1: selection.extend(edges)
            elif len(vertices) > 1: selection.extend(vertices)
            else: selection.append(cq_shape)
        else:
            selection.append(cq_shape)

    def on_tree_click(self, item, column):
        shape = item.data(0, Qt.UserRole)
        if shape: self.highlight_shape(shape)
        elif item.parent() and item.parent().data(0, Qt.UserRole):
            self.highlight_shape(item.parent().data(0, Qt.UserRole))
    def draw_marker(self, vec, color_enum, ctx=None):
        """ Helper to draw a dot at a specific coordinate """
        geom_pt = Geom_CartesianPoint(vec.x, vec.y, vec.z)
        ais_pt = AIS_Point(geom_pt)
        
        drawer = ais_pt.Attributes()
        aspect = Prs3d_PointAspect(Aspect_TOM_O, Quantity_Color(color_enum), 2.0)
        drawer.SetPointAspect(aspect)
        
        if ctx is None:
            ctx = self.locate_context()
        if ctx:
            ctx.Display(ais_pt, True)
        self.temp_objects.append(ais_pt)

    def highlight_shape(self, shape):
        ctx = self.locate_context()
        if not ctx: return
        self.clear_highlight(ctx)
        
        try:
            stype = shape.ShapeType()
            
            main_ais = AIS_Shape(shape.wrapped)
            main_ais.SetColor(Quantity_Color(Quantity_NOC_GREEN))
            main_ais.SetWidth(3.0)
            
            if stype == "Vertex":
                drawer = main_ais.Attributes()
                aspect = Prs3d_PointAspect(Aspect_TOM_PLUS, Quantity_Color(Quantity_NOC_CYAN), 4.0)
                drawer.SetPointAspect(aspect)
            
            ctx.Display(main_ais, True)
            self.temp_objects.append(main_ais)
            
            if stype in ["Edge", "Wire"]:
                try:
                    self.draw_marker(shape.endPoint(), Quantity_NOC_RED, ctx)
                    self.draw_marker(shape.startPoint(), Quantity_NOC_BLUE, ctx) 
                except: 
                    print("Edge marker draw error")

            if stype == "Face":
                try:
                    topo_face = shape.wrapped
                    umin, umax, vmin, vmax = BRepTools.UVBounds_s(topo_face)
                    mid_u = (umin + umax) / 2.0
                    mid_v = (vmin + vmax) / 2.0
                    surf = BRep_Tool.Surface_s(topo_face)
                    p_on_surf = surf.Value(mid_u, mid_v) 
                    c = cq.Vector(p_on_surf.X(), p_on_surf.Y(), p_on_surf.Z())
                    n = shape.normalAt(c)

                    bb = shape.BoundingBox()
                    length = max(bb.DiagonalLength * 0.2, 1.0)
                    end_pt = c + n.multiply(length)
                    line_edge = cq.Edge.makeLine(c, end_pt)
                    
                    vec_ais = AIS_Shape(line_edge.wrapped)
                    vec_ais.SetColor(Quantity_Color(Quantity_NOC_YELLOW))
                    vec_ais.SetWidth(2.0)
                    
                    arrow_size = length * 0.15
                    arrow_base = c + n.multiply(length - arrow_size)
                    

                    arrow = cq.Solid.makeCone(arrow_size * 0.3, 0, arrow_size, 
                                              pnt=arrow_base, dir=n)
                    arrow_ais = AIS_Shape(arrow.wrapped)
                    arrow_ais.SetColor(Quantity_Color(Quantity_NOC_YELLOW))
                    ctx.Display(arrow_ais, True)
                    self.temp_objects.append(arrow_ais)
                    

                    ctx.Display(vec_ais, True)
                    self.temp_objects.append(vec_ais)
                    
                except Exception as e:
                    print(f"Normal draw error: {e}")

        except Exception as e:
            print(f"Highlight Error: {e}")

    def clear_highlight(self, ctx):
        for obj in self.temp_objects:
            ctx.Remove(obj, False)
        if self.temp_objects:
            ctx.UpdateCurrentViewer()
        self.temp_objects = []

    def inspect_shape(self, shape, parent):
        stype = shape.ShapeType()
        try:
            bb = shape.BoundingBox()
            self.add_child(parent, "Dimensions", f"{bb.xlen:.2f} x {bb.ylen:.2f} x {bb.zlen:.2f}")
            c = bb.center
            self.add_child(parent, "Center", f"({c.x:.2f}, {c.y:.2f}, {c.z:.2f})")
        except: pass

        if stype == "Edge" or stype == "Wire":
            try:
                self.add_child(parent, "Length", f"{shape.Length():.4f} mm")
                self.add_child(parent, "Curve Type", shape.geomType())
                sp = shape.positionAt(0)
                self.add_child(parent, "Start Point", f"({sp.x:.2f}, {sp.y:.2f}, {sp.z:.2f})")
                ep = shape.positionAt(1)
                self.add_child(parent, "End Point", f"({ep.x:.2f}, {ep.y:.2f}, {ep.z:.2f})")
            except: pass
        elif stype == "Face":
            try:
                self.add_child(parent, "Area", f"{shape.Area():.4f} mm²")
                self.add_child(parent, "Surface Type", shape.geomType())
                norm = shape.normalAt(shape.Center())
                self.add_child(parent, "Normal Vector", f"({norm.x:.4f}, {norm.y:.4f}, {norm.z:.4f})")
            except: pass
        elif stype == "Solid":
            try:
                self.add_child(parent, "Volume", f"{shape.Volume():.4f} mm³")
                # let's add bounding box dimensions for solids
                bb = shape.BoundingBox()
                self.add_child(parent, "Bounding Box", f"{bb.xlen:.2f} x {bb.ylen:.2f} x {bb.zlen:.2f}")
                
            except: pass

    def add_pair(self, k, v):
        QTreeWidgetItem(self.tree, [k, str(v)])
    
    def add_child(self, p, k, v):
        QTreeWidgetItem(p, [k, str(v)])