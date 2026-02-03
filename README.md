# ExplorationQuantTool

A Python tool for quantitative analysis of images using grid-based pixel density evaluation. This tool processes images by dividing them into a configurable grid and calculating the percentage of non-black pixels in each cell, then normalising the results.

## Features

- **Grid Analysis**: Splits images into a user-defined grid (default 10x10).
- **Pixel Density Calculation**: Counts non-black pixels in each grid cell.
- **Threshold-Based Evaluation**: Assigns a value of 1 to cells where non-black pixels exceed a threshold percentage (default 25%).
- **Normalisation**: Outputs results normalised to a scale of 0-100, regardless of grid size.
- **Output Formats**: Generates CSV files with results.
- **Configurable Parameters**: Easily adjust grid size and threshold.
- **GUI Version**: Interactive GUI for real-time preview and batch processing.
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
4. Adjust grid size and threshold using the input fields.
5. Click "Update" to recalculate for the current image.
6. Click "Apply to Folder" to process all images and save results to `results_{grid}_{threshold}.csv`.

### Command-Line Version

1. Adjust `threshold_percentage` and `grid_size` variables in `run.py` if needed.
2. Run the script:
   ```bash
   python run.py    # On Windows
   python3 run.py   # On macOS/Linux
   ```
3. A folder selection dialog will appear; choose the folder containing your images.
4. View results in the console and in `results_{grid_size}_{threshold_percentage}.csv` (e.g., `results_10_25.csv`, saved in the selected folder).

## Configuration

- `threshold_percentage`: Minimum percentage of non-black pixels required for a grid cell to be counted (default: 25).
- `grid_size`: Number of rows and columns in the grid (default: 10).

## Output

- **CSV Files**: Results saved as `results_{grid_size}_{threshold_percentage}.csv` (e.g., `results_10_25.csv`).
- **Console** (command-line only): Displays configuration and a table with image names and normalised values.

## Example

For a 10x10 grid with 25% threshold:
- If 30 out of 100 cells meet the threshold, the normalised value is 30.0.

## Educational/Research Use

This tool is designed for educational and research purposes. It demonstrates image processing techniques, grid-based analysis, and data normalisation. The example images in `Flat heatmaps/` and `Triangle HeatMaps/` illustrate different heatmap patterns.

## Contributing

Feel free to fork and contribute improvements. Please maintain the educational focus.

## License

See LICENSE file.

## Credits

Initial developer: Dr. Duke Gledhill  
Developed for exploration and quantitative analysis of visual data.