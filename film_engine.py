"""Shared processing pipeline for the GUI and RAW-capable command line."""
from dataclasses import dataclass
from pathlib import Path
import math
import cv2
import numpy as np
import film_crop as fc
from film_detect import detect_auto, analyze
from film_io import read_image, detection_image, write_image, output_path


@dataclass(frozen=True)
class Options:
    format: str = 'auto'
    output_format: str = 'TIFF16'
    keep_border: bool = False
    top_trim: float = .01
    bottom_trim: float = .01
    border_margin: float = .025
    sprocket_side: float = .035
    auto_rotate: bool = True


def _locate(image, fmt):
    preview = detection_image(image)
    if fmt == 'auto':
        detection = detect_auto(preview)
        translations = {
            'boundary estimated from sprocket spacing': '按齿孔间距估算边界',
            'enclosing frame selected over scene edge': '画面内框与场景直线存在歧义',
            'one or more frame edges have low contrast': '部分边界对比度低',
            'measured ratio differs from preset by over 2.5%': '检测比例偏离预设超过 2.5%',
        }
        detection['review_reasons'] = [translations.get(s, s.replace('competing format: ', '候选画幅接近：')) for s in detection['review_reasons']]
        return detection
    candidates, scale, negative = analyze(preview)
    selected = next((q for q in candidates if q['format'] == fmt), None)
    if selected:
        x, y, w, h = selected['box']
        ratio = max(fc.FORMATS[fmt], 1 / fc.FORMATS[fmt])
        ratio = ratio if w >= h else 1 / ratio
        return {'format': fmt, 'ratio': ratio, 'measured_ratio': w / h,
                'bounds': [x / scale, (x+w-1) / scale, y / scale, (y+h-1) / scale],
                'negative_hint': bool(negative), 'needs_review': True,
                'review_reasons': ['用户指定画幅，请检查边界']}
    # The sensor canvas can be square, or horizontal around a portrait frame.
    # Evaluate both inner-frame orientations rather than inheriting the canvas.
    long_ratio = max(fc.FORMATS[fmt], 1 / fc.FORMATS[fmt])
    small, scale = fc.resize_for_detection(preview)
    xp, yp = fc.edge_profiles(small)
    choices = []
    for ratio in sorted({long_ratio, 1 / long_ratio}):
        try:
            bounds = fc.detect_frame(preview, ratio)
        except RuntimeError:
            continue
        x0,x1,y0,y1 = bounds
        ix = np.clip(np.rint(np.array([x0,x1])*scale).astype(int),0,len(xp)-1)
        iy = np.clip(np.rint(np.array([y0,y1])*scale).astype(int),0,len(yp)-1)
        strengths = np.r_[xp[ix]/max(float(xp.max()),1), yp[iy]/max(float(yp.max()),1)]
        quality = float(strengths.min() + strengths.mean())
        choices.append((quality, ratio, bounds))
    if not choices:
        raise RuntimeError('未能定位指定画幅的边界')
    _, ratio, bounds = max(choices, key=lambda item:item[0])
    x0, x1, y0, y1 = bounds
    return {'format': fmt, 'ratio': ratio, 'measured_ratio': (x1-x0)/(y1-y0),
            'bounds': list(bounds), 'needs_review': True,
            'review_reasons': ['画幅候选不足，使用固定比例估算'],
            'negative_hint': bool(negative)}


def locate(image, fmt, auto_rotate=True):
    from film_rotation import estimate_rotation, deskew_preview
    preview = detection_image(image)
    rotation = estimate_rotation(preview) if auto_rotate else dict(angle=0., method='disabled', confident=False)
    angle = rotation['angle'] if rotation['confident'] and abs(rotation['angle']) >= .25 else 0.
    if angle:
        small, scale = fc.resize_for_detection(preview, 1600)
        straight, inverse = deskew_preview(small, angle)
        detection = _locate(straight, fmt)
        x0,x1,y0,y1 = detection['bounds']
        rect = np.float32([[[x0,y0],[x1,y0],[x1,y1],[x0,y1]]])
        quad = cv2.transform(rect, inverse)[0] / scale
        detection['corners'] = quad.tolist()
        detection['bounds'] = [float(quad[:,0].min()),float(quad[:,0].max()),float(quad[:,1].min()),float(quad[:,1].max())]
    else:
        detection = _locate(preview, fmt)
    detection.update(rotation_degrees=float(angle), rotation_estimated_degrees=float(rotation['angle']),
                     rotation_method=rotation['method'], rotation_confident=rotation['confident'])
    if auto_rotate and not rotation['confident']:
        detection['needs_review'] = True
        detection['review_reasons'].append('未找到可靠的小角度旋转依据，未自动转正')
    return detection


def border_corners(corners, shape, fmt, ratio, margin=.025, sprocket_side=.035):
    if fmt == '135':
        # Perforations lie along the long sides of the 36x24 picture.
        margins = fc.sprocket_margins(ratio, sprocket_side)
        expanded = fc.expand_for_sprockets(corners, shape, '135', margins, clip=False)
        return fit_inside(np.asarray(expanded), np.mean(corners,axis=0), shape), (
            fc.SPROCKET_RATIO_135 if ratio >= 1 else 1 / fc.SPROCKET_RATIO_135)
    # Expand in the frame coordinate system, retaining the corrected roll.
    points = fc.order_corners(corners)
    tl,tr,br,bl = points
    expanded = np.array([tl-margin*(tr-tl)-margin*(bl-tl),
                         tr+margin*(tr-tl)-margin*(br-tr),
                         br+margin*(br-bl)+margin*(br-tr),
                         bl-margin*(br-bl)+margin*(bl-tl)], np.float32)
    return fit_inside(expanded, points.mean(axis=0), shape), None


def fit_inside(points, center, shape):
    # Uniformly reduce an expanded quad when the source omits part of the border.
    # Independent coordinate clipping would shear a tilted picture.
    h,w = shape; factor = 1.
    for p in points:
        for axis,limit in ((0,w-1),(1,h-1)):
            delta = p[axis]-center[axis]
            if p[axis]<0 and delta<0: factor=min(factor,-center[axis]/delta)
            if p[axis]>limit and delta>0: factor=min(factor,(limit-center[axis])/delta)
    return (center+(points-center)*max(0.,factor)).tolist()


def crop_pixels(image, detection, options):
    x0, x1, y0, y1 = detection['bounds']
    corners = detection.get('corners', [(x0,y0),(x1,y0),(x1,y1),(x0,y1)])
    ratio = detection['ratio']
    if options.keep_border:
        corners, ratio = border_corners(corners, image.shape[:2],
                                       detection['format'], ratio, options.border_margin, options.sprocket_side)
    result = fc.perspective_crop(image, corners, ratio)
    if not options.keep_border:
        result = fc.trim_borders(result, ratio, options.top_trim, options.bottom_trim)
    return result


def process_file(source, folder, options=Options()):
    source = Path(source)
    image, metadata = read_image(source)
    detection = locate(image, options.format, options.auto_rotate)
    result = crop_pixels(image, detection, options)
    suffix = 'border' if options.keep_border else 'crop'
    output = output_path(folder, source, options.output_format, suffix)
    write_image(output, result, options.output_format, metadata['source_type'] == 'RAW', source=source)
    h, w = image.shape[:2]; oh, ow = result.shape[:2]
    record = {'source': str(source), 'output': str(output), **metadata, **detection,
              'source_width': w, 'source_height': h, 'output_width': ow,
              'output_height': oh, 'output_ratio': ow/oh,
              'output_format': options.output_format, 'keep_border': options.keep_border,
              'sprocket_side': options.sprocket_side,
              'top_trim': 0 if options.keep_border else options.top_trim,
              'bottom_trim': 0 if options.keep_border else options.bottom_trim}
    if options.keep_border:
        record['needs_review'] = True
        record['review_reasons'] = list(record['review_reasons']) + [
            '边框为按比例扩展估算；原文件缺少的齿孔或边框无法恢复']
    return record
