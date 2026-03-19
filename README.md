# ExplorationQuantTool

A Python tool for quantitative analysis of images using grid-based pixel density evaluation and edge squiggliness measurement. The tool processes images by dividing them into a configurable grid, calculates the percentage of non-black pixels per cell, and additionally measures the roughness/squiggliness of the edges present in each image.

## Features

- **Grid Analysis**: Splits images into square cells by pixel size (default 50px).
- **Pixel Density Calculation**: Counts non-black pixels in each grid cell.
- **Threshold-Based Evaluation**: Assigns a value of 1 to cells where non-black pixels exceed a threshold percentage (default 50%).
- **Normalisation**: Outputs results normalised to a scale of 0–100, regardless of grid size.
- **Squiggliness Analysis**: Measures how straight or jagged the edges in each image are, using two complementary metrics:
  - **Arc-Length Ratio** — ratio of actual edge path length to straight-line distance (1.0 = perfectly straight, higher = more squiggly).
  - **Ra Roughness** — mean absolute pixel deviation of the edge from a local best-fit line per segment, analogous to the Ra surface roughness metric.
- **Edge Overlay**: GUI displays detected edge profiles drawn as coloured lines over the image so you can see exactly what is being measured.
- **Output Formats**: Generates CSV files with all metrics.
- **Configurable Parameters**: Adjust cell size, threshold, edge brightness threshold, and segment length.
- **GUI Version**: Interactive GUI for real-time preview and batch processing.
- **Mask Support**: If `mask.png` exists in the image folder, it is applied to all images for both grid and squiggliness analysis.
- **Command-Line Version**: Script for batch processing without a GUI.

## Requirements

- Python 3.x (Python 3.6 or higher recommended)
- Pillow (PIL) library for image processing
- NumPy for fast pixel-level operations
- Tkinter (usually included with Python, required for GUI)

## Installation

### On macOS

1. Ensure Python 3 is installed. You can download it from [python.org](https://www.python.org/downloads/) or use Homebrew:
   ```bash
   brew install python
   ```
2. Install dependencies:
   ```bash
   pip3 install pillow numpy
   ```

### On Windows

1. Download and install Python 3 from [python.org](https://www.python.org/downloads/).
2. Install dependencies:
   ```bash
   pip install pillow numpy
   ```

**Note:** On some systems, you may need to use `python3` and `pip3` instead of `python` and `pip`.

## Usage

### GUI Version (Recommended for Interactive Use)

1. Run the GUI script:
   ```bash
   python gui.py    # On Windows
   python3 gui.py   # On macOS/Linux
   ```
2. A folder selection dialog opens. Choose the folder containing your images.
3. The first image is displayed with a grid overlay and all metrics in the sidebar.
4. Adjust any parameter; the preview and metrics update automatically.
5. Toggle **Show edge overlay** to visualise the detected centerline profiles:
   - **Yellow** — horizontal components (column-by-column centroid trace)
   - **Magenta** — vertical components (row-by-row centroid trace)
6. Click **Apply to Folder** to process all images and save results to `results_{cell_size}px_{threshold}.csv`.
7. Click **Load New Folder** to switch to a different folder without restarting.
8. Optional: add a `mask.png` to the folder to exclude regions (white = exclude, black = include).

### Command-Line Version

1. Run the script:
   ```bash
   python run.py    # On Windows
   python3 run.py   # On macOS/Linux
   ```
   Optional arguments:
   - `--cell-size` (int): Cell size in pixels (must divide image width and height).
   - `--threshold` (float): Threshold percentage for grid analysis (default 50).
   - `--mask` (str): Mask filename in the folder (default `mask.png`).
   - `--edge-threshold` (int): Brightness threshold (0–255) for edge detection (default 30).
   - `--segment-length` (int): Segment length in pixels for Ra calculation (default 100).
   - `--min-run-length` (int): Minimum edge run length to include in squiggliness score (default 50).
  - `--min-component-px` (int): Minimum connected-component size in pixels to include; smaller components are treated as noise (default 200).
2. If `--cell-size` is not provided, the CLI will prompt you to choose from valid sizes.
3. Results are printed to the console and saved to `results_{cell_size}px_{threshold}.csv` in the selected folder.
4. Optional: add a `mask.png` to the folder to exclude regions (white = exclude, black = include).

## Configuration

| Parameter | Default | Description |
|---|---|---|
| `cell_size_px` | 50 | Grid cell size in pixels; must divide both image width and height. |
| `threshold_percentage` | 50 | Minimum % of non-black pixels for a cell to count as active. |
| `edge_threshold` | 30 | Pixel brightness (0–255) above which a pixel is considered lit. |
| `segment_length` | 100 | Target length in pixels for each Ra roughness segment. |
| `min_run_length` | 50 | Minimum contiguous edge run length to include in squiggliness. |
| `min_component_px` | 200 | Minimum connected-component size (pixels) to include; smaller components are ignored as noise. |

## Output

**CSV columns:**
- `Image Name`
- `Normalised Value` — grid-based density score (0–100).
- `Arc-Length Ratio` — squiggliness metric; 1.0 = straight, higher = more squiggly.
- `Ra Roughness (px)` — mean absolute pixel deviation from local best-fit line per segment.
- `Edge Runs Analyzed` — number of edge profile runs that contributed to the squiggliness score.

**CSV filename format:** `results_{cell_size_px}px_{threshold_percentage}.csv` (e.g. `results_50px_50.csv`).

## How Squiggliness Works

Bright pixels (above `edge_threshold`) are grouped into 8-connected components. Each component large enough (≥ `min_component_px` pixels) is traced independently, so the analysis always follows a single line's centre and can never jump between separate lines.

The component's longer axis determines the scan direction:
- **Wider than tall**: traced column-by-column — the brightness-weighted centroid y-position is recorded for each pixel column.
- **Taller than wide**: traced row-by-row — the brightness-weighted centroid x-position is recorded for each pixel row.

Each continuous run of centroid positions is then analysed independently:
- **Arc-length ratio** = total path length along the centroid trace / straight-line extent. A flat line scores 1.0; any deviation increases this value.
- **Ra roughness** = the centroid trace is split into segments of `segment_length` pixels. A straight line is fitted through each segment and the mean absolute deviation from that line is computed (Ra). Segments are length-weighted and averaged to produce the final score.

Final scores are the arc-length-weighted average across all runs and all components.

## Example

For 50px cells with a 50% threshold:
- If 30 out of 100 cells meet the threshold, the normalised value is 30.0.

For squiggliness:
- A perfectly straight horizontal edge → Arc-Length Ratio ≈ 1.000, Ra ≈ 0.0 px.
- A jagged, noisy edge → Arc-Length Ratio > 1.5, Ra > 10 px.

## Educational/Research Use

This tool is designed for educational and research purposes. It demonstrates image processing techniques, grid-based analysis, edge detection, and roughness measurement. The example images in `flat-heatmaps/` and `triangle-heatmaps/` illustrate different heatmap patterns.

## Contributing

Feel free to fork and contribute improvements. Please maintain the educational focus.

## License

See LICENSE file.

## Credits

Initial developer: Dr. Duke Gledhill
Developed for exploration and quantitative analysis of visual data.
