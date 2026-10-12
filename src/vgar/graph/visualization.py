"""Optional Matplotlib graph/resolver diagnostics; returns a Figure."""
from __future__ import annotations

from collections import Counter
from typing import Any


def plot_graph_tracking(document: dict[str, Any], *, context: dict | None = None,
                         events: list[dict] | None = None, max_nodes: int = 60,
                         query: str = "", focus_ids: list[str] | None = None):
    """Return a figure for notebook display, plt.show(), or figure.savefig().

    Graph drawing is bounded; the status counters cover the full snapshot.
    Matplotlib is imported only when this optional function is called.
    """
    if isinstance(max_nodes, bool) or not isinstance(max_nodes, int) or not 1 <= max_nodes <= 200:
        raise ValueError("max_nodes must be within [1, 200]")
    try:
        import matplotlib.pyplot as plt
        from matplotlib.lines import Line2D
        from matplotlib.patches import FancyArrowPatch
    except ImportError as error:
        raise RuntimeError("Install scripts/requirements_m1_plot.txt to enable graph plots") from error
    nodes = {n["id"]: n for n in document["nodes"]}
    edges = [e for e in document["edges"] if e["type"] in {"CALLS", "TESTS"}]
    linked = {node_id for e in edges for node_id in (e["source_id"], e["target_id"])}
    linked.update(n["id"] for n in nodes.values() if n["type"] == "CallSite" and
                  n["properties"].get("resolution_status") != "resolved")
    focus = set(focus_ids or [])
    if focus - nodes.keys():
        raise ValueError("focus_ids contains nodes outside the snapshot")
    if focus:
        linked = focus | {node_id for e in edges if e["source_id"] in focus or e["target_id"] in focus
                          for node_id in (e["source_id"], e["target_id"])}
    selected = sorted((nodes[key] for key in linked if not query or query.lower() in
                       f"{nodes[key]['qualified_name']} {nodes[key]['path']}".lower()),
                      key=lambda n: (n["id"] not in focus, n["type"], n["qualified_name"]))
    count = len(selected)
    selected = selected[:max_nodes]
    groups = [[n for n in selected if n["type"] == kind] for kind in ("Test", "CallSite")]
    groups.append([n for n in selected if n["type"] not in {"Test", "CallSite"}])
    positions = {n["id"]: (column, -(row + 1) / (len(group) + 1))
                 for column, group in enumerate(groups) for row, n in enumerate(group)}
    figure, (graph, summary) = plt.subplots(1, 2, figsize=(15, 8),
                                          gridspec_kw={"width_ratios": [3, 1]}, layout="constrained")
    colors = {"SCIP": "#2563eb", "LSP": "#9333ea", "Static": "#d97706", "Unresolved": "#dc2626", "Test": "#16a34a"}
    bindings = {e["source_id"]: e["properties"].get("binding_kind") for e in edges if e["type"] == "CALLS"}
    for edge in edges:
        if edge["source_id"] not in positions or edge["target_id"] not in positions:
            continue
        kind = "Test" if edge["type"] == "TESTS" else {"scip": "SCIP", "lsp": "LSP"}.get(edge["properties"].get("binding_kind"), "Static")
        graph.add_patch(FancyArrowPatch(positions[edge["source_id"]], positions[edge["target_id"]],
                                       arrowstyle="-|>", mutation_scale=10, color=colors[kind], alpha=.5,
                                       connectionstyle="arc3,rad=0.06", shrinkA=8, shrinkB=8))
    payload = (context or {}).get("context", context or {})
    packed = {item["node_id"] for item in payload.get("items", [])}
    for node in selected:
        unresolved = node["type"] == "CallSite" and node["properties"].get("resolution_status") != "resolved"
        kind = "Test" if node["type"] == "Test" else "Unresolved" if unresolved else {"scip": "SCIP", "lsp": "LSP"}.get(bindings.get(node["id"]), "Static")
        color = colors[kind] if node["type"] in {"Test", "CallSite"} else "#64748b"
        x, y = positions[node["id"]]
        graph.scatter([x], [y], s=85, c=color, edgecolors="#111827" if node["id"] in packed else "white", linewidths=2, zorder=3)
        owner = node["qualified_name"].split("::<", 1)[0].rsplit(".", 1)[-1]
        name = f"{owner}: {node['name']}()" if node["type"] == "CallSite" else node["qualified_name"]
        label = name if len(name) <= 48 else "…" + name[-47:]
        graph.annotate(label, (x, y), xytext=(8, 2), textcoords="offset points", fontsize=8)
    graph.set(xlim=(-.1, 3.1), ylim=(-1.08, .05), yticks=[])
    graph.set_xticks([0, 1, 2], ["Tests", "Call sites", "Functions / methods"])
    graph.set_title(f"Graph · {len(selected)}/{count} matching nodes\nArrows: CALLS / TESTS; black outline: packed context", loc="left", fontsize=12)
    for spine in graph.spines.values():
        spine.set_visible(False)
    handles = [Line2D([0], [0], marker="o", color="white", markerfacecolor=color, label=name, markersize=8)
               for name, color in colors.items()]
    graph.legend(handles=handles, loc="lower left", ncol=2, fontsize=9)
    counts = Counter({"scip": "SCIP", "lsp": "LSP"}.get(e["properties"].get("binding_kind"), "Static") for e in edges if e["type"] == "CALLS")
    counts["Unresolved"] = sum(n["type"] == "CallSite" and n["properties"].get("resolution_status") != "resolved" for n in nodes.values())
    labels = ["Unresolved", "Static", "SCIP", "LSP"]
    summary.barh(labels, [counts[key] for key in labels], color=[colors[key] for key in labels])
    summary.set_xlabel("Calls in full snapshot")
    summary.set_title("Resolver status", loc="left", fontsize=12)
    resolver = document.get("statistics", {}).get("resolver", {})
    detail = [f"Active: {resolver.get('active', 'static')}", f"Status: {resolver.get('status', 'historical')}",
              f"Context: {len(payload.get('items', []))} snippets / {payload.get('total_token_count', 0)} tokens"]
    if resolver.get("lsp"):
        lsp = resolver["lsp"]
        detail.append(f"LSP: {lsp['status']} · {lsp['request_count']}/{lsp['request_limit']} queries")
        if lsp.get("reason"):
            detail.append("LSP fallback: " + str(lsp["reason"])[:160])
    if resolver.get("reason"):
        import textwrap
        reason = str(resolver["reason"])
        if len(reason) > 240:
            reason = reason[:237] + "…"
        detail.append("Fallback: " + textwrap.fill(reason, 40))
    event_counts = Counter(e.get("event", "unknown") for e in events or [])
    if event_counts:
        detail.append("\nDebug events (supplied runs):")
        detail.extend(f"{name}: {number}" for name, number in event_counts.most_common(5))
    summary.set_ylim(-max(3, len("\n".join(detail).splitlines()) * .25), 3.6)
    summary.text(.02, .03, "\n".join(detail), transform=summary.transAxes, fontsize=9, va="bottom")
    figure.suptitle(f"VGAR · {document['repo_key']}\n{document['graph_version'][:28]}…", fontsize=14)
    return figure
