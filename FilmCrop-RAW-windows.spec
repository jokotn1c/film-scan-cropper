# Build from the outputs directory; no network or external compressor needed.
from pathlib import Path
import tkinterdnd2
import runpy

root = Path(SPECPATH)
version = runpy.run_path(str(root / 'film_version.py'))['VERSION']
tkdnd = Path(tkinterdnd2.__file__).parent / 'tkdnd' / 'win-x64'
a = Analysis([str(root / 'film_gui.py')], pathex=[str(root)],
    datas=[(str(tkdnd), 'tkinterdnd2/tkdnd/win-x64'), (str(root / 'assets'), 'assets')],
    binaries=[], hiddenimports=['rawpy','PIL.ImageCms','tifffile'],
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=['PIL.AvifImagePlugin','PIL._avif','PIL.WebPImagePlugin','PIL._webp',
              'PIL.HeifImagePlugin','PIL.Jpeg2KImagePlugin','PIL.PdfImagePlugin',
              'PIL.PdfParser','PIL.ImageQt','PIL.ImageShow','PIL.ImageGrab',
              'matplotlib','scipy','pandas','IPython','pytest'],
    noarchive=False, optimize=1)
# OpenCV is used only for still images. Its FFmpeg plug-in is loaded on demand
# by video I/O, which this application never calls.
a.binaries = [entry for entry in a.binaries if 'opencv_videoio_ffmpeg' not in entry[0].lower()]
pyz = PYZ(a.pure)
exe = EXE(pyz,a.scripts,a.binaries,a.datas,[],name='FilmCrop-RAW-' + version,
    icon=str(root / 'assets' / 'filmcrop.ico'),
    debug=False,bootloader_ignore_signals=False,strip=False,upx=False,
    console=False,disable_windowed_traceback=False)
