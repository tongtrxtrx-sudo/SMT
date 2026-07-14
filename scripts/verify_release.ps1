$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = Split-Path -Parent $PSScriptRoot
$tempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
$smokeDirectory = [System.IO.Path]::GetFullPath(
    (Join-Path $tempRoot ("SMTGuard-Release-" + [guid]::NewGuid().ToString("N")))
)
if (-not $smokeDirectory.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Smoke directory escaped the system temporary directory"
}

Push-Location $projectRoot
try {
    & uv lock --check
    if ($LASTEXITCODE -ne 0) { throw "uv lock check failed" }
    & uv run --offline pytest --cov=smt_guard --cov-report=term-missing --cov-fail-under=90
    if ($LASTEXITCODE -ne 0) { throw "pytest --cov failed" }
    & uv run --offline ruff check .
    if ($LASTEXITCODE -ne 0) { throw "ruff check failed" }
    & uv run --offline pyright
    if ($LASTEXITCODE -ne 0) { throw "pyright failed" }
    & uv run --offline bandit -r src -q
    if ($LASTEXITCODE -ne 0) { throw "bandit -r src failed" }
    & uv run pip-audit
    if ($LASTEXITCODE -ne 0) { throw "pip-audit failed" }
    & .\scripts\build_windows.ps1

    New-Item -ItemType Directory -Path $smokeDirectory | Out-Null
    $oldDataDirectory = $env:SMT_GUARD_DATA_DIR
    $oldQtPlatform = $env:QT_QPA_PLATFORM
    try {
        $env:SMT_GUARD_DATA_DIR = $smokeDirectory
        $env:QT_QPA_PLATFORM = "offscreen"
        $process = Start-Process `
            -FilePath ".\dist\SMTGuard\SMTGuard.exe" `
            -ArgumentList "--smoke-test" `
            -Wait `
            -PassThru `
            -WindowStyle Hidden
        if ($process.ExitCode -ne 0) {
            throw "SMTGuard.exe --smoke-test failed with exit code $($process.ExitCode)"
        }
        if (-not (Test-Path -LiteralPath (Join-Path $smokeDirectory "smt_guard.sqlite3"))) {
            throw "Packaged smoke test did not initialize SQLite"
        }
    } finally {
        $env:SMT_GUARD_DATA_DIR = $oldDataDirectory
        $env:QT_QPA_PLATFORM = $oldQtPlatform
    }
} finally {
    Pop-Location
    $resolvedSmoke = [System.IO.Path]::GetFullPath($smokeDirectory)
    if (
        $resolvedSmoke.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase) -and
        (Test-Path -LiteralPath $resolvedSmoke)
    ) {
        Remove-Item -LiteralPath $resolvedSmoke -Recurse -Force
    }
}
