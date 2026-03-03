import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageTk, ImageOps
import csv
import math
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import numpy as np

MASK_FILENAME = "mask.png"
DEFAULT_THRESHOLD_PERCENTAGE = 50
DEFAULT_CELL_SIZE_PX = 50


def _common_divisors(a, b):
    gcd_value = math.gcd(a, b)
    divisors = set()
    limit = int(math.isqrt(gcd_value))
    for i in range(1, limit + 1):
        if gcd_value % i == 0:
            divisors.add(i)
            divisors.add(gcd_value // i)
    return sorted(divisors)


def process_image(img_path, cell_size_px, threshold_percentage, mask_img):
    with Image.open(img_path) as raw:
        # Always convert to a detached in-memory copy before closing the file
        img = raw.convert('L')

    if img.size[0] % cell_size_px != 0 or img.size[1] % cell_size_px != 0:
        raise ValueError("Cell size must divide both image width and height.")
    if mask_img is not None and mask_img.size != img.size:
        raise ValueError("Mask size does not match image size.")

    if mask_img is not None:
        # White in mask = exclude, black = include (intentionally non-standard)
        black_bg = Image.new('L', img.size, 0)
        img = Image.composite(img, black_bg, ImageOps.invert(mask_img))

    width, height = img.size
    grid_cols = width // cell_size_px
    grid_rows = height // cell_size_px

    img_array = np.array(img)
    total_value = 0
    for col in range(grid_cols):
        for row in range(grid_rows):
            left = col * cell_size_px
            upper = row * cell_size_px
            cell = img_array[upper:upper + cell_size_px, left:left + cell_size_px]
            percentage = (np.count_nonzero(cell) / cell.size) * 100
            if percentage >= threshold_percentage:
                total_value += 1

    normalised_value = round((total_value / (grid_cols * grid_rows)) * 100, 1)

    draw = ImageDraw.Draw(img)
    for col in range(1, grid_cols):
        draw.line([(col * cell_size_px, 0), (col * cell_size_px, height)], fill=255, width=1)
    for row in range(1, grid_rows):
        draw.line([(0, row * cell_size_px), (width, row * cell_size_px)], fill=255, width=1)

    return normalised_value, img


def main():
    current_value = None
    current_img = None

    root = tk.Tk()
    root.withdraw()
    folder_selected = filedialog.askdirectory(
        title="Select folder containing images", initialdir=os.getcwd()
    )
    if not folder_selected:
        print("No folder selected. Exiting.")
        return
    images_folder = Path(folder_selected)

    if not images_folder.exists():
        print("Images folder does not exist.")
        return

    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff'}
    mask_path = images_folder / MASK_FILENAME

    image_files = sorted(
        f for f in images_folder.iterdir()
        if f.is_file() and f.suffix.lower() in image_extensions and f != mask_path
    )

    if not image_files:
        messagebox.showerror("No Images", "No image files found in the images folder.")
        return

    mask_img = None
    if mask_path.exists():
        with Image.open(mask_path) as m:
            mask_img = m.convert('L') if m.mode != 'L' else m.copy()

    with Image.open(image_files[0]) as first_img:
        first_width, first_height = first_img.size

    if mask_img is not None and mask_img.size != (first_width, first_height):
        messagebox.showerror("Invalid Mask", f"{MASK_FILENAME} size must match the images.")
        return

    cell_sizes = _common_divisors(first_width, first_height)
    if not cell_sizes:
        messagebox.showerror("Invalid Image", "Could not determine valid cell sizes.")
        return

    current_img_path = image_files[0]

    def process_and_display():
        nonlocal current_value, current_img
        try:
            cell_size_px = int(cell_size_combo.get())
            threshold = float(threshold_entry.get())
            if threshold < 0 or threshold > 100:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter valid cell size and threshold (0-100).")
            return
        current_value, current_img = process_image(current_img_path, cell_size_px, threshold, mask_img)
        value_label.config(text=f"Normalised Value: {current_value}")
        display_image()

    def display_image():
        if current_img is None:
            return
        canvas_width = canvas.winfo_width()
        canvas_height = canvas.winfo_height()
        if canvas_width <= 1 or canvas_height <= 1:
            return
        img_width, img_height = current_img.size
        scale = min(canvas_width / img_width, canvas_height / img_height)
        new_width = int(img_width * scale)
        new_height = int(img_height * scale)
        img_resized = current_img.resize((new_width, new_height), Image.LANCZOS)
        photo = ImageTk.PhotoImage(img_resized)
        canvas.delete("all")
        x = (canvas_width - new_width) // 2
        y = (canvas_height - new_height) // 2
        canvas.create_image(x, y, anchor=tk.NW, image=photo)
        canvas.image = photo  # prevent garbage collection

    def apply_to_folder():
        try:
            cell_size_px = int(cell_size_combo.get())
            threshold = float(threshold_entry.get())
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter valid cell size and threshold (0-100).")
            return
        if threshold < 0 or threshold > 100:
            messagebox.showerror("Invalid Input", "Threshold must be between 0 and 100.")
            return

        results = []
        for img_file in image_files:
            try:
                value, _ = process_image(img_file, cell_size_px, threshold, mask_img)
            except ValueError as e:
                messagebox.showerror("Error", str(e))
                return
            results.append((img_file.name, value))

        csv_filename = f"results_{cell_size_px}px_{int(threshold)}.csv"
        csv_path = images_folder / csv_filename
        with open(csv_path, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Image Name', 'Normalised Value'])
            for name, value in results:
                writer.writerow([name, value])
        messagebox.showinfo("Done", f"Results saved to {csv_filename}")

    root.deiconify()
    root.title("Image Grid Analysis")

    input_frame = ttk.Frame(root)
    input_frame.pack(pady=10)

    ttk.Label(input_frame, text="Cell Size (px):").grid(row=0, column=0, padx=5)
    cell_size_combo = ttk.Combobox(input_frame, values=cell_sizes, state="readonly", width=10)
    default_cell_size = next((s for s in reversed(cell_sizes) if s <= DEFAULT_CELL_SIZE_PX), cell_sizes[0])
    cell_size_combo.set(str(default_cell_size))
    cell_size_combo.grid(row=0, column=1, padx=5)
    cell_size_combo.bind("<<ComboboxSelected>>", lambda e: process_and_display())

    ttk.Label(input_frame, text="Threshold (%):").grid(row=1, column=0, padx=5)
    threshold_entry = ttk.Entry(input_frame)
    threshold_entry.insert(0, str(DEFAULT_THRESHOLD_PERCENTAGE))
    threshold_entry.grid(row=1, column=1, padx=5)
    threshold_entry.bind("<Return>", lambda e: process_and_display())
    threshold_entry.bind("<FocusOut>", lambda e: process_and_display())

    button_frame = ttk.Frame(root)
    button_frame.pack(pady=10)
    ttk.Button(button_frame, text="Update", command=process_and_display).grid(row=0, column=0, padx=5)
    ttk.Button(button_frame, text="Apply to Folder", command=apply_to_folder).grid(row=0, column=1, padx=5)

    display_frame = ttk.Frame(root)
    display_frame.pack(pady=10, fill=tk.BOTH, expand=True)

    canvas = tk.Canvas(display_frame, bg='gray')
    canvas.pack(fill=tk.BOTH, expand=True)
    canvas.bind('<Configure>', lambda e: display_image())

    value_label = ttk.Label(display_frame, text="Normalised Value: ", font=("Helvetica", 18, "bold"))
    value_label.pack(side=tk.RIGHT, padx=20)

    process_and_display()
    root.mainloop()


if __name__ == "__main__":
    main()
