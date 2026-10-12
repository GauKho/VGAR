"""Source-backed return-type hints for calls missing a SCIP occurrence.

These are possible member references, not resolved runtime call bindings.
No target code is imported, executed, or changed.
"""
from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path


def _dotted(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _dotted(node.value)
        return prefix + "." + node.attr if prefix else None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        try:
            return _dotted(ast.parse(node.value, mode="eval").body)
        except (SyntaxError, ValueError):
            pass
    return None


def _body(node):
    body = node.body
    return body[1:] if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str) else body


class ReturnContracts:
    def __init__(self, root: Path, nodes: list[dict], edges: list[dict], modules: dict) -> None:
        self.root, self.modules = root, modules
        self.nodes = {node["id"]: node for node in nodes}
        self.classes = [node for node in nodes if node["type"] == "Class"]
        self.by_location = defaultdict(list)
        for node in nodes:
            if node["type"] in {"Function", "Method"}:
                self.by_location[(node["path"], node["range"]["start_line"], node["name"])].append(node)
        self.methods = defaultdict(list)
        self.children = defaultdict(set)
        self.bases = defaultdict(set)
        for edge in edges:
            if edge["type"] == "INHERITS":
                self.children[edge["target_id"]].add(edge["source_id"])
                self.bases[edge["source_id"]].add(edge["target_id"])
            if edge["type"] == "CONTAINS" and self.nodes[edge["source_id"]]["type"] == "Class":
                target = self.nodes[edge["target_id"]]
                if target["type"] == "Method":
                    self.methods[(edge["source_id"], target["name"])].append(target["id"])
        self.cache = {}

    def _class(self, module, expression):
        if not expression:
            return None
        prefix, dot, tail = expression.partition(".")
        if prefix in module.imported_modules:
            qualified = module.imported_modules[prefix] + (dot + tail if dot else "")
        elif prefix in module.imported_symbols:
            parent, name = module.imported_symbols[prefix]
            qualified = parent + "." + name + (dot + tail if dot else "")
        elif prefix in module.definitions:
            node = self.nodes[module.definitions[prefix]]
            qualified = node["qualified_name"] + (dot + tail if dot else "")
        else:
            return None
        matches = [node["id"] for node in self.classes if node["qualified_name"] == qualified
                   or node["qualified_name"].endswith("." + qualified)]
        return matches[0] if len(matches) == 1 else None

    def _index(self, path):
        module = next((m for m in self.modules.values() if m.path == path), None)
        contracts = {}
        if module is None:
            return contracts
        try:
            tree = ast.parse((self.root / path).read_bytes(), filename=path)
        except (SyntaxError, UnicodeError):
            return contracts
        # A shadowed isinstance is not evidence for a builtin type guard.
        shadowed = any((isinstance(n, ast.Name) and n.id == "isinstance" and isinstance(n.ctx, (ast.Store, ast.Del)))
                      or (isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name == "isinstance")
                      or (isinstance(n, ast.alias) and (n.asname or n.name) == "isinstance") for n in ast.walk(tree))

        def visit(scope, owner=None):
            functions = [n for n in scope.body if isinstance(n, ast.FunctionDef)]
            guarded, writes = defaultdict(set), defaultdict(list)
            for function in functions:
                body = _body(function)
                args = {arg.arg for arg in function.args.posonlyargs + function.args.args + function.args.kwonlyargs}
                modified = {n.id for n in ast.walk(function) if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del))}
                guard = body[0] if body else None
                checked, class_id = None, None
                method_nodes = self.by_location.get((path, function.lineno, function.name), [])
                instance_method = len(method_nodes) == 1 and method_nodes[0]["properties"].get("method_kind") == "instance"
                if (instance_method and not shadowed and "isinstance" not in args and isinstance(guard, ast.If)
                        and not guard.orelse and len(guard.body) == 1 and isinstance(guard.body[0], ast.Raise)
                        and isinstance(guard.test, ast.UnaryOp) and isinstance(guard.test.op, ast.Not)):
                    test = guard.test.operand
                    if (isinstance(test, ast.Call) and isinstance(test.func, ast.Name) and test.func.id == "isinstance"
                            and len(test.args) == 2 and not test.keywords and isinstance(test.args[0], ast.Name)):
                        checked = test.args[0].id
                        type_text = _dotted(test.args[1])
                        if checked in args and checked not in modified and type_text and type_text.split(".")[0] not in args | modified:
                            class_id = self._class(module, type_text)
                for node in ast.walk(function):
                    if isinstance(node, ast.Attribute) and isinstance(node.ctx, (ast.Store, ast.Del)):
                        field = _dotted(node)
                        if field and field.startswith("self."):
                            writes[field].append(node)
                # Only direct assignments after an unconditional raising guard qualify.
                for statement in body[1:]:
                    if isinstance(statement, ast.Assign) and isinstance(statement.value, ast.Name) and statement.value.id == checked and class_id:
                        for target in statement.targets:
                            field = _dotted(target)
                            if field and field.startswith("self."):
                                guarded[field].add((id(target), class_id, function.lineno))
            fields = {}
            for field, assignments in writes.items():
                evidence = guarded[field]
                types = {item[1] for item in evidence}
                if len(types) == 1 and {id(n) for n in assignments} == {item[0] for item in evidence}:
                    fields[field] = (next(iter(types)), sorted({item[2] for item in evidence}))
            for function in functions:
                matches = self.by_location.get((path, function.lineno, function.name), [])
                if len(matches) != 1:
                    continue
                node = matches[0]
                annotated = self._class(module, _dotted(function.returns))
                if annotated and not any(isinstance(n, (ast.Yield, ast.YieldFrom)) for n in ast.walk(function)):
                    contracts[node["id"]] = {"class_id": annotated, "kind": "return_annotation", "evidence_lines": [function.lineno]}
                elif owner and node["properties"].get("method_kind") == "instance" and len(_body(function)) == 1 and isinstance(_body(function)[0], ast.Return):
                    field = _dotted(_body(function)[0].value)
                    if field in fields and "self" in {a.arg for a in function.args.posonlyargs + function.args.args}:
                        cls, evidence = fields[field]
                        contracts[node["id"]] = {"class_id": cls, "kind": "guarded_field", "field": field,
                                                 "evidence_lines": [function.lineno, *evidence]}
            for child in scope.body:
                if isinstance(child, ast.ClassDef):
                    visit(child, child)
        visit(tree)
        return contracts

    def candidates(self, getter_id, member, *, limit=16):
        getter = self.nodes[getter_id]
        if getter["path"] not in self.cache:
            self.cache[getter["path"]] = self._index(getter["path"])
        contract = self.cache[getter["path"]].get(getter_id)
        if contract is None:
            return [], {"reason": "no_source_return_contract"}
        classes, queue = set(), [contract["class_id"]]
        while queue:
            class_id = queue.pop()
            if class_id in classes:
                continue
            classes.add(class_id)
            queue.extend(self.children[class_id])
        def implementations(class_id, seen):
            if class_id in seen:
                return set()
            own = self.methods.get((class_id, member), [])
            if own:
                return set(own)
            return {target for base in self.bases[class_id] for target in implementations(base, seen | {class_id})}
        targets = sorted({target for class_id in classes for target in implementations(class_id, set())})
        if len(targets) > limit:
            return [], {"reason": "return_contract_candidate_limit", "candidate_count": len(targets)}
        return targets, dict(contract, getter_id=getter_id, reason="source_return_contract",
                             declared_member_ids=sorted(implementations(contract["class_id"], set())))
