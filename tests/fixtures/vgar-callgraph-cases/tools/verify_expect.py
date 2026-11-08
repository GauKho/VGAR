"""Check `# expect:` annotations against runtime targets via sys.setprofile.

Usage: python -I verify_expect.py <repo_root> <source_root>
  source_root: directory whose files map to module names (src/ or repo root).
"""
import os
import re
import runpy
import sys
from collections import defaultdict

EXPECT = re.compile(r"#\s*expect:\s*([^#]+)")


def load_expectations(source_root):
    out = {}
    for dirpath, _, files in os.walk(source_root):
        for name in files:
            if not name.endswith(".py"):
                continue
            path = os.path.realpath(os.path.join(dirpath, name))
            with open(path, encoding="utf-8") as fh:
                for lineno, line in enumerate(fh, 1):
                    m = EXPECT.search(line)
                    if m:
                        names = [n.strip() for n in m.group(1).split(",") if n.strip()]
                        out[(path, lineno)] = names
    return out


def main():
    repo_root, source_root = (os.path.realpath(p) for p in sys.argv[1:3])
    expected = load_expectations(source_root)
    observed = defaultdict(set)

    def in_repo(filename):
        return os.path.realpath(filename).startswith(source_root + os.sep)

    def profiler(frame, event, arg):
        if event == "call":
            caller = frame.f_back
            if caller is None or not in_repo(caller.f_code.co_filename):
                return
            code = frame.f_code
            if in_repo(code.co_filename):
                module = frame.f_globals.get("__name__", "?")
                target = f"{module}.{code.co_qualname}"
            else:
                target = "external"
            observed[(os.path.realpath(caller.f_code.co_filename), caller.f_lineno)].add(target)
        elif event == "c_call":
            if in_repo(frame.f_code.co_filename):
                observed[(os.path.realpath(frame.f_code.co_filename), frame.f_lineno)].add("external")

    sys.path.insert(0, source_root)
    os.chdir(repo_root)
    sys.setprofile(profiler)
    try:
        runpy.run_path(os.path.join(repo_root, "run_all.py"), run_name="__main__")
    finally:
        sys.setprofile(None)

    problems = 0
    for key in sorted(expected):
        exp = expected[key]
        got = observed.get(key, set())
        rel = f"{os.path.relpath(key[0], repo_root)}:{key[1]}"
        if exp == ["unknown"]:
            status = "OK" if got and "external" not in got else "BAD"
        elif exp == ["external"]:
            status = "OK" if got == {"external"} else "BAD"
        else:
            status = "OK" if got == set(exp) else "BAD"
        if status != "OK":
            problems += 1
        print(f"{status:3} {rel:48} expect={exp} got={sorted(got)}")
    print(f"\n{len(expected)} annotated calls, {problems} mismatches")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
