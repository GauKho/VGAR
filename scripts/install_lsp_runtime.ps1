$ErrorActionPreference = 'Stop'
$m1Root = Split-Path -Parent $PSScriptRoot
$m1Runtime = Join-Path $m1Root 'artifacts/m1/w5-w6/lsp-runtime'
$m1Config = Join-Path $m1Root 'configs/lsp'
$m1Npm = (Get-Command npm.cmd -ErrorAction Stop).Source
New-Item -ItemType Directory -Force -Path $m1Runtime | Out-Null
Copy-Item -LiteralPath (Join-Path $m1Config 'package.json') -Destination $m1Runtime
Copy-Item -LiteralPath (Join-Path $m1Config 'package-lock.json') -Destination $m1Runtime
& $m1Npm ci --prefix $m1Runtime --ignore-scripts --no-audit --no-fund
if ($LASTEXITCODE -ne 0) { throw 'LSP runtime installation failed.' }
Write-Output "LSP runtime installed at $m1Runtime"
