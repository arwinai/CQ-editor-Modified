# Modified CQ-Editor

---

## Features

### Kernel Inspector: A robust, deep-dive inspector that bypasses the standard UI to analyze raw OCP kernel geometry.

- Inspect any selection (Faces, Edges, Vertices) without crashing.

- Visual Debugging: Highlights Face Normals (Yellow), Wire Start/End points (Blue/Red), and Vertex locations.

- Unwraps "Compounds" automatically to show true geometry data (Area, Length, Volume).

### DXF Importer: Native "Insert DXF" tool in the editor

- Accessible via Tools > Insert DXF... or Ctrl+Shift+I.

- Converts DXF geometry directly into clean cadquery code strings inserted at your cursor.

---

## Installation

### 1. Prerequisites

Use Mamba or Conda to manage the dependencies

### 2. Clone the Repository

```bash
git clone https://github.com/arwinai/CQ-editor-Modified.git
cd CQ-editor-Modified
```

### 3. Create the Environment

Use the included environment file to pull the core OCP/CadQuery libraries

```bash
# Using Mamba
mamba env create -f cqgui_env.yml -n cq-modified

# OR Using standard Conda
conda env create -f cqgui_env.yml -n cq-modified
```

### 4. Install Extra Dependencies

Activate the environment and install the dxf library.

```bash
conda activate cq-modified
pip install ezdxf
pip install -e . --no-deps
```

---

## Running

```bash
conda activate cq-modified
cq-editor
```
