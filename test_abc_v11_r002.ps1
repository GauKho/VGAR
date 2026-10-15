[CmdletBinding()]
param(
    [ValidateSet('Run','Check','ReadSaved')][string]$Mode = 'Run',
    [string]$Python = '',
    [string]$OutputRoot = '',
    [string]$SavedRoot = '',
    [switch]$SkipSelfTests
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ($env:PYTHONOPTIMIZE -and $env:PYTHONOPTIMIZE -ne '0') { throw 'Unset PYTHONOPTIMIZE: acceptance checks must not be disabled.' }
$root = [IO.Path]::GetFullPath($PSScriptRoot)
if (-not $Python) { $Python = Join-Path $root '.venv\Scripts\python.exe' }
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) { throw 'Core Python missing; install prerequisites first.' }
if (-not $OutputRoot) { $OutputRoot = Join-Path $root ('results\manual_abc\' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ') + '-' + [Guid]::NewGuid().ToString('N').Substring(0,8)) }
$OutputRoot = [IO.Path]::GetFullPath($OutputRoot)
$resultsBoundary = [IO.Path]::GetFullPath((Join-Path $root 'results')) + [IO.Path]::DirectorySeparatorChar
if (-not $OutputRoot.StartsWith($resultsBoundary,[StringComparison]::OrdinalIgnoreCase)) { throw 'OutputRoot must be a new directory below this project results.' }
if (Test-Path -LiteralPath $OutputRoot) { throw 'OutputRoot already exists; evidence is never overwritten. Use a NEW path.' }
$ancestor = [IO.Path]::GetDirectoryName($OutputRoot)
while ($ancestor -and $ancestor.StartsWith($root,[StringComparison]::OrdinalIgnoreCase)) {
    if ((Test-Path -LiteralPath $ancestor) -and ((Get-Item -LiteralPath $ancestor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Reparse-point output ancestors are not allowed.' }
    $ancestor = [IO.Path]::GetDirectoryName($ancestor)
}
if (-not $SavedRoot) { $SavedRoot = Join-Path $root 'results\final_acceptance\2026-10-15-v11-r002' }
$utf8 = New-Object Text.UTF8Encoding($false)
[Console]::OutputEncoding = $utf8
$OutputEncoding = $utf8
New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null
$logPath = Join-Path $OutputRoot 'all_logs.txt'
function Write-Log([string]$Text) {
    [IO.File]::AppendAllText($logPath,$Text + [Environment]::NewLine,$utf8)
    Write-Output $Text
}
function Write-Json([string]$Path,$Value) {
    $temporary = $Path + '.' + [Guid]::NewGuid().ToString('N') + '.tmp'
    [IO.File]::WriteAllText($temporary,($Value | ConvertTo-Json -Depth 100),$utf8)
    if (Test-Path -LiteralPath $Path) { [IO.File]::Replace($temporary,$Path,($Path + '.previous')) } else { [IO.File]::Move($temporary,$Path) }
}
function Invoke-Logged([string]$Name,[string]$Executable,[string[]]$Arguments) {
    $start = [DateTime]::UtcNow
    $timer = [Diagnostics.Stopwatch]::StartNew()
    Write-Log ("COMMAND {0}: {1} {2}" -f $Name,$Executable,($Arguments -join ' '))
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $lines = @(& $Executable @Arguments 2>&1 | ForEach-Object { $_.ToString() })
        $nativeExit = $LASTEXITCODE
    } finally { $ErrorActionPreference = $previousPreference }
    $timer.Stop()
    $text = $lines -join [Environment]::NewLine
    [IO.File]::WriteAllText((Join-Path $OutputRoot ($Name + '.console.log')),$text,$utf8)
    Write-Json (Join-Path $OutputRoot ($Name + '.command.json')) ([ordered]@{argv=@($Executable)+$Arguments;exit_code=$nativeExit;started_utc=$start.ToString('o');ended_utc=[DateTime]::UtcNow.ToString('o');duration_ms=$timer.ElapsedMilliseconds})
    Write-Log $text
    Write-Log ("END {0}; exit={1}; duration_ms={2}" -f $Name,$nativeExit,$timer.ElapsedMilliseconds)
    if ($nativeExit -ne 0) { throw "Command failed: $Name (exit $nativeExit); inspect its console log and canonical evidence." }
}
$helper = @'
import ast,json,sys,importlib.metadata as md,subprocess
from pathlib import Path,PureWindowsPath
if sys.flags.optimize:raise RuntimeError('Optimized Python is not allowed for acceptance checks')
root=Path(sys.argv[2]).resolve();sys.path.insert(0,str(root/'src'))
from vgar_m2_w78.bootstrap import verify_reference
from vgar_m2_w78.b_experiment import runtime_fingerprint
from vgar_m2_w78.campaign import assess_record
from vgar_m2_w78.config import load_config
from vgar_m2_w78.contracts import RepairTask
from vgar_m2_w78.evidence import atomic_json,digest
from vgar_m2_w78.pipeline import require_trusted_fixture
from vgar_m2_w78.patch import PatchPolicy,parse_unified_diff,_bind
output=Path(sys.argv[3]).resolve();action=sys.argv[1]
reference=verify_reference()
prior=root/'results/b_repair/2026-10-15-evidence-driven-b'
old=json.loads((prior/'frozen_inputs.json').read_text(encoding='utf-8'))
registered=json.loads((prior/'revisions/r002.json').read_text(encoding='utf-8'))
oldroot=PureWindowsPath(old['runtime_root'])
expected={PureWindowsPath(p).relative_to(oldroot).as_posix():h for p,h in registered['files'].items()}
current={Path(p).relative_to(root).as_posix():h for p,h in runtime_fingerprint(root).items()}
assert expected==current,'Qualified core r002 changed; do not silently accept a new runtime'
assert digest((root/'prompts/repair_v11.txt').read_bytes())=='sha256:ba6d147898eaf411b57b12ab70527aadef239ff9d7a2a8fb3f6639aa333d5ef8','V11 changed'
policy,profile=load_config(root/'config/demo.json');policy=policy.model_copy(update={'prompt_version':'m2-w78-v11'})
assert policy.model_dump()==dict(old['policy'],prompt_version='m2-w78-v11'),'Policy changed'
tasks={}
for letter,case in zip('ABC',('single_file_login','multi_file_invoice','missing_links')):
    path=root/'examples/tasks'/f'{case}.json';data=json.loads(path.read_text(encoding='utf-8'))
    for key in ('source_repo','bundle_directory'):data[key]=(path.parent/data[key]).resolve()
    task=RepairTask.model_validate(data);require_trusted_fixture(task);tasks[letter]=task
if action=='preflight':
    core={name:md.version(name) for name in ('pydantic','python-dotenv','tokenizers','jinja2','pytest','mypy','ruff')}
    if core!={'pydantic':'2.13.5','python-dotenv':'1.2.3','tokenizers':'0.22.1','jinja2':'3.1.6','pytest':'8.4.2','mypy':'1.20.2','ruff':'0.16.7'}:raise RuntimeError('Core version pins differ from the qualified environment: '+str(core))
    assert sys.version_info[:2]==(3,11),'Qualified profile uses Python 3.11'
    result={'status':'PASS','scope':'preflight, NOT repair acceptance','core_versions':core,'reference':reference,'runtime_revision':'r002','profile':profile.model_dump(mode='json'),'policy':policy.model_dump()}
    if sys.argv[4]!='ReadSaved':
        assert profile.snapshot.name==profile.revision and profile.snapshot.is_dir() and profile.interpreter.is_file()
        code="import json,torch,importlib.metadata as m;print(json.dumps({'cuda':torch.cuda.is_available(),'versions':{n:m.version(n) for n in ('torch','transformers','tokenizers','accelerate','safetensors')},'gpu':torch.cuda.get_device_name(0) if torch.cuda.is_available() else None}))"
        probe=subprocess.run([str(profile.interpreter),'-c',code],capture_output=True,text=True,timeout=60)
        assert probe.returncode==0,probe.stderr
        gpu=json.loads(probe.stdout);assert gpu['cuda'],'No CUDA; no CPU fallback allowed'
        assert gpu['versions']=={'torch':'2.11.0+cu128','transformers':'4.57.6','tokenizers':'0.22.2','accelerate':'1.15.0','safetensors':'0.8.0'},'HF environment differs from qualified profile'
        result['hf']=gpu
    atomic_json(output/'profile.json',{'policy':policy.model_dump(),'model':profile.model_dump(mode='json')})
    atomic_json(output/'preflight.json',result);print(json.dumps(result,ensure_ascii=False,indent=2));sys.exit(0)
assert action=='audit'
case_root=Path(sys.argv[4]).resolve();letter=sys.argv[5];task=tasks[letter]
paths=list((case_root/letter).glob('*/run_record.json'));assert len(paths)==1,'Exactly one canonical per case is required'
path=paths[0];record=json.loads(path.read_text(encoding='utf-8'));assessment=assess_record(path)
print('CANONICAL '+str(path));print(path.read_text(encoding='utf-8'))
for label,key in (('PROMPT','prompt.txt'),('RAW OUTPUT',record.get('artifacts',{}).get('raw_output')),('CANDIDATE',record.get('artifacts',{}).get('candidate')),('APPLIED',record.get('artifacts',{}).get('applied')),('EVIDENCE BUNDLE',record.get('artifacts',{}).get('bundle'))):
    if key:
        artifact=(path.parent/key).resolve();assert artifact.parent==path.parent.resolve() and not artifact.is_symlink()
        print(label+' '+str(artifact))
        try:print(artifact.read_text(encoding='utf-8'))
        except OSError as exc:print('ARTIFACT READ ERROR '+repr(exc))
for worker in sorted((case_root/letter/'model-workers').rglob('*.json')):
    assert not worker.is_symlink();print('WORKER JSON '+str(worker))
    try:print(worker.read_text(encoding='utf-8'))
    except OSError as exc:print('WORKER READ ERROR '+repr(exc))
assert assessment['status']=='PASS' and not assessment['gate_errors'],assessment
assert record['task']==task.model_dump(mode='json') and record['model']==profile.model_dump(mode='json')
assert record['policy']==policy.model_dump() and record.get('prompt_feedback') is None
stages=record['stages'];prompt=stages['prompt'];generation=stages['generation']
assert prompt['template_hash']==digest((root/'prompts/repair_v11.txt').read_bytes()) and prompt.get('metadata',{}).get('feedback') is None
assert digest((path.parent/'prompt.txt').read_bytes())==prompt['prompt_hash']
assert generation['input_sha256']==prompt['prompt_hash'].removeprefix('sha256:')
raw=(path.parent/record['artifacts']['raw_output']).read_bytes()
assert raw==(path.parent/record['artifacts']['candidate']).read_bytes() and raw.decode('utf-8')==generation['raw_text']
diagnostic=generation['generation_diagnostics'];mask=diagnostic['attention_mask']
assert diagnostic['status']=='PASS' and diagnostic['effective_observed'] is True
assert diagnostic['effective_generation_config']['do_sample'] is False and diagnostic['effective_generation_config']['max_new_tokens']==1536
assert 0<generation['input_tokens']==prompt['input_tokens']<=6000 and generation['device_map']
assert mask['shape']==[1,generation['input_tokens']] and mask['binary'] is True and mask['zeros']==0
assert all(record['source_fingerprint'][p]==h for p,h in expected.items())
assert stages['cleanup']['status']=='PASS'
required=stages['baseline']['required_ids'];assert len(required)==(2 if letter=='B' else 1)
assert all(stages['baseline']['tests']['outcomes'][n]=='FAIL' for n in required)
parsed=parse_unified_diff(raw.decode('utf-8'),PatchPolicy(task.allowed_source_paths,task.protected_paths));predicted,_=_bind(parsed,task.source_repo)
def signatures(data):
    return {n.name:(type(n).__name__,ast.dump(n.args),ast.dump(n.returns) if n.returns else None) for n in ast.parse(data).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
assert all(signatures((task.source_repo/p).read_bytes())==signatures(data) for p,data in predicted.items())
require_trusted_fixture(task)
result=dict(assessment,task_id=task.task_id,letter=letter,runtime_revision='r002',prompt_version='m2-w78-v11',input_tokens=generation['input_tokens'],output_tokens=generation['output_tokens'],duration_ms=record['duration_ms'])
atomic_json(output/f'audit_{letter}.json',result);print('AUDIT '+letter+' PASS')
'@
$helperPath = Join-Path $OutputRoot 'verification_job.py'
[IO.File]::WriteAllText($helperPath,$helper,$utf8)
$summary = [ordered]@{status='NOT_RUN';complete=$false;mode=$Mode;skip_self_tests=[bool]$SkipSelfTests;started_utc=[DateTime]::UtcNow.ToString('o');ended_utc=$null;cases=@();output_root=$OutputRoot;reason=$null}
$summaryPath = Join-Path $OutputRoot 'summary.json'
Write-Json $summaryPath $summary
$priorEnvironment = @{PYTHONUTF8=$env:PYTHONUTF8;TEMP=$env:TEMP;TMP=$env:TMP}
Push-Location $root
try {
    $env:PYTHONUTF8 = '1'
    $env:TEMP = Join-Path $OutputRoot 'temp'
    $env:TMP = $env:TEMP
    New-Item -ItemType Directory -Path $env:TEMP | Out-Null
    Write-Log "MODE=$Mode OUTPUT=$OutputRoot; no install, no source edits, no automatic retries."
    Invoke-Logged 'preflight' $Python @($helperPath,'preflight',$root,$OutputRoot,$Mode)
    if ($Mode -eq 'Run' -and -not $SkipSelfTests) {
        try { Invoke-Logged 'self_tests' $Python @('scripts\record_tests.py','tests','--timeout-seconds','240','--output-root',(Join-Path $OutputRoot 'self_tests')) }
        finally {
            if (Test-Path -LiteralPath (Join-Path $OutputRoot 'self_tests')) {
                Get-ChildItem -LiteralPath (Join-Path $OutputRoot 'self_tests') -Filter 'run_record.json' -Recurse -File | ForEach-Object { Write-Log ([IO.File]::ReadAllText($_.FullName,$utf8)) }
            }
        }
        Invoke-Logged 'ruff' $Python @('-m','ruff','check','--select','E9,F','src','scripts','tests')
    }
    if ($Mode -ne 'Check') {
        $caseNames = @('single_file_login','multi_file_invoice','missing_links')
        $letters = @('A','B','C')
        for ($index=0; $index -lt 3; $index++) {
            $letter = $letters[$index]
            $case = $caseNames[$index]
            $summary.cases += [ordered]@{letter=$letter;task_id=$case;status='NOT_RUN';reserved_utc=[DateTime]::UtcNow.ToString('o')}
            Write-Json $summaryPath $summary
            $caseRoot = $SavedRoot
            if ($Mode -eq 'Run') {
                $caseRoot = $OutputRoot
                Invoke-Logged ('run_'+$letter) $Python @('scripts\run_demo.py','--mode','real','--task',('examples\tasks\'+$case+'.json'),'--config',(Join-Path $OutputRoot 'profile.json'),'--output-root',(Join-Path $OutputRoot $letter))
            }
            Invoke-Logged ('audit_'+$letter) $Python @($helperPath,'audit',$root,$OutputRoot,$caseRoot,$letter)
            $audit = Get-Content -Raw -Encoding UTF8 (Join-Path $OutputRoot ('audit_'+$letter+'.json')) | ConvertFrom-Json
            if ($audit.status -ne 'PASS' -or @($audit.gate_errors).Count -ne 0) { throw "Acceptance gate failed for $letter; inspect audit JSON." }
            $summary.cases[$index] = $audit
            Write-Json $summaryPath $summary
        }
        Write-Log '3/3 CASE AUDITS PASS. ReadSaved re-audits existing records; only Run performs NEW generations.'
    }
    $summary.status = 'PASS'
    $summary.complete = $true
    $summary.ended_utc = [DateTime]::UtcNow.ToString('o')
    Write-Json $summaryPath $summary
    Write-Log ("DONE mode={0}; summary={1}" -f $Mode,$summaryPath)
    exit 0
} catch {
    $caughtFailure = $_.ToString() + [Environment]::NewLine + $_.ScriptStackTrace
    if ($Mode -eq 'Run' -and (Get-Variable -Name letter -ErrorAction SilentlyContinue)) {
        try { Invoke-Logged ('failed_evidence_'+$letter) $Python @($helperPath,'audit',$root,$OutputRoot,$OutputRoot,$letter) } catch { Write-Log 'Failure evidence dump completed or failed; original failure is retained below.' }
    }
    $summary.status = 'ERROR'
    $summary.complete = $true
    $summary.reason = $caughtFailure
    $summary.ended_utc = [DateTime]::UtcNow.ToString('o')
    Write-Json $summaryPath $summary
    Write-Log $summary.reason
    Write-Log 'STOP: remaining cases were NOT launched. Inspect canonical/worker evidence; never edit a patch to force PASS.'
    exit 2
} finally {
    Pop-Location
    $env:PYTHONUTF8 = $priorEnvironment.PYTHONUTF8
    $env:TEMP = $priorEnvironment.TEMP
    $env:TMP = $priorEnvironment.TMP
}
