# FilmCrop

中文 | [English](README.en.md)

FilmCrop 用于裁切相机翻拍的胶片照片，可以自动识别画面边界和画幅，并完成小角度转正与批量导出。

## 主要功能

- 支持 RAW、JPEG、PNG、TIFF、BMP 输入。
- 自动识别 135/6x9、6x4.5/半格、6x6、6x7、XPan 6.5x2.4 和 5.6x2.4 宽幅。
- 自动转正，也可指定画幅、方向或四角坐标。
- 可保留 135 齿孔或 120 边框，并调整收边和留边。
- 导出 16 位 TIFF 或 JPEG，支持批量处理。
- 提供经典界面，以及支持手动框选的中英文界面。

## 界面使用

安装依赖并启动经典界面：

```shell
python -m pip install -r requirements.txt
python film_gui.py
```

1. 拖入图片或文件夹，也可以点击“添加文件”或“添加文件夹”。
2. 选择输出文件夹。
3. 选择画幅和导出格式，按需开启“自动转正”或“保留齿孔 / 边框”。
4. 点击“开始裁切”。处理完成后，选中文件可预览结果，双击可打开图片。

“微调”中可以设置上下收边、120 边框扩展和 135 留边。每批处理会生成 CSV 和 JSON 报告。

手动裁切界面：

```shell
python film_gui_modern.py
```

添加图片后，在预览图上拖出选区或拖动角点调整。点击“恢复自动”可重新使用自动检测，然后选择输出位置并开始裁切。

## 命令行使用

裁切单张图片：

```shell
python film_crop.py input.jpg --format auto --output result.jpg
```

处理 RAW 并保留齿孔或边框：

```shell
python film_crop.py input.ARW --format auto --keep-border --output result.tif
```

指定画幅：

```shell
python film_crop.py input.jpg --format 6x6 --output result.jpg
python film_crop.py input.jpg --format 6.5x2.4 --output xpan.jpg
```

批量处理文件夹：

```shell
python film_crop.py scans --format auto --output-dir cropped
```

也可以手动指定四角坐标：

```shell
python film_crop.py input.jpg --format 135/6x9 --corners 289,242 1570,242 1570,1097 289,1097 --output result.jpg
```

更多参数可通过 `python film_crop.py --help` 查看。

## 项目结构

- `film_*.py`：裁切引擎、命令行和桌面界面。
- `tests/`：单元测试。
- `tools/`：诊断、界面检查和 macOS 启动检查工具。
- `docs/`：构建、预览版和性能说明。

## 开发检查

安装 `requirements.txt` 中的依赖后，在仓库根目录运行：

```shell
python -m unittest discover -s tests
```

macOS Apple Silicon 的构建与检查方法见 [docs/MACOS-ARM.md](docs/MACOS-ARM.md)。
