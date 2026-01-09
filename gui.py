# Import necessary modules for file handling, image processing, CSV writing, and GUI
import os  # For operating system interactions and getting current directory
from pathlib import Path  # For handling file paths in an object-oriented way
from PIL import Image, ImageDraw, ImageTk  # For image processing and displaying in tkinter
import csv  # For writing CSV files
import tkinter as tk  # For creating the GUI
from tkinter import filedialog, ttk, messagebox  # For folder selection, styled widgets, and message boxes

# Function to process a single image and return the normalised value and image with grid overlay
def process_image(img_path, grid_size, threshold_percentage):
    # Open the image file
    img = Image.open(img_path)
    # Get image dimensions
    width, height = img.size
    
    # Convert to grayscale if not already
    if img.mode != 'L':
        img = img.convert('L')
    
    # Calculate cell dimensions based on grid size
    cell_width = width // grid_size
    cell_height = height // grid_size
    
    # Initialize total value counter
    total_value = 0
    
    # Loop through each grid cell
    for i in range(grid_size):
        for j in range(grid_size):
            # Define cell boundaries
            left = i * cell_width
            upper = j * cell_height
            right = (i + 1) * cell_width
            lower = (j + 1) * cell_height
            
            # Crop the cell from the image
            cell = img.crop((left, upper, right, lower))
            # Get pixel data from the cell
            pixels = list(cell.get_flattened_data())
            # Count non-black pixels
            non_zero_count = sum(1 for p in pixels if p > 0)
            # Total pixels in cell
            total_pixels = len(pixels)
            
            # Calculate percentage of non-black pixels
            if total_pixels > 0:
                percentage = (non_zero_count / total_pixels) * 100
                # Increment total if above threshold
                if percentage >= threshold_percentage:
                    total_value += 1
    
    # Normalize the total value to a percentage out of 100
    normalised_value = round((total_value / (grid_size ** 2)) * 100, 1)
    
    # Draw grid lines on the image
    draw = ImageDraw.Draw(img)
    for i in range(1, grid_size):
        # Draw vertical grid lines
        draw.line([(i * cell_width, 0), (i * cell_width, height)], fill=255, width=1)
        # Draw horizontal grid lines
        draw.line([(0, i * cell_height), (width, i * cell_height)], fill=255, width=1)
    
    # Return the normalized value and the image with grid
    return normalised_value, img

# Global variables to store the current processed image and its value
current_value = None  # Stores the normalized value of the current image
current_img = None  # Stores the current image with grid overlay

# Function to process the current image and update the display
def process_and_display():
    global current_value, current_img  # Access global variables
    try:
        # Get grid size from input
        grid_size = int(grid_entry.get())
        # Get threshold from input
        threshold = float(threshold_entry.get())
        # Validate inputs
        if grid_size <= 0 or threshold < 0 or threshold > 100:
            raise ValueError
        # Process the image
        current_value, current_img = process_image(current_img_path, grid_size, threshold)
        # Update the value label
        value_label.config(text=f"Normalised Value: {current_value}")
        # Display the image
        display_image()
    except ValueError:
        # Show error for invalid inputs
        messagebox.showerror("Invalid Input", "Please enter valid grid size (positive integer) and threshold (0-100).")

# Function to display the current image scaled to canvas while maintaining aspect ratio
def display_image():
    if current_img is None:
        return  # No image to display
    # Get canvas dimensions
    canvas_width = canvas.winfo_width()
    canvas_height = canvas.winfo_height()
    if canvas_width <= 1 or canvas_height <= 1:
        return  # Canvas not ready
    # Get original image dimensions
    img_width, img_height = current_img.size
    # Calculate scaling factor to fit while maintaining aspect ratio
    scale = min(canvas_width / img_width, canvas_height / img_height)
    # Calculate new dimensions
    new_width = int(img_width * scale)
    new_height = int(img_height * scale)
    # Resize the image
    img_resized = current_img.resize((new_width, new_height), Image.LANCZOS)
    # Create PhotoImage for tkinter
    photo = ImageTk.PhotoImage(img_resized)
    # Clear canvas
    canvas.delete("all")
    # Center the image on the canvas
    x = (canvas_width - new_width) // 2
    y = (canvas_height - new_height) // 2
    canvas.create_image(x, y, anchor=tk.NW, image=photo)
    # Keep reference to prevent garbage collection
    canvas.image = photo

# Function to apply the current settings to all images in the folder and save results to CSV
def apply_to_folder():
    try:
        # Get grid size from input
        grid_size = int(grid_entry.get())
        # Get threshold from input
        threshold = float(threshold_entry.get())
        # Validate inputs
        if grid_size <= 0 or threshold < 0 or threshold > 100:
            raise ValueError
        # Initialize results list
        results = []
        # Process each image in the folder
        for img_file in image_files:
            # Get value for each image
            value, _ = process_image(img_file, grid_size, threshold)
            # Add to results
            results.append((img_file.name, value))
        # Create CSV filename with grid and threshold
        csv_filename = f"results_{grid_size}_{int(threshold)}.csv"
        # Full path for CSV
        csv_path = images_folder / csv_filename
        # Write to CSV
        with open(csv_path, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            # Write header
            writer.writerow(['Image Name', 'Normalised Value'])
            # Write each result
            for name, value in results:
                writer.writerow([name, value])
        # Show success message
        messagebox.showinfo("Done", f"Results saved to {csv_filename}")
    except ValueError:
        # Show error for invalid inputs
        messagebox.showerror("Invalid Input", "Please enter valid grid size (positive integer) and threshold (0-100).")

# Prompt user to select the folder containing the images
root = tk.Tk()  # Create main tkinter window
root.withdraw()  # Hide the window initially
folder_selected = filedialog.askdirectory(title="Select folder containing images", initialdir=os.getcwd())  # Open folder dialog starting in current directory
if not folder_selected:
    print("No folder selected. Exiting.")
    exit(1)  # Exit if no folder selected
images_folder = Path(folder_selected)  # Convert to Path object

if not images_folder.exists():
    print("Images folder does not exist.")
    exit(1)  # Exit if folder doesn't exist

# Define supported image extensions
image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff'}
# Get list of image files in the folder
image_files = [f for f in images_folder.iterdir() if f.is_file() and f.suffix.lower() in image_extensions]

if not image_files:
    messagebox.showerror("No Images", "No image files found in the images folder.")
    exit(1)  # Exit if no images found

current_img_path = image_files[0]  # Use the first image for display

# Create GUI on the same root
root.deiconify()  # Show the window
root.title("Image Grid Analysis")  # Set window title

# Frame for input fields
input_frame = ttk.Frame(root)
input_frame.pack(pady=10)

# Grid size input
ttk.Label(input_frame, text="Grid Size:").grid(row=0, column=0, padx=5)
grid_entry = ttk.Entry(input_frame)
grid_entry.insert(0, "10")  # Default value
grid_entry.grid(row=0, column=1, padx=5)

# Threshold input
ttk.Label(input_frame, text="Threshold (%):").grid(row=1, column=0, padx=5)
threshold_entry = ttk.Entry(input_frame)
threshold_entry.insert(0, "25")  # Default value
threshold_entry.grid(row=1, column=1, padx=5)

# Frame for buttons
button_frame = ttk.Frame(root)
button_frame.pack(pady=10)

# Update button to recalculate for current image
update_button = ttk.Button(button_frame, text="Update", command=process_and_display)
update_button.grid(row=0, column=0, padx=5)

# Apply to folder button
apply_button = ttk.Button(button_frame, text="Apply to Folder", command=apply_to_folder)
apply_button.grid(row=0, column=1, padx=5)

# Frame for display
display_frame = ttk.Frame(root)
display_frame.pack(pady=10, fill=tk.BOTH, expand=True)

# Canvas that resizes with window for image display
canvas = tk.Canvas(display_frame, bg='gray')
canvas.pack(fill=tk.BOTH, expand=True)
canvas.bind('<Configure>', lambda e: display_image())  # Redisplay on resize

# Label for normalized value
value_label = ttk.Label(display_frame, text="Normalised Value: ")
value_label.pack(side=tk.RIGHT, padx=20)

# Initial display of the first image
process_and_display()

# Start the GUI event loop
root.mainloop()