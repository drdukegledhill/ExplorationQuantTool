import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageTk, ImageOps
import csv
import math
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import numpy as np

from squiggliness import (compute_squiggliness, get_edge_runs, compute_shape,
                          DEFAULT_MIN_TRACK_LENGTH, DEFAULT_MAX_JUMP)

MASK_FILENAME = "mask.png"
DEFAULT_THRESHOLD_PERCENTAGE = 50
DEFAULT_CELL_SIZE_PX = 50
DEFAULT_EDGE_THRESHOLD = 30
DEFAULT_SEGMENT_LENGTH = 100

# Colours used to draw each centerline profile on the overlay
EDGE_COLOURS = {
    'h': (255, 220,  0),    # yellow  — horizontally-tracked centroids
    'v': (220,  80, 255),   # magenta — vertically-tracked centroids
}


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

    # Convert to RGB so grid lines and edge overlay can both be coloured
    img_rgb = img.convert('RGB')
    draw = ImageDraw.Draw(img_rgb)
    for col in range(1, grid_cols):
        draw.line([(col * cell_size_px, 0), (col * cell_size_px, height)],
                  fill=(255, 255, 255), width=1)
    for row in range(1, grid_rows):
        draw.line([(0, row * cell_size_px), (width, row * cell_size_px)],
                  fill=(255, 255, 255), width=1)

    return normalised_value, img_rgb


def draw_edge_overlay(img_rgb, edge_run_data):
    """
    Draw centerline profiles as coloured polylines on an RGB image in-place.

    edge_run_data is the list returned by get_edge_runs():
      [(label, profile, runs), ...]
      label 'h' → index is x-column, value is centroid y-row
      label 'v' → index is y-row,    value is centroid x-column
    """
    draw = ImageDraw.Draw(img_rgb)
    for label, profile, runs in edge_run_data:
        colour = EDGE_COLOURS[label]
        for start, end in runs:
            # Convert each 1D centroid profile segment into drawable 2D points.
            seg = profile[start:end + 1]
            if label == 'h':
                pts = [(start + i, int(round(seg[i]))) for i in range(len(seg))]
            else:
                pts = [(int(round(seg[i])), start + i) for i in range(len(seg))]
            if len(pts) >= 2:
                draw.line(pts, fill=colour, width=2)


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
        """Read all control values."""
        cell_size_px = int(cell_size_combo.get())
        threshold    = float(threshold_scale.get())
        edge_thresh  = int(edge_threshold_scale.get())
        seg_len      = int(segment_length_scale.get())
        min_track    = int(min_track_scale.get())
        max_jump     = int(max_jump_scale.get())
        return cell_size_px, threshold, edge_thresh, seg_len, min_track, max_jump

    def process_and_display():
        if not folder_state['image_files']:
            return
        try:
            cell_size_px, threshold, edge_thresh, seg_len, min_track, max_jump = _read_inputs()
        except (ValueError, tk.TclError):
            return

        img_path = folder_state['current_img_path']
        mask_img = folder_state['mask_img']

        # Compute grid score first, then append squiggliness + shape descriptors.
        normalised_value, img_rgb = process_image(img_path, cell_size_px, threshold, mask_img)

        sq = compute_squiggliness(img_path, mask_img,
                                  edge_threshold=edge_thresh, segment_length=seg_len,
                                  min_track_length=min_track, max_jump=max_jump)
        sh = compute_shape(img_path, mask_img, edge_threshold=edge_thresh)

        if show_overlay_var.get():
            # Overlay uses the exact same tracking parameters as metric computation.
            runs_data = get_edge_runs(img_path, mask_img,
                                      edge_threshold=edge_thresh,
                                      min_track_length=min_track, max_jump=max_jump)
            draw_edge_overlay(img_rgb, runs_data)

        current_img[0] = img_rgb

        value_label.config(text=f"Normalised Value: {normalised_value}")
        arc_label.config(text=f"Arc-Length Ratio: {sq['arc_length_ratio']:.4f}")
        ra_label.config(text=f"Ra Roughness: {sq['ra_roughness']:.4f} px")
        runs_label.config(text=f"Edge Runs: {sq['edge_runs_analyzed']}")
        centroid_label.config(text=f"Vert. Centroid: {sh['vertical_centroid']:.4f}")
        spread_label.config(text=f"Vert. Spread: {sh['vertical_spread']:.4f}")
        skew_label.config(text=f"Col-Height Skew: {sh['col_height_skewness']:.4f}")
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
            cell_size_px, threshold, edge_thresh, seg_len, min_track, max_jump = _read_inputs()
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
            # Batch mode mirrors preview mode so CSV values match what the user sees.
            sq = compute_squiggliness(img_file, mask_img,
                                      edge_threshold=edge_thresh, segment_length=seg_len,
                                      min_track_length=min_track, max_jump=max_jump)
            sh = compute_shape(img_file, mask_img, edge_threshold=edge_thresh)
            results.append((img_file.name, value,
                            sq['arc_length_ratio'], sq['ra_roughness'], sq['edge_runs_analyzed'],
                            sh['vertical_centroid'], sh['vertical_spread'],
                            sh['col_height_skewness']))

        csv_filename = f"results_{cell_size_px}px_{int(threshold)}.csv"
        csv_path = folder_state['images_folder'] / csv_filename
        with open(csv_path, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Image Name', 'Normalised Value',
                             'Arc-Length Ratio', 'Ra Roughness (px)', 'Edge Runs Analyzed',
                             'Vertical Centroid', 'Vertical Spread', 'Col-Height Skewness'])
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

    # --- Squiggliness controls ---
    ttk.Separator(input_frame, orient=tk.HORIZONTAL).grid(
        row=2, column=0, columnspan=2, sticky='ew', pady=6)

    edge_threshold_scale = _make_slider(input_frame, 3, "Edge Threshold (0-255):",
                                        0, 255, 1, DEFAULT_EDGE_THRESHOLD)
    segment_length_scale = _make_slider(input_frame, 4, "Segment Length (px):",
                                        5, 500, 5, DEFAULT_SEGMENT_LENGTH)
    min_track_scale      = _make_slider(input_frame, 5, "Min Track (pts):",
                                        5, 300, 5, DEFAULT_MIN_TRACK_LENGTH)
    max_jump_scale       = _make_slider(input_frame, 6, "Max Jump (px):",
                                        2, 100, 2, DEFAULT_MAX_JUMP)

    # --- Edge overlay toggle ---
    show_overlay_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(input_frame, text="Show edge overlay",
                    variable=show_overlay_var,
                    command=process_and_display).grid(
        row=7, column=0, columnspan=2, pady=(6, 0))

    # --- Colour legend ---
    legend_frame = ttk.LabelFrame(input_frame, text="Overlay colours")
    legend_frame.grid(row=8, column=0, columnspan=2, padx=5, pady=6, sticky='ew')
    legend_items = [
        ("Horizontal centroids", EDGE_COLOURS['h']),
        ("Vertical centroids",   EDGE_COLOURS['v']),
    ]
    for i, (label_text, colour) in enumerate(legend_items):
        hex_colour = "#{:02x}{:02x}{:02x}".format(*colour)
        tk.Label(legend_frame, bg=hex_colour, width=2).grid(row=i, column=0, padx=(4, 2), pady=1)
        ttk.Label(legend_frame, text=label_text).grid(row=i, column=1, sticky=tk.W)

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
    arc_label = ttk.Label(metrics_frame, text="Arc-Length Ratio: —", font=("Helvetica", 12))
    arc_label.pack(anchor=tk.W, pady=2)
    ra_label = ttk.Label(metrics_frame, text="Ra Roughness: — px", font=("Helvetica", 12))
    ra_label.pack(anchor=tk.W, pady=2)
    runs_label = ttk.Label(metrics_frame, text="Edge Runs: —",
                           font=("Helvetica", 11), foreground="gray")
    runs_label.pack(anchor=tk.W, pady=2)

    ttk.Separator(metrics_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=6)

    centroid_label = ttk.Label(metrics_frame, text="Vert. Centroid: —", font=("Helvetica", 12))
    centroid_label.pack(anchor=tk.W, pady=2)
    spread_label = ttk.Label(metrics_frame, text="Vert. Spread: —", font=("Helvetica", 12))
    spread_label.pack(anchor=tk.W, pady=2)
    skew_label = ttk.Label(metrics_frame, text="Col-Height Skew: —", font=("Helvetica", 12))
    skew_label.pack(anchor=tk.W, pady=2)

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
