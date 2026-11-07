"""One decode, selection, crop and export pipeline for all application entries."""
from pathlib import Path
from time import perf_counter
import math
import numpy as np
import film_crop as geometry
from film_engine import Options, locate, crop_pixels
from film_io import (RAW_EXTENSIONS, read_image, detection_image, output_path,
                     write_output, validate_output_path)
from film_manual import crop_manual


def _validate_options(options):
    if options.format not in geometry.FORMATS and options.format != 'auto':
        raise ValueError('未知画幅：' + options.format)
    if options.output_format not in {'auto', 'JPEG', 'TIFF16'}:
        raise ValueError('未知输出格式：' + options.output_format)
    if options.collision_policy not in {None, 'overwrite', 'number', 'skip', 'error'}:
        raise ValueError('未知同名文件策略：' + str(options.collision_policy))
    if options.orientation not in {'auto', 'landscape', 'portrait'}:
        raise ValueError('未知画面方向：' + options.orientation)
    if options.ratio is not None and (not math.isfinite(options.ratio) or options.ratio <= 0):
        raise ValueError('ratio must be positive and finite')
    if not 0 <= options.padding < .45:
        raise ValueError('padding must be between 0 and 0.45')
    if not (0 <= options.top_trim < .1 and 0 <= options.bottom_trim < .1):
        raise ValueError('top and bottom trim must be between 0 and 0.1 (exclusive)')
    if options.manual_box is not None and options.corners is not None:
        raise ValueError('choose a manual box or four corners')
    if options.corners is not None:
        points = np.asarray(options.corners, dtype=float)
        if points.shape != (4, 2) or not np.isfinite(points).all():
            raise ValueError('four finite corners are required')


def _selection(image, options):
    """Resolve the legacy CLI overrides and regular automatic requests."""
    default_ratio = geometry.FORMATS.get(options.format)
    automatic = (options.corners is None and
                 (options.format == 'auto' or
                  (options.orientation == 'auto' and
                   (options.ratio is None or options.ratio == default_ratio))))
    if automatic:
        return locate(image, options.format, options.auto_rotate)
    preview = detection_image(image)
    ratio = geometry.oriented_ratio(preview, options.ratio or default_ratio or 1.5,
                                    options.orientation)
    corners = options.corners
    if corners is None:
        x0, x1, y0, y1 = geometry.detect_frame(preview, ratio)
        corners = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
    points = np.asarray(corners, dtype=float)
    return {
        'format': options.format, 'ratio': ratio, 'measured_ratio': ratio,
        'corners': points.tolist(),
        'bounds': [float(points[:, 0].min()), float(points[:, 0].max()),
                   float(points[:, 1].min()), float(points[:, 1].max())],
        'needs_review': False, 'review_reasons': [], 'rotation_degrees': 0.,
        'rotation_method': 'manual_corners' if options.corners is not None else 'ratio_override',
    }


def process_image(source, folder=None, options=Options(), *, output=None):
    """Process one source; manual boxes bypass detection and border expansion.

    collision_policy: overwrite (pipeline/CLI/classic default), number (modern
    entry default), skip (no decode if present), or error. Four explicit corners
    and custom ratios retain the original CLI geometry and trimming behavior.
    """
    start = perf_counter()
    _validate_options(options)
    source = Path(source)
    mode = 'manual' if options.manual_box is not None else 'auto'
    fmt = options.output_format
    if fmt == 'auto':
        if output is not None:
            fmt = 'TIFF16' if Path(output).suffix.lower() in {'.tif', '.tiff'} else 'JPEG'
        else:
            fmt = 'TIFF16' if source.suffix.lower() in RAW_EXTENSIONS else 'JPEG'
    if output is None:
        if folder is None:
            raise ValueError('output file or folder is required')
        suffix = 'border' if options.keep_border and mode == 'auto' else 'crop'
        output = output_path(folder, source, fmt, suffix)
    output = Path(output)
    validate_output_path(output, source)
    policy = options.collision_policy or 'overwrite'
    base = {'source': str(source), 'output': str(output), 'mode': mode,
            'collision_policy': policy, 'output_format': fmt}
    if output.exists():
        if policy == 'skip':
            return {**base, 'skipped': True, 'timings': {'total': perf_counter() - start}}
        if policy == 'error':
            raise FileExistsError(output)

    before = perf_counter()
    image, metadata = read_image(source)
    read_time = perf_counter() - before
    before = perf_counter()
    detection = {} if mode == 'manual' else _selection(image, options)
    detect_time = perf_counter() - before
    before = perf_counter()
    if mode == 'manual':
        result = crop_manual(image, options.manual_box)
        detection = {'manual_box': list(options.manual_box)}
    else:
        result = crop_pixels(image, detection, options)
    crop_time = perf_counter() - before
    before = perf_counter()
    actual, skipped = write_output(output, result, fmt, metadata['source_type'] == 'RAW',
                                    source=source, collision_policy=policy)
    write_time = perf_counter() - before
    timings = {'read': read_time, 'detect': detect_time, 'crop': crop_time,
               'write': write_time, 'total': perf_counter() - start}
    if skipped:
        return {**base, 'output': str(actual), 'skipped': True, 'timings': timings}

    height, width = image.shape[:2]
    oh, ow = result.shape[:2]
    bordered = mode == 'auto' and (options.keep_border or options.keep_sprockets)
    record = {
        **base, 'output': str(actual), **metadata, **detection,
        'source_width': width, 'source_height': height,
        'output_width': ow, 'output_height': oh, 'output_ratio': ow / oh,
        'keep_border': bool(mode == 'auto' and options.keep_border),
        'keep_sprockets': bool(mode == 'auto' and options.keep_sprockets),
        'sprocket_side': options.sprocket_side,
        'top_trim': options.top_trim if mode == 'auto' and not bordered else 0.,
        'bottom_trim': options.bottom_trim if mode == 'auto' and not bordered else 0.,
        'skipped': False, 'timings': timings,
    }
    if record['keep_border']:
        record['needs_review'] = True
        record['review_reasons'] = list(record.get('review_reasons', [])) + [
            '边框为按比例扩展估算；原文件缺少的齿孔或边框无法恢复']
    return record
