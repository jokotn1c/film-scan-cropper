# FilmCrop 1.9

中文 | [English](README.en.md)

自动识别相机翻拍胶片的画面边框，转正并裁切。提供 Windows 界面和 macOS 构建配置，支持批量导入 RAW 与普通JPG。

## macOS 测试版（Apple Silicon）

独立的测试版提供简洁深色界面、中英文界面切换，以及逐张图片的手动矩形裁切。经典版界面和构建仍然保留。

1. 添加图片或文件夹，在左侧选择图片。
2. 在预览图上拖出选区，拖动角点调整；选择“恢复自动”可重新使用自动检测。
3. 选择输出文件夹和 TIFF16 或 JPEG，开始裁切。

手动选区直接裁切按方向校正后的原图；自动转正、画幅比例和边框扩展仅用于自动裁切。测试版遇到同名输出会自动编号，保留已有文件。真实 RAW、实际鼠标拖动及完整批处理仍需进一步验证；应用使用临时签名，尚未经过 Apple 公证。

**下载：** 在[测试版发布页](https://github.com/jokotn1c/film-scan-cropper/releases/tag/v1.9.1-preview.2)的 Assets 中下载 `FilmCrop-Preview-mac-arm64.zip`。该标签指向旧版 main，其自动生成的源码压缩包不包含测试版。测试版源码请见[草稿 PR #2](https://github.com/jokotn1c/film-scan-cropper/pull/2)，可从该分支自行运行或构建：

```shell
python3 -m pip install -r requirements.txt -r requirements-build.txt
python3 film_gui_modern.py
# 构建 Apple Silicon 应用
python3 -m PyInstaller --noconfirm --clean FilmCrop-Preview-mac-arm64.spec
```

更多说明见 [MACOS-PREVIEW.md](MACOS-PREVIEW.md)。

## 版本规则

- 较大的功能性改动或界面改动：第二位加 1，例如 v1.9 → v1.10，第三位归零并省略。
- 单纯的小幅图片处理算法改进：第三位加 1，例如 v1.9 → v1.9.1 → v1.9.2。
- 同次发布同时包含上述改动时，按功能或界面版本递增。仅更新说明不改版本号。
- 应用与构建版本以 `film_version.py` 为准；当前版本为 v1.9.2。

## 经典版使用

1. 将 RAW、JPG或文件夹拖入窗口。
2. 选择输出位置。
3. 选择画幅与导出格式，点击“开始裁切”。

默认自动识别画幅、开启自动转正，导出 16 位 TIFF。可切换 JPEG，或保留 135 齿孔、120 边框。“微调”可调整上下边缘及留边。

画幅预设：135/6x9、6x4.5/半格、6x6、6x7、XPan（6.5x2.4）、中画幅宽幅 135 后背（5.6x2.4）。支持自动识别与手动指定，横竖方向自动判断。


## 从源码运行

```shell
python -m pip install -r requirements.txt
python film_gui.py
```

命令行示例：

```shell
python film_crop.py input.jpg --format auto --output result.jpg
python film_crop.py input.ARW --format auto --keep-border --output result.tif
python film_crop.py input.jpg --format 6.5x2.4 --output xpan.jpg
python film_crop.py input.jpg --format 5.6x2.4 --output panorama.jpg
python film_crop.py input.jpg --format "6x4.5/半格" --output half.jpg
```

## 构建

- Windows：安装构建依赖后运行 build_exe.ps1。
- macOS Apple Silicon：运行 build_macos_arm64.sh，或在 GitHub Actions 手动运行 Build macOS Apple Silicon，从成功运行的 Artifacts 下载产物。

## 经典版图像处理

- RAW 兼容性取决于 LibRaw 支持的相机型号和压缩方式。
- 使用相机白平衡；不读取 Lightroom / ACR 调整。
- 转正根据胶片边框或齿孔判断小角度倾斜；边界不清或明显畸变或歪轴时需检查结果。
- 16 位 TIFF 保存解码后的 RGB；8 位照片转换为 16 位不会增加原有细节。
- 输出添加裁切后缀，保留原始文件；同名裁切结果自动覆盖。
- 新增文件后再次开始，会跳过当前列表中已按相同设置完成的项目；更换输出位置或裁切设置后重新处理。
- 自动模式遇到低亮度、边界不完整的图片会先跳过，整批完成后集中要求指定画幅；开始前手动选择画幅则直接按该比例推算。

## 隐私

照片处理在本机完成，程序没有照片上传或遥测功能。安装依赖及 GitHub Actions 构建需要联网。

处理报告与诊断输出可能含所选文件的路径、文件名及错误详情，分享前请检查。第三方许可随包提供。
