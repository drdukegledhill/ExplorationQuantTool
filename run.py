import os
import argparse
from pathlib import Path
from PIL import Image, ImageOps
import math
import csv
import tkinter as tk
from tkinter import filedialog
import numpy as np

from squiggliness import compute_squiggliness, compute_shape, DEFAULT_MIN_COMPONENT_PX

DEFAULT_THRESHOLD_PERCENTAGE = 50
DEFAULT_CELL_SIZE_PX = 50
DEFAULT_EDGE_THRESHOLD = 30
DEFAULT_SEGMENT_LENGTH = 100
DEFAULT_MIN_RUN_LENGTH = 50


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
    parser.add_argument(
        "--edge-threshold",
        type=int,
        default=DEFAULT_EDGE_THRESHOLD,
        help=f"Brightness threshold (0-255) for edge detection (default: {DEFAULT_EDGE_THRESHOLD}).",
    )
    parser.add_argument(
        "--segment-length",
        type=int,
        default=DEFAULT_SEGMENT_LENGTH,
        help=f"Segment length in pixels for Ra calculation (default: {DEFAULT_SEGMENT_LENGTH}).",
    )
    parser.add_argument(
        "--min-run-length",
        type=int,
        default=DEFAULT_MIN_RUN_LENGTH,
        help=f"Minimum edge run length to include in squiggliness (default: {DEFAULT_MIN_RUN_LENGTH}).",
    )
    parser.add_argument(
        "--min-component-px",
        type=int,
        default=DEFAULT_MIN_COMPONENT_PX,
        help=f"Minimum connected-component size in pixels to include (default: {DEFAULT_MIN_COMPONENT_PX}).",
    )
    return parser.parse_args()


def main():
    args = _parse_args()

    root = tk.Tk()
    root.withdraw()
    folder_selected = filedialog.askdirectory(
        title="Select folder containing images", initialdir=os.getcwd()
    )
    if not folder_selected:
        print("No folder selected. Exiting.")
        exit(1)
    images_folder = Path(folder_selected)

    if not images_folder.exists():
        print("Images folder does not exist.")
        exit(1)

    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff'}
    mask_path = images_folder / args.mask

    # Exclude the mask file itself from the list of images to analyse
    image_files = [
        f for f in images_folder.iterdir()
        if f.is_file() and f.suffix.lower() in image_extensions and f != mask_path
    ]

    if not image_files:
        print("No image files found in the images folder.")
        return

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
        choice = input(f"Choose cell size [default {default_cell_size}]: ").strip()
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
    grid_cols = first_width // cell_size_px
    grid_rows = first_height // cell_size_px

    results = []
    for img_file in image_files:
        with Image.open(img_file) as img:
            width, height = img.size

            if mask_img is not None and mask_img.size != (width, height):
                print(f"{args.mask} size does not match {img_file.name} ({width}x{height}).")
                exit(1)

            if width % cell_size_px != 0 or height % cell_size_px != 0:
                print(f"Cell size {cell_size_px}px does not evenly divide {img_file.name} ({width}x{height}).")
                print(f"Valid cell sizes for this image are: {', '.join(map(str, _common_divisors(width, height)))}")
                exit(1)

            if img.mode != 'L':
                img = img.convert('L')

            if mask_img is not None:
                # White in mask = exclude, black = include (intentionally non-standard)
                black_bg = Image.new('L', img.size, 0)
                img = Image.composite(img, black_bg, ImageOps.invert(mask_img))

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
        sq = compute_squiggliness(img_file, mask_img,
                                  edge_threshold=args.edge_threshold,
                                  segment_length=args.segment_length,
                                  min_component_px=args.min_component_px,
                                  min_run_length=args.min_run_length)
        sh = compute_shape(img_file, mask_img, edge_threshold=args.edge_threshold)
        results.append((img_file.name, normalised_value,
                        sq['arc_length_ratio'], sq['ra_roughness'], sq['edge_runs_analyzed'],
                        sh['vertical_centroid'], sh['vertical_spread'],
                        sh['col_height_skewness']))

    csv_filename = f"results_{cell_size_px}px_{int(threshold_percentage)}.csv"
    csv_path = os.path.join(images_folder, csv_filename)
    with open(csv_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Image Name', 'Normalised Value',
                         'Arc-Length Ratio', 'Ra Roughness (px)', 'Edge Runs Analyzed',
                         'Vertical Centroid', 'Vertical Spread', 'Col-Height Skewness'])
        for row in results:
            writer.writerow(row)

    print(f"Threshold Percentage: {threshold_percentage}%")
    print(f"Cell Size: {cell_size_px}px ({grid_cols}x{grid_rows})")
    print(f"Edge Threshold: {args.edge_threshold}  |  Segment Length: {args.segment_length}px")
    print()
    print("| Image Name | Normalised Value | Arc-Length Ratio | Ra Roughness (px) | Vert. Centroid | Vert. Spread | Col-Height Skew |")
    print("|------------|------------------|------------------|-------------------|----------------|--------------|-----------------|")
    for name, nv, alr, ra, _runs, vc, vs, chs in results:
        print(f"| {name} | {nv:.1f} | {alr:.4f} | {ra:.4f} | {vc:.4f} | {vs:.4f} | {chs:.4f} |")


if __name__ == "__main__":
    main()
