# Sheetris

**Optimize cutting layouts for sheet materials in Blender**

Sheetris is a Blender addon that automatically generates optimized cutting layouts for sheet materials like plywood, MDF, acrylic, aluminum, and more. Think Tetris, but for your workshop!

<div align="center">
  <video src="https://github.com/user-attachments/assets/e7719b16-a7cf-4fda-802a-8091b6fd204b" width="1000"></video>
</div>

## Features

- ✨ **Multiple Packing Algorithms** - Choose the best algorithm for your needs:
  - **MaxRects**: Best material efficiency, tries multiple positions
  - **Guillotine**: Fast but may waste space, makes only straight cuts
  - **Skyline**: Good balance of speed and efficiency, bottom-left placement
- 📏 **Automatic Piece Detection** - Analyzes object dimensions and groups by thickness
- 🎨 **Color Coding** - Visual distinction by thickness or dimension
- 🔤 **Letter Labels** - Each unique dimension gets a letter (A, B, C, etc.)
- 📊 **Summary Tables** - Interactive breakdown of pieces per thickness
- 📄 **PDF Report** - Print-ready cutting diagrams with:
  - Summary tables with quantities
  - One sheet per page layouts
  - Piece labels and dimensions
  - 100mm reference grid
  - Configurable page sizes (A4, A3, Letter, Tabloid)
- 🔄 **Non-Destructive** - Original objects remain untouched
- ⚙️ **Configurable** - Set sheet size, saw kerf, packing algorithm, and orientation

## Installation

### Step 1: Install the Addon

1. Download the latest release from [Releases](https://github.com/beraldoleal/sheetris/releases)
2. In Blender, go to `Edit → Preferences → Add-ons`
3. Click `Install...` and select the downloaded ZIP file
4. Enable "Sheetris" by checking the checkbox

### Step 2: Install Dependencies

Sheetris requires the `reportlab` Python library for PDF generation.

Open Blender's Python Console and run:
```python
import subprocess
import sys
subprocess.check_call([sys.executable, "-m", "pip", "install", "reportlab"])
```

## Usage

### 1. Prepare Your Model

- Model your furniture/project in Blender
- Each piece should be a separate mesh object
- Apply scale to all objects (`Ctrl+A → Scale`)
- Origin placement doesn't matter (Sheetris centers it automatically)

### 2. Configure Settings

Find the **Sheetris** panel in the 3D View sidebar (press `N` if hidden):

- **Sheet Width/Length**: Your plywood sheet dimensions in mm
- **Saw Kerf**: Blade width for spacing between pieces (typically 3mm)
- **Packing Algorithm**: Choose the algorithm that best fits your needs
  - *MaxRects*: Best material efficiency
  - *Guillotine*: Fastest processing
  - *Skyline*: Balanced approach
- **Color By**:
  - *Thickness*: Same color for all pieces of one thickness
  - *Dimension*: Same color for identical pieces
- **Page Size**: Choose your paper size for PDF reports
- **Orientation**: Landscape (recommended) or Portrait

### 3. Generate Layout

1. Select all objects you want to cut
2. Click **Create Layout**
3. Sheetris creates collections like "Plywood_18.0mm", "Plywood_10.0mm", etc.
4. Each collection contains:
   - Flattened pieces laid out on virtual sheets
   - Letter labels (A, B, C, etc.)
   - Sheet reference planes

### 4. Review Summary

The panel shows a summary with:
- Thickness groups (expandable)
- Letter labels
- Dimensions
- Quantities

Click any dimension to select all pieces of that size!

### 5. Generate PDF Report

1. Click **Print Report**
2. PDF opens automatically with:
   - Summary tables
   - One cutting diagram per sheet
   - Piece labels and dimensions
   - Scale reference
3. Print or save for your workshop!

### 6. Clean Up

Click **Clean All Layouts** to remove all generated layouts and start over.

## Requirements

- Blender 4.5 or newer
- reportlab library (for PDF generation)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see [LICENSE](LICENSE) file for details.

You are free to use, modify, and sell this addon.
