from traceback import extract_tb
from itertools import dropwhile

from PyQt5.QtWidgets import (QWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout, 
                             QAction, QMenu, QApplication)
from PyQt5.QtCore import Qt, pyqtSlot, pyqtSignal
from PyQt5.QtGui import QColor, QKeySequence

from ..mixins import ComponentMixin

class TracebackPane(QWidget, ComponentMixin):

    name = "Traceback Viewer"
    sigHighlightLine = pyqtSignal(int)

    def __init__(self, parent=None):
        super(TracebackPane, self).__init__(parent)
        
        # --- UI LAYOUT ---
        # We replace the old helper 'layout()' with standard VBox for clarity
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)

        # --- THE TREE ---
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["File / Error", "Line", "Code"])
        
        # Visual Tweaks
        self.tree.setColumnWidth(0, 300) 
        self.tree.setColumnWidth(1, 60)
        self.tree.setItemsExpandable(True)  # Key feature: Expandable
        self.tree.setRootIsDecorated(True)  # Show the little arrows
        self.tree.setAlternatingRowColors(True)
        
        # Selection Logic
        self.tree.currentItemChanged.connect(self.handleSelection)
        
        # Context Menu (Right Click)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.open_menu)

        self.layout.addWidget(self.tree)

    @pyqtSlot(object, str)
    def addTraceback(self, exc_info, code):
        """
        Populates the tree with an expandable error report.
        """
        self.tree.clear()

        if exc_info:
            t, exc, tb = exc_info
            
            # 1. Create the Top-Level Item (The Error Message)
            exc_name = t.__name__
            exc_msg = str(exc)
            header_text = f"{exc_name}: {exc_msg}"
            
            root_item = QTreeWidgetItem(self.tree, [header_text, "", ""])
            
            # Style it: Bold & Red
            font = root_item.font(0)
            font.setBold(True)
            root_item.setFont(0, font)
            root_item.setForeground(0, QColor("red"))
            
            # Always expand the error so the user sees the stack immediately
            root_item.setExpanded(True)

            # 2. Process Stack Trace
            code_lines = code.splitlines()

            # Filter out internal calls (files not containing <string>)
            # This logic mimics the original behavior to focus on user code
            filtered_trace = dropwhile(
                lambda el: "string>" not in el.filename, extract_tb(tb)
            )

            for el in filtered_trace:
                # Resolve line content
                if el.line == "":
                    # If traceback doesn't have the line content, grab it from source
                    try:
                        line_content = code_lines[el.lineno - 1].strip()
                    except IndexError:
                        line_content = "???"
                else:
                    line_content = el.line

                # Add Child Item
                child = QTreeWidgetItem(root_item, [el.filename, str(el.lineno), line_content])
                
                # Store metadata for navigation
                # data(0) = filename, data(1) = lineno
                child.setData(0, Qt.UserRole, el.filename)
                child.setData(1, Qt.UserRole, el.lineno)

            # 3. Handle SyntaxError specially (it has its own offset info)
            if t is SyntaxError:
                filename = exc.filename or "<string>"
                lineno = str(exc.lineno) if exc.lineno else "?"
                text = exc.text.strip() if exc.text else ""
                
                child = QTreeWidgetItem(root_item, [filename, lineno, text])
                child.setData(0, Qt.UserRole, filename)
                child.setData(1, Qt.UserRole, exc.lineno)

    @pyqtSlot(QTreeWidgetItem, QTreeWidgetItem)
    def handleSelection(self, item, prev):
        """
        Jumps to line in editor when a stack frame is clicked.
        """
        if not item: return

        # Retrieve stored metadata
        f_name = item.data(0, Qt.UserRole)
        lineno = item.data(1, Qt.UserRole)

        if f_name and lineno:
            if "<string>" in f_name:
                self.sigHighlightLine.emit(int(lineno))

    # --- COPY / PASTE SUPPORT ---

    def keyPressEvent(self, event):
        """ Enable Ctrl+C to copy error """
        if event.matches(QKeySequence.Copy):
            self.copy_selection()
        else:
            super().keyPressEvent(event)

    def open_menu(self, position):
        """ Right-click context menu """
        menu = QMenu()
        copy_act = QAction("Copy Error Info", self)
        copy_act.triggered.connect(self.copy_selection)
        menu.addAction(copy_act)
        menu.exec_(self.tree.viewport().mapToGlobal(position))

    def copy_selection(self):
        """ Formats the selected item (or root) for the clipboard """
        item = self.tree.currentItem()
        if not item: return

        text_to_copy = ""
        
        # If it's the root (The Error Message)
        if not item.parent():
            text_to_copy = item.text(0) # The error message
            # Optionally append children info
            for i in range(item.childCount()):
                child = item.child(i)
                text_to_copy += f"\n  File {child.text(0)}, line {child.text(1)}\n    {child.text(2)}"
        else:
            # It's a stack frame
            text_to_copy = f"File {item.text(0)}, line {item.text(1)}\n    {item.text(2)}"

        QApplication.clipboard().setText(text_to_copy)