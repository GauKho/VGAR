"""Which optional graph layers a build runs, from host settings (spec 2026-11-15 §1).

One place turns settings into the builder's layer configs, so ``scripts/build_graph.py`` and the graph
built for the MCP server (``LiveGraphBuilder``) mean the same thing by the same option. A layer whose
setting is absent is off. Paths must be absolute, like the other ``VGAR_*`` host settings.
"""
from __future__ import annotations

import shutil
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from vgar.graph.jarvis_runner import DEFAULT_IMAGE as JARVIS_IMAGE
from vgar.graph.jarvis_runner import JarvisConfig
from vgar.graph.joern_runner import DEFAULT_IMAGE as JOERN_IMAGE
from vgar.graph.joern_runner import JoernConfig
from vgar.graph.lsp_resolver import LspConfig
from vgar.graph.scip_resolver import ScipConfig
from vgar.graph.tsg_extractor import TsgConfig

ROOT = Path(__file__).resolve().parents[3]
SCIP_RUNTIME = ROOT / "artifacts/m1/w7-w8/scip-runtime/node_modules/@sourcegraph/scip-python/index.js"
LSP_RUNTIME = ROOT / "artifacts/m1/w5-w6/lsp-runtime/node_modules/pyright/langserver.index.js"
SCIP_SHIM = ROOT / "scripts" / "scip_windows_compat.cjs"
LAYERS = ("tsg", "scip", "lsp", "jarvis", "joern")
# Path settings of the graph server, checked by host_config (all optional).
PATH_SETTINGS = ("VGAR_TSG_EXECUTABLE", "VGAR_TSG_TREE_SITTER_DIR", "VGAR_SCIP_ENTRY", "VGAR_NODE",
                 "VGAR_SCIP_ENVIRONMENT", "VGAR_SCIP_PYTHON", "VGAR_LSP_ENTRY", "VGAR_LSP_PYTHON")


@dataclass(frozen=True)
class LayerConfigs:
    tsg: Any = None
    scip: Any = None
    lsp: Any = None
    jarvis: Any = None
    joern: Any = None

    @property
    def any_optional(self) -> bool:
        """True when any optional layer is on."""
        return any(getattr(self, name) is not None for name in LAYERS)

    def builder_kwargs(self) -> dict[str, Any]:
        """Keyword arguments for ``PythonGraphBuilder``."""
        return {name: getattr(self, name) for name in LAYERS}


def _node(node: str) -> str:
    return str(Path(shutil.which(node) or node).resolve())


def scip_config(entry: Path | None, *, node: str, timeout: float, strict: bool, environment: Path | None,
                native_config: bool, target_only: str | None, python: Path | None,
                import_roots: tuple[str, ...] = ("src", "lib"), bundle: Path | None = None) -> ScipConfig:
    """SCIP resolver config, as ``build_graph.py --resolver scip`` builds it.

    Args:
        entry: scip-python ``index.js``; the pinned runtime under ``artifacts/`` when ``None``.
        node: Node executable (name on PATH or path).
        timeout: Seconds for indexing.
        strict: Fail instead of falling back to the static resolver.
        environment: Package inventory JSON of the target environment.
        native_config: Use the repository's own import configuration.
        target_only: Optional directory subset.
        python: Interpreter for SCIP.
        import_roots: Repository-relative import roots; ``src`` and ``lib`` by default, so the served graph, R1 and G1
            index a repository the same way.
        bundle: Previously generated index bundle.
    """
    return ScipConfig(command=(_node(node), "-r", str(SCIP_SHIM.resolve()), str((entry or SCIP_RUNTIME).resolve())),
                      bundle=bundle, timeout_seconds=timeout, strict=strict, environment_file=environment,
                      configure_imports=not native_config, import_roots=import_roots, target_only=target_only,
                      python_executable=python)


def lsp_config(entry: Path | None, *, node: str, total_timeout: float, request_timeout: float, max_requests: int,
               python: Path | None, import_roots: tuple[str, ...], strict: bool) -> LspConfig:
    """LSP resolver config, as ``build_graph.py --resolver lsp`` builds it.

    Args:
        entry: Pyright ``langserver.index.js``; the pinned runtime when ``None``.
        node: Node executable.
        total_timeout: Total LSP query budget in seconds.
        request_timeout: Seconds per request.
        max_requests: Request cap.
        python: Interpreter for import resolution.
        import_roots: Repository-relative import roots.
        strict: Fail instead of falling back.
    """
    return LspConfig(command=(_node(node), str((entry or LSP_RUNTIME).resolve()), "--stdio"),
                     total_timeout=total_timeout, request_timeout=request_timeout, max_requests=max_requests,
                     python_executable=python, import_roots=import_roots, strict=strict)


def _path(env: Mapping[str, str], name: str) -> Path | None:
    raw = (env.get(name) or "").strip()
    if not raw:
        return None
    if not Path(raw).is_absolute():
        raise ValueError(f"{name} must be an absolute path")
    return Path(raw)


def _number(env: Mapping[str, str], name: str, default: float) -> float:
    raw = (env.get(name) or "").strip()
    try:
        return float(raw) if raw else default
    except ValueError:
        raise ValueError(f"{name}={raw!r} is not a number") from None


def _on(env: Mapping[str, str], name: str) -> bool:
    return (env.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}


RUNS_KEPT = 3


def prune_runs(directory: Path, keep: int = RUNS_KEPT) -> None:
    """Delete the oldest run folders of a resolver, keeping the ``keep`` newest; a missing folder is fine.

    Args:
        directory: A resolver's ``output_directory``.
        keep: Number of newest run folders to keep.
    """
    try:
        runs = sorted((path for path in Path(directory).iterdir() if path.is_dir()), key=lambda path: path.stat().st_mtime)
    except OSError:
        return
    for path in runs[:-keep] if keep else runs:
        shutil.rmtree(path, ignore_errors=True)


def prune_layer_runs(layers: LayerConfigs) -> None:
    """``prune_runs`` for the SCIP and LSP run folders of ``layers``.

    Args:
        layers: Layer configs of a build.
    """
    for config in (layers.scip, layers.lsp):
        if config is not None:
            prune_runs(Path(config.output_directory))


def default_resolver_entries(env: Mapping[str, str], *, scip_runtime: Path = SCIP_RUNTIME,
                             lsp_runtime: Path = LSP_RUNTIME) -> dict[str, str]:
    """Settings that turn SCIP and LSP on for the server process when their pinned runtimes are installed (§5.4).

    ``VGAR_SCIP=off`` / ``VGAR_LSP=off`` keep a resolver off; an entry the host already set is kept.

    Args:
        env: The server's settings (not modified).
        scip_runtime: Pinned scip-python ``index.js``.
        lsp_runtime: Pinned pyright ``langserver.index.js``.
    """
    entries = {}
    for switch, name, runtime in (("VGAR_SCIP", "VGAR_SCIP_ENTRY", scip_runtime),
                                  ("VGAR_LSP", "VGAR_LSP_ENTRY", lsp_runtime)):
        if (env.get(switch) or "").strip().lower() == "off" or (env.get(name) or "").strip() or not runtime.is_file():
            continue
        entries[name] = str(runtime.resolve())
    return entries


def layer_configs(env: Mapping[str, str]) -> LayerConfigs:
    """Layer configs from host settings; an absent setting leaves its layer off.

    Args:
        env: Settings (the graph server's environment).

    Raises:
        ValueError: A path setting is relative, or only one of the two tree-sitter-graph settings is set.
    """
    executable, tree_sitter = _path(env, "VGAR_TSG_EXECUTABLE"), _path(env, "VGAR_TSG_TREE_SITTER_DIR")
    if (executable is None) != (tree_sitter is None):
        raise ValueError("VGAR_TSG_EXECUTABLE and VGAR_TSG_TREE_SITTER_DIR go together")
    tsg = TsgConfig(executable=executable, tree_sitter_dir=tree_sitter) if executable and tree_sitter else None
    node_path = _path(env, "VGAR_NODE")
    node = str(node_path) if node_path else "node"
    scip_entry = _path(env, "VGAR_SCIP_ENTRY")
    scip = scip_config(scip_entry, node=node, timeout=_number(env, "VGAR_SCIP_TIMEOUT", 120), strict=False,
                       environment=_path(env, "VGAR_SCIP_ENVIRONMENT"), native_config=False, target_only=None,
                       python=_path(env, "VGAR_SCIP_PYTHON")) if scip_entry else None
    lsp_entry = _path(env, "VGAR_LSP_ENTRY")
    lsp = lsp_config(lsp_entry, node=node, total_timeout=30, request_timeout=5, max_requests=200,
                     python=_path(env, "VGAR_LSP_PYTHON"), import_roots=("src", "lib"),
                     strict=False) if lsp_entry else None
    jarvis = JarvisConfig(image=(env.get("VGAR_JARVIS_IMAGE") or JARVIS_IMAGE).strip(),
                          timeout_seconds=_number(env, "VGAR_JARVIS_TIMEOUT", 120)) if _on(env, "VGAR_JARVIS") else None
    joern = JoernConfig(image=(env.get("VGAR_JOERN_IMAGE") or JOERN_IMAGE).strip(),
                        timeout_seconds=_number(env, "VGAR_JOERN_TIMEOUT", 900)) if _on(env, "VGAR_JOERN") else None
    database = (env.get("VGAR_GRAPH_DATABASE") or "").strip()
    if database and Path(database).is_absolute():   # run folders next to the graph, never under the server's cwd
        if scip is not None:
            scip = replace(scip, output_directory=Path(database).parent / "scip-runs")
        if lsp is not None:
            lsp = replace(lsp, output_directory=Path(database).parent / "lsp-runs")
    if scip is not None and lsp is not None:
        lsp = replace(lsp, fallback_only=True)
    return LayerConfigs(tsg=tsg, scip=scip, lsp=lsp, jarvis=jarvis, joern=joern)


def add_layer_options(parser) -> None:
    """Add the measurement scripts' layer options (same names as ``scripts/build_graph.py``).

    Args:
        parser: ``argparse.ArgumentParser`` to extend.
    """
    parser.add_argument("--tsg-executable", type=Path, help="tree-sitter-graph CLI (with --tsg-tree-sitter-dir)")
    parser.add_argument("--tsg-tree-sitter-dir", type=Path, help="folder with the tree-sitter-python grammar")
    parser.add_argument("--joern", action="store_true", help="add G_code with Joern in Docker")
    parser.add_argument("--joern-image", default=JOERN_IMAGE)
    parser.add_argument("--joern-timeout", type=float, default=900)
    parser.add_argument("--enable-jarvis", action="store_true", help="confirm call edges with JARVIS in Docker")
    parser.add_argument("--jarvis-image", default=JARVIS_IMAGE)
    parser.add_argument("--jarvis-timeout", type=float, default=120)


def layers_from_args(args) -> LayerConfigs:
    """Layer configs from ``add_layer_options`` arguments (SCIP/LSP keep the scripts' own resolver options).

    Args:
        args: Parsed arguments.

    Raises:
        ValueError: Only one of the two tree-sitter-graph options is given.
    """
    executable, tree_sitter = getattr(args, "tsg_executable", None), getattr(args, "tsg_tree_sitter_dir", None)
    if (executable is None) != (tree_sitter is None):
        raise ValueError("--tsg-executable and --tsg-tree-sitter-dir go together")
    return LayerConfigs(
        tsg=TsgConfig(executable=executable, tree_sitter_dir=tree_sitter) if executable else None,
        joern=JoernConfig(image=args.joern_image, timeout_seconds=args.joern_timeout) if getattr(args, "joern", False) else None,
        jarvis=JarvisConfig(image=args.jarvis_image, timeout_seconds=args.jarvis_timeout)
        if getattr(args, "enable_jarvis", False) else None)


def layer_profile(layers: LayerConfigs | None) -> dict[str, Any] | None:
    """Identity of the optional layers for graph cache keys; ``None`` when none is on (keys stay as before).

    Args:
        layers: Layer configs of a build.
    """
    if layers is None or not layers.any_optional:
        return None
    return {name: repr(getattr(layers, name)) for name in LAYERS if getattr(layers, name) is not None}


def _status(report: Mapping[str, Any] | None) -> dict[str, Any]:
    if not report:
        return {"status": "failed", "reason": "no report from the build"}
    status = str(report.get("status"))
    if status in {"skipped", "not_needed"}:   # nothing for the layer to do, e.g. LSP while SCIP is ready
        return {"status": "skipped", "reason": report.get("reason")}
    if status == "ready":
        return {"status": "ready", "reason": report.get("reason")}
    if status == "partial":  # the layer ran; some files failed
        failed = len(report.get("failed_files") or [])
        total = report.get("file_count")
        if isinstance(total, int) and total and failed >= total:
            return {"status": "failed", "reason": report.get("reason") or f"all {total} file(s) failed"}
        return {"status": "ready", "reason": report.get("reason") or f"partial: {failed} file(s) failed"}
    return {"status": "failed", "reason": report.get("reason") or status}


def layer_summary(document: Mapping[str, Any], configs: LayerConfigs) -> dict[str, dict[str, Any]]:
    """Per optional layer: ``ready``, ``off`` or ``failed`` with the reason, from the graph's statistics.

    Args:
        document: Built graph document.
        configs: The layer configs the build used.
    """
    statistics = document.get("statistics", {})
    resolver = statistics.get("resolver", {}) or {}
    reports = {"tsg": statistics.get("tsg"), "jarvis": statistics.get("jarvis"), "joern": statistics.get("code_graph"),
               "scip": resolver if resolver.get("requested") in {"scip", "scip-lsp"} else None,
               "lsp": resolver.get("lsp")}
    return {name: _status(reports[name]) if getattr(configs, name) is not None else {"status": "off", "reason": None}
            for name in LAYERS}
