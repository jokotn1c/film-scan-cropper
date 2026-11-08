# FilmCrop macOS Preview / macOS 测试版

This separate Apple Silicon preview keeps the original FilmCrop interface and build unchanged. It introduces a neutral dark interface and a 中文 / English switch.

- Add images or a folder, select an image, and drag over the image to define a rectangular crop. Drag a corner to adjust it; choose **Reset to auto** to use the existing automatic detector again. The selection applies only to the selected image.
- A manual selection uses the original oriented image exactly. Automatic straighten, aspect ratio, and border expansion apply only when no manual selection is set.
- Output is TIFF16 or JPEG. Existing cropped outputs with the same name are overwritten. Processing stays on the local machine.
- The preview is a test build; validate results with your own scans. RAW decoding depends on LibRaw's camera support. The application is ad-hoc signed, not notarized.

在左侧选择图片，在预览上拖出选区，可拖动四角调整；点击“恢复自动”重新使用自动识别。手动选区以原图为准，自动转正、画幅比例及边框扩展只用于自动裁切。输出文件同名时覆盖已有裁切结果。

## Build on Apple Silicon

```sh
python3 -m pip install -r requirements.txt -r requirements-build.txt
python3 -m PyInstaller --noconfirm --clean FilmCrop-Preview-mac-arm64.spec
```

The classic app remains available through `film_gui.py` and `FilmCrop-RAW-mac-arm64.spec`.
