# macOS Apple Silicon 构建

在仓库根目录运行 GitHub Actions：

1. 打开 Actions → Build macOS Apple Silicon → Run workflow。
2. 构建完成后，在 Artifacts 下载 FilmCrop-RAW-1.9-mac-arm64，里面包含 ZIP 应用包与校验文件。
3. 解压后将 FilmCrop-RAW.app 拖到“应用程序”。

Windows 与 macOS 使用同一套裁切、RAW、自动转正和拖放逻辑。应用未签名；首次打开可在 Finder 中右键选择“打开”。
