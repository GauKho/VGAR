"""Process-safe state and audit fixtures; synchronization uses Events, not random sleeps."""
import json
import multiprocessing as mp
import threading
from pathlib import Path

from test_security import HASH


def grant_worker(state, context, go, queue):
    from vgar.mcp.proposal.context import ContextAuthority, authorize_write
    ContextAuthority(Path(state))
    if not go.wait(15):raise RuntimeError("barrier timeout")
    try:
        authorize_write(context,"build",HASH)
        queue.put("PASS")
    except ValueError:
        queue.put("REJECT")


def test_grant_replay_across_processes_only_one_succeeds(bound):
    authority, context=bound; context=authority.grant(context,"build",HASH)
    spawn=mp.get_context("spawn"); go=spawn.Event(); queue=spawn.Queue()
    ps=[spawn.Process(target=grant_worker,args=(str(context.state_root),context,go,queue)) for _ in range(2)]
    for p in ps:p.start()
    go.set()
    try:
        values=[queue.get(timeout=20) for _ in ps]
        for p in ps:p.join(15)
        assert sorted(values)==["PASS","REJECT"] and all(p.exitcode==0 for p in ps)
    finally:
        for p in ps:
            if p.is_alive():p.terminate();p.join(5)


def increment_session(root, run, ready, go):
    from vgar.mcp.proposal.state import session_guard
    from vgar.repair.evidence import atomic_json
    ready.set()
    if not go.wait(15):raise RuntimeError("barrier timeout")
    for _ in range(12):
        with session_guard(Path(root),Path(run)):
            value=json.loads((Path(run)/"session.json").read_text())["count"]+1
            atomic_json(Path(run)/"session.json",{"count":value})
            atomic_json(Path(run)/"run_record.json",{"count":value})


def test_two_process_session_updates_have_no_lost_updates(tmp_path):
    root=tmp_path/"runs";run=root/"one";run.mkdir(parents=True)
    for n in ("session.json","run_record.json"):(run/n).write_text('{"count":0}',encoding="utf-8")
    spawn=mp.get_context("spawn");ready=[spawn.Event(),spawn.Event()];go=spawn.Event()
    ps=[spawn.Process(target=increment_session,args=(str(root),str(run),ready[i],go)) for i in range(2)]
    for p in ps:p.start()
    try:
        assert all(x.wait(15) for x in ready);go.set()
        for p in ps:p.join(25)
        assert all(p.exitcode==0 for p in ps)
    finally:
        for p in ps:
            if p.is_alive():p.terminate();p.join(5)
    assert json.loads((run/"session.json").read_text())=={"count":24}
    assert (run/"session.json").read_bytes()==(run/"run_record.json").read_bytes()


def crash_session(root,run,changed):
    from vgar.mcp.proposal.state import session_guard
    from vgar.repair.evidence import atomic_json
    with session_guard(Path(root),Path(run)):
        atomic_json(Path(run)/"session.json",{"partial":True})
        changed.set()
        threading.Event().wait(60)


def test_process_crash_releases_lock_but_torn_session_fails_closed(tmp_path):
    import pytest

    from vgar.mcp.proposal.state import session_guard
    root=tmp_path/"runs";run=root/"one";run.mkdir(parents=True)
    for n in ("session.json","run_record.json"):(run/n).write_text('{}',encoding="utf-8")
    spawn=mp.get_context("spawn");changed=spawn.Event();p=spawn.Process(target=crash_session,args=(str(root),str(run),changed));p.start()
    try:
        assert changed.wait(15)
    finally:
        p.terminate();p.join(10)
    with pytest.raises(ValueError,match="integrity"), session_guard(root,run):
        pytest.fail("partial session accepted")


def test_repo_guards_serialize_threads_and_publication_compare_revision(bound):
    import pytest

    from vgar.mcp.proposal.state import (
        manifest_input_hash,
        publish_manifest,
        repo_guard,
    )
    authority,ctx=bound;first=threading.Event();release=threading.Event();second=threading.Event();order=[]
    def owner():
        with repo_guard(ctx):
            order.append("first");first.set()
            if not release.wait(10):raise RuntimeError("barrier timeout")
            order.append("first-end")
    def follower():
        if not first.wait(10):raise RuntimeError("barrier timeout")
        second.set()
        with repo_guard(ctx):order.append("second")
    a=threading.Thread(target=owner);b=threading.Thread(target=follower);a.start();b.start()
    assert first.wait(10) and second.wait(10);release.set();a.join(15);b.join(15)
    assert order==["first","first-end","second"]
    value={"revision":HASH};digest=manifest_input_hash("ready.json",value)
    first_ctx=authority.grant(ctx,"publish",digest);second_ctx=authority.grant(ctx,"publish",digest)
    p=publish_manifest(first_ctx,"ready.json",value,input_hash=digest)
    before=p.read_bytes()
    with pytest.raises(ValueError,match="Stale"):
        publish_manifest(second_ctx,"ready.json",value,input_hash=digest)
    assert p.read_bytes()==before


def test_two_real_repair_calls_apply_once(tmp_path,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor

    from vgar.mcp.audit import AuditLogger
    from vgar.mcp.servers import repair_server as server
    root=Path(__file__).resolve().parents[2]
    monkeypatch.setenv("PYTHONPATH",str(root/"src"))
    monkeypatch.setenv("VGAR_RUN_ROOT",str(tmp_path))
    monkeypatch.setattr(server,"_audit_logger",AuditLogger(tmp_path/"audit.jsonl"))
    opened=server.get_task_context(str(root/"examples/m2/tasks/single_file_login.json"),"fake",str(tmp_path/"runs"),str(tmp_path/"work"))
    assert opened["status"]=="PASS" and opened["data"]["verdict"]=="PASS",opened
    run=opened["data"]["run_dir"];patch=(root/"tests/fixtures/m2/reference_patches/single_file_login.diff").read_text(encoding="utf-8")
    gate=threading.Barrier(2)
    def apply():
        gate.wait(timeout=15)
        return server.apply_patch(run,patch)
    with ThreadPoolExecutor(max_workers=2) as pool:
        values=[f.result(timeout=30) for f in [pool.submit(apply),pool.submit(apply)]]
    assert sorted(x["status"] for x in values)==["ERROR","PASS"]
    assert next(x for x in values if x["status"]=="ERROR")["error"]["code"]=="TOOL_ORDER_VIOLATION"
    tested=server.run_relevant_tests(run)
    assert tested["status"]=="PASS" and tested["data"]["verdict"]=="PASS",tested
    final=server.verify_patch(run)
    assert final["data"]["recommendation"]=="ACCEPT",final


def test_cancellation_and_final_publication_have_one_commit_order(bound,monkeypatch):
    from vgar.mcp.proposal import state
    from vgar.mcp.proposal.context import cancel_request
    authority,ctx=bound;value={"ready":True};digest=state.manifest_input_hash("ready.json",value)
    ctx=authority.grant(ctx,"publish",digest)
    at_commit=threading.Event();release=threading.Event();cancel_started=threading.Event();cancel_returned=threading.Event();order=[];errors=[]
    original=state.os.replace
    def paused_replace(src,dst):
        if Path(dst).name=="ready.json":
            at_commit.set()
            if not release.wait(10):raise RuntimeError("commit barrier timeout")
            original(src,dst);order.append("commit")
        else:original(src,dst)
    monkeypatch.setattr(state.os,"replace",paused_replace)
    def publish():
        try:state.publish_manifest(ctx,"ready.json",value,input_hash=digest)
        except (OSError,ValueError,RuntimeError) as e:errors.append(e)
    def cancel():
        cancel_started.set()
        try:cancel_request(ctx);order.append("cancel-return");cancel_returned.set()
        except (OSError,ValueError,RuntimeError) as e:errors.append(e)
    a=threading.Thread(target=publish);a.start();assert at_commit.wait(10)
    b=threading.Thread(target=cancel);b.start()
    try:
        assert cancel_started.wait(10)
        assert not cancel_returned.wait(1),"Cancellation returned while final publication was still paused"
    finally:
        release.set();a.join(15);b.join(15)
    assert not errors and order==["commit","cancel-return"]


def append_worker(path, ready, go, number):
    from vgar.mcp.audit import AuditLogger
    logger=AuditLogger(Path(path)); ready.set()
    if not go.wait(15):
        raise RuntimeError("barrier timeout")
    for i in range(60):
        logger.write("fixture",{"worker":number,"index":i,"password":"synthetic-password"})


def test_two_processes_append_full_audit_records(tmp_path):
    ctx=mp.get_context("spawn"); go=ctx.Event(); ready=[ctx.Event(),ctx.Event()]
    path=tmp_path/"audit.jsonl"
    ps=[ctx.Process(target=append_worker,args=(str(path),ready[i],go,i)) for i in range(2)]
    for p in ps:p.start()
    try:
        assert all(r.wait(15) for r in ready); go.set()
        for p in ps:p.join(20)
        assert all(p.exitcode==0 for p in ps)
    finally:
        for p in ps:
            if p.is_alive():p.terminate();p.join(5)
    lines=path.read_text(encoding="utf-8").splitlines()
    assert len(lines)==120
    values=[json.loads(s)["payload"] for s in lines]
    assert {(x["worker"],x["index"]) for x in values}=={(w,i) for w in range(2) for i in range(60)}
    assert "synthetic-password" not in path.read_text(encoding="utf-8")


def test_commit_sidecar_detects_torn_session(tmp_path):
    from vgar.mcp.proposal.state import session_guard
    root=tmp_path/"runs"; run=root/"one";run.mkdir(parents=True)
    (run/"session.json").write_text('{"phase":"prepared"}',encoding="utf-8")
    (run/"run_record.json").write_text('{"run_id":"one"}',encoding="utf-8")
    with session_guard(root,run):
        pass
    assert (run/"session_commit.json").is_file()
    (run/"session.json").write_text('{"phase":"applied"}',encoding="utf-8")
    import pytest
    before=(run/"run_record.json").read_bytes()
    with pytest.raises(ValueError,match="integrity"), session_guard(root,run):
        pytest.fail("torn session entered")
    assert (run/"run_record.json").read_bytes()==before
