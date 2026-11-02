"""Decode camera RAW / raster files and export sRGB JPEG or 16-bit TIFF."""
from pathlib import Path
import os
import shutil
import uuid
import cv2
import numpy as np
from film_paths import output_path, require_output_available

RAW_EXTENSIONS = {'.arw', '.srf', '.sr2', '.cr2', '.cr3', '.crw', '.nef', '.nrw',
                  '.raf', '.orf', '.ori', '.rw2', '.raw', '.rwl', '.dng', '.pef',
                  '.ptx', '.srw', '.3fr', '.fff', '.iiq', '.kdc', '.dcr', '.mos',
                  '.mrw', '.mef', '.erf', '.x3f'}
RASTER_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp'}
SUPPORTED_EXTENSIONS = RAW_EXTENSIONS | RASTER_EXTENSIONS


def read_image(path):
    """Return oriented BGR data and source information. RAW is decoded at 16 bit."""
    path = Path(path)
    if path.suffix.lower() in RAW_EXTENSIONS:
        import rawpy
        try:
            with rawpy.imread(str(path)) as raw:
                rgb = raw.postprocess(use_camera_wb=True, no_auto_bright=True,
                                      output_bps=16, output_color=rawpy.ColorSpace.sRGB,
                                      gamma=(2.222, 4.5))
            return np.ascontiguousarray(rgb[:, :, ::-1]), {
                'source_type': 'RAW', 'source_bit_depth': 16,
                'rendering': 'camera WB; sRGB; gamma 2.222/4.5; no auto bright',
            }
        except Exception as exc:
            raise RuntimeError('RAW 解码失败：' + str(exc)) from exc
    if path.suffix.lower() not in RASTER_EXTENSIONS:
        raise ValueError('不支持此扩展名：' + path.suffix)
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise RuntimeError('无法读取图片：' + str(path))
    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    elif image.shape[2] == 4:
        image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    # IMREAD_UNCHANGED preserves 16-bit data but does not apply EXIF orientation.
    from PIL import Image
    with Image.open(path) as source:
        orientation = source.getexif().get(274, 1)
    if orientation == 2: image = np.fliplr(image)
    elif orientation == 3: image = np.rot90(image, 2)
    elif orientation == 4: image = np.flipud(image)
    elif orientation == 5: image = image.transpose(1, 0, 2)
    elif orientation == 6: image = np.rot90(image, 3)
    elif orientation == 7: image = np.flip(image.transpose(1, 0, 2), axis=(0, 1))
    elif orientation == 8: image = np.rot90(image)
    return np.ascontiguousarray(image), {
        'source_type': 'raster', 'source_bit_depth': image.dtype.itemsize * 8,
        'rendering': 'source pixels; no color conversion',
    }


def detection_image(image):
    if image.dtype == np.uint16:
        return (image // 257).astype(np.uint8)
    if image.dtype != np.uint8:
        raise ValueError('仅支持 8 位或 16 位整数图像')
    return image


def _path_matches_stat(path, expected):
    try:
        return os.path.samestat(expected, Path(path).stat())
    except OSError:
        return False


def _copy_exclusive(temp, path):
    """Copy an encoded temp file into a newly reserved destination."""
    descriptor = None
    created_stat = None
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
        created_stat = os.fstat(descriptor)
        with os.fdopen(descriptor, 'wb') as destination:
            descriptor = None
            with Path(temp).open('rb') as source:
                shutil.copyfileobj(source, destination)
        if not _path_matches_stat(path, created_stat):
            raise FileExistsError(f'输出路径在写入期间发生变化：{path}')
        Path(temp).unlink()
    except Exception:
        if descriptor is not None:
            os.close(descriptor)
        if created_stat is not None and _path_matches_stat(path, created_stat):
            Path(path).unlink()
        raise


def _commit_without_overwrite(temp, path):
    """Publish a complete file without ever replacing an existing path."""
    try:
        os.link(temp, path)
    except FileExistsError:
        raise
    except OSError:
        _copy_exclusive(temp, path)
    else:
        Path(temp).unlink()


def write_image(path, image, output_format='TIFF16', is_raw=False, *, source=None):
    """Encode completely, then commit only to an unoccupied destination."""
    path = Path(path)
    if source is not None:
        source = Path(source)
        if (path.resolve() == source.resolve()
                or (path.exists() and source.exists() and path.samefile(source))):
            raise ValueError('输出文件不能与原始文件相同')
    require_output_available(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name('.' + path.stem + '-' + uuid.uuid4().hex + '.tmp')
    try:
        if output_format == 'TIFF16':
            import tifffile
            pixels = image if image.dtype == np.uint16 else image.astype(np.uint16) * 257
            extra = []
            if is_raw:
                from PIL import ImageCms
                icc = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
                extra = [(34675, 'B', len(icc), icc, False)]
            tifffile.imwrite(temp, np.ascontiguousarray(pixels[:, :, ::-1]),
                             photometric='rgb', compression=None, metadata=None,
                             extratags=extra)
        elif output_format == 'JPEG':
            pixels = detection_image(image)
            if is_raw:
                from PIL import Image, ImageCms
                icc = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
                Image.fromarray(pixels[:, :, ::-1]).save(temp, format='JPEG', quality=98,
                                                       subsampling=0, icc_profile=icc)
            else:
                ok, encoded = cv2.imencode('.jpg', pixels, [cv2.IMWRITE_JPEG_QUALITY, 98])
                if not ok: raise RuntimeError('JPEG 编码失败')
                encoded.tofile(temp)
        else:
            raise ValueError('未知输出格式：' + output_format)
        require_output_available(path)
        _commit_without_overwrite(temp, path)
    finally:
        if temp.exists(): temp.unlink()
