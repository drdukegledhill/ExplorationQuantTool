"""
Squiggliness analysis for heatmap images.

Two complementary metrics are computed:
  arc_length_ratio  — actual path length / straight-line extent (1.0 = perfectly straight)
  ra_roughness      — mean absolute pixel deviation from a local best-fit line per segment

For each pixel column the image is scanned to find all distinct bright-pixel runs.
Each run's brightness-weighted centroid is tracked across adjacent columns using a
greedy nearest-neighbour linker, producing one independent centroid trace per detected
line.  The same process is repeated row-by-row for lines with a vertical orientation.
Tracks shorter than min_track_length positions are discarded as noise.

Each continuous centroid run is analysed independently; results are combined as an
arc-length-weighted average across all tracks.
"""

import numpy as np
from PIL import Image, ImageOps

DEFAULT_MIN_TRACK_LENGTH = 30    # minimum scan-positions for a tracked centerline
DEFAULT_MAX_JUMP = 25            # maximum pixel distance between adjacent centroids

# Legacy aliases
DEFAULT_MIN_COMPONENT_PX = DEFAULT_MIN_TRACK_LENGTH
DEFAULT_BAND_SIZE = DEFAULT_MIN_TRACK_LENGTH


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
# Centerline extraction — multi-run tracking
# ---------------------------------------------------------------------------

def _find_run_centroids(values, binary):
    """
    Brightness-weighted centroid of each consecutive bright run in a 1-D array.

    values  – raw pixel brightness (used as weights)
    binary  – boolean array (True where pixel is above threshold)
    Returns a list of float centroid positions.
    """
    if not binary.any():
        return []
    padded = np.concatenate(([False], binary.astype(bool), [False]))
    starts = np.where(~padded[:-1] & padded[1:])[0]   # F→T transitions → run start
    ends   = np.where( padded[:-1] & ~padded[1:])[0]  # T→F transitions → exclusive end
    centroids = []
    for s, e in zip(starts, ends):
        vals = values[s:e].astype(float)
        w_sum = vals.sum()
        if w_sum > 0:
            pos = np.arange(s, e, dtype=float)
            centroids.append(float((pos * vals).sum() / w_sum))
    return centroids


def _track_centroids(scan_length, get_centroids_fn, max_jump, max_gap=5):
    """
    Greedy nearest-neighbour tracker across scan positions.

    At each scan position, centroids are matched to the nearest active track
    within max_jump pixels.  Unmatched centroids start new tracks.  Tracks
    with no match for more than max_gap consecutive positions are retired.

    Returns a list of tracks; each track is a list of (pos, centroid) pairs.
    """
    tracks = {}     # id → [(pos, centroid), ...]
    active = {}     # id → (last_pos, last_centroid)
    next_id = 0

    for pos in range(scan_length):
        centroids = get_centroids_fn(pos)
        available = {tid: d for tid, d in active.items() if pos - d[0] <= max_gap}

        matched_t = set()
        matched_c = set()

        if available and centroids:
            pairs = []
            for tid, (_, last_y) in available.items():
                for ci, cy in enumerate(centroids):
                    dist = abs(cy - last_y)
                    if dist <= max_jump:
                        pairs.append((dist, tid, ci))
            pairs.sort()
            for dist, tid, ci in pairs:
                if tid in matched_t or ci in matched_c:
                    continue
                tracks[tid].append((pos, centroids[ci]))
                active[tid] = (pos, centroids[ci])
                matched_t.add(tid)
                matched_c.add(ci)

        for ci, cy in enumerate(centroids):
            if ci not in matched_c:
                tracks[next_id] = [(pos, cy)]
                active[next_id] = (pos, cy)
                next_id += 1

        stale = [tid for tid, (lp, _) in active.items() if pos - lp > max_gap]
        for tid in stale:
            del active[tid]

    return list(tracks.values())


def _build_centerline_profiles_multiscan(arr, threshold, min_track_length, max_jump):
    """
    Scan the image column-by-column and row-by-row, tracking brightness-weighted
    centroids of each bright-pixel run into independent per-line profiles.

    Each distinct line gets its own trace regardless of whether it touches or
    crosses other lines.

    Returns a list of (label, profile) tuples:
      'h': index = x-column, value = centroid y-row
      'v': index = y-row,    value = centroid x-column
    """
    h, w = arr.shape
    binary = arr > threshold
    max_gap = 5

    profiles = []

    # Horizontal scan (column by column) — tracks lines with horizontal extent
    h_raw = _track_centroids(
        w,
        lambda x: _find_run_centroids(arr[:, x], binary[:, x]),
        max_jump, max_gap,
    )
    for points in h_raw:
        if len(points) < min_track_length:
            continue
        profile = np.full(w, np.nan)
        for x, y in points:
            profile[x] = y
        profiles.append(('h', profile))

    # Vertical scan (row by row) — tracks lines with vertical extent
    v_raw = _track_centroids(
        h,
        lambda y: _find_run_centroids(arr[y, :], binary[y, :]),
        max_jump, max_gap,
    )
    for points in v_raw:
        if len(points) < min_track_length:
            continue
        profile = np.full(h, np.nan)
        for y, x in points:
            profile[y] = x
        profiles.append(('v', profile))

    return profiles


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_edge_runs(img_path, mask_img=None, edge_threshold=30,
                  min_track_length=DEFAULT_MIN_TRACK_LENGTH,
                  max_jump=DEFAULT_MAX_JUMP,
                  min_run_length=50,
                  # legacy aliases
                  min_component_px=None, band_size=None):
    """
    Return per-line centerline profiles and their continuous runs for visual overlay.

    Returns a list of (label, profile, runs) tuples:
      label   – 'h' (horizontal scan) or 'v' (vertical scan)
      profile – 1-D float array, NaN where the track has no data
      runs    – list of (start, end) index pairs (both inclusive)
    """
    if band_size is not None:
        min_track_length = band_size
    if min_component_px is not None:
        min_track_length = min_component_px
    arr = _load_image(img_path, mask_img)
    labeled_profiles = _build_centerline_profiles_multiscan(
        arr, edge_threshold, min_track_length, max_jump)
    return [
        (label, profile, _find_continuous_runs(profile, min_run_length))
        for label, profile in labeled_profiles
    ]


def compute_squiggliness(img_path, mask_img=None, edge_threshold=30,
                         segment_length=100,
                         min_track_length=DEFAULT_MIN_TRACK_LENGTH,
                         max_jump=DEFAULT_MAX_JUMP,
                         min_run_length=50,
                         # legacy aliases
                         min_component_px=None, band_size=None):
    """
    Compute squiggliness metrics for the lines in a heatmap image.

    Parameters
    ----------
    img_path : str or Path
    mask_img : PIL.Image.Image or None
    edge_threshold : int
        Brightness value (0–255) above which a pixel counts as 'lit'.
    segment_length : int
        Target length in pixels for each Ra segment.
    min_track_length : int
        Minimum number of scan positions for a tracked centerline to be included.
    max_jump : int
        Maximum pixel distance between consecutive centroids for the same track.
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
        min_track_length = band_size
    if min_component_px is not None:
        min_track_length = min_component_px
    arr = _load_image(img_path, mask_img)
    labeled_profiles = _build_centerline_profiles_multiscan(
        arr, edge_threshold, min_track_length, max_jump)

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
