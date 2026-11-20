# Run from zk-stark-access-control. All downloaded dependencies and outputs stay here.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$env:CARGO_HOME = Join-Path $projectRoot '.cargo-home'
$env:CARGO_TARGET_DIR = Join-Path $projectRoot 'target'
Push-Location $projectRoot
try { & cargo @args; exit $LASTEXITCODE } finally { Pop-Location }

