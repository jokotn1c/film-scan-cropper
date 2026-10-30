from pathlib import Path
import tkinterdnd2
import runpy
root = Path(SPECPATH)
version = runpy.run_path(str(root / 'film_version.py'))['VERSION']
tkdnd = Path(tkinterdnd2.__file__).parent / "tkdnd" / "osx-arm64"
a = Analysis([str(root / "film_gui.py")], pathex=[str(root)], datas=[(str(tkdnd), "tkinterdnd2/tkdnd/osx-arm64"), (str(root / "assets"), "assets")], binaries=[], hiddenimports=["rawpy","PIL.ImageCms","tifffile"], excludes=["PIL.AvifImagePlugin","PIL._avif","PIL.WebPImagePlugin","PIL._webp","PIL.HeifImagePlugin","PIL.Jpeg2KImagePlugin","PIL.PdfImagePlugin","PIL.ImageQt","PIL.ImageShow","PIL.ImageGrab","matplotlib","scipy","pandas","IPython","pytest"], noarchive=False, optimize=1)
a.binaries = [entry for entry in a.binaries if "opencv_videoio_ffmpeg" not in entry[0].lower()]
pyz = PYZ(a.pure)
# A macOS .app is already a directory. Keep libraries inside the bundle so
# launching it does not unpack a onefile archive or leave a launcher parent.
exe = EXE(pyz,a.scripts,[],exclude_binaries=True,name="FilmCrop-RAW",
          console=False,disable_windowed_traceback=False,target_arch="arm64")
coll = COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name="FilmCrop-RAW")
app = BUNDLE(coll,name="FilmCrop-RAW.app",version=version,bundle_identifier="com.jokotn1c.filmscancropper", icon=str(root / "assets" / "filmcrop.icns"),info_plist={'CFBundleShortVersionString': version, 'CFBundleVersion': version, 'CFBundleDisplayName': 'FilmCrop', 'NSHighResolutionCapable': True})
