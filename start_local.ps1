$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not $env:AGHC_CONFIG) { throw '请设置AGHC_CONFIG为私有config.local.json的路径' }
$cfg = Get-Content -LiteralPath $env:AGHC_CONFIG -Raw | ConvertFrom-Json
$python = [Environment]::ExpandEnvironmentVariables($cfg.paths.python_service)
if (-not [IO.Path]::IsPathRooted($python)) { $python = Join-Path (Split-Path -Parent (Resolve-Path $env:AGHC_CONFIG)) $python }
$env:PYTHONUTF8 = '1'
$env:CUDNN_CONV_WSCAP_DBG = '1024'
Write-Host 'http://127.0.0.1:8000/static/index.html；本机单GPU串行队列，按Ctrl+C停止'
& $python -m uvicorn main:app --host 127.0.0.1 --port 8000 --workers 1
