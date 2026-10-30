#!/usr/bin/env python3
"""Detect and crop camera-copied film frames.

Examples:
  python film_crop.py input.jpg --format 135/6x9 --output out.jpg
  python film_crop.py scans --format 6x6 --output-dir cropped
  python film_crop.py input.jpg --corners 289,242 1570,242 1570,1097 289,1097

The automatic detector is deliberately conservative. It estimates the inner
picture area from horizontal/vertical edge projections, then crops to the
requested aspect ratio. Use --corners when a frame edge is obscured or the
image contains unusually strong horizontal/vertical details.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Iterable, Optional, Sequence, Tuple

import cv2
import numpy as np


FORMATS = {
    "135/6x9": 36 / 24,       # 1.5000
    "6x4.5/半格": 56 / 41.5,  # shared medium-format / half-frame crop family
    "6x6": 1.0,
    "6x7": 56 / 69,        # approximately 0.8116
    # 6x9 and 135 are treated as the same 3:2 crop family. The small
    # nominal difference between 56x84 and 36x24 is below reliable detection
    # precision in these camera copies.
    "6.5x2.4": 65 / 24,     # Hasselblad XPan
    "5.6x2.4": 56 / 24,     # medium-format panoramic 135 back
}

PANORAMIC_FORMATS = {'6.5x2.4', '5.6x2.4'}
FORMAT_LABELS = {key: ('XPan ' + key if key == '6.5x2.4' else key) for key in FORMATS}
FORMAT_CHOICES = {'自动识别': 'auto', **{label: key for key, label in FORMAT_LABELS.items()}}

# User's reference look for a 135 frame with both perforation bands retained.
# This is the full-strip presentation ratio, width:height = 6:5.5.
SPROCKET_RATIO_135 = 6 / 5.5
SPROCKET_SIDE_MARGIN = 0.035


def sprocket_margins(ratio=1.5, side_margin=SPROCKET_SIDE_MARGIN):
    """Match full-strip ratio without the later center crop eating side borders."""
    long_margin = ((1 + 2 * side_margin) * 1.5 / SPROCKET_RATIO_135 - 1) / 2
    return ((long_margin, side_margin, long_margin, side_margin) if ratio >= 1
            else (side_margin, long_margin, side_margin, long_margin))



def parse_point(value: str) -> Tuple[float, float]:
    try:
        x, y = value.split(",")
        return float(x), float(y)
    except Exception as exc:  # pragma: no cover - argparse displays message
        raise argparse.ArgumentTypeError(f"invalid point {value!r}; use x,y") from exc


def resize_for_detection(image: np.ndarray, max_side: int = 1600) -> Tuple[np.ndarray, float]:
    h, w = image.shape[:2]
    scale = min(1.0, max_side / max(h, w))
    if scale == 1.0:
        return image, 1.0
    small = cv2.resize(image, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA)
    return small, scale


def edge_profiles(image: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Return robust horizontal and vertical edge profiles.

    The central 70% is used so sprocket holes and the black camera background
    have less influence than the actual inner frame boundary.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (0, 0), 2.0)
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    h, w = gray.shape
    x0, x1 = int(.15 * w), int(.85 * w)
    y0, y1 = int(.15 * h), int(.85 * h)
    # Median is less affected by trees, text, and other high-frequency detail.
    x_profile = np.median(np.abs(gx[y0:y1, :]), axis=0)
    y_profile = np.median(np.abs(gy[:, x0:x1]), axis=1)
    return x_profile.astype(np.float32), y_profile.astype(np.float32)


def nms_peaks(profile: np.ndarray, count: int = 32, radius: int = 24) -> list[Tuple[int, float]]:
    """Return strong, spatially separated local maxima."""
    p = profile.copy()
    # Normalize broad illumination changes while retaining sharp boundaries.
    p = p - cv2.GaussianBlur(p.reshape(1, -1), (0, 0), 18).ravel()
    p = np.maximum(p, 0)
    result: list[Tuple[int, float]] = []
    for _ in range(count):
        i = int(np.argmax(p))
        v = float(p[i])
        if v <= 0:
            break
        result.append((i, v))
        lo, hi = max(0, i - radius), min(len(p), i + radius + 1)
        p[lo:hi] = 0
    return result


def choose_bounds(
    x_profile: np.ndarray,
    y_profile: np.ndarray,
    target_ratio: float,
    gray: Optional[np.ndarray] = None,
) -> Tuple[int, int, int, int]:
    """Choose x0,x1,y0,y1 using edge peaks and aspect-ratio scoring."""
    xp = nms_peaks(x_profile)
    yp = nms_peaks(y_profile)
    w, h = len(x_profile), len(y_profile)
    # Ignore a narrow outer margin. The requested picture is normally inside
    # the film border, while the outside black background is not useful.
    xp = [(i, v) for i, v in xp if .005 * w < i < .995 * w]
    yp = [(i, v) for i, v in yp if .005 * h < i < .995 * h]
    if len(xp) < 2 or len(yp) < 2:
        raise RuntimeError("could not find enough frame edges")

    # Median intensity profiles make it possible to distinguish the actual
    # picture edge (dark film border -> picture) from the outer film edge or
    # sprocket edge. This is especially useful for positive scans with a
    # nearly black frame surround.
    col_intensity = np.median(gray, axis=0) if gray is not None else None
    row_intensity = np.median(gray, axis=1) if gray is not None else None
    x_step = max(3, round(.008 * w))
    y_step = max(3, round(.008 * h))

    def rising(profile: Optional[np.ndarray], i: int, step: int) -> float:
        if profile is None:
            return 0.0
        a = float(profile[min(len(profile) - 1, i + step)])
        b = float(profile[max(0, i - step)])
        return max(0.0, (a - b) / 255.0)

    def falling(profile: Optional[np.ndarray], i: int, step: int) -> float:
        if profile is None:
            return 0.0
        a = float(profile[max(0, i - step)])
        b = float(profile[min(len(profile) - 1, i + step)])
        return max(0.0, (a - b) / 255.0)

    best = None
    for x0, sx in xp:
        for x1, ex in xp:
            if x1 <= x0 or x1 - x0 < .55 * w:
                continue
            for y0, sy in yp:
                for y1, ey in yp:
                    if y1 <= y0 or y1 - y0 < .55 * h:
                        continue
                    ratio = (x1 - x0) / (y1 - y0)
                    # Log-ratio makes over/under estimates symmetric.
                    ratio_penalty = abs(math.log(max(ratio, 1e-6) / target_ratio))
                    area_bonus = ((x1 - x0) * (y1 - y0)) / (w * h)
                    edge_score = sum(math.log1p(v / (np.mean(p) + 1e-6)) for v,p in [(sx,x_profile),(ex,x_profile),(sy,y_profile),(ey,y_profile)])
                    # Several film structures can produce a strong edge
                    # (especially the sprocket band). Among rectangles with
                    # the requested ratio, prefer the largest plausible
                    # interior frame rather than a smaller edge fragment.
                    direction_score = (
                        rising(col_intensity, x0, x_step)
                        + falling(col_intensity, x1, x_step)
                        + rising(row_intensity, y0, y_step)
                        + falling(row_intensity, y1, y_step)
                    )
                    score = edge_score + 8 * area_bonus + 2 * direction_score - 30 * ratio_penalty
                    if best is None or score > best[0]:
                        best = (score, x0, x1, y0, y1)
    if best is None:
        raise RuntimeError("could not choose a plausible frame rectangle")
    _, x0, x1, y0, y1 = best
    return int(x0), int(x1), int(y0), int(y1)


def detect_frame(image: np.ndarray, target_ratio: float) -> Tuple[float, float, float, float]:
    """Detect an axis-aligned frame and return coordinates in original pixels."""
    small, scale = resize_for_detection(image)
    x_profile, y_profile = edge_profiles(small)
    gray = cv2.cvtColor(cv2.GaussianBlur(small, (0, 0), 2.0), cv2.COLOR_BGR2GRAY)
    # On converted positives the connected picture area is separated from
    # the edge lettering by the dark film surround. Prefer a large contour
    # with the expected aspect; internal scene edges cannot shrink this box.
    h, w = gray.shape
    candidates = []
    for threshold in (8, 16, 24):
        mask = (gray > threshold).astype(np.uint8) * 255
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            x, y, cw, ch = cv2.boundingRect(contour)
            area = cw * ch / (w * h)
            error = abs(math.log((cw / ch) / target_ratio))
            if .55 < area < .88 and error < .03 and x > 0 and y > 0 and x+cw < w and y+ch < h:
                candidates.append((area - error, x, x+cw-1, y, y+ch-1))
    if candidates:
        _, x0, x1, y0, y1 = max(candidates)
        # Lettering can join a low-contrast picture component through flare.
        # If four independent edge peaks give the expected ratio but the
        # component extends well beyond them, use the actual boundary peaks.
        try:
            ex0, ex1, ey0, ey1 = choose_bounds(x_profile, y_profile, target_ratio, gray)
            edge_error = abs(math.log(((ex1-ex0)/(ey1-ey0))/target_ratio))
            disagreement = max(abs(ex0-x0)/w, abs(ex1-x1)/w, abs(ey0-y0)/h, abs(ey1-y1)/h)
            if edge_error < .02 and disagreement > .02:
                x0,x1,y0,y1 = ex0,ex1,ey0,ey1
        except RuntimeError:
            pass
        return x0 / scale, x1 / scale, y0 / scale, y1 / scale
    x0, x1, y0, y1 = choose_bounds(x_profile, y_profile, target_ratio, gray)
    # A full 135 strip with perforations is close to 6:5.5. When its
    # dark picture edges disappear into the black border, reject a small
    # scene-content rectangle and use film geometry as an explicit fallback.
    strip_ratio = max(w, h) / min(w, h)
    if abs(strip_ratio / SPROCKET_RATIO_135 - 1) < .025 and abs(max(target_ratio,1/target_ratio)-1.5)<.01:
        if target_ratio > 1:
            invalid = x0 > .075*w or x1 < .925*w or y0 > .20*h or y1 < .80*h
            if invalid:
                frame_h = (y1-y0) if .60*h < y1-y0 < .75*h else .69*h
                frame_w = frame_h*target_ratio
                cx = .5*w
                cy = (y0+y1)/2 if y0 < .20*h and y1 > .80*h else .5*h
                x0,x1,y0,y1=cx-frame_w/2,cx+frame_w/2,cy-frame_h/2,cy+frame_h/2
        else:
            invalid = x0 > .20*w or x1 < .80*w or y0 > .075*h or y1 < .925*h
            if invalid:
                frame_w=.69*w
                frame_h=frame_w/target_ratio
                x0,x1,y0,y1=.5*w-frame_w/2,.5*w+frame_w/2,.5*h-frame_h/2,.5*h+frame_h/2
    return x0 / scale, x1 / scale, y0 / scale, y1 / scale


def oriented_ratio(image: np.ndarray, ratio: float, orientation: str = "auto") -> float:
    """Keep portrait frames in portrait orientation without rotating pixels."""
    landscape = image.shape[1] >= image.shape[0] if orientation == "auto" else orientation == "landscape"
    return max(ratio, 1 / ratio) if landscape else min(ratio, 1 / ratio)


def order_corners(points: Sequence[Tuple[float, float]]) -> np.ndarray:
    p = np.asarray(points, dtype=np.float32)
    if p.shape != (4, 2):
        raise ValueError("four corners are required")
    s = p.sum(axis=1)
    d = np.diff(p, axis=1).ravel()
    return np.array([p[np.argmin(s)], p[np.argmin(d)], p[np.argmax(s)], p[np.argmax(d)]], dtype=np.float32)


def perspective_crop(
    image: np.ndarray,
    corners: Sequence[Tuple[float, float]],
    ratio: Optional[float],
    padding: float = 0.0,
) -> np.ndarray:
    """Rectify a quadrilateral and optionally center-crop it to ratio.

    ``ratio=None`` is used by the sprocket-preserving mode: after rectification
    the whole selected film strip is retained instead of being center-cropped.
    """
    tl, tr, br, bl = order_corners(corners)
    width = int(round(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl))))
    height = int(round(max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr))))
    if width < 20 or height < 20:
        raise ValueError("corner points are too close together")
    src = np.array([tl, tr, br, bl], dtype=np.float32)
    dst = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(image, matrix, (width, height), flags=cv2.INTER_LANCZOS4)

    if padding:
        pad_x, pad_y = round(width * padding), round(height * padding)
        warped = warped[pad_y:height - pad_y, pad_x:width - pad_x]
        height, width = warped.shape[:2]
    if ratio is None:
        return warped
    current = width / height
    if current > ratio:
        new_width = max(1, round(height * ratio))
        x = (width - new_width) // 2
        warped = warped[:, x:x + new_width]
    else:
        new_height = max(1, round(width / ratio))
        y = (height - new_height) // 2
        warped = warped[y:y + new_height, :]
    return warped


def expand_for_sprockets(
    corners: Sequence[Tuple[float, float]],
    image_shape: Tuple[int, int],
    fmt: str,
    margins: Optional[Tuple[float, float, float, float]] = None,
    clip: bool = True,
) -> Sequence[Tuple[float, float]]:
    """Expand an inner 135 frame to include its perforation bands.

    Margins are fractions of the detected picture width/height in the order
    top, right, bottom, left. The defaults match common 35 mm camera-copy
    layouts and are intentionally conservative. Users can override them with
    ``--sprocket-margin`` when their mask or holder has a different border.
    """
    if fmt != "135/6x9":
        raise ValueError("--keep-sprockets is currently supported for 135 only")
    p = np.asarray(order_corners(corners), dtype=np.float32)
    tl, tr, br, bl = p
    width = max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl))
    height = max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr))
    # top/right/bottom/left, relative to the inner picture dimensions
    # Expand both dimensions together, preserving side borders at 6:5.5.
    mt, mr, mb, ml = margins or sprocket_margins(width / height)
    # The camera is normally nearly square to the film. These margins are
    # applied in the rectified frame coordinate system before warping.
    frame = np.array([
        [-ml * width, -mt * height],
        [(1 + mr) * width, -mt * height],
        [(1 + mr) * width, (1 + mb) * height],
        [-ml * width, (1 + mb) * height],
    ], dtype=np.float32)
    src = np.array([tl, tr, br, bl], dtype=np.float32)
    # Map the expanded rectified coordinates back to the original image.
    rect_w = int(round(width))
    rect_h = int(round(height))
    dst = np.array([[0, 0], [rect_w - 1, 0], [rect_w - 1, rect_h - 1], [0, rect_h - 1]], dtype=np.float32)
    inv = cv2.getPerspectiveTransform(dst, src)
    expanded = cv2.perspectiveTransform(frame.reshape(-1, 1, 2), inv).reshape(-1, 2)
    h, w = image_shape
    if clip:
        expanded[:, 0] = np.clip(expanded[:, 0], 0, w - 1)
        expanded[:, 1] = np.clip(expanded[:, 1], 0, h - 1)
    return [tuple(x) for x in expanded]


def trim_borders(
    image: np.ndarray,
    ratio: float,
    top_fraction: float = 0.01,
    bottom_fraction: float = 0.01,
) -> np.ndarray:
    """Remove top/bottom safety bands and retain the requested aspect ratio.

    Detection on a reduced image can leave a curved film edge inside the
    rectified rectangle. Trim from both ends first, then equally from the left
    and right; never stretch the picture to restore its aspect ratio.
    """
    if not (0 <= top_fraction < 0.1 and 0 <= bottom_fraction < 0.1):
        raise ValueError("top and bottom trim must be between 0 and 0.1 (exclusive)")
    if top_fraction == 0 and bottom_fraction == 0:
        return image
    h, w = image.shape[:2]
    top = math.ceil(h * top_fraction)
    bottom = math.ceil(h * bottom_fraction)
    new_height = h - top - bottom
    if new_height < 1:
        raise ValueError("image is too small for the requested border trim")
    new_width = min(w, max(1, round(new_height * ratio)))
    left = (w - new_width) // 2
    return image[top:h - bottom, left:left + new_width]


def trim_top_border(
    image: np.ndarray,
    ratio: float,
    fraction: float = 0.01,
) -> np.ndarray:
    """Backward-compatible top-only helper; use trim_borders for both ends."""
    return trim_borders(image, ratio, fraction, 0.0)


def process_one(
    path: Path,
    output: Path,
    ratio: Optional[float],
    corners: Optional[Sequence[Tuple[float, float]]],
    padding: float,
    fmt: str,
    keep_sprockets: bool,
    sprocket_margins: Optional[Tuple[float, float, float, float]],
    orientation: str = "auto",
    top_trim: float = 0.01,
    bottom_trim: float = 0.01,
    output_format: str = 'auto',
    keep_border: bool = False,
    auto_rotate: bool = True,
) -> None:
    from film_io import read_image, detection_image, write_image
    image, metadata = read_image(path)
    preview = detection_image(image)
    if corners is None and (fmt == 'auto' or (orientation == 'auto' and ratio == FORMATS.get(fmt))):
        from film_engine import locate
        detection = locate(image, fmt, auto_rotate)
        ratio = detection['ratio']
        fmt = detection['format']
        x0,x1,y0,y1 = detection['bounds']
        corners = detection.get('corners', [(x0,y0),(x1,y0),(x1,y1),(x0,y1)])
        print(f"  detected {fmt}, W/H={detection['measured_ratio']:.4f}, roll={detection['rotation_degrees']:+.2f} deg, review={detection['needs_review']}")
    else:
        ratio = oriented_ratio(preview, ratio, orientation)
    if corners is None:
        # Explicit custom ratios/orientation retain their established selection semantics.
        x0,x1,y0,y1 = detect_frame(preview, ratio)
        corners = [(x0,y0),(x1,y0),(x1,y1),(x0,y1)]
    if keep_border:
        from film_engine import border_corners
        corners, ratio = border_corners(corners, image.shape[:2], fmt, ratio)
    elif keep_sprockets:
        corners = expand_for_sprockets(corners, image.shape[:2], fmt, sprocket_margins)
        ratio = SPROCKET_RATIO_135 if ratio >= 1 else 1 / SPROCKET_RATIO_135
    result = perspective_crop(image, corners, ratio, padding=padding)
    if not keep_sprockets and not keep_border:
        result = trim_borders(result, ratio, top_trim, bottom_trim)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output_format == 'auto':
        output_format = 'TIFF16' if output.suffix.lower() in {'.tif', '.tiff'} else 'JPEG'
    write_image(output, result, output_format, metadata['source_type'] == 'RAW', source=path)
    print(f"{path.name} -> {output}  ({result.shape[1]}x{result.shape[0]})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Automatically crop camera-copied film frames")
    parser.add_argument("input", type=Path, help="an image file or a folder")
    parser.add_argument("--format", choices=["auto"]+sorted(FORMATS), default="135/6x9", help="film frame format; auto infers from the inner picture")
    parser.add_argument("--ratio", type=float, help="custom width/height ratio; overrides --format")
    parser.add_argument("--orientation", choices=["auto", "landscape", "portrait"], default="auto", help="frame orientation; auto follows input orientation")
    parser.add_argument("--output", type=Path, help="output file for a single input")
    parser.add_argument("--output-dir", type=Path, help="output folder for a folder input")
    parser.add_argument("--output-format", choices=['auto', 'TIFF16', 'JPEG'], default='auto', help="default: TIFF16 for RAW, JPEG for raster input")
    parser.add_argument("--no-auto-rotate", action="store_true", help="disable small-angle film roll correction")
    parser.add_argument("--keep-border", action='store_true', help="retain 135 perforations or expand a 120 frame border")
    parser.add_argument("--corners", nargs=4, type=parse_point, metavar="X,Y", help="four frame corners: TL TR BR BL")
    parser.add_argument("--padding", type=float, default=0.0, help="fraction to trim from each side before ratio crop")
    parser.add_argument("--top-trim", type=float, default=0.01, help="ordinary crop only: top safety trim after ratio crop (default 0.01 = 1%%); 0 disables it")
    parser.add_argument("--bottom-trim", type=float, default=0.01, help="ordinary crop only: bottom safety trim after ratio crop (default 0.01 = 1%%); 0 disables it")
    parser.add_argument("--keep-sprockets", action="store_true", help="135 only: retain the top/bottom perforations and film border")
    parser.add_argument(
        "--sprocket-margin", nargs=4, type=float, metavar=("TOP", "RIGHT", "BOTTOM", "LEFT"),
        help="override sprocket margins as fractions of the picture: top right bottom left (default landscape: 0.235625 0.035 0.235625 0.035)",
    )
    args = parser.parse_args()
    if args.keep_border and args.keep_sprockets:
        parser.error('choose --keep-border or --keep-sprockets')
    from film_io import RAW_EXTENSIONS, SUPPORTED_EXTENSIONS, output_path
    def export_format(path):
        if args.output_format != 'auto': return args.output_format
        return 'TIFF16' if path.suffix.lower() in RAW_EXTENSIONS else 'JPEG'
    if args.padding < 0 or args.padding >= .45:
        parser.error("--padding must be between 0 and 0.45")
    if not 0 <= args.top_trim < .1:
        parser.error("--top-trim must be between 0 and 0.1 (exclusive)")
    if not 0 <= args.bottom_trim < .1:
        parser.error("--bottom-trim must be between 0 and 0.1 (exclusive)")
    if args.format == "auto" and (args.ratio is not None or args.corners is not None or args.orientation != "auto"):
        parser.error("auto format requires automatic ratio, corners and orientation; use a specified format for overrides")
    ratio = args.ratio or FORMATS.get(args.format,1.5)
    if ratio <= 0:
        parser.error("ratio must be positive")
    if args.input.is_file():
        fmt = export_format(args.input)
        output = args.output or output_path(args.input.parent, args.input, fmt, args.format)
        if args.output and args.output_format == 'auto':
            fmt = 'TIFF16' if output.suffix.lower() in {'.tif', '.tiff'} else 'JPEG'
        process_one(args.input, output, ratio, args.corners, args.padding, args.format, args.keep_sprockets, tuple(args.sprocket_margin) if args.sprocket_margin else None, args.orientation, args.top_trim, args.bottom_trim, fmt, args.keep_border, not args.no_auto_rotate)
    elif args.input.is_dir():
        out_dir = args.output_dir or args.input / "cropped"
        files = sorted(p for p in args.input.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS)
        if not files:
            raise SystemExit("no supported image files found")
        for path in files:
            try:
                fmt = export_format(path)
                output = output_path(out_dir, path, fmt, args.format)
                process_one(path, output, ratio, args.corners, args.padding, args.format, args.keep_sprockets, tuple(args.sprocket_margin) if args.sprocket_margin else None, args.orientation, args.top_trim, args.bottom_trim, fmt, args.keep_border)
            except Exception as exc:
                print(f"SKIP {path.name}: {exc}")
    else:
        raise SystemExit(f"input does not exist: {args.input}")


if __name__ == "__main__":
    main()
