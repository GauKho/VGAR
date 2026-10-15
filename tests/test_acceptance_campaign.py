import json
from pathlib import Path

import pytest
from test_bootstrap import api

A,B,C='single_file_login','multi_file_invoice','missing_links'
V3,V4='m2-w78-v3','m2-w78-v4'


@pytest.mark.parametrize('history,want',[
    ([],(V3,A)),
    ([(V3,A,'PASS')],(V3,B)),
    ([(V3,A,'FAIL')],(V4,A)),
    ([(V3,A,'PASS'),(V3,B,'FAIL')],(V4,A)),
    ([(V3,A,'PASS'),(V3,B,'PASS'),(V3,C,'FAIL')],(V4,A)),
    ([(V3,A,'FAIL'),(V4,A,'PASS'),(V4,B,'PASS')],(V4,C)),
])
def test_next_attempt_uses_order_and_restarts_all_cases_on_v4(history,want):
    entries=[dict(version=v,task_id=t,status=s) for v,t,s in history]
    step=api('campaign').next_step(entries)
    assert (step['next']['version'],step['next']['task_id'])==want


@pytest.mark.parametrize('history,status',[
    ([(V3,A,'PASS'),(V3,B,'PASS'),(V3,C,'PASS')],'PASS'),
    ([(V3,A,'FAIL'),(V4,A,'FAIL')],'FAIL'),
    ([(V3,A,'ERROR')],'ERROR'),
    ([(V3,A,'PASS'),(V3,B,'PASS'),(V3,C,'FAIL'),(V4,A,'PASS'),(V4,B,'PASS'),(V4,C,'PASS')],'PASS'),
])
def test_terminal_campaign_never_launches_more_after_success_error_or_two_failures(history,status):
    step=api('campaign').next_step([dict(version=v,task_id=t,status=s) for v,t,s in history])
    assert step['status']==status and step['next'] is None


def test_wrong_order_and_seventh_attempt_are_rejected():
    with pytest.raises(ValueError):
        api('campaign').next_step([dict(version=V4,task_id=B,status='PASS')])
    with pytest.raises(ValueError):
        api('campaign').next_step([dict(version=V3,task_id=A,status='PASS')]*7)


def test_reservation_is_durable_and_live_pending_blocks_new_attempt(tmp_path):
    store=api('campaign').CampaignStore.create(tmp_path/'campaign',{'pin':'fixture'})
    with store.session():
        entry=store.reserve()
        assert entry['number']==1 and entry['task_id']==A
        saved=json.loads(store.path.read_text(encoding='utf-8'))
        assert len(saved['attempts'])==1 and saved['attempts'][0]['status']=='NOT_RUN'
        assert saved['attempts'][0]['owner']['pid']>0
        with pytest.raises(RuntimeError,match='pending|Pending'):
            store.reserve()
    resumed=api('campaign').CampaignStore.open(store.directory)
    with resumed.session():
        assert resumed.recover_pending()=='LIVE'
        assert len(json.loads(resumed.path.read_text(encoding='utf-8'))['attempts'])==1


def test_dead_pending_consumes_attempt_and_runtime_error_stops(tmp_path,monkeypatch):
    module=api('campaign')
    store=module.CampaignStore.create(tmp_path/'campaign',{'pin':'fixture'})
    with store.session(): store.reserve()
    monkeypatch.setattr(module,'process_identity',lambda pid:None)
    resumed=module.CampaignStore.open(store.directory)
    with resumed.session():
        assert resumed.recover_pending()=='RECOVERED'
        assert resumed.state['attempts'][0]['status']=='ERROR'
        assert resumed.decision()['status']=='ERROR'
        with pytest.raises(RuntimeError): resumed.reserve()


def test_changed_snapshot_and_concurrent_owner_block(tmp_path):
    module=api('campaign')
    store=module.CampaignStore.create(tmp_path/'campaign',{'pin':'fixture'})
    other=module.CampaignStore.open(store.directory)
    with store.session():
        with pytest.raises(RuntimeError,match='owner|locked|Locked'):
            with other.session(): pass
    path=store.directory/'frozen_inputs.json'
    path.write_text('{"pin":"changed"}',encoding='utf-8')
    with pytest.raises(ValueError,match='snapshot|Snapshot'):
        module.CampaignStore.open(store.directory)


def test_frozen_source_file_change_is_detected_before_another_run(tmp_path):
    file=tmp_path/'source.py'; file.write_bytes(b'value=1\n')
    snapshot={'files':{str(file):api('evidence').digest(file.read_bytes())}}
    file.write_bytes(b'value=2\n')
    with pytest.raises(ValueError,match='changed'):
        api('campaign').verify_frozen_files(snapshot)


def simulated_record(folder,case=A,version=V3,campaign_id='campaign',attempt_id='attempt-01',status='PASS'):
    # Independent structural evidence fixture; NEVER counted as real inference.
    from vgar_m2_w78.evidence import atomic_json,digest
    folder.mkdir(parents=True,exist_ok=True)
    record=dict(run_id='simulated',campaign_id=campaign_id,attempt_id=attempt_id,
        task_id=case,mode='real',status=status,complete=True,original_source_unchanged=True,
        model={'model_id':'Qwen/Qwen3-4B-Instruct-2507','revision':'cdbee75f17c01a7cc42f958dc650907174af0554'},
        policy={'prompt_version':version},stages={
            'context':{'status':'PASS'},'prompt':{'status':'PASS','version':version},
            'generation':{'status':'PASS','mode':'real','truncated':False},'parse_patch':{'status':'PASS'},
            'apply':{'status':'PASS','patch_applied':True,'changed_files':['auth.py'] if case==A else ['invoice.py','pricing.py'] if case==B else ['formatter.py'],
                     'commands':[{'argv':['git','diff','--cached','--no-ext-diff','--no-textconv'],'status':'PASS','complete':True,'stdout':'--- a/auth.py\n+++ b/auth.py\n@@ -1 +1 @@\n-old\n+new\n'}]},
            'selection':{'status':'PASS','selected':['tests'],'fallback_scope':['tests'],'fallback_required':case==C,'required_selectors':['test.py::test_fix'],'reasons':['unlinked'] if case==C else ['small_fixture_full_regression']},
            'baseline':{'status':'PASS','required_ids':['test.py::test_fix'],'tests':{'status':'FAIL','outcomes':{'test.py::test_fix':'FAIL','test.py::test_ok':'PASS'}}},
            'verification':{'status':'PASS','collection':{'status':'PASS','node_ids':['test.py::test_fix','test.py::test_ok'],'command':{'complete':True,'exit_code':0,'argv':['python','-m','pytest','--collect-only','tests']}},'tests':{'status':'PASS','command':{'complete':True,'exit_code':0},'outcomes':{'test.py::test_fix':'PASS','test.py::test_ok':'PASS'}},'static':{'syntax':{'status':'PASS'},'mypy':{'status':'PASS'},'ruff':{'status':'PASS'}}}},
        artifacts={'applied':'applied.diff','bundle':'evidence_bundle.json'})
    (folder/'applied.diff').write_bytes(b'--- a/auth.py\n+++ b/auth.py\n@@ -1 +1 @@\n-old\n+new\n')
    path=folder/'run_record.json'; atomic_json(path,record)
    atomic_json(folder/'evidence_bundle.json',dict(metadata={'canonical_sha256':digest(path.read_bytes())},
        verification={'patch_applied':True,'tests':{'status':'PASS'},'typecheck':{'status':'PASS'},'lint':{'status':'PASS'}},source_hash_before='fixture',source_hash_after='fixture'))
    return path


@pytest.mark.parametrize('fault',['fake','required_skip','one_file','bundle_hash','lint_missing'])
def test_top_level_pass_cannot_hide_failed_acceptance_gate(tmp_path,fault):
    case=B if fault=='one_file' else A
    path=simulated_record(tmp_path/'run',case)
    record=json.loads(path.read_text(encoding='utf-8'))
    if fault=='fake': record['mode']='fake'
    elif fault=='required_skip': record['stages']['verification']['tests']['outcomes']['test.py::test_fix']='SKIP'
    elif fault=='one_file': record['stages']['apply']['changed_files']=['invoice.py']
    elif fault=='lint_missing': record['stages']['verification']['static']['ruff']['status']='NOT_RUN'
    if fault!='bundle_hash':
        api('evidence').atomic_json(path,record)
        bundle=json.loads((path.parent/'evidence_bundle.json').read_text(encoding='utf-8'))
        bundle['metadata']['canonical_sha256']=api('evidence').digest(path.read_bytes())
        api('evidence').atomic_json(path.parent/'evidence_bundle.json',bundle)
    else:
        path.write_text(path.read_text(encoding='utf-8')+' ',encoding='utf-8')
    assessment=api('campaign').assess_record(path)
    assert assessment['status']=='ERROR' and assessment['gate_errors']


def test_finish_records_terminal_path_and_resumed_campaign_advances(tmp_path):
    module=api('campaign')
    store=module.CampaignStore.create(tmp_path/'campaign',{'pin':'fixture'})
    with store.session():
        attempt=store.reserve()
        path=simulated_record(Path(attempt['run_root'])/'simulated',campaign_id=store.directory.name,attempt_id=attempt['attempt_id'])
        store.finish(path)
        assert store.state['attempts'][0]['status']=='PASS'
    resumed=module.CampaignStore.open(store.directory)
    with resumed.session():
        assert resumed.decision()['next']['task_id']==B


def test_pipeline_embeds_campaign_identity_before_bundle_hash(m1_case,tmp_path):
    from conftest import CharacterChatTokenizer
    from test_pipeline import FIX
    task,counter=m1_case
    result=api('pipeline').run_repair(task,api('contracts').RepairPolicy(prompt_version=V3),api('generator').FakeGenerator(FIX),None,
        tmp_path/'runs',m1_counter=counter,tokenizer=CharacterChatTokenizer(),temp_root=tmp_path/'temp',campaign_id='campaign',attempt_id='attempt-01')
    record=json.loads(result.path.read_text(encoding='utf-8'))
    assert record['campaign_id']=='campaign' and record['attempt_id']=='attempt-01'
    bundle=json.loads((result.directory/'evidence_bundle.json').read_text(encoding='utf-8'))
    assert bundle['metadata']['canonical_sha256']==api('evidence').digest(result.path.read_bytes())


def test_frozen_snapshot_includes_actual_task_jsons():
    import importlib.util
    root=Path(__file__).resolve().parents[1]
    spec=importlib.util.spec_from_file_location('acceptance_script',root/'scripts/run_acceptance.py')
    script=importlib.util.module_from_spec(spec);spec.loader.exec_module(script)
    snapshot=script.freeze_inputs()
    for case in (A,B,C):
        assert str(root/'examples/tasks'/f'{case}.json') in snapshot['files']


def test_modified_frozen_task_prevents_reservation(tmp_path):
    module=api('campaign')
    path=tmp_path/'task.json';path.write_bytes(b'{"issue_text":"original"}')
    store=module.CampaignStore.create(tmp_path/'campaign',{'files':{str(path):api('evidence').digest(path.read_bytes())}})
    path.write_bytes(b'{"issue_text":"different"}')
    with pytest.raises(ValueError,match='changed'):
        with store.session():store.reserve()
    assert json.loads(store.path.read_text(encoding='utf-8'))['attempts']==[]


def test_ledger_fail_to_pass_mutation_cannot_change_resume_branch(tmp_path):
    module=api('campaign');store=module.CampaignStore.create(tmp_path/'campaign',{'pin':'fixture'})
    with store.session():
        attempt=store.reserve();path=simulated_record(Path(attempt['run_root'])/'simulated',status='FAIL')
        store.finish(path)
    ledger=json.loads(store.path.read_text(encoding='utf-8'))
    ledger['attempts'][0]['status']='PASS'
    api('evidence').atomic_json(store.path,ledger)
    with pytest.raises(ValueError,match='ledger|canonical|Historical'):
        module.CampaignStore.open(store.directory)


def test_historical_delivered_artifact_tamper_blocks_resume(tmp_path):
    module=api('campaign');store=module.CampaignStore.create(tmp_path/'campaign',{'pin':'fixture'})
    with store.session():
        attempt=store.reserve();path=simulated_record(Path(attempt['run_root'])/'simulated')
        store.finish(path)
    (path.parent/'applied.diff').write_bytes(b'corrupt')
    with pytest.raises(ValueError,match='ledger|canonical|Historical'):
        module.CampaignStore.open(store.directory)


@pytest.mark.parametrize('fault',['selection_missing','fallback_missing','collection_command_missing','collection_ids_missing','export_mismatch'])
def test_acceptance_requires_actual_selection_collection_and_export(tmp_path,fault):
    path=simulated_record(tmp_path/'run',case=C)
    assert api('campaign').assess_record(path)['status']=='PASS'
    record=json.loads(path.read_text(encoding='utf-8'))
    if fault=='selection_missing':record['stages'].pop('selection')
    elif fault=='fallback_missing':record['stages']['selection']['fallback_scope']=[]
    elif fault=='collection_command_missing':record['stages']['verification']['collection'].pop('command')
    elif fault=='collection_ids_missing':record['stages']['verification']['collection']['node_ids']=[]
    else:(path.parent/'applied.diff').write_bytes(b'nonempty but not actual export')
    api('evidence').atomic_json(path,record)
    bundle=json.loads((path.parent/'evidence_bundle.json').read_text(encoding='utf-8'))
    bundle['metadata']['canonical_sha256']=api('evidence').digest(path.read_bytes())
    api('evidence').atomic_json(path.parent/'evidence_bundle.json',bundle)
    assert api('campaign').assess_record(path)['status']=='ERROR'
