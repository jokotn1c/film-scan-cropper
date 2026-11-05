# FilmCrop 1.9

[中文](README.md) | English

FilmCrop detects the frame in camera-digitized film, straightens it, and crops it. It provides a Windows interface and macOS build configuration, with batch import for RAW and JPEG images.

## macOS preview (Apple Silicon)

This separate preview offers a simple dark interface, a Chinese/English language switch, and a manual rectangular crop for each image. The classic interface and build remain available.

1. Add images or a folder and select an image on the left.
2. Drag over the preview to draw a selection, then drag its corners to adjust it. Choose **Reset to auto** to return to automatic detection.
3. Choose an output folder and TIFF16 or JPEG, then start cropping.

Manual selections crop the oriented original image directly; automatic straightening, aspect ratio, and border expansion apply only to automatic crops. The preview numbers output filenames on collisions to preserve existing files. Real RAW samples, physical mouse dragging, and full batch workflows need further verification. The app is ad-hoc signed and has not been notarized by Apple.

**Download:** Download `FilmCrop-Preview-mac-arm64.zip` from Assets on the [preview release](https://github.com/jokotn1c/film-scan-cropper/releases/tag/v1.9.1-preview.2). That tag points to the older main branch; its generated source archives do not contain the preview. The preview source is in [draft PR #2](https://github.com/jokotn1c/film-scan-cropper/pull/2). Run or build it from that branch:

```shell
python3 -m pip install -r requirements.txt -r requirements-build.txt
python3 film_gui_modern.py
# Build the Apple Silicon app
python3 -m PyInstaller --noconfirm --clean FilmCrop-Preview-mac-arm64.spec
```

See [MACOS-PREVIEW.md](MACOS-PREVIEW.md) for more details.

## Using the classic version

1. Drag RAW or JPEG files, or a folder, into the window.
2. Choose an output location.
3. Choose the film format and export format, then start cropping.

By default, FilmCrop detects the format, straightens the image, and exports 16-bit TIFF. You can select JPEG or keep 135 sprocket holes or 120 borders. Fine adjustments control the top and bottom edges and margins.

Format presets include 135/6x9, 6x4.5/half-frame, 6x6, 6x7, XPan (6.5x2.4), and medium-format panoramic 135 backs (5.6x2.4). Formats can be detected automatically or selected manually; portrait or landscape orientation is detected automatically.

## Run from source

```shell
python -m pip install -r requirements.txt
python film_gui.py
```

Command-line examples:

```shell
python film_crop.py input.jpg --format auto --output result.jpg
python film_crop.py input.ARW --format auto --keep-border --output result.tif
python film_crop.py input.jpg --format 6.5x2.4 --output xpan.jpg
python film_crop.py input.jpg --format 5.6x2.4 --output panorama.jpg
python film_crop.py input.jpg --format "6x4.5/半格" --output half.jpg
```

## Build

- Windows: install the build dependencies and run `build_exe.ps1`.
- macOS Apple Silicon: run `build_macos_arm64.sh`, or run **Build macOS Apple Silicon** manually in GitHub Actions and download the artifact from a successful run.

## Classic image processing

- RAW compatibility depends on the camera model and compression formats supported by LibRaw.
- Camera white balance is used; Lightroom / ACR adjustments are not read.
- Straightening detects small angles using film borders or sprocket holes. Check results when boundaries are unclear, distortion is significant, or the camera is misaligned.
- 16-bit TIFF stores decoded RGB data; converting an 8-bit image to 16-bit does not add detail.
- Output files get a crop suffix and leave the originals untouched; existing cropped outputs with the same name are overwritten.
- When processing is started again after adding files, items in the current list already completed with the same settings are skipped. Changing the output location or crop settings processes them again.
- In automatic mode, dark images or images with incomplete boundaries are initially skipped; after the batch finishes, the user is asked to specify a format. Selecting a format before starting estimates the crop using that ratio.

## Privacy

Photo processing is local; the application does not upload photos or use telemetry. Installing dependencies and building with GitHub Actions require network access.

Processing reports and diagnostic output may contain selected file paths, filenames, and error details. Review them before sharing. Third-party licenses are included with the package.
