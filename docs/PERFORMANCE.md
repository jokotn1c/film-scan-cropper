# 性能优化与统一处理管线（实验副本）

原版源码与 EXE 保留；此副本以 1.10.1 为基础，尚未发布，版本号保持 1.10.1。

## 测速

同一台 Windows 电脑，旧版与优化版依次运行；每张图预热 1 次，再测 3 次，取中位数。
只测 `locate()` 识别阶段，不包含解码、像素裁切和编码；没有启用性能分析器。
OpenCV 线程设置相同（16）。暗片一项包含自动识别后按指定 6x6 重试。

| 样片 | 原版识别（秒） | 优化后（秒） | 耗时下降 |
| --- | ---: | ---: | ---: |
| 135 | 4.457 | 2.336 | 47.6% |
| 645 | 4.246 | 2.314 | 45.5% |
| multi | 3.663 | 1.946 | 46.9% |
| panorama | 2.040 | 1.305 | 36.1% |
| RAW | 0.642 | 0.633 | 1.4% |
| dark | 6.101 | 3.063 | 49.8% |
| rotation | 0.250 | 0.253 | -1.1% |

七张样片的中位数合计：21.40 秒 → 11.85 秒，下降 44.6%。
这是本机样片结果，不代表每张照片都有相同提速；RAW 与原本识别很快的旋转样片变化较小。
本次没有更改 RAW 解码、TIFF 编码参数或图像识别规则。

## 改动

- `DetectionContext` 在单次识别中共享 1200 像素预览、通道最大亮度图与齿孔证据。
- 齿孔完整、截断、自适应搜索复用相同阈值的轮廓几何；只缓存筛选后的少量候选。
- 旋转判断与画面识别共享齿孔搜索结果；校正旋转后重新创建上下文，避免使用旧坐标。
- 缓存随本张图片的识别结束释放，不长期占用 RAW 大图内存。
- `film_pipeline.process_image()` 统一校验、输出路径、解码、选区、裁切、导出、元数据与阶段计时。
- `process_one()`、`process_file()`、`export_one()` 保留为兼容入口，调用同一管线。
- `film_io.write_output()` 负责一次编码与原子写入，集中处理同名文件策略。
- 修正文件夹 CLI 未传递 `--no-auto-rotate` 的问题。

## 使用选项

```python
from film_engine import Options
from film_pipeline import process_image

# 自动识别；输出 16 位 TIFF；覆盖同名裁切结果。
record = process_image('input.ARW', 'cropped', Options(collision_policy='overwrite'))

# 手动选区使用归一化的 (left, top, right, bottom)，保留原始像素位深。
record = process_image('input.tif', 'cropped', Options(
    manual_box=(.1, .15, .9, .85), collision_policy='number'))
```

自动模式保留画幅、旋转、留边、边缘微裁等已有设置。
手动矩形选区直接作用于原图，不执行自动转正、比例重裁或留边扩展。
CLI 的四角坐标、自定义比例、强制横竖方向、padding 与齿孔边距均保留。

| `collision_policy` | 行为 |
| --- | --- |
| `overwrite` | 完整编码后原子替换已有文件 |
| `number` | 使用 `_2`、`_3` 等编号；并发提交不会覆盖其他结果 |
| `skip` | 已有结果时在解码前跳过；提交时再次处理竞争 |
| `error` | 已有结果时报错；提交时再次处理竞争 |

兼容入口保留既有默认值：CLI / 经典界面覆盖，现代界面编号。
显式传入 `collision_policy` 可统一三入口行为；独立调用管线默认覆盖。
`number` / `skip` / `error` 使用与原现代界面一致的同目录硬链接提交机制，目标文件系统需支持硬链接。

命令行新增 `--existing overwrite|number|skip|error`：

```shell
python film_crop.py scans --format auto --output-dir cropped --existing skip
```

返回记录增加 `mode`、`collision_policy`、`skipped`、`timings`。
`timings` 包含 read / detect / crop / write / total 秒数。
跳过已有文件时不虚构尺寸信息，只返回路径、策略和耗时；原文件路径与硬链接始终受保护。

## 验证

- 26 项单元测试：入口一致性、手动选区、兼容参数、16 位 / RAW ICC、同名策略、并发与编码失败。
- 003–007 共 69 张：画幅、边界、旋转、复核判断完全匹配原版已验收记录；普通 / 留边 1200 像素预览裁切逐像素一致。
- 4 张暗片继续按原流程暂缓识别，不改变批处理后的指定画幅行为。
- `_7R30575` 原片与横竖 / 明暗变体共 14 项通过。
- 6 次全分辨率 TIFF 导出与原裁切逻辑逐像素一致，覆盖三入口、普通 / 留边、真实 RAW；位深与 RAW sRGB ICC 检查通过。
- 仅保留两种裁切缩略图；本次全尺寸测试输出均在检验后清理。
- 原始备份 ZIP 内全部 41 个源码 / 资源文件的 SHA256 与原工作副本一致。

复现入口：`python -m unittest discover -s tests`。
完整样片回归与重复测速脚本随 `performance-tools.zip` 提供，需要原样片目录和项目已有验收报告。
