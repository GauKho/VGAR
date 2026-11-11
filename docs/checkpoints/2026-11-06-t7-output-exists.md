# T7 ? Ph?n bi?t output ?? t?n t?i v? ch?ng l?n pool, 06/11/2026

**T7 DONE code/fixture; d?ng ch? x?c nh?n T5.** Kh?ng commit/push.

## Thay ??i v? th? t? x? l?

- `evaluate_pool()` v?n resolve ???ng d?n v? `load_pool()`/ki?m hash tr??c.
- Output ?? t?n t?i (file/th? m?c, k? c? tr?ng pool): `ValueError("Campaign output already exists; choose a new output directory")`.
- Output m?i trong pool: gi? l?i `Fresh campaign output must not overlap frozen pool`.
- Gi? source overlap, `mkdir` kh?ng ghi ??, API/schema/policy/metrics/slot ERROR.
- Kh?ng c?n Docker/model; kh?ng ch?y campaign th?t, kh?ng l?m T5.

## B?ng ch?ng

- RED: 4 FAIL do th?ng b?o c?, 4 PASS; 13 test c? kh?ng thu?c reproducer.
- GREEN to?n b? hai module: **75 PASS, 0 FAIL/ERROR/SKIP** trong 2,76s.
- 8 case m?i: output empty/populated/file/tr?ng pool/trong pool; 2 case hash sai; 1 race output xu?t hi?n sau preflight. Fixture ki?m bytes v? c?u tr?c kh?ng ??i khi b? t? ch?i, kh?ng g?i prepare/verifier s?m.
- Regression c? source overlap v? output m?i h?p l?. Ruff scoped PASS, whitespace scoped PASS.
- M?t review ??c l?p scoped T7: kh?ng finding. Review kh?ng ??nh gi? l?i T6/l?ch s?; hashes preservation ki?m c?c file ??.
- Artifact: `results/m2/w1112/t7/20261106-output-exists/`; RED/GREEN logs+JUnit, commands, review, preservation, source snapshots, artifact hashes.
- TEMP ledger: `C:/Users/pc/AppData/Local/Temp/vgt7-cannohx1/`.

## L?nh test ?? d?ng

Thi?t l?p `PYTHONUTF8=1`, `PYTHONDONTWRITEBYTECODE=1`, `VGAR_GRAPH_BACKEND=demo`.
Python: `D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe`.

```powershell
$vgarPython = 'D:/Project/CAPSTONES/environments/vgar-week78-cuda/Scripts/python.exe'
$work = 'C:/Users/pc/AppData/Local/Temp/vgt7-cannohx1'
& $vgarPython -B -m pytest tests/m2/w1112/test_verifier_campaign.py -k 'output_rejection or pool_hash_validation_precedes or output_created_after_preflight' -q -p no:cacheprovider --basetemp "$work/red-t" --junitxml "$work/red.xml"
& $vgarPython -B -m pytest tests/m2/w1112/test_verifier_campaign.py tests/m2/w1112/test_verifier_eval.py -q -p no:cacheprovider --basetemp "$work/green-t" --junitxml "$work/green.xml"
& $vgarPython -B -m ruff check --no-cache src/vgar/evaluation/repair/verifier_eval.py tests/m2/w1112/test_verifier_campaign.py
git -c core.whitespace=cr-at-eol diff --check -- src/vgar/evaluation/repair/verifier_eval.py tests/m2/w1112/test_verifier_campaign.py PROGRESS.md docs/status/m2.md
```

`-B` kh?ng ghi bytecode, `-p no:cacheprovider` t?t pytest cache; basetemp ri?ng ngo?i repo, JUnit/log l?u k?t qu?. `-k` ch? d?ng t?i hi?n RED; gate GREEN ch?y ?? hai module. Khi t? ch?y l?i ph?i d?ng temp m?i. `*-command.json` l?u argv/env/exit code th?c, `gate.py` l? wrapper thu log ?? ch?y.

## B?o to?n v? gi?i h?n

- Gi? T6/source/test/docs v? b?o c?o Codex Diff ch?a commit, fixture DB; kh?ng t?o worktree ho?c thay Git metadata. D?ng checkout feature hi?n t?i theo plan b?o to?n dirty workspace.
- PROGRESS th?m ??u, m2 status th?m cu?i; gi? nguy?n l?ch s? b?ng ki?m bytes.
- Kh?ng ch?y full suite/T6 theo gi?i h?n gate c?a plan ?? duy?t.
- T6 v?n ch? smoke Docker th?t nh? checkpoint ri?ng; T7 kh?ng ??ng thay dependency ??.
