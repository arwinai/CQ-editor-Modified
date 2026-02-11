import cadquery as cq
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget, 
                             QPushButton, QComboBox, QMessageBox, QLabel, 
                             QDoubleSpinBox, QCheckBox, QAbstractItemView)
from PyQt5.QtCore import Qt
from ..mixins import ComponentMixin

from OCP.AIS import AIS_Shape
from OCP.Quantity import Quantity_Color, Quantity_NOC_ORANGE, Quantity_NOC_CYAN
# WIP - this doesn't work yet. 
class Pathfinder(QWidget, ComponentMixin):
    name = "Pathfinder"
    
    def __init__(self, parent=None):
        super(Pathfinder, self).__init__(parent)
        self.app = parent
        self.points = []
        self.temp_shapes = []
        
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)

        layout.addWidget(QLabel("<b>Path Points:</b>"))
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list_widget.setDragDropMode(QAbstractItemView.InternalMove)
        layout.addWidget(self.list_widget)

        btn_layout = QHBoxLayout()
        self.btn_capture = QPushButton("Capture Vertex")
        self.btn_capture.clicked.connect(self.capture_point)
        self.btn_capture.setStyleSheet("font-weight: bold;")
        self.btn_remove = QPushButton("Remove")
        self.btn_remove.clicked.connect(self.remove_point)
        btn_layout.addWidget(self.btn_capture)
        btn_layout.addWidget(self.btn_remove)
        layout.addLayout(btn_layout)

        prev_group = QHBoxLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Polyline", "Spline"])
        self.mode_combo.currentIndexChanged.connect(self.update_preview)
        
        self.chk_pipe = QCheckBox("Pipe")
        self.chk_pipe.toggled.connect(self.update_preview)
        
        self.spin_radius = QDoubleSpinBox()
        self.spin_radius.setValue(1.0)
        self.spin_radius.setSingleStep(0.5)
        self.spin_radius.setSuffix(" mm")
        self.spin_radius.valueChanged.connect(self.update_preview)
        
        prev_group.addWidget(self.mode_combo)
        prev_group.addWidget(self.chk_pipe)
        prev_group.addWidget(self.spin_radius)
        layout.addLayout(prev_group)

        act_layout = QHBoxLayout()
        self.btn_preview = QPushButton("Refresh")
        self.btn_preview.clicked.connect(self.update_preview)
        self.btn_clear = QPushButton("Clear")
        self.btn_clear.clicked.connect(self.clear_all)
        act_layout.addWidget(self.btn_preview)
        act_layout.addWidget(self.btn_clear)
        layout.addLayout(act_layout)

        self.btn_insert = QPushButton("Insert Code ->")
        self.btn_insert.setStyleSheet("background-color: #d1e7dd; color: #0f5132; font-weight: bold;")
        self.btn_insert.clicked.connect(self.insert_code)
        layout.addWidget(self.btn_insert)
        self.setLayout(layout)

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

    def capture_point(self):
        ctx = self.locate_context()
        if not ctx: return

        ctx.InitSelected()
        found = False
        
        while ctx.MoreSelected():
            ais = ctx.SelectedInteractive()
            try:
                if hasattr(ais, "Shape"):
                    # 1. Cast the generic OCP shape to a CadQuery shape
                    raw_shape = ais.Shape()
                    shp = cq.Shape.cast(raw_shape)
                    
                    # 2. Extract vertices regardless of the wrapper (Compound/Solid/etc)
                    # This fixes the "It's always a Compound" issue.
                    selected_vertices = shp.Vertices()
                    
                    if not selected_vertices:
                        # If for some reason .Vertices() comes up empty (unlikely),
                        # check if the shape itself is a vertex (fallback)
                        if shp.ShapeType() == "Vertex":
                            selected_vertices = [shp]

                    # 3. Add valid vertices
                    for v in selected_vertices:
                        vec = v.Center()
                        
                        # Optional: Avoid duplicates (clicking the same spot twice)
                        # A simple check to see if we already have this point
                        is_duplicate = False
                        if self.points:
                            last = self.points[-1]
                            if (vec - last).Length < 1e-5: # Tolerance check
                                is_duplicate = True
                        
                        if not is_duplicate:
                            self.points.append(vec)
                            self.list_widget.addItem(f"({vec.x:.2f}, {vec.y:.2f}, {vec.z:.2f})")
                            found = True
                            
            except Exception as e:
                print(f"Capture Error: {e}")
                
            ctx.NextSelected()
        
        if found: 
            self.update_preview()
        else: 
            # If we truly found nothing
            # Note: Sometimes OCP selection is tricky. If this triggers when you feel
            # you HAVE selected something, try selecting the object first, then the vertex.
            QMessageBox.warning(self, "Selection Error", "Could not find a Vertex in the selection.")
    
    def remove_point(self):
        rows = sorted([item.row() for item in self.list_widget.selectedIndexes()], reverse=True)
        for row in rows:
            self.points.pop(row)
            self.list_widget.takeItem(row)
        self.update_preview()

    def update_preview(self):
        ctx = self.locate_context()
        if not ctx: return
        for obj in self.temp_shapes: ctx.Remove(obj, True)
        self.temp_shapes = []
        if len(self.points) < 2: return

        try:
            mode = self.mode_combo.currentText()
            path_wire = cq.Workplane().polyline(self.points).val() if mode == "Polyline" else cq.Workplane().spline(self.points).val()

            ais_wire = AIS_Shape(path_wire.wrapped)
            ais_wire.SetColor(Quantity_Color(Quantity_NOC_ORANGE))
            ais_wire.SetWidth(3.0)
            ctx.Display(ais_wire, True)
            self.temp_shapes.append(ais_wire)

            if self.chk_pipe.isChecked():
                r = self.spin_radius.value()
                pipe_solid = cq.Workplane().circle(r).sweep(cq.Workplane(obj=path_wire)).val()
                ais_pipe = AIS_Shape(pipe_solid.wrapped)
                ais_pipe.SetColor(Quantity_Color(Quantity_NOC_CYAN))
                ais_pipe.SetTransparency(0.6)
                ctx.Display(ais_pipe, True)
                self.temp_shapes.append(ais_pipe)
        except Exception as e: print(f"Preview Error: {e}")

    def clear_all(self):
        ctx = self.locate_context()
        for obj in self.temp_shapes:
            if ctx: ctx.Remove(obj, True)
        self.temp_shapes = []
        self.points = []
        self.list_widget.clear()
    def get_editor(self):
        # Use self.app instead of self.parent()
        if hasattr(self.app, 'components'):
            return self.app.components.get('editor')
        return None
    
    def insert_code(self):
        if not self.points: return
        try:
            pts_str = "[\n" + ",\n".join([f"    ({p.x:.3f}, {p.y:.3f}, {p.z:.3f})" for p in self.points]) + "\n]"
            mode = self.mode_combo.currentText().lower()
            r = self.spin_radius.value()
            code = f"""
path_points = {pts_str}
path = cq.Workplane().{mode}(path_points)
profile = cq.Wire.makeCircle({r})
path_w = path.wire()
p = path_w.positionAt(0)
xDir = path_w.tangentAt(0)
normal = path_w.normalAt(0)
plane = cq.Plane(origin=p, xDir=xDir, normal=normal)
profile = profile.move(plane.location)
sweep = cq.Workplane(profile).sweep(path)
"""
            
            # Use the fixed helper
            editor = self.get_editor()
            if editor:
                print(dir(editor))
                editor.textCursor().insertText(code)
        except Exception as e:
            print(f"Insert Code Error: {e}")