"""
Squiggliness analysis for heatmap images.

Two complementary metrics are computed:
  arc_length_ratio  — actual edge path length / straight-line extent (1.0 = perfectly straight)
  ra_roughness      — mean absolute pixel deviation from a local best-fit line per segment

The image is divided into horizontal and vertical bands of configurable size. Within each band
the topmost and bottommost (or leftmost and rightmost) edge pixel per scan line is recorded,
producing one profile per band boundary. Using multiple bands captures internal lines, not just
the outermost boundary of the bright region. Smaller band_size → finer internal detail.

Each continuous run of edge positions is analysed independently; results are combined
as an arc-length-weighted average across all runs and bands.
"""

import numpy as np
from PIL import Image, ImageOps

DEFAULT_BAND_SIZE = 200   # px — height/width of each scan band


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


def _find_edge_map(arr, threshold):
    """
    Return a boolean array marking the 1-pixel-thick boundary of bright regions.
    Uses 8-connected morphological erosion (numpy only, no scipy).
    """
    binary = arr > threshold
    h, w = binary.shape
    padded = np.pad(binary, 1, mode='edge')
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


def _build_profiles_banded(edge_map, band_size):
    """
    Build edge-position profiles by scanning within fixed-size bands.

    Divides the image into horizontal bands (for column-wise top/bottom profiles)
    and vertical bands (for row-wise left/right profiles). Each band independently
    finds the nearest edges within its slice, so internal lines are captured rather
    than only the outermost boundary of the whole image.

    Returns a list of (label, profile) tuples where:
      label   – 'top' | 'bottom' | 'left' | 'right'
      profile – 1-D float array (absolute pixel coordinates), NaN where no edge.
                For top/bottom: index = x-column, value = y-row.
                For left/right: index = y-row,    value = x-column.
    """
    height, width = edge_map.shape
    profiles = []

    # --- Horizontal bands → column-wise top/bottom profiles ---
    n_hbands = max(1, round(height / band_size))
    band_h = height // n_hbands

    for b in range(n_hbands):
        y0 = b * band_h
        y1 = (b + 1) * band_h if b < n_hbands - 1 else height
        band = edge_map[y0:y1, :]
        bh = y1 - y0

        has_col = band.any(axis=0)
        top = np.where(has_col,
                       np.argmax(band, axis=0).astype(float) + y0,
                       np.nan)
        bottom = np.where(has_col,
                          (bh - 1 - np.argmax(band[::-1, :], axis=0)).astype(float) + y0,
                          np.nan)
        profiles.append(('top', top))
        profiles.append(('bottom', bottom))

    # --- Vertical bands → row-wise left/right profiles ---
    n_vbands = max(1, round(width / band_size))
    band_w = width // n_vbands

    for b in range(n_vbands):
        x0 = b * band_w
        x1 = (b + 1) * band_w if b < n_vbands - 1 else width
        band = edge_map[:, x0:x1]
        bw = x1 - x0

        has_row = band.any(axis=1)
        left = np.where(has_row,
                        np.argmax(band, axis=1).astype(float) + x0,
                        np.nan)
        right = np.where(has_row,
                         (bw - 1 - np.argmax(band[:, ::-1], axis=1)).astype(float) + x0,
                         np.nan)
        profiles.append(('left', left))
        profiles.append(('right', right))

    return profiles


def get_edge_runs(img_path, mask_img=None, edge_threshold=30,
                  band_size=DEFAULT_BAND_SIZE, min_run_length=50):
    """
    Return edge profiles and their continuous runs for visual overlay.

    Returns a list of (label, profile, runs) tuples:
      label   – 'top' | 'bottom' | 'left' | 'right'
      profile – 1-D float array, NaN where no edge exists
      runs    – list of (start, end) index pairs (both inclusive)

    For 'top'/'bottom' profiles: index = x-column, value = y-row.
    For 'left'/'right' profiles: index = y-row,    value = x-column.
    """
    arr = _load_image(img_path, mask_img)
    edge_map = _find_edge_map(arr, edge_threshold)
    labeled_profiles = _build_profiles_banded(edge_map, band_size)
    return [
        (label, profile, _find_continuous_runs(profile, min_run_length))
        for label, profile in labeled_profiles
    ]


def compute_squiggliness(img_path, mask_img=None, edge_threshold=30,
                         segment_length=100, band_size=DEFAULT_BAND_SIZE,
                         min_run_length=50):
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
    band_size : int
        Height/width in pixels of each scan band. Smaller values capture more internal
        detail; larger values only capture the outermost boundary per direction.
    min_run_length : int
        Minimum contiguous run length to include in the analysis.

    Returns
    -------
    dict with:
      'arc_length_ratio'   – float  (1.0 = straight, higher = more squiggly)
      'ra_roughness'       – float  (mean absolute pixel deviation from local best-fit line)
      'edge_runs_analyzed' – int    (number of edge runs that contributed to the score)
    """
    arr = _load_image(img_path, mask_img)
    edge_map = _find_edge_map(arr, edge_threshold)
    labeled_profiles = _build_profiles_banded(edge_map, band_size)

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

    These metrics capture the overall layout of the bright region rather than the
    roughness of individual edges.  Two metrics show strong statistical separation
    between image classes (p < 0.001):

      vertical_centroid — normalised vertical centre of mass of all bright pixels
                          (0 = top, 1 = bottom, 0.5 = perfectly centred).
                          Captures whether activity sits high or low in the frame.

      vertical_spread   — std of bright-pixel y-positions, normalised by image height.
                          Low = activity concentrated in a narrow band;
                          high = activity spread across the full vertical range.

    A third metric provides supplementary shape information:

      col_height_skewness — skewness of the per-column bright-region height profile
                            (bottom_edge[x] − top_edge[x]).
                            Negative = most columns are tall with a few short outliers;
                            positive = most columns are short with a few tall ones.

    Parameters
    ----------
    img_path : str or Path
    mask_img : PIL.Image.Image or None
        Grayscale mask — white = exclude, black = include.
    edge_threshold : int
        Brightness value (0–255) above which a pixel counts as 'lit'.

    Returns
    -------
    dict with:
      'vertical_centroid'  – float  (0–1, lower = activity sits higher in image)
      'vertical_spread'    – float  (0–1, higher = more vertically dispersed)
      'col_height_skewness'– float  (negative = tall-column-dominant distribution)
    """
    arr = _load_image(img_path, mask_img)
    h, w = arr.shape
    binary = arr > edge_threshold

    # Vertical centroid and spread from all bright-pixel y-positions
    ys = np.where(binary)[0]
    if len(ys) == 0:
        return {
            'vertical_centroid':   0.5,
            'vertical_spread':     0.0,
            'col_height_skewness': 0.0,
        }

    vertical_centroid = float(ys.mean() / (h - 1))
    vertical_spread   = float(ys.std() / h)

    # Per-column bright-region height  (bottom_edge − top_edge)
    has_col = binary.any(axis=0)
    top    = np.where(has_col, np.argmax(binary,          axis=0).astype(float), np.nan)
    bottom = np.where(has_col, (h - 1 - np.argmax(binary[::-1, :], axis=0)).astype(float), np.nan)
    col_heights = (bottom - top)[~np.isnan(bottom - top)]

    col_height_skewness = _skewness(col_heights) if len(col_heights) >= 3 else 0.0

    return {
        'vertical_centroid':   round(vertical_centroid,   4),
        'vertical_spread':     round(vertical_spread,     4),
        'col_height_skewness': round(col_height_skewness, 4),
    }
