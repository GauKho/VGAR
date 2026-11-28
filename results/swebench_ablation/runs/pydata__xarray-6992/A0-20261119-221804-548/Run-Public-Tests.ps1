param([Parameter(Mandatory=$true)][string]$DiffFile)
$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$receipt = Get-Content "$PSScriptRoot/binding-receipt.json" -Raw -Encoding UTF8 | ConvertFrom-Json
if ($receipt.arm -ne 'A0') { throw 'Use execution MCP on MCP-enabled arms.' }
$diff = (Resolve-Path -LiteralPath $DiffFile).Path
if (-not $diff.StartsWith('D:\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Save the diff under drive D first.' }
$linuxDiff = $diff.Substring(2).Replace('\','/')
$linuxDiff = '/mnt/d' + $linuxDiff
if ($receipt.runtime -ne '/home/vgar/swebench-ablation/a5/task-profiles-20261119/runtime-02') {
    throw 'Unexpected Xarray runtime; recheck the trusted binding before testing.'
}
$pythonPath = 'PYTHONPATH=' + $receipt.runtime + '/src'
& wsl.exe -d VGAR-Harness-W9 -- env $pythonPath PYTHONDONTWRITEBYTECODE=1 /home/vgar/swebench-ablation/bindings/20261117-completion/venv/bin/python -B -m vgar.evaluation.swebench_ablation.binding_server --binding $receipt.binding --expected-hash $receipt.binding_hash --server native-tests --diff-file $linuxDiff
exit $LASTEXITCODE
