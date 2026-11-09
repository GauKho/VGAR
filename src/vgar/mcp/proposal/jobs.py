"""Host-owned cancellable subprocess jobs. This is containment, not an OS sandbox."""
import hashlib
import json
import os
import shutil
import signal
import subprocess
import threading
import time
from functools import partial
from uuid import uuid4

import anyio

from vgar.repair.evidence import atomic_json
from vgar.repair.executor import _WindowsJob

from .context import (
    authorize_write,
    cancel_request,
    check_context,
    check_source,
    request_cancelled,
)
from .locking import no_links
from .security import sanitize
from .state import repo_guard


def job_input_hash(operation, argv):
    if not isinstance(operation, str) or not operation or type(argv) not in (tuple,list) or not argv or any(not isinstance(a,str) or "\0" in a for a in argv):
        raise ValueError("Host fixed argv required")
    return "sha256:"+hashlib.sha256(json.dumps({"operation":operation,"argv":list(argv)},sort_keys=True,separators=(",",":")).encode()).hexdigest()


def run_guarded_job(ctx, operation, input_hash, argv, *, cancel_event=None):
    check_context(ctx)
    if input_hash!=job_input_hash(operation,argv):
        raise ValueError("Job argv/input hash mismatch")
    cancel_event=cancel_event or threading.Event()
    with repo_guard(ctx,cancel_event=cancel_event):
        authorize_write(ctx,operation,input_hash)
        check_source(ctx)
        job_id="job-"+uuid4().hex
        stage=no_links(ctx.output_root/job_id); stage.mkdir(exist_ok=False)
        process=job=None
        started=time.monotonic(); end=min(ctx.deadline,time.time()+ctx.limits.worker_seconds)
        report={"job_id":job_id,"operation":operation,"input_hash":input_hash,"run_id":ctx.run_id,"task_id":ctx.task_id,
                "status":"ERROR","complete":False,"cancelled":False,"timed_out":False,"output_truncated":False,
                "exit_code":None,"cleanup":"NOT_RUN"}
        stdout=stage/"stdout.bin"; stderr=stage/"stderr.bin"
        try:
            if cancel_event.is_set():
                report["cancelled"]=True
            else:
                # No inherited secrets, authority paths or .env reload in a target child.
                allow={"PATH","PATHEXT","SYSTEMROOT","WINDIR","TEMP","TMP","COMSPEC"}
                environment={k:v for k,v in os.environ.items() if k.upper() in allow}
                environment.update(PYTHONUTF8="1",PYTHONIOENCODING="utf-8",PYTHONDONTWRITEBYTECODE="1",PYTHONOPTIMIZE="0",
                                   PYTHON_DOTENV_DISABLED="1",PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",HF_HUB_OFFLINE="1")
                with stdout.open("wb") as out, stderr.open("wb") as err:
                    process=subprocess.Popen(tuple(argv),cwd=stage,stdin=subprocess.DEVNULL,stdout=out,stderr=err,env=environment,
                                             shell=False,creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP|0x4) if os.name=="nt" else 0,
                                             start_new_session=os.name!="nt")
                    if os.name=="nt":
                        job=_WindowsJob(process)
                    while process.poll() is None:
                        if cancel_event.is_set() or request_cancelled(ctx):
                            report["cancelled"]=True; break
                        if time.time()>=end:
                            report["timed_out"]=True; break
                        if max(stdout.stat().st_size,stderr.stat().st_size)>ctx.limits.output_bytes:
                            report["output_truncated"]=True; break
                        cancel_event.wait(.02)
                    report["cancelled"] |= cancel_event.is_set() or request_cancelled(ctx)
                    report["timed_out"] |= time.time()>=end
                    if job:
                        job.close()
                    elif os.name!="nt":
                        try: os.killpg(process.pid,signal.SIGKILL)
                        except ProcessLookupError: pass
                    process.wait(timeout=5)
                    report["exit_code"]=process.returncode
                for key,path in (("stdout",stdout),("stderr",stderr)):
                    size=path.stat().st_size
                    with path.open("rb") as stream:
                        report[key]=stream.read(ctx.limits.output_bytes).decode("utf-8",errors="replace")
                    report["output_truncated"]|=size>ctx.limits.output_bytes
                report["complete"]=not any(report[k] for k in ("cancelled","timed_out","output_truncated"))
                report["status"]="PASS" if report["complete"] and process.returncode==0 else "FAIL" if report["complete"] else "ERROR"
                check_source(ctx)
        except BaseException as error:
            report.update(status="ERROR",complete=False,error_type=type(error).__name__,error=str(error))
            if not isinstance(error,Exception):
                report["cancelled"]=True
                raise
        finally:
            if job:
                job.close()
            if process and process.poll() is None:
                if os.name!="nt":
                    try: os.killpg(process.pid,signal.SIGKILL)
                    except ProcessLookupError: pass
                else:
                    process.kill()
                process.wait(timeout=5)
            if report["cancelled"] or report["timed_out"]:
                try:
                    cancel_request(ctx)
                except (OSError,ValueError) as error:
                    report.update(status="ERROR",complete=False,cancellation_persistence_error=type(error).__name__)
            try:
                no_links(stage)
                if stage.parent.resolve()!=ctx.output_root or not stage.name.startswith("job-"):
                    raise ValueError("Unsafe cleanup target")
                shutil.rmtree(stage)
                report["cleanup"]="PASS"
            except (OSError,ValueError) as error:
                report.update(status="ERROR",complete=False,cleanup="ERROR",cleanup_error=type(error).__name__)
            report["duration_ms"]=round((time.monotonic()-started)*1000)
            report=sanitize(report,secret_values=ctx.secrets)
            atomic_json(ctx.output_root/(job_id+".json"),report)
        return report


async def run_guarded_job_async(ctx, operation, input_hash, argv):
    cancel=threading.Event(); done=threading.Event()
    def work():
        try:
            return run_guarded_job(ctx,operation,input_hash,argv,cancel_event=cancel)
        finally:
            done.set()
    try:
        return await anyio.to_thread.run_sync(work,abandon_on_cancel=True)
    except BaseException as exc:
        if isinstance(exc,anyio.get_cancelled_exc_class()) or not done.is_set():
            cancel.set()
            marker_error=None
            try:
                cancel_request(ctx)
            except (OSError,ValueError) as error:
                marker_error=error
            finally:
                with anyio.CancelScope(shield=True):
                    cleaned=await anyio.to_thread.run_sync(partial(done.wait,10))
                    if not cleaned:
                        raise RuntimeError("Worker cleanup incomplete after cancellation") from None
            if marker_error:
                raise RuntimeError("Cancellation persistence failed after cleanup") from marker_error
        raise
