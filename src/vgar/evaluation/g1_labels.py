"""G1 labelled edges (spec 2026-11-16): enumerate call sites and non-call name uses, sample them, write blind sheets.

Items come from ``ast`` on the checkout, never from graph nodes. ``col`` is a byte offset in the RAW file bytes
(what tree-sitter, and so the graph's ``CallSite`` range, count); for UTF-8 files it equals the ``ast`` offset.
Names local to the enclosing function are found from the AST (parameters and bound names), not ``symtable``.
"""
from __future__ import annotations

import ast
import csv
import hashlib
import json
import random
import re
import sys
import tokenize
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from vgar.evaluation.retrieval.chunks import is_source
from vgar.graph.builder import module_name_for

SHEET_COLUMNS = ("item_id", "repo", "task_id", "path", "line", "col", "code", "candidates", "label", "note")
KEYWORDS = ("external", "builtin", "unknown")


@dataclass(frozen=True)
class Definition:
    kind: str
    qualified_name: str
    name: str
    path: str
    line: int
    lines: tuple[int, ...]


@dataclass(frozen=True)
class Item:
    kind: str
    repo: str
    task_id: str
    path: str
    line: int
    col: int
    name: str
    code: str
    enclosing: str
    candidates: tuple[Definition, ...]


@dataclass(frozen=True)
class Label:
    cls: str
    targets: tuple


def production_files(tree: Path) -> list[str]:
    """Repository-relative POSIX paths of production ``.py`` files (no tests, docs, conftest, setup)."""
    found = []
    for path in Path(tree).rglob("*.py"):
        relative = path.relative_to(tree).as_posix()
        if is_source(relative) and PurePosixPath(relative).name not in {"conftest.py", "setup.py"}:
            found.append(relative)
    return sorted(found)


def _read(path: Path) -> tuple[str, str]:
    data = path.read_bytes()
    encoding, _ = tokenize.detect_encoding(__import__("io").BytesIO(data).readline)
    return data.decode(encoding), encoding


def _flat(body):
    """Statements of a module/class body with if/try/with/for/while blocks expanded (definitions kept whole)."""
    for stmt in body:
        yield stmt
        if isinstance(stmt, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith, ast.Try)):
            for field in ("body", "orelse", "finalbody"):
                yield from _flat(getattr(stmt, field, []))
            for handler in getattr(stmt, "handlers", []):
                yield from _flat(handler.body)


def _store_names(stmt):
    targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
    return [t.id for t in targets if isinstance(t, ast.Name)]


def _collect_definitions(module_ast: ast.Module, module: str, path: str, into: dict) -> None:
    """Add this file's definitions to ``into[(kind, qualified_name)] = (name, line, [lines])``."""
    def add(kind, qname, name, line, lines=None):
        entry = into.setdefault((kind, qname, path), [name, line, []])
        entry[2].extend(lines or [line])

    def visit(body, prefix, in_class, at_module):
        for stmt in _flat(body):
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qname = f"{prefix}.{stmt.name}"
                add("method" if in_class else "function", qname, stmt.name, stmt.lineno)
                if in_class and stmt.args.args:
                    self_name = stmt.args.args[0].arg
                    for node in ast.walk(stmt):
                        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, (ast.AnnAssign, ast.AugAssign)) else []
                        for target in targets:
                            if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == self_name:
                                add("field", f"{prefix}.{target.attr}", target.attr, target.lineno)
                visit(stmt.body, qname, False, False)
            elif isinstance(stmt, ast.ClassDef):
                qname = f"{prefix}.{stmt.name}"
                add("class", qname, stmt.name, stmt.lineno)
                visit(stmt.body, qname, True, False)
            elif isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.AugAssign)) and (at_module or in_class):
                for name in _store_names(stmt):
                    add("global" if at_module else "field", f"{prefix}.{name}", name, stmt.lineno)

    visit(module_ast.body, module, False, True)


def _locals(function) -> set[str]:
    names = {a.arg for a in (*function.args.posonlyargs, *function.args.args, *function.args.kwonlyargs)}
    names |= {a.arg for a in (function.args.vararg, function.args.kwarg) if a}
    declared = set()
    for node in ast.walk(function):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            names.add(node.id)
        elif isinstance(node, ast.ExceptHandler) and node.name or isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node is not function:
            names.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names |= {(a.asname or a.name).split(".")[0] for a in node.names}
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            declared |= set(node.names)
    return names - declared


class _Scan(ast.NodeVisitor):
    def __init__(self, module, lines, encoding, aliases):
        self.module, self.lines, self.encoding, self.aliases = module, lines, encoding, aliases
        self.stack: list[tuple[str, set[str]]] = []
        self.skip: set[int] = set()
        self.raw: list[tuple[str, str, int, int, str, str]] = []  # kind, lookup name, line, col, code, enclosing

    def _col(self, node) -> int:
        text = self.lines[node.lineno - 1]
        chars = len(text.encode("utf-8")[:node.col_offset].decode("utf-8", "ignore"))
        return len(text[:chars].encode(self.encoding, "ignore"))

    def _enclosing(self) -> str:
        return self.stack[-1][0] if self.stack else self.module

    def _record(self, kind, name, node):
        self.raw.append((kind, name, node.lineno, self._col(node), self.lines[node.lineno - 1], self._enclosing()))

    def _function(self, node):
        for expr in (*node.decorator_list, *node.args.defaults, *[d for d in node.args.kw_defaults if d]):
            self.visit(expr)
        inherited = set().union(*(frame[1] for frame in self.stack)) if self.stack else set()
        self.stack.append((f"{self._enclosing()}.{node.name}", inherited | _locals(node)))
        for stmt in node.body:
            self.visit(stmt)
        self.stack.pop()

    visit_FunctionDef = visit_AsyncFunctionDef = _function

    def visit_ClassDef(self, node):
        for expr in (*node.decorator_list, *node.bases):
            self.visit(expr)
        self.stack.append((f"{self._enclosing()}.{node.name}", self.stack[-1][1] if self.stack else set()))
        for stmt in node.body:
            self.visit(stmt)
        self.stack.pop()

    def visit_Call(self, node):
        func = node.func
        name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
        if name:
            self._record("call", name, node)
        self.skip.add(id(func))
        self.generic_visit(node)

    def visit_Name(self, node):
        if (isinstance(node.ctx, ast.Load) and id(node) not in self.skip and self.stack
                and node.id not in self.stack[-1][1]):
            self._record("name", node.id, node)

    def visit_Attribute(self, node):
        if isinstance(node.ctx, ast.Load) and id(node) not in self.skip and self.stack:
            self._record("name", node.attr, node)
        self.generic_visit(node)


def scan_repository(tree: Path, *, repo: str, task_id: str, source_roots: tuple[str, ...] = ("src",)):
    """Eligible items (at least one same-name definition) of both kinds, and per-repository statistics."""
    tree = Path(tree)
    parsed, unparsed, definitions = [], [], {}
    for relative in production_files(tree):
        try:
            text, encoding = _read(tree / relative)
            module_ast = ast.parse(text, filename=relative)
        except (SyntaxError, ValueError, UnicodeDecodeError, LookupError):
            unparsed.append(relative)
            continue
        module = module_name_for(relative, source_roots, tree.name)
        _collect_definitions(module_ast, module, relative, definitions)
        parsed.append((relative, module, module_ast, text, encoding))
    by_name: dict[str, list[Definition]] = defaultdict(list)
    for (kind, qname, path), (name, line, lines) in definitions.items():
        by_name[name].append(Definition(kind, qname, name, path, line, tuple(sorted(set(lines)))))
    items, stats = [], {"files": len(parsed), "unparsed_files": unparsed, "calls_total": 0, "calls_eligible": 0,
                        "names_total": 0, "names_eligible": 0}
    for relative, module, module_ast, text, encoding in parsed:
        aliases = {(a.asname or a.name): a.name for stmt in ast.walk(module_ast) if isinstance(stmt, ast.ImportFrom)
                   for a in stmt.names if a.asname}
        scan = _Scan(module, re.split(r"\r\n|\r|\n", text), encoding, aliases)
        scan.visit(module_ast)
        for kind, name, line, col, code, enclosing in scan.raw:
            stats[f"{'calls' if kind == 'call' else 'names'}_total"] += 1
            candidates = tuple(sorted(by_name.get(aliases.get(name, name), ()), key=lambda d: (d.qualified_name, d.line)))
            if candidates:
                stats[f"{'calls' if kind == 'call' else 'names'}_eligible"] += 1
                items.append(Item(kind, repo, task_id, relative, line, col, name, code, enclosing, candidates))
    return items, stats


# ---- sampling and sheets -------------------------------------------------------------------------------------------

def allocate(eligible: dict[str, int], total: int) -> dict[str, int]:
    """Even quota per repository; the remainder goes round-robin to the repositories with the most eligible items."""
    quota = {name: min(total // len(eligible), count) for name, count in eligible.items()}
    order = sorted(eligible, key=lambda name: (-eligible[name], name))
    remaining = total - sum(quota.values())
    while remaining > 0 and any(quota[n] < eligible[n] for n in order):
        for name in order:
            if remaining and quota[name] < eligible[name]:
                quota[name] += 1
                remaining -= 1
    return quota


def sample_items(items: list[Item], kind: str, total: int, seed: int) -> list[Item]:
    pool: dict[str, list[Item]] = defaultdict(list)
    for item in items:
        if item.kind == kind:
            pool[item.repo].append(item)
    quota = allocate({repo: len(rows) for repo, rows in pool.items()}, total)
    chosen = []
    for repo, rows in pool.items():
        rows = sorted(rows, key=lambda i: (i.path, i.line, i.col, i.name))
        chosen += random.Random(f"{seed}:{repo}:{kind}").sample(rows, quota[repo])
    chosen.sort(key=lambda i: (i.repo, i.path, i.line, i.col))
    random.Random(seed).shuffle(chosen)
    return chosen


def _candidates_cell(item: Item) -> str:
    return "; ".join(f"{n}) {d.qualified_name} — {d.path}:{d.line}" for n, d in enumerate(item.candidates, 1))


def write_sheet(path: Path, items: list[Item], prefix: str) -> list[str]:
    ids = [f"{prefix}{n:03d}" for n in range(1, len(items) + 1)]
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, SHEET_COLUMNS)
        writer.writeheader()
        for item_id, item in zip(ids, items):
            writer.writerow({"item_id": item_id, "repo": item.repo, "task_id": item.task_id, "path": item.path,
                             "line": item.line, "col": item.col, "code": item.code,
                             "candidates": _candidates_cell(item), "label": "", "note": ""})
    return ids


def read_sheet(path: Path) -> dict[str, dict]:
    with open(path, encoding="utf-8", newline="") as handle:
        return {row["item_id"]: row for row in csv.DictReader(handle)}


def write_items_md(path: Path, rows: list[tuple[str, Item]], tree_of: dict[str, Path]) -> None:
    out = ["# Items to label", ""]
    cache: dict[str, list[str]] = {}
    for item_id, item in rows:
        key = f"{item.task_id}/{item.path}"
        if key not in cache:
            text, _ = _read(Path(tree_of[item.task_id]) / item.path)
            cache[key] = re.split(r"\r\n|\r|\n", text)
        lines = cache[key]
        out += [f"## {item_id} · {item.kind} `{item.name}` · {item.repo} · {item.path}:{item.line}:{item.col}",
                f"enclosing: `{item.enclosing}`", "", "```python"]
        for number in range(max(1, item.line - 3), min(len(lines), item.line + 3) + 1):
            out.append(f"{'>>' if number == item.line else '  '} {number:5d} | {lines[number - 1]}")
        out += ["```", "candidates:"]
        out += [f"{n}. `{d.qualified_name}` ({d.kind}) — {d.path}:{d.line}" for n, d in enumerate(item.candidates, 1)]
        out.append("")
    Path(path).write_text("\n".join(out), encoding="utf-8")


def agreement_ids(call_ids: list[str], name_ids: list[str], k: int = 15, seed: int = 1) -> list[str]:
    rng = random.Random(seed)
    return (rng.sample(sorted(call_ids), min(k, len(call_ids))) + rng.sample(sorted(name_ids), min(k, len(name_ids))))


def write_agreement_sheet(path: Path, main_rows: dict[str, dict], ids: list[str], seed: int = 1) -> None:
    order = sorted(ids)
    random.Random(seed).shuffle(order)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, SHEET_COLUMNS)
        writer.writeheader()
        for item_id in order:
            writer.writerow({**main_rows[item_id], "label": "", "note": ""})


# ---- labels and lock -----------------------------------------------------------------------------------------------

def parse_label(text: str, candidates: tuple[Definition, ...]) -> Label:
    value = (text or "").strip()
    if not value:
        raise ValueError("empty label")
    if value.lower() in KEYWORDS:
        return Label(value.lower(), ())
    if value.lower().startswith("other:"):
        qname = value[6:].strip()
        if not qname:
            raise ValueError("other: needs a qualified name")
        return Label("in_repo", (qname,))
    numbers = [part.strip() for part in value.split(";")]
    if not all(part.isdigit() and 1 <= int(part) <= len(candidates) for part in numbers):
        raise ValueError(f"invalid label {text!r}")
    targets = []
    for part in numbers:
        if candidates[int(part) - 1] not in targets:
            targets.append(candidates[int(part) - 1])
    return Label("in_repo", tuple(targets))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def item_to_dict(item: Item) -> dict:
    return asdict(item)


def item_from_dict(data: dict) -> Item:
    candidates = tuple(Definition(**{**c, "lines": tuple(c["lines"])}) for c in data["candidates"])
    return Item(**{**data, "candidates": candidates})


SHEETS = ("calls.csv", "name_uses.csv")


def _manifest(out: Path) -> dict:
    return json.loads((Path(out) / "manifest.json").read_text(encoding="utf-8"))


def lock(out: Path, items_by_id: dict[str, Item]) -> None:
    """Validate every label, then record each sheet's SHA-256 in ``manifest.json`` (history appended)."""
    out, invalid = Path(out), []
    for sheet in SHEETS:
        for item_id, row in read_sheet(out / sheet).items():
            try:
                parse_label(row["label"], items_by_id[item_id].candidates)
            except ValueError:
                invalid.append(item_id)
    if invalid:
        raise ValueError(f"invalid labels: {invalid}")
    manifest = _manifest(out)
    now = datetime.now(UTC).isoformat()
    manifest["locks"] += [{"sheet": s, "sha256": sha256_file(out / s), "at": now} for s in SHEETS]
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def check_lock(out: Path, sheet: str) -> None:
    locks = [entry for entry in _manifest(out)["locks"] if entry["sheet"] == sheet]
    if not locks:
        raise ValueError(f"{sheet} is not locked")
    if locks[-1]["sha256"] != sha256_file(Path(out) / sheet):
        raise ValueError(f"{sheet} differs from its locked version")


# ---- matching to the graph, metrics, agreement ---------------------------------------------------------------------

READS_RULE = "python.layer1.reads.v1"
_CALLABLE = {"Function", "Method", "Class"}
_VARIABLE = {"GlobalVariable", "Field"}


class GraphIndex:
    """Lookups the evaluator needs on one graph document."""

    def __init__(self, document: dict):
        self.nodes = {n["id"]: n for n in document["nodes"]}
        self.by_path_name: dict[tuple[str, str], list[dict]] = defaultdict(list)
        self.by_qname: dict[str, str] = {}
        self.callsites: dict[tuple[str, int, int], list[dict]] = defaultdict(list)
        self.functions: dict[str, list[dict]] = defaultdict(list)
        for node in document["nodes"]:
            self.by_path_name[(node.get("path"), node.get("name"))].append(node)
            self.by_qname.setdefault(node.get("qualified_name"), node["id"])
            if node["type"] == "CallSite" and node.get("range"):
                r = node["range"]
                # Chained calls (super().f(), a.b().c()) share their start: keep every CallSite there.
                self.callsites[(node["path"], r["start_line"], r["start_col"])].append(node)
            elif node["type"] in {"Function", "Method"} and node.get("range"):
                self.functions[node["path"]].append(node)
        self.out: dict[str, list[dict]] = defaultdict(list)
        for edge in document["edges"]:
            self.out[edge["source_id"]].append(edge)

    @staticmethod
    def _span(node) -> int:
        return node["range"]["end_line"] - node["range"]["start_line"]

    def nodes_for(self, target) -> set[str]:
        """Every graph node a candidate can stand for: one per definition line it merges (if/else defs, overloads)."""
        if isinstance(target, str):
            return {self.by_qname[target]} if target in self.by_qname else set()
        found = set()
        for node in self.by_path_name.get((target.path, target.name), ()):
            if not node.get("range"):
                continue
            r = node["range"]
            if target.kind in {"function", "method", "class"} and node["type"] in _CALLABLE:
                if any(r["start_line"] <= line <= r["end_line"] for line in target.lines):
                    found.add(node["id"])
            elif target.kind in {"global", "field"} and node["type"] in _VARIABLE:
                lines = set(node.get("properties", {}).get("assignment_lines") or [r["start_line"]])
                if lines & set(target.lines):
                    found.add(node["id"])
        return found

    def node_for(self, target) -> str | None:
        if isinstance(target, str):
            return self.by_qname.get(target)
        found = []
        for node in self.by_path_name.get((target.path, target.name), ()):
            if not node.get("range"):
                continue
            r = node["range"]
            if target.kind in {"function", "method", "class"} and node["type"] in _CALLABLE:
                if r["start_line"] <= target.line <= r["end_line"]:
                    found.append(node)
            elif target.kind in {"global", "field"} and node["type"] in _VARIABLE:
                lines = set(node.get("properties", {}).get("assignment_lines") or [r["start_line"]])
                if lines & set(target.lines):
                    found.append(node)
        return min(found, key=self._span)["id"] if found else None

    def call_targets(self, item: Item) -> tuple[bool, set[str], set[str]]:
        sites = self.callsites.get((item.path, item.line, item.col), [])
        if len(sites) > 1:  # chained call: the CallSite whose callee is this item's name, else the outermost
            named = [n for n in sites if n.get("name") == item.name
                     or str(n.get("properties", {}).get("callee_text", "")).rsplit(".", 1)[-1] == item.name]
            sites = named or sites
        if not sites:
            return False, set(), set()
        site = max(sites, key=lambda n: (n["range"]["end_line"], n["range"]["end_col"]))["id"]
        calls = {e["target_id"] for e in self.out[site] if e["type"] == "CALLS"}
        may = {e["target_id"] for e in self.out[site] if e["type"] == "MAY_CALL"}
        return True, calls, calls | may

    def enclosing(self, item: Item) -> str | None:
        around = [n for n in self.functions.get(item.path, ())
                  if n["range"]["start_line"] <= item.line <= n["range"]["end_line"]]
        return min(around, key=self._span)["id"] if around else None

    def name_targets(self, item: Item) -> set[str]:
        enclosing = self.enclosing(item)
        if enclosing is None:
            return set()
        return {e["target_id"] for e in self.out[enclosing]
                if e["type"] == "REFERENCES" and e["provenance"]["rule_id"] == READS_RULE
                and self.nodes.get(e["target_id"], {}).get("name") == item.name}


@dataclass
class Scored:
    item_id: str
    kind: str
    repo: str
    label: Label
    truth: set
    predicted: set
    status: str
    unmapped: int


def score_item(index: GraphIndex, item_id: str, item: Item, label: Label, *, may_call: bool = False) -> Scored:
    found, outside = True, False
    if item.kind == "call":
        found, calls, both = index.call_targets(item)
        predicted = both if may_call else calls
    else:
        outside = index.enclosing(item) is None
        predicted = index.name_targets(item)
    truth, unmapped = set(), 0
    for target in label.targets:
        nodes = index.nodes_for(target)
        if not nodes:
            unmapped += 1
            truth.add(f"unmapped:{target if isinstance(target, str) else target.qualified_name}")
        else:  # one target per candidate: hit when any of its nodes is predicted
            truth.add(min(nodes & predicted) if nodes & predicted else min(nodes))
    if outside:
        status = "outside_function"
    elif not found:
        status = "no_callsite"
    elif not predicted:
        status = "no_edge" if truth else "right"
    elif predicted == truth:
        status = "right"
    elif predicted & truth:
        status = "partial"
    else:
        status = "wrong"
    return Scored(item_id, item.kind, item.repo, label, truth, predicted, status, unmapped)


def bom_adjusted(item: Item, tree: Path) -> Item:
    """Undo the kit's BOM offset: it added 3 bytes on every line of a UTF-8-with-BOM file, tree-sitter only on line 1."""
    with open(Path(tree) / item.path, "rb") as handle:
        bom = handle.read(3) == b"\xef\xbb\xbf"
    if bom and item.line != 1:
        from dataclasses import replace
        return replace(item, col=item.col - 3)
    return item


def _pr(rows) -> tuple[int, int, int]:
    tp = sum(len(r.truth & r.predicted) for r in rows)
    return tp, sum(len(r.predicted) for r in rows) - tp, sum(len(r.truth) for r in rows) - tp


def micro_pr(rows: list[Scored]) -> dict:
    """Micro P/R over items, with a 95 % bootstrap interval (2,000 resamples, seed 7)."""
    tp, fp, fn = _pr(rows)
    ratio = lambda a, b: a / b if b else None
    out = {"n": len(rows), "tp": tp, "fp": fp, "fn": fn, "precision": ratio(tp, tp + fp), "recall": ratio(tp, tp + fn),
           "precision_ci95": None, "recall_ci95": None}
    if rows:
        rng, ps, rs = random.Random(7), [], []
        for _ in range(2000):
            t, f, n = _pr([rows[rng.randrange(len(rows))] for _ in rows])
            if t + f:
                ps.append(t / (t + f))
            if t + n:
                rs.append(t / (t + n))
        for key, values in (("precision_ci95", ps), ("recall_ci95", rs)):
            if values:
                values.sort()
                out[key] = [values[int(0.025 * len(values))], values[int(0.975 * len(values)) - 1]]
    return out


def _target_key(target):
    return target if isinstance(target, str) else (target.qualified_name, target.path, target.line)


def agreement(claude: dict[str, Label], user: dict[str, Label]) -> dict:
    """Raw agreement, Cohen's kappa on the label class, and equality of in-repo target sets."""
    ids = sorted(set(claude) & set(user))
    same = lambda a, b: a.cls == b.cls and (a.cls != "in_repo" or {_target_key(t) for t in a.targets} == {_target_key(t) for t in b.targets})
    disagreements = [i for i in ids if not same(claude[i], user[i])]
    n = len(ids)
    observed = sum(claude[i].cls == user[i].cls for i in ids) / n if n else None
    classes = {claude[i].cls for i in ids} | {user[i].cls for i in ids}
    expected = sum((sum(claude[i].cls == c for i in ids) / n) * (sum(user[i].cls == c for i in ids) / n) for c in classes) if n else None
    kappa = None if not n or expected == 1 else (observed - expected) / (1 - expected)
    in_repo = [i for i in ids if claude[i].cls == user[i].cls == "in_repo"]
    return {"n": n, "raw": (n - len(disagreements)) / n if n else None, "kappa": kappa,
            "target_equal_in_repo": (sum(i not in disagreements for i in in_repo), len(in_repo)),
            "disagreements": disagreements}


DEFAULT_AGREEMENT_SHEET = "agreement_user.csv"


@dataclass
class AgreementOutcome:
    """Result of checking one agreement sheet: ``exit_code`` None means go on with ``labels``."""

    exit_code: int | None
    report: dict
    labels: dict


def _sheet_files(sheet: str) -> tuple[str, str]:
    """Disagreement and settlement file names of an agreement sheet (plan 2026-11-17 Task 2)."""
    if sheet == DEFAULT_AGREEMENT_SHEET:
        return "disagreements.csv", "settlement.csv"
    stem = PurePosixPath(sheet).stem
    return f"disagreements_{stem}.csv", f"settlement_{stem}.csv"


HUMAN_AGREEMENT_SHEET = "agreement_human.csv"
_KNOWN_SHEETS = {DEFAULT_AGREEMENT_SHEET: DEFAULT_AGREEMENT_SHEET, HUMAN_AGREEMENT_SHEET: HUMAN_AGREEMENT_SHEET}


def run_agreements(kit: Path, sheet: str, manifest: dict, items: dict, labels: dict, main_rows: dict) -> AgreementOutcome:
    """Check ``sheet``; for the human sheet, first apply the locked default sheet's settlement.

    The human sheet is compared with Claude's own labels, but the final labels keep the settlement of the earlier
    Claude second pass, so a human run never silently changes the locked G1 numbers.
    """
    if _KNOWN_SHEETS.get(sheet.lower()) != HUMAN_AGREEMENT_SHEET:
        return check_agreement(kit, sheet, manifest, items, labels, main_rows)
    default = check_agreement(kit, DEFAULT_AGREEMENT_SHEET, manifest, items, labels, main_rows)
    if default.exit_code is not None:
        return default
    human = check_agreement(kit, sheet, manifest, items, labels, main_rows, prior=default.labels)
    human.report["default_settlement"] = default.report["settlement"]
    return human


def check_agreement(kit: Path, sheet: str, manifest: dict, items: dict, labels: dict, main_rows: dict, *,
                    prior: dict | None = None) -> AgreementOutcome:
    """Compare one agreement sheet with Claude's labels, lock it on first use, apply its settlement.

    The default sheet (``agreement_user.csv``, a second Claude pass) keeps its lock in ``manifest["agreement_lock"]``;
    any other sheet is a human labeller's and is locked in ``manifest["agreement_locks"][sheet]`` with its own
    disagreement and settlement files.

    Args:
        kit: Kit folder.
        sheet: Agreement sheet file name inside ``kit``.
        manifest: Parsed ``manifest.json``; written back when a lock is added.
        items: Item id -> Item.
        labels: Claude's labels (item id -> Label); not changed.
        main_rows: Rows of ``calls.csv`` and ``name_uses.csv``.
        prior: Labels the final labels start from (default: ``labels``); comparisons always use ``labels``.
    """
    known = _KNOWN_SHEETS.get(sheet.lower())
    if known is None:  # only the two kit sheets: a renamed copy would get a fresh lock and fresh disagreements
        print(f"refused: agreement sheet must be {sorted(_KNOWN_SHEETS)}, got {sheet!r}", file=sys.stderr)
        return AgreementOutcome(2, {"agreement": None, "agreement_sheet": sheet}, dict(labels))
    sheet = known
    human = sheet != DEFAULT_AGREEMENT_SHEET
    report = {"agreement": None, "agreement_source": "human" if human else "claude_second_pass",
              "agreement_sheet": sheet, "settlement": {"sha256": None, "changed": []}}
    final = dict(prior if prior is not None else labels)
    path = Path(kit) / sheet
    rows = read_sheet(path) if path.exists() else {}
    filled = [i for i, row in rows.items() if row["label"].strip()]
    if not filled:
        report["agreement_status"] = f"not done: {sheet} has no labels"
        return AgreementOutcome(None, report, final)

    def refuse(problem: str) -> AgreementOutcome:
        print(f"refused: {problem}", file=sys.stderr)
        return AgreementOutcome(2, report, final)

    if len(filled) != len(rows):
        return refuse(f"{sheet} is partly filled; empty: {sorted(set(rows) - set(filled))}")
    invalid = []
    for item_id in filled:
        try:
            parse_label(rows[item_id]["label"], items[item_id].candidates)
        except (ValueError, KeyError):
            invalid.append(item_id)
    if invalid:
        return refuse(f"invalid labels in {sheet}: {invalid}")
    digest = sha256_file(path)
    locks = manifest.setdefault("agreement_locks", {}) if human else None
    locked = locks.get(sheet) if human else manifest.get("agreement_lock")
    if locked is not None and locked != digest:
        return refuse(f"{sheet} changed after it was first used")
    if locked is None:  # fixed on first use, so it cannot be edited after seeing disagreements
        if human:
            locks[sheet] = digest
        else:
            manifest["agreement_lock"] = digest
        (Path(kit) / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    other = {i: parse_label(row["label"], items[i].candidates) for i, row in rows.items()}
    result = agreement({i: labels[i] for i in other}, other)
    report["agreement"] = result
    disagreements_name, settlement_name = _sheet_files(sheet)
    settled = {}
    settlement_path = Path(kit) / settlement_name
    if settlement_path.exists():
        with open(settlement_path, encoding="utf-8", newline="") as handle:
            settled = {row["item_id"]: row["final_label"] for row in csv.DictReader(handle) if row.get("final_label", "").strip()}
        report["settlement"]["sha256"] = sha256_file(settlement_path)
        outside = sorted(set(settled) - set(result["disagreements"]))
        if outside:
            return refuse(f"{settlement_name} may only settle disagreements; not disagreements: {outside}")
    missing = [i for i in result["disagreements"] if i not in settled]
    if missing:
        with open(Path(kit) / disagreements_name, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, ["item_id", "code", "candidates", "claude_label", "user_label", "final_label"])
            writer.writeheader()
            for item_id in result["disagreements"]:
                writer.writerow({"item_id": item_id, "code": main_rows[item_id]["code"],
                                 "candidates": main_rows[item_id]["candidates"], "claude_label": main_rows[item_id]["label"],
                                 "user_label": rows[item_id]["label"], "final_label": ""})
        print(f"{len(missing)} disagreement(s) to settle: fill final_label in {Path(kit) / disagreements_name} "
              f"and save it as {settlement_path}", file=sys.stderr)
        return AgreementOutcome(3, report, final)
    for item_id, value in settled.items():
        label = parse_label(value, items[item_id].candidates)
        if label != labels[item_id]:
            report["settlement"]["changed"].append(item_id)
        final[item_id] = label
    return AgreementOutcome(None, report, final)
