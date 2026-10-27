# FilmCrop

自动识别相机翻拍胶片的画面边框，转正并裁切。提供 Windows 界面和 macOS 构建配置，支持批量导入 RAW 与普通JPG。

## 使用

1. 将 RAW、JPG或文件夹拖入窗口。
2. 选择输出位置。
3. 选择画幅与导出格式，点击“开始裁切”。

默认自动识别画幅、开启自动转正，导出 16 位 TIFF。可切换 JPEG，或保留 135 齿孔、120 边框。“微调”可调整上下边缘及留边。

画幅预设：135（3:2）、645、66、67、69。135 保留齿孔时目标比例为 6:5.5。

## 从源码运行

```shell
python -m pip install -r requirements.txt
python film_gui.py
```

命令行示例：

```shell
python film_crop.py input.jpg --format auto --output result.jpg
python film_crop.py input.ARW --format auto --keep-border --output result.tif
```

## 构建

- Windows：安装构建依赖后运行 build_exe.ps1。
- macOS Apple Silicon：运行 build_macos_arm64.sh，或在 GitHub Actions 手动运行 Build macOS Apple Silicon，从成功运行的 Artifacts 下载产物。


## 图像处理

- RAW 兼容性取决于 LibRaw 支持的相机型号和压缩方式。
- 使用相机白平衡
- 转正根据胶片边框或齿孔判断小角度倾斜；边界不清或明显透视时需检查结果。
- 16 位 TIFF 保存解码后的 RGB；8 位照片转换为 16 位不会增加原有细节。
- 输出添加裁切后缀，保留原始文件；同名裁切结果自动覆盖。
- 新增文件后再次开始，会跳过当前列表中已按相同设置完成的项目；更换输出位置或裁切设置后重新处理。

## 隐私

照片处理在本机完成，程序没有照片上传或遥测功能。安装依赖及 GitHub Actions 构建需要联网。

处理报告与诊断输出可能含所选文件的路径、文件名及错误详情，分享前请检查。源码发布包不包含照片、测试报告、开发环境或本机目录；第三方许可随包提供。
