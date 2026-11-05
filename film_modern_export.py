"""Safe export for the modern interface, using the existing processing engine."""
from pathlib import Path
import os
import uuid
from film_io import read_image, write_image, output_path
from film_engine import locate, crop_pixels
from film_manual import crop_manual


def export_one(source, folder, options, box=None):
    source, folder = Path(source), Path(folder)
    image, metadata = read_image(source)
    if box is None:
        detection = locate(image, options.format, options.auto_rotate)
        result = crop_pixels(image, detection, options)
        mode = 'auto'
        suffix = 'border' if options.keep_border else 'crop'
    else:
        result = crop_manual(image, box)
        detection = {'manual_box': list(box)}
        mode, suffix = 'manual', 'crop'
    target = output_path(folder, source, options.output_format, suffix)
    temporary = folder / ('.filmcrop-' + uuid.uuid4().hex + target.suffix)
    try:
        write_image(temporary, result, options.output_format,
                    metadata['source_type'] == 'RAW', source=source)
        for n in range(1, 100000):
            candidate = target if n == 1 else target.with_name(f'{target.stem}_{n}{target.suffix}')
            try:
                os.link(temporary, candidate)
                break
            except FileExistsError:
                continue
        else:
            raise FileExistsError('Could not allocate an output filename')
    finally:
        temporary.unlink(missing_ok=True)
    return {'source': str(source), 'output': str(candidate), 'mode': mode,
            'output_width': result.shape[1], 'output_height': result.shape[0],
            **metadata, **detection}
