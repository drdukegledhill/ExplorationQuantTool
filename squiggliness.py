"""
Squiggliness analysis for heatmap images.

Two complementary metrics are computed:
  arc_length_ratio  — actual edge path length / straight-line extent (1.0 = perfectly straight)
  ra_roughness      — mean absolute pixel deviation from a local best-fit line per segment

The analysis scans the image in both orientations:
  - Column-wise: tracks the y-position of the top and bottom edges per column (captures horizontal lines)
  - Row-wise:    tracks the x-position of the left and right edges per row  (captures vertical lines)
Each continuous run of edge positions is analysed independently; results are combined
as an arc-length-weighted average across all runs.
"""

import numpy as np
from PIL import Image, ImageOps


def _find_edge_map(arr, threshold):
    """
    Return a boolean array marking the 1-pixel-thick boundary of bright regions.
    Uses 8-connected morphological erosion (numpy only, no scipy).
    """
    binary = arr > threshold
    h, w = binary.shape
    # Extend with edge-mirrored values so true image borders aren't falsely detected
    padded = np.pad(binary, 1, mode='edge')
    # Erode: pixel survives only if all 8 neighbours are also bright
    eroded = (
        padded[0:h,   0:w]   & padded[0:h,   1:w+1] & padded[0:h,   2:w+2] &
        padded[1:h+1, 0:w]   &                         padded[1:h+1, 2:w+2] &
        padded[2:h+2, 0:w]   & padded[2:h+2, 1:w+1] & padded[2:h+2, 2:w+2]
    )
    return binary & ~eroded


def _find_continuous_runs(profile, min_length):
    """
    Find contiguous non-NaN spans in a 1-D float array of at least min_length samples.
    Returns a list of (start, end) index pairs (both inclusive).
    """
    runs = []
    n = len(profile)
    start = None
    for i in range(n):
        if not np.isnan(profile[i]):
            if start is None:
                start = i
        else:
            if start is not None and (i - start) >= min_length:
                runs.append((start, i - 1))
            start = None
    if start is not None and (n - start) >= min_length:
        runs.append((start, n - 1))
    return runs


def _arc_length_ratio(profile):
    """
    Arc-length ratio for a 1-D profile sampled at unit intervals.
    Each step is from (i, profile[i]) to (i+1, profile[i+1]).
    Returns arc_length / (number of steps) — equals 1.0 for a flat line.
    """
    dy = np.diff(profile)
    arc_len = float(np.sum(np.sqrt(1.0 + dy ** 2)))
    chord_len = len(profile) - 1
    return arc_len / chord_len if chord_len > 0 else 1.0


def _segmented_ra(profile, segment_length):
    """
    Split the profile into segments of ~segment_length samples, fit a straight line
    through each segment, and compute Ra (mean absolute deviation from that line).
    Returns the segment-length-weighted average Ra.
    """
    n = len(profile)
    if n < 2:
        return 0.0

    n_segments = max(1, round(n / segment_length))
    seg_size = n / n_segments

    ra_values = []
    weights = []

    for i in range(n_segments):
        s = int(round(i * seg_size))
        e = int(round((i + 1) * seg_size))
        e = min(e, n)
        seg = profile[s:e]
        if len(seg) < 2:
            continue
        x = np.arange(len(seg), dtype=float)
        coeffs = np.polyfit(x, seg, 1)
        residuals = seg - np.polyval(coeffs, x)
        ra_values.append(float(np.mean(np.abs(residuals))))
        weights.append(len(seg))

    if not ra_values:
        return 0.0
    w = np.array(weights, dtype=float)
    return float(np.average(ra_values, weights=w / w.sum()))


def _build_profiles(edge_map):
    """
    Build four 1-D edge-position profiles from a 2-D boolean edge map.

    Column-wise (horizontal lines):
      top_edge[x]    — y-coord of the topmost edge pixel in column x
      bottom_edge[x] — y-coord of the bottommost edge pixel in column x

    Row-wise (vertical lines):
      left_edge[y]   — x-coord of the leftmost edge pixel in row y
      right_edge[y]  — x-coord of the rightmost edge pixel in row y

    Positions with no edge pixel are NaN.
    """
    height, width = edge_map.shape

    has_col = edge_map.any(axis=0)
    top_edge = np.where(has_col,
                        np.argmax(edge_map, axis=0).astype(float),
                        np.nan)
    bottom_edge = np.where(has_col,
                           (height - 1 - np.argmax(edge_map[::-1, :], axis=0)).astype(float),
                           np.nan)

    has_row = edge_map.any(axis=1)
    left_edge = np.where(has_row,
                         np.argmax(edge_map, axis=1).astype(float),
                         np.nan)
    right_edge = np.where(has_row,
                          (width - 1 - np.argmax(edge_map[:, ::-1], axis=1)).astype(float),
                          np.nan)

    return top_edge, bottom_edge, left_edge, right_edge


def get_edge_runs(img_path, mask_img=None, edge_threshold=30, min_run_length=50):
    """
    Return edge profiles and their continuous runs for visual overlay.

    Returns a list of (label, profile, runs) tuples:
      label   – 'top' | 'bottom' | 'left' | 'right'
      profile – 1-D float array, NaN where no edge exists
      runs    – list of (start, end) index pairs (both inclusive)

    For 'top'/'bottom' profiles: index = x-column, value = y-row.
    For 'left'/'right' profiles: index = y-row,    value = x-column.
    """
    with Image.open(img_path) as raw:
        img = raw.convert('L')
    if mask_img is not None:
        black_bg = Image.new('L', img.size, 0)
        img = Image.composite(img, black_bg, ImageOps.invert(mask_img))
    arr = np.array(img)
    edge_map = _find_edge_map(arr, edge_threshold)
    top, bottom, left, right = _build_profiles(edge_map)
    labels = ('top', 'bottom', 'left', 'right')
    return [
        (label, profile, _find_continuous_runs(profile, min_run_length))
        for label, profile in zip(labels, (top, bottom, left, right))
    ]


def compute_squiggliness(img_path, mask_img=None, edge_threshold=30,
                         segment_length=100, min_run_length=50):
    """
    Compute squiggliness metrics for the lines in a heatmap image.

    Parameters
    ----------
    img_path : str or Path
    mask_img : PIL.Image.Image or None
        Grayscale mask — white = exclude, black = include (same convention as main tool).
    edge_threshold : int
        Brightness value (0–255) above which a pixel counts as 'lit'.
    segment_length : int
        Target length in pixels for each Ra segment.
    min_run_length : int
        Minimum contiguous run length to include in the analysis.

    Returns
    -------
    dict with:
      'arc_length_ratio'   – float  (1.0 = straight, higher = more squiggly)
      'ra_roughness'       – float  (mean absolute pixel deviation from local best-fit line)
      'edge_runs_analyzed' – int    (number of edge runs that contributed to the score)
    """
    with Image.open(img_path) as raw:
        img = raw.convert('L')

    if mask_img is not None:
        black_bg = Image.new('L', img.size, 0)
        img = Image.composite(img, black_bg, ImageOps.invert(mask_img))

    arr = np.array(img)
    edge_map = _find_edge_map(arr, edge_threshold)
    profiles = _build_profiles(edge_map)

    arc_ratios = []
    ra_values = []
    arc_lengths = []

    for profile in profiles:
        runs = _find_continuous_runs(profile, min_run_length)
        for start, end in runs:
            seg = profile[start:end + 1]
            arc_ratios.append(_arc_length_ratio(seg))
            ra_values.append(_segmented_ra(seg, segment_length))
            arc_lengths.append(float(np.sum(np.sqrt(1.0 + np.diff(seg) ** 2))))

    if not arc_ratios:
        return {
            'arc_length_ratio': 1.0,
            'ra_roughness': 0.0,
            'edge_runs_analyzed': 0,
        }

    w = np.array(arc_lengths)
    w = w / w.sum()

    return {
        'arc_length_ratio': round(float(np.average(arc_ratios, weights=w)), 4),
        'ra_roughness': round(float(np.average(ra_values, weights=w)), 4),
        'edge_runs_analyzed': len(arc_ratios),
    }
