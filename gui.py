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
    # GUI cell-size options are restricted to values that tile the image exactly.
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
        img = raw.convert('L')

    if img.size[0] % cell_size_px != 0 or img.size[1] % cell_size_px != 0:
        raise ValueError("Cell size must divide both image width and height.")
    if mask_img is not None and mask_img.size != img.size:
        raise ValueError("Mask size does not match image size.")

    if mask_img is not None:
        # Keep only black regions of the mask (white = excluded area).
        black_bg = Image.new('L', img.size, 0)
        img = Image.composite(img, black_bg, ImageOps.invert(mask_img))

    width, height = img.size
    grid_cols = width // cell_size_px
    grid_rows = height // cell_size_px

    img_array = np.array(img)
    # Same algorithm as CLI: count cells whose non-black density meets threshold.
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

    # Convert to RGB so grid lines can be coloured
    img_rgb = img.convert('RGB')
    draw = ImageDraw.Draw(img_rgb)
    for col in range(1, grid_cols):
        draw.line([(col * cell_size_px, 0), (col * cell_size_px, height)],
                  fill=(255, 255, 255), width=1)
    for row in range(1, grid_rows):
        draw.line([(0, row * cell_size_px), (width, row * cell_size_px)],
                  fill=(255, 255, 255), width=1)

    return normalised_value, img_rgb


def main():
    root = tk.Tk()
    root.withdraw()

    # All folder-dependent state lives here so load_folder() can replace it
    folder_state = {
        'images_folder': None,
        'image_files':   [],
        'mask_img':      None,
        'current_img_path': None,
    }
    current_img = [None]  # list so closures can rebind the element

    # ------------------------------------------------------------------ #
    # Folder loading                                                       #
    # ------------------------------------------------------------------ #

    def load_folder():
        folder_selected = filedialog.askdirectory(
            title="Select folder containing images", initialdir=os.getcwd()
        )
        if not folder_selected:
            return False

        images_folder = Path(folder_selected)
        if not images_folder.exists():
            messagebox.showerror("Error", "Selected folder does not exist.")
            return False

        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff'}
        mask_path = images_folder / MASK_FILENAME
        image_files = sorted(
            f for f in images_folder.iterdir()
            if f.is_file() and f.suffix.lower() in image_extensions and f != mask_path
        )
        if not image_files:
            messagebox.showerror("No Images", "No image files found in the selected folder.")
            return False

        mask_img = None
        if mask_path.exists():
            with Image.open(mask_path) as m:
                mask_img = m.convert('L') if m.mode != 'L' else m.copy()

        with Image.open(image_files[0]) as first_img:
            first_width, first_height = first_img.size

        if mask_img is not None and mask_img.size != (first_width, first_height):
            messagebox.showerror("Invalid Mask", f"{MASK_FILENAME} size must match the images.")
            return False

        cell_sizes = _common_divisors(first_width, first_height)
        if not cell_sizes:
            messagebox.showerror("Invalid Image", "Could not determine valid cell sizes.")
            return False

        folder_state.update({
            'images_folder':    images_folder,
            'image_files':      image_files,
            'mask_img':         mask_img,
            'current_img_path': image_files[0],
        })

        # Refresh cell-size combobox for the new folder's image dimensions
        default_cell_size = next(
            (s for s in reversed(cell_sizes) if s <= DEFAULT_CELL_SIZE_PX), cell_sizes[0]
        )
        cell_size_combo['values'] = cell_sizes
        cell_size_combo.set(str(default_cell_size))

        root.title(f"Image Grid Analysis — {images_folder.name}")
        return True

    def reload_folder():
        if load_folder():
            process_and_display()

    # ------------------------------------------------------------------ #
    # Analysis & display                                                   #
    # ------------------------------------------------------------------ #

    # Debounce: fire process_and_display 200 ms after last slider movement
    _update_job = [None]

    def _debounce_update(*_):
        if _update_job[0] is not None:
            root.after_cancel(_update_job[0])
        _update_job[0] = root.after(200, process_and_display)

    def _read_inputs():
        cell_size_px = int(cell_size_combo.get())
        threshold    = float(threshold_scale.get())
        return cell_size_px, threshold

    def process_and_display():
        if not folder_state['image_files']:
            return
        try:
            cell_size_px, threshold = _read_inputs()
        except (ValueError, tk.TclError):
            return

        img_path = folder_state['current_img_path']
        mask_img = folder_state['mask_img']

        normalised_value, img_rgb = process_image(img_path, cell_size_px, threshold, mask_img)
        current_img[0] = img_rgb

        value_label.config(text=f"Normalised Value: {normalised_value}")
        display_image()

    def display_image():
        if current_img[0] is None:
            return
        canvas_width = canvas.winfo_width()
        canvas_height = canvas.winfo_height()
        if canvas_width <= 1 or canvas_height <= 1:
            return
        img_width, img_height = current_img[0].size
        scale = min(canvas_width / img_width, canvas_height / img_height)
        new_width = int(img_width * scale)
        new_height = int(img_height * scale)
        img_resized = current_img[0].resize((new_width, new_height), Image.LANCZOS)
        photo = ImageTk.PhotoImage(img_resized)
        canvas.delete("all")
        x = (canvas_width - new_width) // 2
        y = (canvas_height - new_height) // 2
        canvas.create_image(x, y, anchor=tk.NW, image=photo)
        canvas.image = photo  # prevent garbage collection

    def apply_to_folder():
        if not folder_state['image_files']:
            return
        try:
            cell_size_px, threshold = _read_inputs()
        except (ValueError, tk.TclError):
            messagebox.showerror("Invalid Input", "Please check all input values.")
            return

        mask_img = folder_state['mask_img']
        results = []
        for img_file in folder_state['image_files']:
            try:
                value, _ = process_image(img_file, cell_size_px, threshold, mask_img)
            except ValueError as e:
                messagebox.showerror("Error", str(e))
                return
            results.append((img_file.name, value))

        csv_filename = f"results_{cell_size_px}px_{int(threshold)}.csv"
        csv_path = folder_state['images_folder'] / csv_filename
        with open(csv_path, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Image Name', 'Normalised Value'])
            for row in results:
                writer.writerow(row)
        messagebox.showinfo("Done", f"Results saved to {csv_filename}")

    # ------------------------------------------------------------------ #
    # Build UI                                                             #
    # ------------------------------------------------------------------ #

    root.deiconify()
    root.title("Image Grid Analysis")

    input_frame = ttk.Frame(root)
    input_frame.pack(pady=10)

    SLIDER_W = 160   # slider widget width in pixels

    def _make_slider(parent, row, label_text, from_, to, resolution, default):
        ttk.Label(parent, text=label_text).grid(row=row, column=0, padx=5, sticky=tk.E)
        scale = tk.Scale(parent, from_=from_, to=to, resolution=resolution,
                         orient=tk.HORIZONTAL, length=SLIDER_W, showvalue=True,
                         command=_debounce_update)
        scale.set(default)
        scale.grid(row=row, column=1, padx=5, sticky='ew')
        return scale

    # --- Grid analysis controls ---
    ttk.Label(input_frame, text="Cell Size (px):").grid(row=0, column=0, padx=5, sticky=tk.E)
    cell_size_combo = ttk.Combobox(input_frame, values=[], state="readonly", width=10)
    cell_size_combo.grid(row=0, column=1, padx=5)
    cell_size_combo.bind("<<ComboboxSelected>>", lambda _: process_and_display())

    threshold_scale = _make_slider(input_frame, 1, "Threshold (%):",
                                   0, 100, 1, DEFAULT_THRESHOLD_PERCENTAGE)

    # --- Buttons ---
    button_frame = ttk.Frame(root)
    button_frame.pack(pady=10)
    ttk.Button(button_frame, text="Update",
               command=process_and_display).grid(row=0, column=0, padx=5)
    ttk.Button(button_frame, text="Apply to Folder",
               command=apply_to_folder).grid(row=0, column=1, padx=5)
    ttk.Button(button_frame, text="Load New Folder",
               command=reload_folder).grid(row=0, column=2, padx=5)

    # --- Display area ---
    display_frame = ttk.Frame(root)
    display_frame.pack(pady=10, fill=tk.BOTH, expand=True)

    canvas = tk.Canvas(display_frame, bg='gray')
    canvas.pack(fill=tk.BOTH, expand=True)
    canvas.bind('<Configure>', lambda _: display_image())

    metrics_frame = ttk.Frame(display_frame)
    metrics_frame.pack(side=tk.RIGHT, padx=20, pady=10)

    value_label = ttk.Label(metrics_frame, text="Normalised Value: —",
                            font=("Helvetica", 14, "bold"))
    value_label.pack(anchor=tk.W)

    # ------------------------------------------------------------------ #
    # Initial load                                                         #
    # ------------------------------------------------------------------ #

    if not load_folder():
        root.destroy()
        return
    process_and_display()
    root.mainloop()


if __name__ == "__main__":
    main()
