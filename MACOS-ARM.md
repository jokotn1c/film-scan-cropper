# macOS Apple Silicon 构建

在仓库根目录运行 GitHub Actions：

1. 打开 Actions → Build macOS Apple Silicon → Run workflow。
2. 构建完成后，在 Artifacts 下载 FilmCrop-RAW-1.9-mac-arm64，里面包含 ZIP 应用包与校验文件。
3. 解压后将 FilmCrop-RAW.app 拖到“应用程序”。

Windows 与 macOS 使用同一套裁切、RAW、自动转正和拖放逻辑。应用未签名；首次打开可在 Finder 中右键选择“打开”。

Mac 版使用标准目录式 .app，依赖直接保存在应用内，启动时无需解压临时副本；Dock 图标由应用包提供。请退出旧版后替换整个 .app。

Actions 构建后通过 LaunchServices 打开应用，验证窗口可见、依赖来自 .app 内、仅有一个应用进程，并附上 startup-check.json。首次安全检查耗时及 Dock 实际显示仍需 Mac 实机确认。
