[CmdletBinding()]
param(
    [ValidateSet('Run', 'Check', 'ReadSaved')][string]$Mode = 'Check',
    [string]$Python = '',
    [string]$OutputRoot = '',
    [string]$SavedRoot = '',
    [switch]$SkipSelfTests
)
# VGAR launcher: Check is safe by default. Explicit Run performs NEW generations.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$m2Root = Join-Path $PSScriptRoot 'M2_week_7_8'
$runner = Join-Path $m2Root 'test_abc_v11_r002.ps1'
if (-not (Test-Path -LiteralPath $runner -PathType Leaf)) {
    throw 'Embedded M2 runner is missing; do not fall back to the independent M2 directory.'
}
if (-not $Python) { $Python = Join-Path $m2Root '.venv\Scripts\python.exe' }
# Bind user paths to the caller's PowerShell location before the child changes cwd.
$Python = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Python)
if ($OutputRoot) { $OutputRoot = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($OutputRoot) }
if ($SavedRoot) { $SavedRoot = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($SavedRoot) }
$arguments = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $runner,
               '-Mode', $Mode, '-Python', $Python)
if ($OutputRoot) { $arguments += @('-OutputRoot', $OutputRoot) }
if ($SavedRoot) { $arguments += @('-SavedRoot', $SavedRoot) }
if ($SkipSelfTests) { $arguments += '-SkipSelfTests' }
Write-Output "VGAR M2 standalone integration r002-vgar-i001; mode=$Mode; root=$m2Root"
Write-Output 'MCP/LangChain is NOT connected by this launcher; the original M2 directory is not used.'
& (Join-Path $PSHOME 'powershell.exe') @arguments
exit $LASTEXITCODE
