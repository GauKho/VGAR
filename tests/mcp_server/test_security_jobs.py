"""Real contained subprocess cancellation at named fixture phase barriers."""
import json
import os
import sys
import threading
from multiprocessing.connection import Listener
from uuid import uuid4

import anyio
import pytest
from test_runtime_lifecycle import alive
from test_security import HASH


@pytest.mark.parametrize("phase",["build","copy","test"])
@pytest.mark.parametrize("cancel_method",["event","context"])
def test_cancel_at_phase_barrier_kills_tree_and_blocks_publication(bound,phase,cancel_method):
    from vgar.mcp.proposal.context import cancel_request
    from vgar.mcp.proposal.jobs import job_input_hash, run_guarded_job
    from vgar.mcp.proposal.state import manifest_input_hash
    authority,ctx=bound
    family="AF_PIPE" if os.name=="nt" else "AF_INET"
    address=r"\\.\pipe\vgar-"+uuid4().hex if os.name=="nt" else ("127.0.0.1",0)
    cancel=threading.Event();result=[]
    with Listener(address,family=family,authkey=b"synthetic") as listener:
        code=f'''
from multiprocessing.connection import Client
from pathlib import Path
import os,subprocess,sys,threading
Path('partial-{phase}.json').write_text('{{"partial":true}}')
child=subprocess.Popen([sys.executable,'-B','-c','import threading; threading.Event().wait(60)'])
with Client({listener.address!r},family={family!r},authkey=b'synthetic') as conn:
    conn.send(({phase!r},os.getpid(),child.pid))
    conn.recv()
'''
        argv=(sys.executable,"-B","-c",code);digest=job_input_hash(phase,argv);ctx=authority.grant(ctx,phase,digest)
        def run():result.append(run_guarded_job(ctx,phase,digest,argv,cancel_event=cancel))
        worker=threading.Thread(target=run);worker.start()
        try:
            with listener.accept() as conn:
                reported,parent,child=conn.recv();assert reported==phase
                if cancel_method=="event":cancel.set()
                else:cancel_request(ctx)
                worker.join(15)
            assert not worker.is_alive()
        finally:
            cancel.set();worker.join(15)
    assert len(result)==1 and result[0]["status"]=="ERROR" and result[0]["cancelled"]
    assert result[0]["cleanup"]=="PASS" and not alive(parent) and not alive(child)
    assert not (ctx.output_root/result[0]["job_id"]).exists()
    value={"revision":HASH};pd=manifest_input_hash("ready.json",value)
    with pytest.raises(ValueError,match="cancelled"):
        authority.grant(ctx,"publish",pd)
    assert not (ctx.output_root/"ready.json").exists()


def test_guarded_job_hash_mismatch_zero_spawn_and_success_receipt(bound,monkeypatch):
    from vgar.mcp.proposal.context import request_scope
    from vgar.mcp.proposal.jobs import job_input_hash, run_guarded_job
    authority,ctx=bound
    monkeypatch.setenv("VGAR_SECRET","do-not-forward")
    argv=(sys.executable,"-B","-c","import os; print(os.getenv('VGAR_SECRET','absent'))")
    digest=job_input_hash("build",argv);granted=authority.grant(ctx,"build",digest)
    with pytest.raises(ValueError,match="hash mismatch"):
        run_guarded_job(granted,"build",HASH,argv)
    assert not list(ctx.output_root.iterdir())
    with request_scope(granted):report=run_guarded_job(granted,"build",digest,argv)
    assert report["status"]=="PASS" and report["stdout"].strip()=="absent"
    assert report["cleanup"]=="PASS"
    assert json.loads((ctx.output_root/(report["job_id"]+".json")).read_text())["complete"]


def test_async_sdk_cancellation_waits_for_cleanup(bound):
    from vgar.mcp.proposal.jobs import job_input_hash, run_guarded_job_async
    authority,ctx=bound
    family="AF_PIPE" if os.name=="nt" else "AF_INET"
    address=r"\\.\pipe\vgar-"+uuid4().hex if os.name=="nt" else ("127.0.0.1",0)
    with Listener(address,family=family,authkey=b"synthetic") as listener:
        code=f"from multiprocessing.connection import Client\nwith Client({listener.address!r},family={family!r},authkey=b'synthetic') as c:\n c.send('ready')\n c.recv()\n"
        argv=(sys.executable,"-B","-c",code)
        digest=job_input_hash("build",argv);ctx=authority.grant(ctx,"build",digest)
        async def run():
            with anyio.fail_after(20):
                async with anyio.create_task_group() as group:
                    group.start_soon(run_guarded_job_async,ctx,"build",digest,argv)
                    conn=await anyio.to_thread.run_sync(listener.accept)
                    with conn:
                        assert await anyio.to_thread.run_sync(conn.recv)=="ready"
                        group.cancel_scope.cancel()
        anyio.run(run)
    receipts=list(ctx.output_root.glob("job-*.json"))
    assert len(receipts)==1
    report=json.loads(receipts[0].read_text())
    assert report["cancelled"] and report["cleanup"]=="PASS" and report["status"]=="ERROR"
    assert not [p for p in ctx.output_root.iterdir() if p.is_dir()]


@pytest.mark.parametrize("kind",["timeout","output_cap"])
def test_worker_deadline_and_output_cap_are_incomplete_with_cleanup(bound,kind):
    import time

    from vgar.mcp.proposal.context import SecurityLimits, bind_context
    from vgar.mcp.proposal.jobs import job_input_hash, run_guarded_job
    authority,ctx=bound
    ctx=bind_context(authority,repo_root=ctx.repo_root,lease_root=ctx.lease_root,output_root=ctx.output_root,
                     request_id=ctx.request_id,run_id=ctx.run_id,task_id=ctx.task_id,snapshot_hash=ctx.snapshot_hash,
                     source_hash=ctx.source_hash,config_hash=ctx.config_hash,deadline=time.time()+120,
                     limits=SecurityLimits(worker_seconds=.3 if kind=="timeout" else 10))
    code="import threading; threading.Event().wait(60)" if kind=="timeout" else "import sys,threading; sys.stdout.write('x'*50000); sys.stdout.flush(); threading.Event().wait(60)"
    argv=(sys.executable,"-B","-c",code);digest=job_input_hash("build",argv);ctx=authority.grant(ctx,"build",digest)
    result=run_guarded_job(ctx,"build",digest,argv)
    assert result["status"]=="ERROR" and not result["complete"] and result["cleanup"]=="PASS"
    assert result["timed_out"] if kind=="timeout" else result["output_truncated"]


def test_cancellation_marker_io_error_does_not_skip_cleanup(bound,monkeypatch):
    import time

    from vgar.mcp.proposal import jobs
    from vgar.mcp.proposal.context import SecurityLimits, bind_context
    authority,ctx=bound
    ctx=bind_context(authority,repo_root=ctx.repo_root,lease_root=ctx.lease_root,output_root=ctx.output_root,
                     request_id=ctx.request_id,run_id=ctx.run_id,task_id=ctx.task_id,snapshot_hash=ctx.snapshot_hash,
                     source_hash=ctx.source_hash,config_hash=ctx.config_hash,deadline=time.time()+120,
                     limits=SecurityLimits(worker_seconds=.3))
    original=jobs.cancel_request
    def failed_marker(context):
        original(context)
        raise OSError("synthetic marker persistence error")
    monkeypatch.setattr(jobs,"cancel_request",failed_marker)
    argv=(sys.executable,"-B","-c","import threading; threading.Event().wait(60)");digest=jobs.job_input_hash("build",argv)
    result=jobs.run_guarded_job(authority.grant(ctx,"build",digest),"build",digest,argv)
    assert result["status"]=="ERROR" and result["cleanup"]=="PASS"
    assert result["cancellation_persistence_error"]=="OSError"
    assert not [p for p in ctx.output_root.iterdir() if p.is_dir()]
