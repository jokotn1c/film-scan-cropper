"""Shared geometry and localized labels for the modern desktop UI."""
import math
import numpy as np

TEXT = {
 'zh': {'reopen_formats':'指定画幅', 'needs_format':'待指定画幅', 'format_prompt':'以下图片边界不清晰，请选择画幅后重试。鼠标移到文件名上可预览原图。', 'choose_format':'请选择画幅', 'retry_format':'按所选画幅重试', 'later':'稍后处理', 'files':'文件', 'add':'添加文件', 'folder':'添加文件夹', 'remove':'移除', 'clear':'清空', 'drop':'拖入照片或文件夹', 'crop_settings':'裁切设置', 'format':'画幅', 'auto':'自动识别', 'rotate':'自动转正', 'border':'保留齿孔 / 边框', 'export_settings':'导出设置', 'export':'导出格式', 'location':'输出位置', 'choose':'选择…', 'start':'开始裁切', 'stop':'停止', 'open':'打开输出', 'reset':'恢复自动', 'manual':'手动选区', 'draw':'拖动角点或在图片上拖出选区', 'select':'选择图片以预览', 'pending':'待处理', 'processing':'处理中', 'done':'完成', 'failed':'失败', 'manual_state':'手动裁切', 'language':'语言', 'output_required':'请选择输出文件夹', 'select_required':'请先添加图片', 'error':'错误', 'no_image':'无法加载预览', 'stopping':'将在当前图片处理完成后停止', 'summary':'完成 {ok}，失败 {failed}，未处理 {remaining}', 'loading':'正在读取预览…', 'auto_short':'自动', 'file_types':'图片', 'current':'当前图片', 'previous':'上一张', 'next':'下一张', 'busy':'正在处理，请稍候', 'manual_note':'手动选区以原图为准；自动转正与边框扩展仅用于自动裁切。'},
 'en': {'reopen_formats':'Choose formats', 'needs_format':'Choose format', 'format_prompt':'Choose a format. Hover over a filename to preview the original.', 'choose_format':'Select format', 'retry_format':'Retry selected', 'later':'Later', 'files':'Files', 'add':'Add files', 'folder':'Add folder', 'remove':'Remove', 'clear':'Clear', 'drop':'Drop photos or a folder', 'crop_settings':'Crop settings', 'format':'Format', 'auto':'Auto detect', 'rotate':'Auto straighten', 'border':'Keep sprockets / border', 'export_settings':'Export settings', 'export':'Export format', 'location':'Output folder', 'choose':'Choose…', 'start':'Start cropping', 'stop':'Stop', 'open':'Open output', 'reset':'Reset to auto', 'manual':'Manual crop', 'draw':'Drag a corner or draw a selection on the image', 'select':'Select an image to preview', 'pending':'Pending', 'processing':'Processing', 'done':'Done', 'failed':'Failed', 'manual_state':'Manual crop', 'language':'Language', 'output_required':'Choose an output folder', 'select_required':'Add images first', 'error':'Error', 'no_image':'Could not load preview', 'stopping':'Stopping after the current image', 'summary':'Done {ok}, failed {failed}, remaining {remaining}', 'loading':'Loading preview…', 'auto_short':'Auto', 'file_types':'Images', 'current':'Current image', 'previous':'Previous', 'next':'Next', 'busy':'Processing; please wait', 'manual_note':'Manual selection uses the original image; auto straighten and border expansion apply to automatic crops.'}
}

def translate(language):
    return TEXT[language]


def detected_outline(record):
    """Map a successful automatic detection back onto its source preview."""
    if record.get('mode') != 'auto' or record.get('error') or record.get('skipped'):
        return None
    width, height = record.get('source_width', 0), record.get('source_height', 0)
    if not width or not height or 'bounds' not in record:
        return None
    x0, x1, y0, y1 = record['bounds']
    corners = record.get('corners', [(x0,y0),(x1,y0),(x1,y1),(x0,y1)])
    points = np.asarray(corners, dtype=float) / [width, height]
    if points.shape != (4, 2) or not np.isfinite(points).all():
        return None
    return np.clip(points, 0, 1).tolist()

def normalize_box(a, b):
    values = [float(a[0]), float(a[1]), float(b[0]), float(b[1])]
    if not all(math.isfinite(v) for v in values):
        raise ValueError('Invalid crop coordinates')
    x0, x1 = sorted((max(0., min(1., values[0])), max(0., min(1., values[2]))))
    y0, y1 = sorted((max(0., min(1., values[1])), max(0., min(1., values[3]))))
    if x1-x0 < .005 or y1-y0 < .005:
        raise ValueError('Selection is too small')
    return x0, y0, x1, y1

def crop_manual(image, box):
    x0, y0, x1, y1 = normalize_box(box[:2], box[2:])
    h, w = image.shape[:2]
    left, top = int(round(x0*w)), int(round(y0*h))
    right, bottom = int(round(x1*w)), int(round(y1*h))
    if right-left < 2 or bottom-top < 2:
        raise ValueError('Selection is too small')
    return np.ascontiguousarray(image[top:bottom, left:right])
