# ExplorationQuantTool

A Python tool for quantitative analysis of images using grid-based pixel density evaluation. The tool processes images by dividing them into a configurable grid and calculates the percentage of non-black pixels per cell, producing a normalised density score.

## Features

- **Grid Analysis**: Splits images into square cells by pixel size (default 50px).
- **Pixel Density Calculation**: Counts non-black pixels in each grid cell.
- **Threshold-Based Evaluation**: Assigns a value of 1 to cells where non-black pixels exceed a threshold percentage (default 50%).
- **Normalisation**: Outputs results normalised to a scale of 0–100, regardless of grid size.
- **Output Formats**: Generates CSV files with results.
- **Configurable Parameters**: Adjust cell size and threshold.
- **GUI Version**: Interactive GUI for real-time preview and batch processing.
- **Mask Support**: If `mask.png` exists in the image folder, it is applied to all images.
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
3. The first image is displayed with a grid overlay and the normalised value in the sidebar.
4. Adjust cell size or threshold; the preview and value update automatically.
5. Click **Apply to Folder** to process all images and save results to `results_{cell_size}px_{threshold}.csv`.
6. Click **Load New Folder** to switch to a different folder without restarting.
7. Optional: add a `mask.png` to the folder to exclude regions (white = exclude, black = include).

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
2. If `--cell-size` is not provided, the CLI will prompt you to choose from valid sizes.
3. Results are printed to the console and saved to `results_{cell_size}px_{threshold}.csv` in the selected folder.
4. Optional: add a `mask.png` to the folder to exclude regions (white = exclude, black = include).

## Configuration

| Parameter | Default | Description |
|---|---|---|
| `cell_size_px` | 50 | Grid cell size in pixels; must divide both image width and height. |
| `threshold_percentage` | 50 | Minimum % of non-black pixels for a cell to count as active. |

## Output

**CSV columns:**
- `Image Name`
- `Normalised Value` — grid-based density score (0–100).

**CSV filename format:** `results_{cell_size_px}px_{threshold_percentage}.csv` (e.g. `results_50px_50.csv`).

## Example Data

Two folders of greyscale heatmap images are included so you can try the tool straight away:

- **`flat-heatmaps/`** — 17 images with a uniform flat heatmap pattern. No mask is included, so the full image is analysed.
- **`triangle-heatmaps/`** — 17 images with a triangular heatmap pattern, plus a `mask.png` that excludes the background and restricts analysis to the triangle region.

To run the GUI on either folder, start `gui.py` and select the folder when prompted. To run the CLI, pass `--cell-size` or accept the default and select the folder from the dialog.

## Example

For 50px cells with a 50% threshold:
- If 30 out of 100 cells meet the threshold, the normalised value is 30.0.

## Educational/Research Use

This tool is designed for educational and research purposes. It demonstrates image processing techniques and grid-based analysis.

## Contributing

Feel free to fork and contribute improvements. Please maintain the educational focus.

## License

See LICENSE file.

## Credits

Initial developer: Dr. Duke Gledhill
Developed for exploration and quantitative analysis of visual data.
