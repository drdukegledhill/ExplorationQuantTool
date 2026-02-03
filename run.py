# Import necessary modules for file handling, image processing, CSV writing, and GUI
import os  # For operating system interactions and getting current directory
import argparse  # For CLI arguments
from pathlib import Path  # For handling file paths in an object-oriented way
from PIL import Image, ImageOps  # For image processing using the Pillow library
import math  # For gcd and divisor calculation
import csv  # For writing CSV files
import tkinter as tk  # For GUI folder selection
from tkinter import filedialog  # For the folder dialog

# Default parameters
DEFAULT_THRESHOLD_PERCENTAGE = 50  # The minimum percentage of non-black pixels required for a grid cell to be counted as 1
DEFAULT_CELL_SIZE_PX = 50  # Preferred cell size in pixels

def _common_divisors(a, b):
    gcd_value = math.gcd(a, b)
    divisors = set()
    limit = int(math.isqrt(gcd_value))
    for i in range(1, limit + 1):
        if gcd_value % i == 0:
            divisors.add(i)
            divisors.add(gcd_value // i)
    return sorted(divisors)

def _parse_args():
    parser = argparse.ArgumentParser(description="Grid-based image analysis.")
    parser.add_argument(
        "--cell-size",
        type=int,
        help="Cell size in pixels (must divide image width/height).",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD_PERCENTAGE,
        help="Threshold percentage for non-black pixels (default: 50).",
    )
    parser.add_argument(
        "--mask",
        type=str,
        default="mask.png",
        help="Mask filename in the selected folder (default: mask.png).",
    )
    return parser.parse_args()

args = _parse_args()

# Prompt user to select the folder containing the images
root = tk.Tk()  # Create tkinter window
root.withdraw()  # Hide the window
folder_selected = filedialog.askdirectory(title="Select folder containing images", initialdir=os.getcwd())  # Open folder dialog starting in current directory
if not folder_selected:
    print("No folder selected. Exiting.")
    exit(1)  # Exit if no folder selected
images_folder = Path(folder_selected)  # Convert to Path object

# Check if the images folder exists; if not, print an error and exit
if not images_folder.exists():
    print("Images folder does not exist.")
    exit(1)

# Define the set of supported image file extensions
image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff'}

# Get a list of all files in the images folder that have supported extensions
image_files = [f for f in images_folder.iterdir() if f.is_file() and f.suffix.lower() in image_extensions]

# If no image files are found, print a message
if not image_files:
    print("No image files found in the images folder.")
else:
    mask_path = images_folder / args.mask
    mask_img = None
    if mask_path.exists():
        with Image.open(mask_path) as m:
            mask_img = m.convert('L') if m.mode != 'L' else m.copy()

    with Image.open(image_files[0]) as first_img:
        first_width, first_height = first_img.size
    if mask_img is not None and mask_img.size != (first_width, first_height):
        print(f"{args.mask} size must match the images.")
        exit(1)
    cell_sizes = _common_divisors(first_width, first_height)
    if not cell_sizes:
        print("Could not determine valid cell sizes for the first image.")
        exit(1)
    if args.cell_size is not None:
        if args.cell_size not in cell_sizes:
            print(
                f"Cell size {args.cell_size}px is invalid for {image_files[0].name} "
                f"({first_width}x{first_height})."
            )
            print(f"Valid cell sizes for this image are: {', '.join(map(str, cell_sizes))}")
            exit(1)
        cell_size_px = args.cell_size
    else:
        default_cell_size = DEFAULT_CELL_SIZE_PX if DEFAULT_CELL_SIZE_PX in cell_sizes else None
        if default_cell_size is None:
            smaller_or_equal = [s for s in cell_sizes if s <= DEFAULT_CELL_SIZE_PX]
            default_cell_size = smaller_or_equal[-1] if smaller_or_equal else cell_sizes[0]
        print(f"Valid cell sizes for {image_files[0].name} ({first_width}x{first_height}):")
        print(", ".join(map(str, cell_sizes)))
        prompt = f"Choose cell size [default {default_cell_size}]: "
        choice = input(prompt).strip()
        if choice:
            try:
                chosen = int(choice)
            except ValueError:
                print("Invalid cell size. Must be an integer.")
                exit(1)
            if chosen not in cell_sizes:
                print(f"Cell size {chosen}px is invalid for {image_files[0].name} ({first_width}x{first_height}).")
                print(f"Valid cell sizes for this image are: {', '.join(map(str, cell_sizes))}")
                exit(1)
            cell_size_px = chosen
        else:
            cell_size_px = default_cell_size

    threshold_percentage = args.threshold

    # Initialize a list to store results for each image
    results = []
    # Loop through each image file
    for img_file in image_files:
        # Open the image using Pillow
        img = Image.open(img_file)
        # Get the width and height of the image
        width, height = img.size

        if mask_img is not None and mask_img.size != (width, height):
            print(f"{args.mask} size does not match {img_file.name} ({width}x{height}).")
            exit(1)
        
        # Convert the image to grayscale if it's not already in grayscale mode ('L')
        if img.mode != 'L':
            img = img.convert('L')

        if mask_img is not None:
            black_bg = Image.new('L', img.size, 0)
            img = Image.composite(img, black_bg, ImageOps.invert(mask_img))
        
        if cell_size_px <= 0:
            print("Cell size must be a positive integer.")
            exit(1)
        if width % cell_size_px != 0 or height % cell_size_px != 0:
            print(f"Cell size {cell_size_px}px does not evenly divide {img_file.name} ({width}x{height}).")
            print(f"Valid cell sizes for this image are: {', '.join(map(str, _common_divisors(width, height)))}")
            exit(1)

        # Calculate the grid dimensions and cell size
        grid_cols = width // cell_size_px
        grid_rows = height // cell_size_px
        
        # Initialize the total value for this image (sum of grid cells with >= threshold_percentage non-black pixels)
        total_value = 0
        
        # Loop through each row of the grid
        for i in range(grid_cols):
            # Loop through each column of the grid
            for j in range(grid_rows):
                # Calculate the coordinates for the current grid cell
                left = i * cell_size_px
                upper = j * cell_size_px
                right = (i + 1) * cell_size_px
                lower = (j + 1) * cell_size_px
                
                # Crop the image to get the current grid cell
                cell = img.crop((left, upper, right, lower))
                
                # Get the pixel data from the cropped cell
                pixels = list(cell.getdata())
                # Count the number of pixels that are not black (value > 0)
                non_zero_count = sum(1 for p in pixels if p > 0)
                # Get the total number of pixels in the cell
                total_pixels = len(pixels)
                
                # Calculate the percentage of non-black pixels
                if total_pixels > 0:
                    percentage = (non_zero_count / total_pixels) * 100
                    # If the percentage is at least the threshold, increment the total value
                    if percentage >= threshold_percentage:
                        total_value += 1
        
        # Normalise the total value to a percentage out of 100
        normalised_value = round((total_value / (grid_cols * grid_rows)) * 100, 1)
        # Append the image name and its normalised value to the results list
        results.append((img_file.name, normalised_value))
    
    # Write the results to a CSV file in the selected folder
    csv_filename = f"results_{cell_size_px}px_{int(threshold_percentage)}.csv"
    csv_path = os.path.join(images_folder, csv_filename)
    with open(csv_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        # Write header row
        writer.writerow(['Image Name', 'Normalised Value'])
        # Write each result
        for name, value in results:
            writer.writerow([name, value])
    
    # Print the configuration variables
    print(f"Threshold Percentage: {threshold_percentage}%")
    print(f"Cell Size: {cell_size_px}px ({grid_cols}x{grid_rows})")
    print()
    
    # Print the header of the output table
    print("| Image Name | Normalised Value (out of 100) |")
    print("|------------|-------------------------------|")
    # Print each row of the table
    for name, value in results:
        print(f"| {name} | {value:.1f} |")
