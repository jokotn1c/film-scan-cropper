# 胶卷翻拍画面自动裁切

新增 Windows 64 位便携界面版 `FilmCrop-RAW-1.1.exe`，默认 16 位 TIFF。拖入 RAW / 照片，选择输出文件夹，再点击开始；可切换普通裁切与保留135齿孔/120边框。详细操作和解码限制见 `使用说明.txt`。支持范围由 LibRaw 决定，本次已实测 Sony ARW。

命令行 RAW 示例：

```powershell
python film_crop.py "F:\datatemp\004" --format auto --output-format TIFF16 --output-dir "F:\datatemp\004\cropped"
# 保留135齿孔或120边框
python film_crop.py input.ARW --format auto --keep-border --output result.tif
```

依赖安装：`python -m pip install -r requirements.txt`。从源码启动界面：`python film_gui.py`；打包需安装 `requirements-build.txt`，再运行 `build_exe.ps1`。CLI 输出仅支持 JPEG 或16位 TIFF，目标文件存在时拒绝覆盖。


新增 `--format auto` 混合画幅识别。它先检测有效画面内框，再推测画幅和横竖方向，支持画面方向与原文件方向不同的翻拍布局。请将 `film_crop.py` 和 `film_detect.py` 放在同一文件夹。

`film_crop.py` 用 OpenCV 从相机翻拍图中估计胶卷画面的四条边，然后透视校正并裁成指定比例。内置格式：

- `135`：36×24，比例 3:2
- `645`：约 56×41.5
- `66`：1:1
- `67`：约 56×69
- `69`：约 56×84

## 安装

```powershell
python -m pip install -r requirements.txt
```

## 单张图片

```powershell
python film_crop.py "D:\BaiduSyncdisk\照片\lr成片\_7R30702.jpg" `
  --format 135 --output "D:\BaiduSyncdisk\照片\lr成片\_7R30702_135.jpg"
```

## 批量处理

混合 135、645、正片、未反转负片、带齿孔或带边框的图片：

```powershell
python film_crop.py "F:\datatemp\003" --format auto --output-dir "F:\datatemp\003\cropped_auto"
```

默认普通裁切，不保留齿孔和外框。不会自动反转负片或调整颜色。负片的橙色遮罩归一化只用于边界检测。输出 JPEG，质量 98；原文件不修改。命令行逐张显示推测画幅、检测内框宽高比和复核提示。

普通裁切现在默认额外从上、下边缘**各收进画面高度的 1%**（合计 2%），清除缩图检测误差和略弯边框造成的上下残边；同时等量收进左右两侧以维持目标比例，不拉伸画面。这是固定安全余量，会舍弃少量边缘内容，并非逐像素追踪弯曲边界。可分别用 `--top-trim 0.005` 和 `--bottom-trim 0.005` 改为各 0.5%，或用 `--top-trim 0 --bottom-trim 0` 全部关闭。它在比例裁切和 `--padding` 之后执行，两项均按同一张裁切图的高度计算，不作用于 `--keep-sprockets`。若从 Python 调用基础函数，需在 `perspective_crop(...)` 后调用 `trim_borders(crop, ratio)`；旧函数 `trim_top_border` 保持仅裁上缘的兼容行为。

已知整批画幅时可指定格式：

```powershell
python film_crop.py "D:\BaiduSyncdisk\照片\翻拍" --format 66 --output-dir "D:\BaiduSyncdisk\照片\翻拍\cropped"
```

固定格式默认按原文件横竖方向选择比例，可用 `--orientation landscape` 或 `--orientation portrait` 覆盖。`auto` 根据内框方向选择比例，不能同时指定 `--ratio`、`--corners` 或强制方向。默认格式仍是 `135`；混合文件夹需明确使用 `--format auto`。

## 如何理解识别结果

- `source_ratio`：原文件宽÷高，包含周围空白、底片边框等。
- `measured_ratio`：候选有效画面内框的宽÷高，保留检测误差。
- `format`：根据内框几何形状推测的胶卷格式。
- `output_ratio`：最终按预设裁切后的宽÷高，有像素取整误差。它不能用来证明识别成功。
- `negative_hint`：橙色负片遮罩的启发式提示，不是可靠的负片分类器。
- `needs_review`：边界低对比、画幅候选接近或齿孔估算等复核提示。没有提示也不保证边界完全正确。

第三批测试报告在 `F:\datatemp\003\cropped_normal`，包含 CSV、JSON、HTML 和检测框总览图。报告由本次批处理生成，普通 CLI 只在终端显示识别信息。

## 自动检测失败时指定四角

四个点按左上、右上、右下、左下顺序，单位是原图像素：

```powershell
python film_crop.py input.jpg --format 135 `
  --corners 289,242 1570,242 1570,1097 289,1097
```

`--ratio 1.5` 可以覆盖内置格式。`--padding 0.01` 可在检测出的区域四边各缩进 1%，用于去除边缘漏光或底片边框。

## 保留 135 齿孔

默认输出只保留有效画幅，例如 135 输出 3:2。若想得到类似整段底片的效果，保留上下齿孔、胶卷编号和边框，可以使用 135 齿孔模式：

```powershell
python film_crop.py input.jpg --format 135 --keep-sprockets --output film_with_sprockets.jpg
```

齿孔模式的目标比例是 **6:5.5（约 1.0909）**，对应你的手动裁切样片。默认扩展量为“上约 23.56%、右 3.5%、下约 23.56%、左 3.5%”（横幅，竖幅自动换向），相对于检测出的 135 画幅尺寸；不同翻拍支架可以手动调整：

```powershell
python film_crop.py input.jpg --format 135 --keep-sprockets `
  --sprocket-margin 0.25 0.03 0.25 0.03
```

四个数的顺序是：上、右、下、左。`--keep-sprockets` 当前只对 135 开启，因为 120 胶卷没有 135 式齿孔。

当前自动检测是实验版本：假设有效画面大致居中，边界基本水平/垂直。较大旋转、明显透视、画面被遮挡或没有可见边框时可能失败。135 齿孔间距可辅助估算边界，但仍可能少裁或多裁；深色画面、边缘漏光和胶卷文字也可能干扰检测。输出可能残留细边，可检查后添加 `--padding 0.003`（每边缩进 0.3%）。

第三批 28 张样片均成功写出：推测 135 共 13 张、645 共 15 张；6 张标记复核。已抽查实际裁切图并核对全部输出尺寸与比例。当前样本验证覆盖 135 和 645；66、67、69 虽有比例预设，尚未用对应实片验证自动识别。仅凭边界比例也无法确定真实相机型号或底片规格。


自动转正（1.2）：GUI 默认开启；命令行自动/预设画幅默认开启，可用 `--no-auto-rotate` 关闭。自定义 `--corners`、`--ratio` 或显式 `--orientation` 保留手动几何设置。支持 ±10° 内胶片边框/齿孔可识别的小角度翻拍倾斜，0.25° 以下不重采样；不保证校正透视或场景自身的地平线。原始图像只在最终裁切时重采样一次。输出报告包含 `rotation_degrees`（图像坐标中顺时针为正的原始倾斜角，校正时反向旋转）、`rotation_method`、`rotation_confident`。


1.3：精简窗口，移除内容区标题、品牌列表和常驻备注，参数收进“微调”；构建使用 FilmCrop-RAW-1.3.spec，排除视频插件、非 Windows x64 拖拽组件及未使用的 Pillow 格式插件。照片读取格式、RAW 解码、16 位 TIFF、JPEG、自动转正功能保留。使用说明见 使用说明.txt，详细行为见 技术说明.txt。
