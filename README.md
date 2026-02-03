# ExplorationQuantTool

A Python tool for quantitative analysis of images using grid-based pixel density evaluation. This tool processes images by dividing them into a configurable grid and calculating the percentage of non-black pixels in each cell, then normalising the results.

## Features

- **Grid Analysis**: Splits images into square cells by pixel size (default 50px).
- **Pixel Density Calculation**: Counts non-black pixels in each grid cell.
- **Threshold-Based Evaluation**: Assigns a value of 1 to cells where non-black pixels exceed a threshold percentage (default 50%).
- **Normalisation**: Outputs results normalised to a scale of 0-100, regardless of grid size.
- **Output Formats**: Generates CSV files with results.
- **Configurable Parameters**: Easily adjust cell size (px) and threshold.
- **GUI Version**: Interactive GUI for real-time preview and batch processing with dropdown cell sizes.
- **Mask Support**: If `mask.png` exists in the image folder, it is applied to all images.
- **Command-Line Version**: Script for batch processing without GUI.

## Requirements

- Python 3.x (Python 3.6 or higher recommended)
- Pillow (PIL) library for image processing
- Tkinter (usually included with Python for GUI)

## Installation

### On macOS

1. Ensure Python 3 is installed. You can download it from [python.org](https://www.python.org/downloads/) or use Homebrew:
   ```bash
   brew install python
   ```
2. Install Pillow:
   ```bash
   pip3 install pillow
   ```

### On Windows

1. Download and install Python 3 from [python.org](https://www.python.org/downloads/).
2. Install Pillow:
   ```bash
   pip install pillow
   ```

**Note:** On some systems, you may need to use `python3` and `pip3` instead of `python` and `pip`. If you encounter issues, try the alternative commands.

## Usage

### GUI Version (Recommended for Interactive Use)

1. Run the GUI script:
   ```bash
   python gui.py    # On Windows
   python3 gui.py   # On macOS/Linux
   ```
2. Select a folder containing images.
3. The first image will be displayed with grid overlay and normalised value.
4. Adjust cell size (px) and threshold using the dropdown/input.
5. The preview updates automatically on cell size change, Enter, or focus loss in the threshold field (you can still click "Update").
6. Click "Apply to Folder" to process all images and save results to `results_{cell_size}px_{threshold}.csv`.
7. Optional: Add a `mask.png` in the folder to exclude regions (white removes, black keeps).

### Command-Line Version

1. Adjust `threshold_percentage` and `cell_size_px` variables in `run.py` if needed.
2. Run the script:
   ```bash
   python run.py    # On Windows
   python3 run.py   # On macOS/Linux
   ```
3. A folder selection dialog will appear; choose the folder containing your images.
4. View results in the console and in `results_{cell_size_px}px_{threshold_percentage}.csv` (e.g., `results_50px_50.csv`, saved in the selected folder).
5. Optional: Add a `mask.png` in the folder to exclude regions (white removes, black keeps).

## Configuration

- `threshold_percentage`: Minimum percentage of non-black pixels required for a grid cell to be counted (default: 50).
- `cell_size_px`: Cell size in pixels; must divide both image width and height (default: 50).
- `mask.png`: Optional grayscale image in the folder. White removes pixels; black keeps.

## Output

- **CSV Files**: Results saved as `results_{cell_size_px}px_{threshold_percentage}.csv` (e.g., `results_50px_50.csv`).
- **Console** (command-line only): Displays configuration and a table with image names and normalised values.

## Example

For 50px cells with a 50% threshold:
- If 30 out of 100 cells meet the threshold, the normalised value is 30.0.

## Educational/Research Use

This tool is designed for educational and research purposes. It demonstrates image processing techniques, grid-based analysis, and data normalisation. The example images in `flat-heatmaps/` and `triangle-heatmaps/` illustrate different heatmap patterns.

## Contributing

Feel free to fork and contribute improvements. Please maintain the educational focus.

## License

See LICENSE file.

## Credits

Initial developer: Dr. Duke Gledhill  
Developed for exploration and quantitative analysis of visual data.
