"""Gold changed-file/function proxy from unified developer diff, never query context."""
import re
import shlex

from .chunks import entities, is_source, normalize_path, physical_lines


HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def diff_path(value):
    value = value.split("\t", 1)[0]
    if value == "/dev/null":
        return None
    if value.startswith('"'):
        parts = shlex.split(value)
        value = parts[0]
    if value.startswith(("a/", "b/")):
        value = value[2:]
    return normalize_path(value)


def parse_patch(patch):
    files, current, hunk = [], None, None
    lines = physical_lines(patch)
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("diff --git "):
            fields = shlex.split(line)[2:]
            if len(fields) != 2:
                raise ValueError("Malformed diff --git header")
            current = {"old_path": diff_path(fields[0]), "new_path": diff_path(fields[1]), "hunks": []}
            files.append(current)
            hunk = None
        elif line.startswith("--- ") and (hunk is None or hunk["old_seen"] == hunk["old_count"] and hunk["new_seen"] == hunk["new_count"]):
            if index + 1 >= len(lines) or not lines[index + 1].startswith("+++ "):
                raise ValueError("Missing +++ header")
            if current is None or current["hunks"]:
                current = {"hunks": []}
                files.append(current)
            current.update(old_path=diff_path(line[4:]), new_path=diff_path(lines[index + 1][4:]))
            hunk = None
            index += 1
        elif line.startswith("@@ "):
            match = HUNK.match(line)
            if match is None or current is None:
                raise ValueError("Malformed hunk")
            a, ac, b, bc = match.groups()
            hunk = {"old_start": int(a), "old_count": int(ac or 1), "new_start": int(b), "new_count": int(bc or 1),
                    "old_seen": 0, "new_seen": 0, "lines": [], "removed": [], "added": []}
            current["hunks"].append(hunk)
        elif hunk is not None and (hunk["old_seen"] < hunk["old_count"] or hunk["new_seen"] < hunk["new_count"]):
            if line.startswith("\\ No newline"):
                index += 1
                continue
            if not line or line[0] not in " +-":
                raise ValueError("Unexpected hunk content")
            marker = line[0]
            old_line = hunk["old_start"] + hunk["old_seen"]
            new_line = hunk["new_start"] + hunk["new_seen"]
            if marker == "-":
                hunk["removed"].append(old_line)
            if marker == "+":
                hunk["added"].append(new_line)
            hunk["lines"].append(line)
            hunk["old_seen"] += marker != "+"
            hunk["new_seen"] += marker != "-"
        index += 1
    if not files:
        raise ValueError("No unified diff files")
    for file in files:
        for item in file["hunks"]:
            if item["old_seen"] != item["old_count"] or item["new_seen"] != item["new_count"]:
                raise ValueError("Hunk line count mismatch")
    return files


def align_patch(source, hunks):
    old = physical_lines(source)
    result, origins, aligned = [], {}, []
    position, previous_offset = 0, 0

    def append(line, origin):
        result.append(line)
        origins[len(result)] = origin

    for hunk in hunks:
        declared = hunk["old_start"] - 1 if hunk["old_count"] else hunk["old_start"]
        start = declared + previous_offset
        needle = [line[1:] for line in hunk["lines"] if line[0] != "+"]
        if needle and (start < position or old[start:start + len(needle)] != needle):
            matches = [i for i in range(position, len(old) - len(needle) + 1) if old[i:i + len(needle)] == needle]
            if len(matches) != 1:
                raise ValueError("Patch context missing or ambiguous in base source")
            start = matches[0]
        if start < position or start > len(old):
            raise ValueError("Hunk outside base source")
        previous_offset = start - declared
        for old_index in range(position, start):
            append(old[old_index], old_index + 1)
        position = start
        item = {"offset_lines": previous_offset, "removed": [], "added": []}
        for line in hunk["lines"]:
            if line[0] != "+":
                if position >= len(old) or old[position] != line[1:]:
                    raise ValueError("Patch does not match base source")
                origin = position + 1
                if line[0] == "-":
                    item["removed"].append(origin)
                position += 1
            else:
                origin = None
            if line[0] != "-":
                if line[0] == "+":
                    item["added"].append(len(result) + 1)
                append(line[1:], origin)
        aligned.append(item)
    for old_index in range(position, len(old)):
        append(old[old_index], old_index + 1)
    return "\n".join(result) + "\n", aligned, origins


def patched_source(source, hunks):
    return align_patch(source, hunks)[0]


def owner(definitions, line):
    candidates = [d for d in definitions if d["start_line"] <= line <= d["end_line"]]
    return max(candidates, key=lambda d: (d["depth"], -(d["end_line"] - d["start_line"]))) if candidates else None


def extract_gold(patch, sources):
    files, functions, missing_files, events, all_files = set(), set(), set(), [], set()
    for change in parse_patch(patch):
        old_path, new_path = change["old_path"], change["new_path"]
        path = old_path or new_path
        if not path or not is_source(path):
            continue
        all_files.add(path)
        if old_path is None:
            missing_files.add(new_path)
            events.append({"path": new_path, "disposition": "new_file", "function_id": None})
            continue
        if old_path not in sources:
            missing_files.add(old_path)
            events.append({"path": old_path, "disposition": "missing_base_file", "function_id": None})
            continue
        files.add(old_path)
        source = sources[old_path]
        try:
            before = entities(old_path, source)
            after_source, aligned_hunks, origins = align_patch(source, change["hunks"])
        except (SyntaxError, ValueError) as exc:
            events.append({"path": old_path, "disposition": "unmapped", "function_id": None, "error": str(exc)})
            continue
        try:
            after = entities(old_path, after_source)
            after_ok = True
        except (SyntaxError, ValueError) as exc:
            after = []
            after_ok = False
            events.append({"path": old_path, "disposition": "unmapped_after", "function_id": None, "error": str(exc)})
        base_ids = {d["parent_id"] for d in before}
        for hunk in aligned_hunks:
            if hunk["offset_lines"]:
                events.append({"path": old_path, "disposition": "hunk_relocated", "offset_lines": hunk["offset_lines"], "function_id": None})
            removed_owners = {d["parent_id"]: d for line in hunk["removed"] if (d := owner(before, line)) is not None}
            for side, lines, definitions in (("old", hunk["removed"], before), ("new", hunk["added"], after)):
                for line in lines:
                    definition = owner(definitions, line)
                    identity = definition["parent_id"] if definition else None
                    if side == "new" and definition:
                        original_header = origins.get(definition["definition_line"])
                        matches = [d for d in before if d["symbol"] == definition["symbol"] and d["definition_line"] == original_header] if original_header is not None else [d for d in removed_owners.values() if d["symbol"] == definition["symbol"]]
                        identity = matches[0]["parent_id"] if len(matches) == 1 else None
                    if identity in base_ids:
                        functions.add(identity)
                        disposition = "mapped_function"
                    elif definition:
                        disposition = "new_function"
                    else:
                        disposition = "module_edit" if side == "old" or after_ok else "unmapped_after"
                    events.append({"path": old_path, "side": side, "line": line, "function_id": identity, "disposition": disposition})
        if old_path != new_path:
            events.append({"path": old_path, "new_path": new_path, "disposition": "rename" if new_path else "deleted_file", "function_id": None})
    mapping = [e for e in events if e["disposition"] in {"mapped_function", "new_function", "module_edit", "unmapped", "unmapped_after"}]
    handled = [e for e in mapping if e["disposition"] in {"mapped_function", "new_function", "module_edit"}]
    return {"gold_files": sorted(files), "gold_functions": sorted(functions), "all_changed_source_files": sorted(all_files),
            "unretrievable_files": sorted(missing_files), "mapping_events": events,
            "function_labels_complete": not any(e["disposition"] in {"unmapped", "unmapped_after", "missing_base_file"} for e in events),
            "mapping_coverage": len(handled) / len(mapping) if mapping else None,
            "file_retrievability_coverage": len(files) / len(all_files) if all_files else None,
            "label_semantics": "developer_changed_code_proxy_not_complete_relevance"}
