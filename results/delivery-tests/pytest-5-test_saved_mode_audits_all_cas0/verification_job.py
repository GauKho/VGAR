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
        print(label+' '+str(artifact));print(artifact.read_text(encoding='utf-8'))
for worker in sorted((case_root/letter/'model-workers').rglob('*.json')):
    assert not worker.is_symlink();print('WORKER JSON '+str(worker));print(worker.read_text(encoding='utf-8'))
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