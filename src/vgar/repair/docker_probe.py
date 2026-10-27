"""Stdlib target driver; Python 3.6+, no VGAR install in benchmark images."""

import ast
import hashlib
import json
import os
import platform
import subprocess
import sys
import tarfile
import traceback


def sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def safe_name(name):
    if (
        not name
        or name.startswith(("/", "-"))
        or any(c in name for c in ("\\", ":", "\0", "\n", "\r"))
        or any(p in ("", ".", "..", ".git") for p in name.split("/"))
    ):
        raise ValueError("Unsafe snapshot member")
    return name


def attest_snapshot(root, expected):
    observed = {}
    for relative, expected_hash in expected.items():
        safe_name(relative)
        path = os.path.join(root, relative)
        current = root
        for part in relative.split("/"):
            current = os.path.join(current, part)
            if os.path.islink(current):
                raise ValueError("Snapshot contains a link")
        with open(path, "rb") as stream:
            observed[relative] = sha(stream.read())
        if observed[relative] != expected_hash:
            raise ValueError("Execution snapshot drift: " + relative)
    return observed


def load_snapshot(archive, root, expected):
    with tarfile.open(archive, "r") as stream:
        members = stream.getmembers()
        names = [safe_name(m.name) for m in members]
        if (
            len(names) != len(set(names))
            or set(names) != set(expected)
            or any(not m.isfile() for m in members)
        ):
            raise ValueError("Snapshot must contain exactly the approved regular files")
        for member in members:
            target = os.path.join(root, member.name)
            parent = os.path.dirname(target)
            current = root
            for part in member.name.split("/"):
                current = os.path.join(current, part)
                if os.path.islink(current):
                    raise ValueError("Snapshot path traverses a link")
            if not os.path.isdir(parent):
                os.makedirs(parent)
            raw = stream.extractfile(member).read()
            if sha(raw) != expected[member.name]:
                raise ValueError("Snapshot member hash mismatch")
            with open(target, "wb") as output:
                output.write(raw)
    return attest_snapshot(root, expected)


def syntax_report(root, targets):
    diagnostics = []
    for relative in targets:
        safe_name(relative)
        with open(os.path.join(root, relative), "rb") as stream:
            raw = stream.read()
        try:
            ast.parse(raw, filename=relative)
        except SyntaxError as error:
            diagnostics.append(
                dict(
                    tool="syntax",
                    path=relative,
                    line=error.lineno or 1,
                    column=error.offset or 1,
                    code="SyntaxError",
                    severity="error",
                    message=error.msg,
                )
            )
    return dict(tool_version=platform.python_version(), diagnostics=diagnostics)


def base_identity(root):
    def git(*args):
        return (
            subprocess.check_output(
                ["git", "--no-replace-objects", "-C", root] + list(args)
            )
            .decode("utf-8")
            .strip()
        )

    paths = sorted(p for p in git("ls-files", "-z", "--", "*.py").split("\0") if p)
    files = []
    for relative in paths:
        safe_name(relative)
        path = os.path.join(root, relative)
        if os.path.islink(path):
            raise ValueError("Linked base Python source")
        with open(path, "rb") as stream:
            files.append([relative, hashlib.sha256(stream.read()).hexdigest()])
    return dict(
        head=git("rev-parse", "HEAD"),
        clean=not bool(git("status", "--porcelain", "--untracked-files=no")),
        inventory_hash=sha(
            json.dumps(files, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ),
        inventory_count=len(files),
    )


def run(config):
    result = dict(
        protocol="vgar-docker-repair-v1",
        complete=False,
        exit_code=None,
        runtime=dict(python=platform.python_version(), executable=sys.executable),
        base=None,
        snapshot_before=None,
        snapshot_after=None,
        argv=config.get("argv"),
        syntax=None,
    )
    root = config["root"]
    try:
        import pytest

        result["runtime"]["pytest"] = pytest.__version__
        if result["runtime"] != config["runtime"]:
            raise ValueError("Target interpreter version/identity mismatch")
        # Only the fresh owned container is reset, before loading private patched bytes.
        subprocess.check_call(
            [
                "git",
                "--no-replace-objects",
                "-C",
                root,
                "reset",
                "-q",
                "--hard",
                config["base_commit"],
            ],
            stdout=subprocess.DEVNULL,
        )
        result["base"] = base_identity(root)
        if result["base"] != config["base_identity"]:
            raise ValueError("Image base source differs from qualified profile")
        result["snapshot_before"] = load_snapshot(
            config["archive"], root, config["expected"]
        )
        os.chdir(root)
        if config["kind"] == "syntax":
            result["syntax"] = syntax_report(root, config["targets"])
            result["exit_code"] = 0 if not result["syntax"]["diagnostics"] else 1
        elif config["kind"] == "command":
            env = os.environ.copy()
            env.update(
                PYTHONPATH="/vgar",
                PYTHONDONTWRITEBYTECODE="1",
                PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
                PYTHONUTF8="1",
            )
            result["exit_code"] = subprocess.call(config["argv"], cwd=root, env=env)
        else:
            raise ValueError("Unsupported target operation")
        result["snapshot_after"] = attest_snapshot(root, config["expected"])
        result["complete"] = True
    except BaseException:
        result.update(complete=False, traceback=traceback.format_exc())
    return result


def main():
    with open(sys.argv[1]) as stream:
        config = json.load(stream)
    result = run(config)
    with open(sys.argv[2], "x") as stream:
        json.dump(result, stream, ensure_ascii=True, indent=2)
    return result["exit_code"] if result["complete"] else 97


if __name__ == "__main__":
    sys.exit(main())
