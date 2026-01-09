# Import necessary modules
import os  # For operating system interactions
from pathlib import Path  # For handling file paths in an object-oriented way
from PIL import Image  # For image processing using the Pillow library
import csv  # For writing CSV files
import tkinter as tk  # For GUI folder selection
from tkinter import filedialog  # For the folder dialog

threshold_percentage = 25  # The minimum percentage of non-black pixels required for a grid cell to be counted as 1
grid_size = 10  # The number of rows and columns in the grid (e.g., 10x10 = 100 cells)

# Prompt user to select the folder containing the images
root = tk.Tk()
root.withdraw()  # Hide the main window
folder_selected = filedialog.askdirectory(title="Select folder containing images")
if not folder_selected:
    print("No folder selected. Exiting.")
    exit(1)
images_folder = Path(folder_selected)

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
    # Initialize a list to store results for each image
    results = []
    # Loop through each image file
    for img_file in image_files:
        # Open the image using Pillow
        img = Image.open(img_file)
        # Get the width and height of the image
        width, height = img.size
        
        # Convert the image to grayscale if it's not already in grayscale mode ('L')
        if img.mode != 'L':
            img = img.convert('L')
        
        # Calculate the width and height of each grid cell
        cell_width = width // grid_size
        cell_height = height // grid_size
        
        # Initialize the total value for this image (sum of grid cells with >= threshold_percentage non-black pixels)
        total_value = 0
        
        # Loop through each row of the grid
        for i in range(grid_size):
            # Loop through each column of the grid
            for j in range(grid_size):
                # Calculate the coordinates for the current grid cell
                left = i * cell_width
                upper = j * cell_height
                right = (i + 1) * cell_width
                lower = (j + 1) * cell_height
                
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
        
        # Normalize the total value to a percentage out of 100
        normalized_value = round((total_value / (grid_size ** 2)) * 100, 1)
        # Append the image name and its normalized value to the results list
        results.append((img_file.name, normalized_value))
    
    # Write the results to a CSV file in the selected folder
    csv_path = os.path.join(images_folder, 'results.csv')
    with open(csv_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Image Name', 'Normalized Value'])
        for name, value in results:
            writer.writerow([name, value])
    
    # Print the configuration variables
    print(f"Threshold Percentage: {threshold_percentage}%")
    print(f"Grid Size: {grid_size}x{grid_size}")
    print()
    
    # Print the header of the output table
    print("| Image Name | Normalized Value (out of 100) |")
    print("|------------|-------------------------------|")
    # Print each row of the table
    for name, value in results:
        print(f"| {name} | {value:.1f} |")
