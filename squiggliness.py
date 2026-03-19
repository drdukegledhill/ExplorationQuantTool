"""
Squiggliness analysis for heatmap images.

Two complementary metrics are computed:
  arc_length_ratio  — actual path length / straight-line extent (1.0 = perfectly straight)
  ra_roughness      — mean absolute pixel deviation from a local best-fit line per segment

Bright pixels are grouped into connected components (8-connectivity).  Each component
that is large enough gets its own independent brightness-weighted centroid trace, so the
profile always follows a single line's centre and can never jump between separate lines.
Components whose longer dimension is horizontal are traced column-by-column ('h');
those that are taller than wide are traced row-by-row ('v').

Each continuous centroid run is analysed independently; results are combined as an
arc-length-weighted average across all components.
"""

import numpy as np
from PIL import Image, ImageOps
from scipy.ndimage import label as _scipy_label

DEFAULT_MIN_COMPONENT_PX = 200   # minimum component size (pixels) to include in analysis


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _load_image(img_path, mask_img):
    """Load image as greyscale, apply mask if provided."""
    with Image.open(img_path) as raw:
        img = raw.convert('L')
    if mask_img is not None:
        black_bg = Image.new('L', img.size, 0)
        img = Image.composite(img, black_bg, ImageOps.invert(mask_img))
    return np.array(img)


def _skewness(x):
    """Sample skewness (Fisher's moment coefficient), numpy-only."""
    n = len(x)
    if n < 3:
        return 0.0
    m = x.mean()
    s = x.std(ddof=1)
    if s == 0:
        return 0.0
    return float(((x - m) ** 3).mean() / s ** 3)


# ---------------------------------------------------------------------------
# Profile analysis
# ---------------------------------------------------------------------------

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
        e = min(int(round((i + 1) * seg_size)), n)
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


# ---------------------------------------------------------------------------
# Centerline extraction
# ---------------------------------------------------------------------------

def _build_centerline_profiles_components(arr, threshold, min_component_px):
    """
    Label 8-connected components of bright pixels and compute per-component
    brightness-weighted centroid profiles.

    Each component gets an independent trace so the centroid can never average
    across two separate lines.  The component's longer axis determines the scan
    direction:
      - wider than tall  → column-centroid trace, label 'h'
      - taller than wide → row-centroid trace,    label 'v'

    Returns a list of (label, profile) tuples:
      label   – 'h' or 'v'
      profile – 1-D float array (absolute pixel coordinates), NaN where the
                component has no pixels in that scan line.
                'h': index = x-column, value = centroid y-row.
                'v': index = y-row,    value = centroid x-column.
    """
    h, w = arr.shape
    binary = arr > threshold

    # 8-connectivity so diagonal lines form single components
    struct = np.ones((3, 3), dtype=int)
    labeled, n_components = _scipy_label(binary, structure=struct)

    # Pre-compute brightness weights (use raw pixel values, not just binary)
    brightness = arr.astype(float) * binary

    profiles = []
    y_coords = np.arange(h, dtype=float)
    x_coords = np.arange(w, dtype=float)

    for comp_id in range(1, n_components + 1):
        comp_mask = labeled == comp_id
        if comp_mask.sum() < min_component_px:
            continue

        comp_brightness = brightness * comp_mask
        rows, cols = np.where(comp_mask)
        col_extent = int(cols.max() - cols.min())
        row_extent = int(rows.max() - rows.min())

        if col_extent >= row_extent:
            # Primarily horizontal — trace column by column
            col_bright = comp_brightness.sum(axis=0)        # (w,)
            y_sum = (comp_brightness * y_coords[:, np.newaxis]).sum(axis=0)
            centroid = np.where(
                col_bright > 0,
                y_sum / np.where(col_bright > 0, col_bright, 1.0),
                np.nan,
            )
            profiles.append(('h', centroid))
        else:
            # Primarily vertical — trace row by row
            row_bright = comp_brightness.sum(axis=1)        # (h,)
            x_sum = (comp_brightness * x_coords[np.newaxis, :]).sum(axis=1)
            centroid = np.where(
                row_bright > 0,
                x_sum / np.where(row_bright > 0, row_bright, 1.0),
                np.nan,
            )
            profiles.append(('v', centroid))

    return profiles


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_edge_runs(img_path, mask_img=None, edge_threshold=30,
                  min_component_px=DEFAULT_MIN_COMPONENT_PX, min_run_length=50,
                  # legacy alias kept for callers that still pass band_size
                  band_size=None):
    """
    Return per-line centerline profiles and their continuous runs for visual overlay.

    Returns a list of (label, profile, runs) tuples:
      label   – 'h' (horizontal component) or 'v' (vertical component)
      profile – 1-D float array, NaN where the component has no pixels
      runs    – list of (start, end) index pairs (both inclusive)

    'h' profiles: index = x-column, value = centroid y-row.
    'v' profiles: index = y-row,    value = centroid x-column.
    """
    if band_size is not None:
        min_component_px = band_size   # honour legacy callers
    arr = _load_image(img_path, mask_img)
    labeled_profiles = _build_centerline_profiles_components(arr, edge_threshold, min_component_px)
    return [
        (label, profile, _find_continuous_runs(profile, min_run_length))
        for label, profile in labeled_profiles
    ]


def compute_squiggliness(img_path, mask_img=None, edge_threshold=30,
                         segment_length=100,
                         min_component_px=DEFAULT_MIN_COMPONENT_PX,
                         min_run_length=50,
                         # legacy alias
                         band_size=None):
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
    min_component_px : int
        Minimum connected-component size (pixels) to include.  Smaller components
        are treated as noise and ignored.
    min_run_length : int
        Minimum contiguous centroid-run length to include in the analysis.

    Returns
    -------
    dict with:
      'arc_length_ratio'   – float  (1.0 = straight, higher = more squiggly)
      'ra_roughness'       – float  (mean absolute pixel deviation from local best-fit line)
      'edge_runs_analyzed' – int    (number of centroid runs that contributed to the score)
    """
    if band_size is not None:
        min_component_px = band_size
    arr = _load_image(img_path, mask_img)
    labeled_profiles = _build_centerline_profiles_components(arr, edge_threshold, min_component_px)

    arc_ratios = []
    ra_values = []
    arc_lengths = []

    for _label, profile in labeled_profiles:
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


def compute_shape(img_path, mask_img=None, edge_threshold=30):
    """
    Compute shape metrics that describe the spatial distribution of bright pixels.

    Two metrics show strong statistical separation between image classes (p < 0.001):

      vertical_centroid — normalised vertical centre of mass of all bright pixels
                          (0 = top, 1 = bottom, 0.5 = perfectly centred).

      vertical_spread   — std of bright-pixel y-positions, normalised by image height.
                          Low = activity concentrated in a narrow band;
                          high = activity spread across the full vertical range.

    A third metric provides supplementary shape information:

      col_height_skewness — skewness of the per-column bright-region height profile.

    Parameters
    ----------
    img_path : str or Path
    mask_img : PIL.Image.Image or None
    edge_threshold : int

    Returns
    -------
    dict with 'vertical_centroid', 'vertical_spread', 'col_height_skewness'
    """
    arr = _load_image(img_path, mask_img)
    h, w = arr.shape
    binary = arr > edge_threshold

    ys = np.where(binary)[0]
    if len(ys) == 0:
        return {
            'vertical_centroid':   0.5,
            'vertical_spread':     0.0,
            'col_height_skewness': 0.0,
        }

    vertical_centroid = float(ys.mean() / (h - 1))
    vertical_spread   = float(ys.std() / h)

    has_col = binary.any(axis=0)
    top    = np.where(has_col, np.argmax(binary, axis=0).astype(float), np.nan)
    bottom = np.where(has_col, (h - 1 - np.argmax(binary[::-1, :], axis=0)).astype(float), np.nan)
    col_heights = (bottom - top)[~np.isnan(bottom - top)]
    col_height_skewness = _skewness(col_heights) if len(col_heights) >= 3 else 0.0

    return {
        'vertical_centroid':   round(vertical_centroid,   4),
        'vertical_spread':     round(vertical_spread,     4),
        'col_height_skewness': round(col_height_skewness, 4),
    }
