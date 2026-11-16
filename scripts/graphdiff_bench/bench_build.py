"""Build a labelled GraphDiff benchmark from the shopflow ground truth.

Each scenario is two commits on one linear branch: P (17 bugs: one bug injected into reference_fixed) then
C (the fix, optionally tangled with one known refactoring and/or one formatting-only change). Only C is
evaluated; its gold labels are computed from the known components, never from a tool under test.
"""
from __future__ import annotations

import ast
import difflib
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import tokenize
from pathlib import Path

# Work folder (benchmark git repo, tool downloads, outputs): outside this repository on purpose.
WORK = Path(os.environ.get("VGAR_GRAPHDIFF_WORK", Path(tempfile.gettempdir()) / "vgar-graphdiff-bench"))
GT = Path(os.environ.get("SHOPFLOW_GROUND_TRUTH", r"D:\kltn\shopflow-ground-truth\ground_truth"))
REF = GT / "reference_fixed" / "shopflow"
VGAR = Path(__file__).resolve().parents[2]
REPO = WORK / "bench" / "repo"
sys.path.insert(0, str(GT / "tools"))
from bugs import BUGS

Tree = dict[str, str]  # "shopflow/..." -> text


def load_ref() -> Tree:
    return {f"shopflow/{p.relative_to(REF).as_posix()}": p.read_text(encoding="utf-8")
            for p in sorted(REF.rglob("*.py")) if "__pycache__" not in p.parts}


def sub(tree: Tree, path: str, old: str, new: str, count: int | None = 1) -> None:
    text = tree[path]
    n = text.count(old)
    assert n >= 1 and (count is None or n == count), (path, old[:60], n)
    tree[path] = text.replace(old, new)


# ---------------------------------------------------------------- refactorings (gold type, entity names)
ORDER_WEIGHT = '''def order_weight(order: Order, products: ProductRepository) -> Decimal:
    return sum(
        (products.require(line.sku).weight_kg * line.quantity for line in order.lines),
        Decimal("0"),
    )


'''


def r_rename_percent(t):
    sub(t, "shopflow/utils/money.py", "def percent_of(", "def percentage_of(")
    sub(t, "shopflow/services/pricing.py", "percent_of", "percentage_of", None)


def r_rename_estimate(t):
    sub(t, "shopflow/services/shipping.py", "def estimate_delivery(", "def estimate_delivery_date(")
    sub(t, "shopflow/services/order_service.py", "estimate_delivery", "estimate_delivery_date", 2)


def r_extract_discount(t):
    p = "shopflow/services/pricing.py"
    sub(t, p, "    rate = combine_rates(tier_discount_rate(customer.tier), coupon_rate(coupon_code))\n"
              "    discount = percent_of(subtotal, rate)\n",
        "    discount = _discount_for(subtotal, customer, coupon_code)\n")
    sub(t, p, "def quote_order(",
        "def _discount_for(subtotal: Decimal, customer: Customer, coupon_code: Optional[str]) -> Decimal:\n"
        "    rate = combine_rates(tier_discount_rate(customer.tier), coupon_rate(coupon_code))\n"
        "    return percent_of(subtotal, rate)\n\n\ndef quote_order(")


def r_move_weight(t):
    sub(t, "shopflow/services/pricing.py", ORDER_WEIGHT, "")
    sub(t, "shopflow/services/pricing.py", "from shopflow.services.shipping import shipping_fee",
        "from shopflow.services.shipping import order_weight, shipping_fee")
    s = "shopflow/services/shipping.py"
    sub(t, s, "from shopflow import config\n",
        "from shopflow import config\nfrom shopflow.models.order import Order\n"
        "from shopflow.repositories.product_repo import ProductRepository\n")
    t[s] = t[s].rstrip("\n") + "\n\n\n" + ORDER_WEIGHT.rstrip("\n") + "\n"


def r_rename_param(t):
    p = "shopflow/utils/validators.py"
    sub(t, p, "def validate_quantity(quantity) -> int:", "def validate_quantity(qty) -> int:")
    sub(t, p, "    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:\n"
              "        raise ValidationError(f\"invalid quantity: {quantity!r}\")\n    return quantity\n",
        "    if isinstance(qty, bool) or not isinstance(qty, int) or qty <= 0:\n"
        "        raise ValidationError(f\"invalid quantity: {qty!r}\")\n    return qty\n")


def r_rename_class(t):
    sub(t, "shopflow/services/notifications.py", "class Notifier:", "class NotificationService:")
    sub(t, "shopflow/app.py", "Notifier", "NotificationService", 3)
    sub(t, "shopflow/services/order_service.py", "Notifier", "NotificationService", 2)


def r_rename_var(t):
    p = "shopflow/services/reporting.py"
    sub(t, p, "    counter: Counter = Counter()\n", "    sku_counts: Counter = Counter()\n")
    sub(t, p, "            counter[line.sku] += line.quantity\n    ranked = sorted(counter.items(),",
        "            sku_counts[line.sku] += line.quantity\n    ranked = sorted(sku_counts.items(),")


def r_inline_tier(t):
    sub(t, "shopflow/services/discount.py",
        "def tier_discount_rate(tier: str) -> Decimal:\n    return config.TIER_DISCOUNTS.get(tier, ZERO)\n\n\n", "")
    p = "shopflow/services/pricing.py"
    sub(t, p, "from shopflow.services.discount import combine_rates, coupon_rate, tier_discount_rate",
        "from shopflow.services.discount import ZERO, combine_rates, coupon_rate")
    sub(t, p, "combine_rates(tier_discount_rate(customer.tier), coupon_rate(coupon_code))",
        "combine_rates(config.TIER_DISCOUNTS.get(customer.tier, ZERO), coupon_rate(coupon_code))")


REFACTORINGS = [  # (id, function, family, entity names, files touched)
    ("R1", r_rename_percent, "rename_method", ["percent_of", "percentage_of"], {"money.py", "pricing.py"}),
    ("R2", r_rename_estimate, "rename_method", ["estimate_delivery", "estimate_delivery_date"],
     {"shipping.py", "order_service.py"}),
    ("R3", r_extract_discount, "extract_method", ["_discount_for", "quote_order"], {"pricing.py"}),
    ("R4", r_move_weight, "move_method", ["order_weight"], {"pricing.py", "shipping.py"}),
    ("R5", r_rename_param, "rename_parameter", ["quantity", "qty"], {"validators.py"}),
    ("R6", r_rename_class, "rename_class", ["Notifier", "NotificationService"],
     {"notifications.py", "app.py", "order_service.py"}),
    ("R7", r_rename_var, "rename_variable", ["counter", "sku_counts"], {"reporting.py"}),
    ("R8", r_inline_tier, "inline_method", ["tier_discount_rate"], {"discount.py", "pricing.py"}),
]

FORMAT_TARGETS = [
    ("shopflow/models/product.py", "Product.to_dict"),
    ("shopflow/models/customer.py", "Customer.to_dict"),
    ("shopflow/repositories/product_repo.py", "ProductRepository.search"),
    ("shopflow/services/reporting.py", "revenue_by_day"),
    ("shopflow/services/inventory.py", "InventoryService.restock"),
    ("shopflow/models/order.py", "Order.to_dict"),
]


# ---------------------------------------------------------------- symbols
def definitions(text: str) -> list[tuple[str, int, int]]:
    out = []

    def walk(body, scope):
        for node in body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                name = scope + node.name
                start = min([node.lineno] + [d.lineno for d in node.decorator_list])
                out.append((name, start, node.end_lineno))
                if isinstance(node, ast.ClassDef):
                    walk(node.body, name + ".")
    walk(ast.parse(text).body, "")
    return out


def enclosing(defs, line: int) -> str:
    best = None
    for name, start, end in defs:
        if start <= line <= end and (best is None or end - start < best[2] - best[1]):
            best = (name, start, end)
    return best[0] if best else "<module>"


def changed_symbols(before: Tree, after: Tree) -> set[str]:
    out = set()
    for path in sorted(before.keys() | after.keys()):
        a, b = before.get(path, ""), after.get(path, "")
        if a == b:
            continue
        al, bl = a.splitlines(), b.splitlines()
        da, db = definitions(a), definitions(b)
        for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, al, bl, autojunk=False).get_opcodes():
            if tag == "equal":
                continue
            out |= {f"{path}::{enclosing(da, i + 1)}" for i in range(i1, i2) if al[i].strip()}
            out |= {f"{path}::{enclosing(db, j + 1)}" for j in range(j1, j2) if bl[j].strip()}
    return out


def format_only(tree: Tree, path: str, qualname: str) -> None:
    """Comment line + double->single quotes inside one function; the AST must not change."""
    text = tree[path]
    (_name, start, end), = [d for d in definitions(text) if d[0] == qualname]
    lines = text.splitlines(keepends=True)
    tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    for tok in reversed(tokens):
        s = tok.string
        if (tok.type == tokenize.STRING and start <= tok.start[0] <= end and tok.start[0] == tok.end[0]
                and s.startswith('"') and not s.startswith('"""') and "'" not in s and "\\" not in s):
            row, col = tok.start[0] - 1, tok.start[1]
            lines[row] = lines[row][:col] + "'" + s[1:-1] + "'" + lines[row][col + len(s):]
    node = next(n for n in ast.walk(ast.parse(text)) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                and n.lineno >= start and n.name == qualname.split(".")[-1])
    first = node.body[0].lineno - 1
    indent = lines[first][: len(lines[first]) - len(lines[first].lstrip())]
    lines.insert(first, f"{indent}# formatting-only change (style pass)\n")
    new = "".join(lines)
    assert ast.dump(ast.parse(new)) == ast.dump(ast.parse(text)), (path, qualname)
    assert new != text
    tree[path] = new


# ---------------------------------------------------------------- git
def git(*args: str, cwd: Path = REPO) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "bench", "GIT_AUTHOR_EMAIL": "bench@example.invalid",
           "GIT_COMMITTER_NAME": "bench", "GIT_COMMITTER_EMAIL": "bench@example.invalid",
           "GIT_AUTHOR_DATE": "2026-11-14T00:00:00", "GIT_COMMITTER_DATE": "2026-11-14T00:00:00"}
    return subprocess.run(["git", "-c", "core.autocrlf=false", "-c", "commit.gpgsign=false", *args], cwd=cwd,
                          env=env, check=True, capture_output=True, text=True).stdout.strip()


def commit_tree(tree: Tree, message: str) -> str:
    shutil.rmtree(REPO / "shopflow", ignore_errors=True)
    for path, text in tree.items():
        target = REPO / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")
    git("add", "-A")
    git("commit", "-q", "--allow-empty", "-m", message)
    return git("rev-parse", "HEAD")


def importable(tree: Tree) -> None:
    tmp = WORK / "bench" / "check"
    shutil.rmtree(tmp, ignore_errors=True)
    for path, text in tree.items():
        (tmp / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp / path).write_text(text, encoding="utf-8")
    subprocess.run([sys.executable, "-B", "-c", "import shopflow.app; shopflow.app.build_app()"], cwd=tmp,
                   check=True, capture_output=True)
    shutil.rmtree(tmp)


def main() -> None:
    ref = load_ref()
    if (WORK / "bench").exists():  # Git marks objects read-only on Windows
        shutil.rmtree(WORK / "bench", onerror=lambda f, p, _: (os.chmod(p, stat.S_IWRITE), f(p)))
    REPO.mkdir(parents=True)
    git("init", "-q", "-b", "main")
    commit_tree(ref, "base: reference_fixed")
    scenarios = []
    for k, bug in enumerate(BUGS):
        buggy = dict(ref)
        for rel, fixed, wrong in bug["edits"]:
            sub(buggy, rel, fixed, wrong)
        bug_files = {Path(rel).name for rel, *_ in bug["edits"]}
        gold_fix = changed_symbols(buggy, ref)
        for variant in ("pure", "format", "refactor", "refactor+format"):
            child, gold_ref, gold_fmt, refactoring = dict(ref), set(), set(), None
            if "refactor" in variant:
                for j in range(len(REFACTORINGS)):
                    rid, fn, family, names, files = REFACTORINGS[(k + j) % len(REFACTORINGS)]
                    if not files & bug_files:
                        break
                fn(child)
                gold_ref = changed_symbols(ref, child)
                refactoring = {"id": rid, "family": family, "entities": names}
            if "format" in variant:
                busy = bug_files | (set(refactoring and REFACTORINGS[int(rid[1:]) - 1][4] or ()))
                path, qual = next(t for i in range(len(FORMAT_TARGETS))
                                  for t in [FORMAT_TARGETS[(k + i) % len(FORMAT_TARGETS)]]
                                  if Path(t[0]).name not in busy)
                before_fmt = dict(child)
                format_only(child, path, qual)
                gold_fmt = changed_symbols(before_fmt, child)
            importable(child)
            assert not (gold_fix & (gold_ref | gold_fmt)), (bug["id"], variant)
            parent_sha = commit_tree(buggy, f"setup {bug['id']} {variant}: inject bug")
            sha = commit_tree(child, f"fix {bug['id']} ({variant})")
            scenarios.append({"sha": sha, "parent": parent_sha, "bug": bug["id"], "variant": variant,
                              "gold_bugfix": sorted(gold_fix), "gold_refactor": sorted(gold_ref),
                              "gold_format": sorted(gold_fmt), "refactoring": refactoring})
    # real history sample: 30 most recent first-parent commits of this repository that touch Python files
    shas = subprocess.run(["git", "log", "--first-parent", "--format=%H", "-n", "30", "--", "*.py"], cwd=VGAR,
                          check=True, capture_output=True, text=True).stdout.split()
    history = []
    for sha in shas:
        files = subprocess.run(["git", "diff-tree", "--no-commit-id", "-r", "--name-status", f"{sha}^", sha],
                               cwd=VGAR, check=True, capture_output=True, text=True).stdout.splitlines()
        pairs = [line.split("\t")[1] for line in files if line.startswith("M\t") and line.endswith(".py")]
        history.append({"sha": sha, "modified_py": pairs})
    out = {"bench_repo": str(REPO), "vgar_repo": str(VGAR), "scenarios": scenarios, "history": history}
    (WORK / "bench" / "gold.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(len(scenarios), "scenarios;", sum(len(h["modified_py"]) for h in history), "history file pairs")


if __name__ == "__main__":
    main()
