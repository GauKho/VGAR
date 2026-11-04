# Runbook: `solve --agent` trên 5 dev task (M3-X2b, nguồn bảng M1)

> Spec: `docs/superpowers/specs/2026-11-03-m3-w12-design.md` §2–3. **Người dùng tự chạy** trên máy GPU (WSL), Qwen thật.
> Kết quả chỉ để mô tả (N = 5), không so sánh thống kê với A0–A3.

## Task (chốt trước khi chạy)

5 task RUNNABLE đầu tiên theo thứ tự `configs/m3/w10_dev_stage1.json`, đúng thứ tự này:

1. `astropy__astropy-13033`
2. `django__django-10914`
3. `matplotlib__matplotlib-13989`
4. `mwaskom__seaborn-3069`
5. `pallets__flask-5014`

Task nào lỗi vẫn nằm trong mẫu số, ghi lý do. Task `OVER_CAP` ở preflight không chạy, ghi `TASK_EXCLUDED` (D25).
**Không chạy lại có chọn lọc.** Nếu trễ: chỉ chạy 3 task đầu và ghi N = 3.

## Tiền điều kiện

- H3 (`signature_changed`) đã merge (quyết định E7).
- Dry-run M1-W12-2 đã PASS (H7).
- Cùng commit code và cùng model SHA với batch W12. Ghi `git log -1 --oneline` vào status trước khi chạy.
- Config thí nghiệm W12 (sinh bằng `scripts/derive_experiment_config.py`, có đủ 5 task trên). Trong các lệnh dưới,
  thay **`CONFIG`** bằng đường dẫn file đó; đây là chỗ duy nhất phải tự điền. Variant phải là bản W10
  (`path_listing = context`, D19); script sinh config đã kiểm điều này.
- Data root là `~/w10`. Trong clone dùng venv cũ thì `export PYTHONPATH=$PWD/src` trước mọi lệnh.

## Lệnh (trong WSL, thư mục repo; mỗi lệnh một dòng)

Bước 0, bắt buộc: preflight token (không cần GPU/Docker). Mọi task phải `FITS`; task `OVER_CAP` bỏ khỏi vòng lặp
dưới và ghi `TASK_EXCLUDED`.

```bash
.venv/bin/python scripts/run_repair_experiment.py preflight --config CONFIG --data-root ~/w10 --output-root /tmp/x2b-preflight
```

```bash
OUT=results/m3/w12/agent/$(date -u +%Y%m%dT%H%M%SZ); mkdir -p $OUT; export VGAR_MCP_AUDIT_LOG=$PWD/$OUT/mcp_audit.jsonl; { git log -1 --oneline; git status --porcelain | grep -v '^?? results/'; } | tee $OUT/commit.txt
for T in astropy__astropy-13033 django__django-10914 matplotlib__matplotlib-13989 mwaskom__seaborn-3069 pallets__flask-5014; do .venv/bin/python -m vgar.cli solve --agent --mode real --experiment CONFIG --task-id $T --variant A2 --generator agent --data-root ~/w10 --output-root $OUT 2>&1 | tee $OUT/$T.log; done
.venv/bin/python scripts/aggregate_agent_traces.py --traces $OUT --audit $OUT/mcp_audit.jsonl --out $OUT/m1
```

`commit.txt` ghi cả commit lẫn file chưa commit (E6). Console mỗi task: header, một dòng mỗi bước và lượt model, khối
`== RESULT` (spec `docs/superpowers/specs/2026-11-03-m3-w12-trace-design.md`); dòng `[VGAR_TRACE]` đầy đủ chỉ in khi
`export VGAR_TRACE=debug`.

`VGAR_MCP_AUDIT_LOG` riêng cho lần chạy này để audit của lần khác không lẫn vào phép tính audit completeness.
`--generator agent`: diff sinh bằng chính model agent đã nạp (cùng snapshot, cùng prompt kiểm bằng hash, greedy,
`output_cap`), nên GPU 6 GB chỉ giữ một bản Qwen. Với generator mặc định (`hf_worker`), hai bản Qwen chia GPU và mọi
lần sinh chạm `generation_timeout` 900 s (03/11, seaborn 3/3 lần). Từ 04/11 generator agent cũng áp
`generation_timeout` (qua `max_time`), quá giờ thì ra `GENERATION_TIMEOUT`; trace ghi `generator = agent_model`. Bảng M1 phải ghi rõ đường sinh này.

## Gửi lại

- Nội dung `$OUT/m1/m1.md`.
- 3 dòng cuối (`[status]`, `[run]`, `[trace]`) của từng `$OUT/<task>.log`.
- Đường dẫn `$OUT` để ghi vào `docs/status/m3.md`.
