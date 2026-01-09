# ExplorationQuantTool

A Python tool for quantitative analysis of images using grid-based pixel density evaluation. This tool processes images by dividing them into a configurable grid and calculating the percentage of non-black pixels in each cell, then normalizing the results.

## Features

- **Grid Analysis**: Splits images into a user-defined grid (default 10x10).
- **Pixel Density Calculation**: Counts non-black pixels in each grid cell.
- **Threshold-Based Evaluation**: Assigns a value of 1 to cells where non-black pixels exceed a threshold percentage (default 25%).
- **Normalization**: Outputs results normalized to a scale of 0-100, regardless of grid size.
- **Output Formats**: Generates both a CSV file and console table for results.
- **Configurable Parameters**: Easily adjust grid size and threshold via variables at the top of the script.

## Requirements

- Python 3.x
- Pillow (PIL) library for image processing
- Tkinter (usually included with Python for GUI dialogs)

Install dependencies:
```bash
pip install pillow
```

## Usage

1. Adjust `threshold_percentage` and `grid_size` variables in the script if needed.
2. Run the script:
   ```bash
   python run.py
   ```
3. A folder selection dialog will appear; choose the folder containing your images.
4. View results in the console and in `results.csv` (saved in the selected folder).

## Configuration

- `threshold_percentage`: Minimum percentage of non-black pixels required for a grid cell to be counted (default: 25).
- `grid_size`: Number of rows and columns in the grid (default: 10).

## Output

- **Console**: Displays configuration, then a table with image names and normalized values.
- **CSV File**: `results.csv` contains the same data in CSV format.

## Example

For a 10x10 grid with 25% threshold:
- If 30 out of 100 cells meet the threshold, the normalized value is 30.0.

## Educational/Research Use

This tool is designed for educational and research purposes. It demonstrates image processing techniques, grid-based analysis, and data normalization. The example images in `Flat heatmaps/` and `Triangle HeatMaps/` illustrate different heatmap patterns.

## Contributing

Feel free to fork and contribute improvements. Please maintain the educational focus.

## License

See LICENSE file.

## Credits

Initial developer: Dr. Duke Gledhill  
Developed for exploration and quantitative analysis of visual data.