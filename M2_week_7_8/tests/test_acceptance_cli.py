import json
from pathlib import Path
import subprocess
import sys

from test_bootstrap import api

ROOT=Path(__file__).resolve().parents[1]


def test_status_does_not_create_campaign_or_load_model(tmp_path):
    folder=tmp_path/'absent'
    p=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/run_acceptance.py'),'--status','--campaign',str(folder)],capture_output=True,text=True,timeout=15)
    assert p.returncode==0,p.stdout+p.stderr
    assert json.loads(p.stdout)['reason']=='CAMPAIGN_NOT_CREATED'
    assert not folder.exists()


def test_status_is_readonly_on_saved_campaign(tmp_path):
    store=api('campaign').CampaignStore.create(tmp_path/'campaign',{'pin':'fixture'})
    original=store.path.read_bytes()
    p=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/run_acceptance.py'),'--status','--campaign',str(store.directory)],capture_output=True,text=True,timeout=15)
    assert p.returncode==0,p.stdout+p.stderr
    result=json.loads(p.stdout)
    assert result['campaign_id']=='campaign' and result['attempts']==[]
    assert store.path.read_bytes()==original
