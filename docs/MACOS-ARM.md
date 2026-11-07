# macOS Apple Silicon 构建

## GitHub Actions

1. 打开仓库的 Actions → Build macOS Apple Silicon → Run workflow。
2. 工作流会构建应用，运行 `tests/` 中的单元测试，再执行 `tools/check_macos_startup.py` 检查应用启动。
3. 构建完成后，在 Artifacts 下载 `FilmCrop-RAW-<版本>-mac-arm64`，其中包含 ZIP 应用包、SHA256 校验文件和 `startup-check.json`。
4. 解压后将 `FilmCrop-RAW.app` 拖到“应用程序”。

也可以在 Apple Silicon Mac 上从仓库根目录本地构建：

```sh
bash build_macos_arm64.sh
python3 -m unittest discover -s tests
python3 tools/check_macos_startup.py
```

Windows 与 macOS 使用同一套裁切、RAW、自动转正和拖放逻辑。经典版应用未签名；首次打开可在 Finder 中右键选择“打开”。

Mac 版使用标准目录式 `.app`，依赖直接保存在应用内，启动时无需解压临时副本；Dock 图标由应用包提供。请退出旧版后替换整个 `.app`。

启动检查通过 LaunchServices 打开应用，验证窗口可见、依赖来自 `.app` 内且仅有一个应用进程。首次安全检查耗时及 Dock 实际显示仍需 Mac 实机确认。
