# vgar-callgraph-cases

Ground-truth cases for call-graph resolution. Run: `PYTHONPATH=src python run_all.py`.

Annotation on the call line: `# expect: <qualified>[, <qualified>...] | external | unknown`.
Module names are relative to `src/`. Closures and lambdas use runtime `__qualname__`
(`f.<locals>.g`, `main.<locals>.<lambda>`).

Open conventions (need team decision):
- `g06_class_calls.py:36` `Child()` inherits `__init__` from `Parent`; annotated as `Parent.__init__`.
- `super().fetch()` / `super().__init__()` are two syntactic calls on one line; only the outer
  call is annotated (on CPython 3.13 `super()` emits no profile event).
- Group 9 annotations are the TRUE targets; the 5-vs-6 candidate threshold is a spec test of the
  static mode, not ground truth.
- Group 10 `unknown` lines: runtime target is recorded for reference only.

Second layout (no `src/`, namespace package `nsp`): `../vgar-callgraph-cases-flat`, run `python run_all.py`.
