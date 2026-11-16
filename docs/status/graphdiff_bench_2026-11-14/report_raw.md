# GraphDiff benchmark: ast vs proposal tools

Scenarios: 68 (17 bugs x pure / format / refactor / refactor+format). Java tool outputs present: True

## Bug-fix edit isolation (symbol level)

| Pipeline | Variant | P | R | F1 | FP from refactor | FP from format | other FP |
|---|---|---:|---:|---:|---:|---:|---:|
| ast (TV3) | pure | 1.00 | 1.00 | 1.00 | 0 | 0 | 0 |
| ast (TV3) | format | 1.00 | 1.00 | 1.00 | 0 | 0 | 0 |
| ast (TV3) | refactor | 0.61 | 1.00 | 0.76 | 12 | 0 | 0 |
| ast (TV3) | refactor+format | 0.61 | 1.00 | 0.76 | 12 | 0 | 0 |
| ast (TV3) | ALL | 0.76 | 1.00 | 0.86 | 24 | 0 | 0 |
| GumTree + RefactoringMiner | pure | 1.00 | 1.00 | 1.00 | 0 | 0 | 0 |
| GumTree + RefactoringMiner | format | 0.53 | 1.00 | 0.69 | 0 | 17 | 0 |
| GumTree + RefactoringMiner | refactor | 0.79 | 1.00 | 0.88 | 5 | 0 | 0 |
| GumTree + RefactoringMiner | refactor+format | 0.58 | 1.00 | 0.73 | 5 | 9 | 0 |
| GumTree + RefactoringMiner | ALL | 0.68 | 1.00 | 0.81 | 10 | 26 | 0 |
| ast + RefactoringMiner | pure | 1.00 | 1.00 | 1.00 | 0 | 0 | 0 |
| ast + RefactoringMiner | format | 1.00 | 1.00 | 1.00 | 0 | 0 | 0 |
| ast + RefactoringMiner | refactor | 0.79 | 1.00 | 0.88 | 5 | 0 | 0 |
| ast + RefactoringMiner | refactor+format | 0.79 | 1.00 | 0.88 | 5 | 0 | 0 |
| ast + RefactoringMiner | ALL | 0.88 | 1.00 | 0.94 | 10 | 0 | 0 |

## Refactoring detection (step 1)

| Detector | Family | gold | found | reported (all) |
|---|---|---:|---:|---:|
| ast exact-body pairs | extract_method | 2 | 0 | 0 |
| ast exact-body pairs | inline_method | 2 | 0 | 0 |
| ast exact-body pairs | move_method | 4 | 4 | 4 |
| ast exact-body pairs | rename_class | 4 | 4 | 4 |
| ast exact-body pairs | rename_method | 12 | 12 | 12 |
| ast exact-body pairs | rename_parameter | 6 | 0 | 0 |
| ast exact-body pairs | rename_variable | 4 | 0 | 0 |
| ast exact-body pairs | **total** | 34 | 20 (recall 0.59) | 20 (precision 1.00) |
| RefactoringMiner 3.2.0 | extract_method | 2 | 2 | 2 |
| RefactoringMiner 3.2.0 | inline_method | 2 | 0 | 0 |
| RefactoringMiner 3.2.0 | move_method | 4 | 4 | 4 |
| RefactoringMiner 3.2.0 | rename_class | 4 | 4 | 4 |
| RefactoringMiner 3.2.0 | rename_method | 12 | 12 | 12 |
| RefactoringMiner 3.2.0 | rename_parameter | 6 | 6 | 6 |
| RefactoringMiner 3.2.0 | rename_variable | 4 | 4 | 4 |
| RefactoringMiner 3.2.0 | **total** | 34 | 32 (recall 0.94) | 40 (precision 0.80) |
| RefactoringMiner 3.2.0 | not in gold | | | {'other:Change Attribute Type': 4, 'other:Change Variable Type': 4} |

## Speed (benchmark commits)

- ast (TV3, in-process): median 12 ms/commit, max 51 ms
- RefactoringMiner (one JVM per commit): median 1.48 s/commit
- RefactoringMiner (one JVM, -bc over 135 commits): 0.06 s/commit amortised
- GumTree JVM start-up (identical 1-line files): median 0.47 s
- GumTree: median 0.59 s/file, 1.21 s/commit (one JVM per file)
  - minus start-up: ~0.12 s/file of diff work

## Real history (30 first-parent commits of vgar_mcp_mvp_demo, no labels)

| Commit | py files | ast ms | ast refactorings | RM s | RM refactorings (rename/move) | GumTree s |
|---|---:|---:|---:|---:|---:|---:|
| 9c3532c92e | 12 | 433 | 0 | 9.114 | 7 (0) | 10.5 |
| b4cbaec048 | 2 | 30 | 0 | 1.989 | 1 (0) | 1.6 |
| e668ba0f45 | 4 | 62 | 0 | 2.308 | 2 (0) | 3.7 |
| 2bdbba4763 | 2 | 55 | 0 | 2.072 | 0 (0) | 1.7 |
| 244cdd8ec6 | 8 | 105 | 0 | 2.52 | 0 (0) | 7.3 |
| 90a7902968 | 48 | 22590 | 3 | 48.709 | 12 (7) | 47.2 |
| 6a0f16c71f | 24 | 1514 | 1 | 9.035 | 21 (3) | 24.3 |
| 122ee6662b | 3 | 122 | 0 | 2.635 | 0 (0) | 4.1 |
| ea4d6face0 | 31 | 1330 | 0 | 13.816 | 18 (0) | 35.2 |
| 64e23d78be | 0 | 79 | 0 | 1.084 | 0 (0) | 0.0 |
| 8220b6e713 | 4 | 241 | 0 | 3.844 | 0 (0) | 10.1 |
| 0a89b5a678 | 2 | 182 | 0 | 3.819 | 4 (0) | 3.8 |
| 18ed055ea5 | 1 | 101 | 0 | 2.912 | 2 (0) | 1.4 |
| caed1eb11f | 4 | 328 | 0 | 6.274 | 6 (2) | 9.7 |
| fc98ee568d | 5 | 154 | 0 | 2.708 | 3 (1) | 6.0 |
| 3267d5b1ef | 5 | 338 | 0 | 4.674 | 10 (1) | 7.0 |
| bca3372053 | 6 | 519 | 0 | 6.295 | 3 (0) | 11.6 |
| 9eab5c4d0c | 7 | 540 | 0 | 6.408 | 16 (1) | 13.8 |
| 9150cea296 | 6 | 236 | 0 | 4.685 | 2 (0) | 9.6 |
| a1a7215be7 | 7 | 536 | 0 | 8.119 | 5 (0) | 11.8 |
| c2cb8f620d | 0 | 80 | 0 | 1.114 | 0 (0) | 0.0 |
| ebc06527fc | 1 | 122 | 0 | 3.364 | 0 (0) | 1.0 |
| f95cf684bd | 4 | 92 | 0 | 2.229 | 1 (0) | 3.2 |
| c88290a147 | 0 | 26 | 0 | 1.011 | 0 (0) | 0.0 |
| ad0aa7407e | 18 | 344 | 0 | 5.799 | 12 (0) | 17.2 |
| ccac57d3c3 | 2 | 68 | 0 | 2.556 | 1 (0) | 2.4 |
| ac312f587f | 3 | 57 | 0 | 2.101 | 2 (0) | 2.5 |
| bcc8cb0857 | 3 | 35 | 0 | 2.007 | 2 (0) | 2.3 |
| e0b5b10a19 | 0 | 38 | 0 | 1.005 | 0 (0) | 0.0 |
| 3e50d24565 | 0 | 27 | 0 | 0.995 | 0 (0) | 0.0 |
| **total** | 212 | 30381 | 4 | 165.2 | (15) | 249.2 |

Rename/move pairs found by ast: 4, by RefactoringMiner: 15, by both (same name pair): 3
