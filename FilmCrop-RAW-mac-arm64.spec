from pathlib import Path
import tkinterdnd2
root = Path(SPECPATH)
tkdnd = Path(tkinterdnd2.__file__).parent / "tkdnd" / "osx-arm64"
a = Analysis([str(root / "film_gui.py")], pathex=[str(root)], datas=[(str(tkdnd), "tkinterdnd2/tkdnd/osx-arm64")], binaries=[], hiddenimports=["rawpy","PIL.ImageCms","tifffile"], excludes=["PIL.AvifImagePlugin","PIL._avif","PIL.WebPImagePlugin","PIL._webp","PIL.HeifImagePlugin","PIL.Jpeg2KImagePlugin","PIL.PdfImagePlugin","PIL.ImageQt","PIL.ImageShow","PIL.ImageGrab","matplotlib","scipy","pandas","IPython","pytest"], noarchive=False, optimize=1)
a.binaries = [entry for entry in a.binaries if "opencv_videoio_ffmpeg" not in entry[0].lower()]
pyz = PYZ(a.pure)
exe = EXE(pyz,a.scripts,a.binaries,a.datas,[],name="FilmCrop-RAW",console=False,disable_windowed_traceback=False)
app = BUNDLE(exe,name="FilmCrop-RAW.app",bundle_identifier="com.jokotn1c.filmscancropper")
