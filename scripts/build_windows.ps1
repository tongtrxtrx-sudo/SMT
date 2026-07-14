$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    & uv run --offline pyinstaller --noconfirm --clean packaging/SMTGuard.spec
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE"
    }
    $templateSource = Join-Path $projectRoot "templates\站位表导入模板.xlsx"
    $templateDestination = Join-Path $projectRoot "dist\SMTGuard\站位表导入模板.xlsx"
    if (-not (Test-Path -LiteralPath $templateSource)) {
        throw "Station table template not found: $templateSource"
    }
    Copy-Item -LiteralPath $templateSource -Destination $templateDestination -Force
} finally {
    Pop-Location
}
