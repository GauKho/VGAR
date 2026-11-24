# ShopFlow clean — OpenCode scenario in English (23/11/2026)

English translation of `shopflow_opencode_scenario.md` (version 3, bug 5 text fixed 22/11). Content and order are
unchanged; only the language differs, so a rerun measures the effect of the language. Repository:
`D:\kltn\shopflow-clean\shopflow`, original code at commit `77426bb` (17 bugs B01–B17). Model for every run:
`oc/nemotron-3.5-lightning-free` (9Router), one NEW OpenCode session per run.

Expectation (probe 23/11): `find_task_anchors` still finds no correct anchor for English business-language bug texts
(0/5); it works when the text names functions or contains an exception line. This rerun measures whether English helps
the model itself, not grounding.

## Commands (PowerShell)

```powershell
Set-Location D:\kltn\shopflow-clean\shopflow

# Vietnamese runs are saved: run-vgar (b7d9c70), run-nomcp (9d51bff). Check that nothing is left uncommitted:
git status --short            # must be empty

# Optional: start from an empty graph (the first build_or_update_graph rebuilds it)
Remove-Item D:\kltn\vgar-work\data\shopflow-clean\graph.db -ErrorAction SilentlyContinue
```

### Run 1 — B-en (no VGAR). Runs first this time (order swapped against the Vietnamese runs).

```powershell
git switch -c run-nomcp-en 77426bb
git log --oneline -1          # 77426bb shopflow clean (17 bugs)
git status --short            # empty
opencode.cmd mcp list         # the three vgar servers must be disabled (still disabled from run B)
opencode.cmd                  # NEW session, model oc/nemotron-3.5-lightning-free; paste the B-en prompts
```

After the run:

```powershell
git add -A; git commit -m "run-nomcp-en: nemotron-3.5-lightning"
```

### Run 2 — A-en (with VGAR)

```powershell
git switch -c run-vgar-en 77426bb
# enable the three servers (remove "disabled"; written without BOM, otherwise OpenCode ignores the file)
$p = "D:\kltn\shopflow-clean\shopflow\opencode.json"; $cfg = Get-Content $p -Raw | ConvertFrom-Json
foreach ($n in "vgar-graph","vgar-execution","vgar-repository") { $cfg.mcp.servers.$n.PSObject.Properties.Remove("disabled") }
[IO.File]::WriteAllText($p, ($cfg | ConvertTo-Json -Depth 10), (New-Object Text.UTF8Encoding($false)))
opencode.cmd mcp list         # the three vgar servers must be connected
opencode.cmd                  # NEW session, same model; paste the A-en prompts
```

After the run:

```powershell
git add -A; git commit -m "run-vgar-en: nemotron-3.5-lightning"
```

To disable the servers again later:

```powershell
$p = "D:\kltn\shopflow-clean\shopflow\opencode.json"; $cfg = Get-Content $p -Raw | ConvertFrom-Json
foreach ($n in "vgar-graph","vgar-execution","vgar-repository") { $cfg.mcp.servers.$n | Add-Member -NotePropertyName disabled -NotePropertyValue $true -Force }
[IO.File]::WriteAllText($p, ($cfg | ConvertTo-Json -Depth 10), (New-Object Text.UTF8Encoding($false)))
```

If the model does not answer, stop and report it; do not switch to another model.

## Prompts — B-en (no VGAR)

Step 1:

```text
Read this repository and summarize the architecture: the components, the order-placement flow from API -> service ->
repository, and which module depends on which. Read only; do not change anything.
```

Step 2:

```text
This repository has no tests and no documentation. The business specification is:
- Money uses Decimal, rounded ROUND_HALF_UP to 2 decimal places.
- The customer-tier discount and the coupon combine multiplicatively, capped at 50%. Coupons in config.COUPONS are stored as percentages.
- Shipping is free when the value after discount is >= 100; the 10% tax applies only to the goods after discount, not to the shipping fee.
- Placing an order reserves stock; any error while placing an order must release every reservation.
- Status flow: pending -> confirmed -> shipped; pending/confirmed -> cancelled. shipped and cancelled are final states.
- The expected delivery date counts business days (Monday to Friday).
For EACH rule: find and read the related files and functions; if the logic spans several files, follow the callers and
the called functions.
Besides the specification, also look for places where the code contradicts itself across files: wrong argument order,
attributes that do not exist, data stored one way and read another, wrong boundary comparisons, pagination, HTTP error
codes.
List: file:line, the symptom a user would see, and whether the bug involves several files. Examine every module in
shopflow/ and finally list the modules you examined. Do not list the same bug twice. Do NOT change code yet.
```

Step 3 (one bug per message; replace `<BUG DESCRIPTION>` with a row of the bug table; order 3, 1, 2, 4, 5):

```text
<BUG DESCRIPTION>
Work in this order and do not create new files in the repository:
1. Find the files and functions related to the bug.
2. If the bug spans several files, follow the callers and the called functions.
3. Read those files. Reproduce the bug with `python -c` using shopflow.app.build_app.
4. Make a minimal fix that follows the specification, then rerun the reproduction.
5. Run `git diff` and check, by reading the change, whether it breaks any other caller.
6. Report: root cause, file:line changed, result of the check.
```

Steps 4–5:

```text
Rerun every reproduction you used, each as a separate `python -c` command, and report the result of each. Then write a
table: bug -> root cause -> file:line changed -> evidence (reproduction before/after) -> what could not be checked.
```

## Prompts — A-en (with VGAR)

Step 1:

```text
Use the vgar-graph tools. Call build_or_update_graph for this repository, then summarize the architecture: the
components, the order-placement flow from API -> service -> repository, and which module depends on which. Read only;
do not change anything.
```

Step 2:

```text
This repository has no tests and no documentation. The business specification is:
- Money uses Decimal, rounded ROUND_HALF_UP to 2 decimal places.
- The customer-tier discount and the coupon combine multiplicatively, capped at 50%. Coupons in config.COUPONS are stored as percentages.
- Shipping is free when the value after discount is >= 100; the 10% tax applies only to the goods after discount, not to the shipping fee.
- Placing an order reserves stock; any error while placing an order must release every reservation.
- Status flow: pending -> confirmed -> shipped; pending/confirmed -> cancelled. shipped and cancelled are final states.
- The expected delivery date counts business days (Monday to Friday).
For EACH rule: call find_task_anchors with the full rule sentence; if there is no anchor, call search_symbols with the
rule's keywords; call get_related_context from the anchors (never with an empty list); follow get_callers/get_callees
when the logic spans several files (explain_dependency_path: source is the CALLER, target is the CALLEE); read the
related files.
Besides the specification, also look for places where the code contradicts itself across files: wrong argument order,
attributes that do not exist, data stored one way and read another, wrong boundary comparisons, pagination, HTTP error
codes.
List: file:line, the symptom a user would see, and whether the bug involves several files. Examine every module in
shopflow/ and finally list the modules you examined. Do not list the same bug twice. Do NOT change code yet.
```

Step 3 (one bug per message; order 3, 1, 2, 4, 5):

```text
<BUG DESCRIPTION>
Work in this order and do not create new files in the repository:
1. Call find_task_anchors with the bug description; if there is no anchor, use search_symbols to find the related functions.
2. Call get_related_context from the anchors; follow get_callers / get_callees if the bug spans several files.
   (explain_dependency_path: source is the CALLER, target is the CALLEE.)
3. Read the files the graph points to. Reproduce the bug with `python -c` using shopflow.app.build_app.
4. Make a minimal fix that follows the specification, then rerun the reproduction.
5. Call analyze_patch_impact and verify_patch_graph_constraints WITHOUT a diff (the server compares the working tree
   with the code of the graph). Report their results verbatim, including checked_diff.not_checked. If a tool reports an
   error, treat the change as NOT checked.
6. Call build_or_update_graph (committing is optional).
7. Report: root cause, file:line changed, result of each check (checked or not checked).
```

Steps 4–5:

```text
Rerun every reproduction you used, each as a separate `python -c` command, and report the result of each. Then write a
table: bug -> root cause -> file:line changed -> evidence (reproduction before/after, results of analyze_patch_impact
and verify_patch_graph_constraints, verbatim) -> what could not be checked.
```

## Bug table (same for both runs)

| # | Bugs | `<BUG DESCRIPTION>` |
|---|---|---|
| 1 | B03 + B08 | Customer C003 orders 1 MOU-2001 with coupon WELCOME10 and always gets "discount rate out of range". After that error, the "reserved" count of MOU-2001 goes up even though no order was created. |
| 2 | B16 + B11 | Customer C003 (standard tier) orders 2 KEY-1001 (159.80 USD, 2.4 kg). The quote shows a shipping fee of 244.70 and the tax is also charged on the shipping fee. The order should ship free, with tax 15.98 and total 175.78. |
| 3 | B04 | Alice (C001) orders 1 MOU-2001, then Bob (C002) orders 1 CAB-4001. Bob's order also contains Alice's MOU-2001 line, and its subtotal includes the other order's amount. |
| 4 | B09 + B17 | Order 2 HUB-5001, confirm it, then call POST /orders/<id>/ship: the response is 500 "internal error". Despite the error, the order becomes shipped and the stock has been reduced; afterwards "available" for HUB-5001 is negative. |
| 5 | B13 | A shipped order can be cancelled, and the cancellation also puts the items back into stock. Per the specification, shipped is a final state: cancelling a shipped order must raise an invalid-transition error and must not return items to stock. |
| 6 | B06 | HUB-5001 has 3 left. A first order for 2 succeeds; a second order for 2 more also succeeds, so the total reserved exceeds the stock. |
| 7 | B07 | With build_app(today=lambda: date(2026, 11, 20)) (a Friday), shipping an order gives an expected delivery date of 2026-11-26, one day early, as if Saturday were a business day. |
| 8 | B02 | The price 2.675 is rounded to 2.67, but it must be 2.68 (ROUND_HALF_UP). |
| 9 | B10 | There are 2 confirmed orders (totals 100 and 50) and 1 pending order. average_order_value returns 50; it should be 75. |
| 10 | B01 | GET /products?page=1&size=2 returns only 1 product. |
| 11 | B12 | GET /products/XYZ-9999 (a SKU that does not exist) returns 500; it should be 404. |
| 12 | B05 | CAB-4001 has exactly 5 available (equal to LOW_STOCK_THRESHOLD = 5) but is not in the low-stock list. A product at the threshold must also be listed. |
| 13 | B15 | Looking up a customer by the email "ALICE@EXAMPLE.COM" (upper case) does not find Alice. |
| 14 | B14 | Registering a customer with the valid email "user+tag@example.com" fails with "invalid email". |
