"""Fixed-argv Docker bridge bound to an admitted host lease; no native fallback."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import tarfile
import time
import uuid

from vgar.evaluation.harness.task_env import docker_environment, validate_profile
from vgar.repair.admission import validate_admission
from vgar.repair.config import CONFIG_DIR
from vgar.repair.contracts import safe_selector
from vgar.repair.evidence import atomic_json, digest
from vgar.repair.executor import remaining_timeout, run_bounded
from vgar.repair.pipeline import DeadlineExecutor
from vgar.repair.workspace import inventory


class DockerExecutor:
    def __init__(
        self, lease, task, admission, deadline, output_cap, evidence_root=None
    ):
        self.lease, self.task = lease, task
        self.admission = validate_admission(task, admission).snapshot()
        self.profile = validate_profile(
            json.loads(Path(self.admission["profile_path"]).read_text(encoding="utf-8"))
        )
        self.deadline, self.output_cap = deadline, output_cap
        self.evidence_root = (
            Path(evidence_root) if evidence_root else lease.private / "docker"
        )
        self.interpreter_ref = (
            self.profile["env_ref"]
            + "|"
            + self.profile["python"]
            + "|"
            + self.profile["runtime"]["python"]
        )
        self.reserved = False

    def verify_snapshot(self):
        validate_admission(self.task, self.admission)
        if not self.lease.active:
            raise ValueError("Inactive private workspace")
        self.lease.assert_original()
        expected = dict(self.admission["inventory"])
        expected.update({p: digest(t) for p, t in self.admission["overlay"].items()})
        if getattr(self.lease, "execution_before", None) != expected:
            raise ValueError("Private base/overlay execution binding changed")
        observed = inventory(self.lease.path)
        if set(observed) != set(expected) or any(
            observed[p] != h
            for p, h in expected.items()
            if p not in self.task.allowed_source_paths
        ):
            raise ValueError("Protected private snapshot drift")
        return observed

    def map_command(self, argv):
        argv = tuple(argv)
        if argv[:3] != (sys.executable, "-m", "pytest"):
            for name in ("mypy", "ruff"):
                prefix = (sys.executable, "-m", name)
                config = CONFIG_DIR / (
                    "static/mypy.ini" if name == "mypy" else "static/ruff.toml"
                )
                targets = tuple(self.task.allowed_source_paths)
                full = (
                    prefix
                    + (
                        "--config-file",
                        str(config),
                        "--no-incremental",
                        "--cache-dir",
                        str(self.lease.private / "mypy-cache"),
                        "--output",
                        "json",
                        "--no-error-summary",
                        *targets,
                    )
                    if name == "mypy"
                    else prefix
                    + (
                        "check",
                        "--config",
                        str(config),
                        "--no-cache",
                        "--no-fix",
                        "--output-format",
                        "json",
                        *targets,
                    )
                )
                if argv == prefix + ("--version",):
                    return [self.profile["python"], "-m", name, "--version"], {}
                if argv == full:
                    mapped = [self.profile["python"], *argv[1:]]
                    mapped = [
                        (
                            "/vgar/" + config.name
                            if a == str(config)
                            else "/vgar/mypy-cache"
                            if a == str(self.lease.private / "mypy-cache")
                            else a
                        )
                        for a in mapped
                    ]
                    return mapped, {}
            raise ValueError("Unapproved target command")
        prefix = (
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "-p",
            "vgar.repair.pytest_plugin",
        )
        if (
            argv[:8] != prefix
            or len(argv) < 11
            or not argv[8].startswith("--m2-report-json=")
            or not argv[9].startswith("--junitxml=")
        ):
            raise ValueError("Unapproved pytest argv")
        report, junit = Path(argv[8].split("=", 1)[1]), Path(argv[9].split("=", 1)[1])
        root = (self.lease.private / "reports").resolve()
        if (
            report.name != "nodeids.json"
            or junit.name != "junit.xml"
            or report.parent != junit.parent
            or not report.resolve().is_relative_to(root)
            or not junit.resolve().is_relative_to(root)
            or report.exists()
            or junit.exists()
        ):
            raise ValueError("Pytest report path escapes private report directory")
        tail = list(argv[10:])
        collect = tail[:1] == ["--collect-only"]
        selectors = tail[1:] if collect else tail
        for selector in selectors:
            safe_selector(selector)
            if not any(
                selector == s
                or selector.startswith(s + "::")
                or selector.startswith(s + "/")
                for s in (*self.task.fallback_scope, *self.task.failing_selectors)
            ):
                raise ValueError("Selector outside admitted test scope")
        if not selectors:
            raise ValueError("Empty admitted pytest selection")
        return [
            self.profile["python"],
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "-p",
            "vgar_pytest_reporter",
            "--m2-report-json=/vgar/nodeids.json",
            "--junitxml=/vgar/junit.xml",
            *tail,
        ], {"nodeids.json": report, "junit.xml": junit}

    def run(self, argv, cwd, timeout_seconds):
        if Path(cwd).resolve() != self.lease.path or not self.lease.active:
            raise ValueError("Docker executor requires its active private lease")
        if argv[0] == "git":
            return DeadlineExecutor(self.lease, self.deadline, self.output_cap).run(
                argv, cwd, timeout_seconds
            )
        mapped, reports = self.map_command(argv)
        return self.execute_operation(
            {"kind": "command", "argv": mapped}, timeout_seconds, reports=reports
        )

    def syntax_report(self, targets, timeout_seconds):
        if tuple(targets) != self.task.allowed_source_paths:
            raise ValueError("Syntax scope differs from admitted source inventory")
        return self.execute_operation(
            {"kind": "syntax", "targets": list(targets)}, timeout_seconds
        )

    def _cli(self, args, directory, deadline):
        result = run_bounded(
            ("docker", *map(str, args)),
            self.lease.path,
            remaining_timeout(deadline, 60),
            output_cap=self.output_cap,
            environment=docker_environment(self.admission["docker_host"]),
        )
        path = directory / ("cli-%03d.json" % len(list(directory.glob("cli-*.json"))))
        atomic_json(path, result)
        return result

    def _checked(self, args, directory, deadline):
        result = self._cli(args, directory, deadline)
        if not result["complete"] or result["exit_code"] != 0:
            raise RuntimeError(
                "Docker operation incomplete: "
                + str(args[:2])
                + " "
                + result.get("stderr", "")[-1000:]
            )
        return result

    def _identity(self, directory):
        info = json.loads(
            self._checked(
                ["info", "--format", "{{json .}}"], directory, self.operation_deadline
            )["stdout"]
        )
        if (
            info.get("ID") != self.profile["daemon_id"]
            or info.get("OSType") != "linux"
            or info.get("Architecture") not in ("amd64", "x86_64")
        ):
            raise ValueError("Docker daemon differs from qualified profile")
        rows = json.loads(
            self._checked(
                ["image", "inspect", self.profile["env_ref"][9:]],
                directory,
                self.operation_deadline,
            )["stdout"]
        )
        if (
            len(rows) != 1
            or rows[0]["Id"] != self.profile["image_id"]
            or rows[0].get("Os") != "linux"
            or rows[0].get("Architecture") != "amd64"
            or self.profile["env_ref"][9:] not in rows[0].get("RepoDigests", [])
        ):
            raise ValueError("Docker image differs from pinned immutable profile")

    def _execute(self, directory, operation, reports, expected):
        absent = self._checked(
            ["ps", "-aq", "--filter", "name=^/" + self.name + "$"],
            directory,
            self.operation_deadline,
        )
        if absent["stdout"].strip():
            raise ValueError("Fresh container name already exists")
        self.reserved = True
        self._checked(
            [
                "create",
                "--name",
                self.name,
                "--label",
                "vgar.m2.operation=" + self.operation_id,
                "--label",
                "vgar.m2.admission=" + self.admission["admission_hash"],
                "--network",
                "none",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--pids-limit",
                "256",
                "--entrypoint",
                "/bin/sleep",
                self.profile["env_ref"][9:],
                "infinity",
            ],
            directory,
            self.operation_deadline,
        )
        self._checked(["start", self.name], directory, self.operation_deadline)
        control = directory / "control"
        control.mkdir()
        with tarfile.open(control / "snapshot.tar", "w") as archive:
            for relative in sorted(expected):
                archive.add(
                    self.lease.path / relative, arcname=relative, recursive=False
                )
        for source, name in (
            (Path(__file__).with_name("docker_probe.py"), "docker_probe.py"),
            (Path(__file__).with_name("pytest_plugin.py"), "vgar_pytest_reporter.py"),
            (CONFIG_DIR / "static/mypy.ini", "mypy.ini"),
            (CONFIG_DIR / "static/ruff.toml", "ruff.toml"),
        ):
            shutil.copyfile(source, control / name)
        config = dict(
            operation,
            root="/testbed",
            archive="/vgar/snapshot.tar",
            expected=expected,
            base_commit=self.task.revision,
            base_identity=self.profile["source_before"],
            runtime=dict(self.profile["runtime"]),
        )
        atomic_json(control / "config.json", config)
        # docker cp keeps the host uid and mode; container root has no CAP_DAC_OVERRIDE.
        for path in control.iterdir():
            path.chmod(0o644)
        control.chmod(0o777)
        self._checked(
            ["cp", str(control), self.name + ":/vgar"],
            directory,
            self.operation_deadline,
        )
        result = self._cli(
            [
                "exec",
                "-w",
                "/testbed",
                self.name,
                self.profile["python"],
                "/vgar/docker_probe.py",
                "/vgar/config.json",
                "/vgar/result.json",
            ],
            directory,
            self.operation_deadline,
        )
        result.update(
            target_argv=operation.get("argv"),
            environment_ref=self.profile["env_ref"],
            admission_hash=self.admission["admission_hash"],
        )
        if result["complete"]:
            self._checked(
                [
                    "cp",
                    self.name + ":/vgar/result.json",
                    str(directory / "target_result.json"),
                ],
                directory,
                self.operation_deadline,
            )
            data = json.loads(
                (directory / "target_result.json").read_text(encoding="utf-8")
            )
            result["target_result"] = data
            if (
                not data["complete"]
                or data["exit_code"] != result["exit_code"]
                or data["snapshot_before"] != expected
                or data["snapshot_after"] != expected
                or data["runtime"] != config["runtime"]
                or data["base"] != config["base_identity"]
                or data["protocol"] != "vgar-docker-repair-v1"
                or data["argv"] != operation.get("argv")
            ):
                result.update(status="ERROR", complete=False)
            if result["complete"]:
                for name, path in reports.items():
                    self._checked(
                        ["cp", self.name + ":/vgar/" + name, str(directory / name)],
                        directory,
                        self.operation_deadline,
                    )
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with path.open("xb") as output:
                        output.write((directory / name).read_bytes())
        return result

    def _cleanup(self, directory):
        if not self.reserved:
            return dict(status="PASS", detail="No container reserved")
        deadline = time.monotonic() + 30
        try:
            ids = self._checked(
                ["ps", "-aq", "--filter", "name=^/" + self.name + "$"],
                directory,
                deadline,
            )["stdout"].split()
            if not ids:
                return dict(status="PASS", detail="Owned container absent")
            rows = json.loads(
                self._checked(["container", "inspect", ids[0]], directory, deadline)[
                    "stdout"
                ]
            )
            if (
                len(ids) != 1
                or len(rows) != 1
                or rows[0]["Name"] != "/" + self.name
                or rows[0]["Image"] != self.profile["image_id"]
                or rows[0]["Config"]["Labels"].get("vgar.m2.operation")
                != self.operation_id
                or rows[0]["Config"]["Labels"].get("vgar.m2.admission")
                != self.admission["admission_hash"]
            ):
                raise ValueError("Cannot prove container ownership")
            self._checked(["rm", "-f", ids[0]], directory, deadline)
            if self._checked(
                ["ps", "-aq", "--filter", "name=^/" + self.name + "$"],
                directory,
                deadline,
            )["stdout"].strip():
                raise RuntimeError("Owned container remains")
            return dict(status="PASS", removed=ids[0])
        except Exception as error:
            return dict(status="ERROR", reason=str(error))

    def execute_operation(self, operation, timeout_seconds, *, reports=None):
        expected = self.verify_snapshot()
        self.operation_deadline = min(self.deadline, time.monotonic() + timeout_seconds)
        remaining_timeout(self.operation_deadline)
        self.operation_id = uuid.uuid4().hex
        self.name = "vgar-m2w93-" + self.operation_id
        self.reserved = False
        directory = self.evidence_root / self.operation_id
        directory.mkdir(parents=True, exist_ok=False)
        result = None
        try:
            self._identity(directory)
            result = self._execute(directory, operation, reports or {}, expected)
            # Check again after Docker, including protected host files and original source.
            if self.verify_snapshot() != expected:
                raise ValueError("Host snapshot changed during execution")
        finally:
            cleanup = self._cleanup(directory)
            atomic_json(directory / "cleanup.json", cleanup)
            if cleanup["status"] != "PASS":
                raise RuntimeError("Docker cleanup failed: " + str(cleanup))
        result["docker_cleanup"] = cleanup
        result["docker_evidence"] = str(directory)
        atomic_json(directory / "command.json", result)
        return result
