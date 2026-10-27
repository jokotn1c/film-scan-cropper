$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    python -m PyInstaller --noconfirm --clean --distpath .\outputs --workpath .\work\build-icon .\FilmCrop-RAW-windows.spec
    if ($LASTEXITCODE -ne 0) { throw 'EXE build failed' }
} finally { Pop-Location }
