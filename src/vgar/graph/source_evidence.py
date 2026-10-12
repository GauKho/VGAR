"""Lexical evidence from executable syntax, without importing target code."""
from __future__ import annotations

import ast
import math
import re
from collections import Counter, defaultdict
from functools import lru_cache


_FORMAT_SLOT = re.compile(r'%(?:\([^)]+\))?[#0 +\-]*\d*(?:\.\d+)?[a-zA-Z]|\{[^{}]*\}')
_DIAGNOSTIC_LINE = re.compile(r'\b(?:WARNING|ERROR|CRITICAL|[A-Za-z_][\w.]*(?:Error|Exception))\s*:', re.IGNORECASE)


def diagnostic_lines(text):
    """Only labeled runtime output supplies message evidence, not ordinary prose."""
    return tuple(' '.join(line.lower().split()) for line in text.splitlines()
                 if _DIAGNOSTIC_LINE.search(line))


def _message_fragments(function):
    body = function.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        body = body[1:]
    nodes = [node for statement in body for node in _scope(statement)]
    bindings = defaultdict(set)

    def strings(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return [node.value]
        if isinstance(node, ast.Name):
            return sorted(bindings[node.id])
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
            return strings(node.left)
        if isinstance(node, ast.JoinedStr):
            return [''.join(value.value if isinstance(value, ast.Constant) and isinstance(value.value, str)
                            else '{}' for value in node.values)]
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in {'_', '__', 'gettext'} and node.args:
                return strings(node.args[0])
            if isinstance(node.func, ast.Attribute) and node.func.attr == 'format':
                return strings(node.func.value)
        return []

    # Literal local assignments support logger.warning(message, arg) without
    # evaluating target code. All possible literals remain hints, not flow facts.
    for node in nodes:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    bindings[target.id].update(strings(node.value))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value:
            bindings[node.target.id].update(strings(node.value))
    messages = []
    for node in nodes:
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {'warning', 'error', 'critical', 'exception'} and node.args:
            messages.extend(strings(node.args[0]))
        elif isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call) and node.exc.args:
            messages.extend(strings(node.exc.args[0]))
    fragments = set()
    for message in messages:
        for fragment in _FORMAT_SLOT.split(message):
            fragment = ' '.join(fragment.lower().split()).strip()
            # Generic messages and variable slots cannot identify a function.
            if len(re.findall(r'[a-z][a-z0-9_]*', fragment)) >= 4:
                fragments.add(fragment)
    return tuple(sorted(fragments))


def _scope(node):
    yield node
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
        return
    for child in ast.iter_child_nodes(node):
        yield from _scope(child)


def _functions(node):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        yield node
    for child in ast.iter_child_nodes(node):
        # Python expressions cannot contain a def statement. Skip their trees
        # while discovering functions; executable terms get their own traversal.
        if not isinstance(child, ast.expr):
            yield from _functions(child)


def _terms(function, tokenize):
    body = function.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        body = body[1:]
    bound = {arg.arg for arg in function.args.posonlyargs + function.args.args + function.args.kwonlyargs}
    bound.update(arg.arg for arg in (function.args.vararg, function.args.kwarg) if arg)
    loaded, literals, attributes = set(), set(), set()
    for node in (node for statement in body for node in _scope(statement)):
        if isinstance(node, ast.Attribute):
            attributes.add(node.attr)
        elif isinstance(node, ast.Name):
            if isinstance(node.ctx, ast.Load):
                loaded.add(node.id)
            elif isinstance(node.ctx, (ast.Store, ast.Del)):
                bound.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
        elif isinstance(node, ast.alias):
            bound.add(node.asname or node.name.split('.')[0])
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and len(node.value) <= 64 and node.value.isidentifier():
            # Short literal tags such as "log" or "timeout" are code evidence;
            # prose/docstrings, paths and URLs are not.
            literals.add(node.value)
    terms = set()
    for value in attributes | literals | (loaded - bound):
        terms.update(tokenize(value))
    return terms


class SourceEvidence:
    def __init__(self, nodes, verified_sources, tokenize, *, include_messages=False):
        tokenize = lru_cache(maxsize=4096)(tokenize)
        wanted = defaultdict(dict)
        for node in nodes:
            if node['type'] in {'Function', 'Method', 'Test'}:
                span = node['range']
                wanted[node['path']][(span['start_line'], span['start_col'], node['name'])] = node['id']
        self.terms = {}
        self.messages = {}
        self.has_messages = include_messages
        self.unavailable_paths = []
        for path, locations in wanted.items():
            try:
                tree = ast.parse(verified_sources[path], filename=path)
            except (SyntaxError, UnicodeError, ValueError, RecursionError):
                self.unavailable_paths.append(path)
                continue
            for function in _functions(tree):
                node_id = locations.get((function.lineno, function.col_offset, function.name))
                if node_id:
                    self.terms[node_id] = _terms(function, tokenize)
                    fragments = _message_fragments(function) if include_messages else ()
                    if fragments:
                        self.messages[node_id] = fragments
        frequency = Counter(term for terms in self.terms.values() for term in terms)
        self.idf = {term: math.log(1 + len(self.terms) / count) for term, count in frequency.items()}
        self.mass = {node_id: sum(self.idf[term] for term in sorted(terms)) for node_id, terms in self.terms.items()}
        # Each immutable source snapshot owns bounded caches. Query keys keep
        # concurrent requests from sharing a mutable "current query" value.
        self._query_mass = lru_cache(maxsize=32)(self._compute_query_mass)
        self._similarity = lru_cache(maxsize=4096)(self._score)

    def similarity(self, node_id, task_words):
        return self._similarity(node_id, frozenset(task_words))

    def diagnostic_matches(self, lines):
        return {node_id: [fragment for fragment in fragments
                          if any(fragment in line for line in lines)]
                for node_id, fragments in self.messages.items()
                if any(fragment in line for fragment in fragments for line in lines)}

    def _compute_query_mass(self, task_words):
        return sum(self.idf.get(term, 0) for term in sorted(task_words))

    def _score(self, node_id, task_words):
        terms = self.terms[node_id]
        task_mass = self._query_mass(task_words)
        denominator = math.sqrt(task_mass * self.mass[node_id])
        matched = sum(self.idf[term] for term in sorted(terms & task_words))
        return matched / denominator if denominator else 0.0
