# TV2 · Các lượt chạy người dùng thực hiện (plan 2026-11-17)

> Plan: `docs/superpowers/plans/2026-11-17-tv2-g1-embedding-r1-heldout.md`. Code của Task 1–7 đã xong; các bước dưới cần GPU, nhãn của người, hoặc quyết định của nhóm.
> Chạy trong WSL, tại `~/rt1`, **attached** (`tee` log), không chạy hai lượt nặng cùng lúc (WSL chỉ có 7,8 GB RAM; lượt kiểm tra G1 ngày 17/11 đã bị dừng vì máy hết bộ nhớ).
> `R` = đường dẫn repo trong WSL, ví dụ `R=/mnt/d/kltn/vgar_mcp_mvp_demo`.

## 1. G1: kiểm tra số cũ không đổi (Task 2, bước 5)

```bash
cd ~/rt1/g1
PYTHONPATH=$R/src ~/.vgar-wsl/bin/python $R/scripts/g1_evaluate.py --kit ~/rt1/g1 --out ~/rt1/g1/report_check \
  --tsg-executable ~/tsg/bin/tree-sitter-graph --tsg-tree-sitter-dir ~/tsg/config --enable-jarvis | tee check.log
python3 -c "import json;a=json.load(open('report/g1_report.json'));b=json.load(open('report_check/g1_report.json'));print(a['configurations']==b['configurations'], a['agreement']==b['agreement'])"
```

Kỳ vọng: `True True`.

## 2. G1: độ khớp với người (Task 2, bước 6)

Nhãn người dùng gửi: `C:\Users\nlhnh\Downloads\agreement_human_labelled.csv` (30/30 mục, khớp code và ứng viên của bộ G1; khác nhãn Claude ở 8 mục). Xác nhận đây là nhãn người gán mù, rồi:

```bash
cp /mnt/c/Users/nlhnh/Downloads/agreement_human_labelled.csv ~/rt1/g1/agreement_human.csv
PYTHONPATH=$R/src ~/.vgar-wsl/bin/python $R/scripts/g1_evaluate.py --kit ~/rt1/g1 --out ~/rt1/g1/report_human \
  --agreement-sheet agreement_human.csv \
  --tsg-executable ~/tsg/bin/tree-sitter-graph --tsg-tree-sitter-dir ~/tsg/config --enable-jarvis | tee human.log
```

Mã 3: điền `final_label` trong `~/rt1/g1/disagreements_agreement_human.csv`, lưu thành `~/rt1/g1/settlement_agreement_human.csv`, chạy lại. Không sửa `agreement_human.csv` sau lần chạy đầu (bị khóa bằng hash).

## 3. Component boundary (Task 3)

Gán cột `label` (`correct` / `merge` / `split`) trong `C:\Users\nlhnh\Downloads\components.csv`, đọc `components.md`. Sau đó:

```bash
cp /mnt/c/Users/nlhnh/Downloads/components.csv ~/rt1/g1/components/components.csv
PYTHONPATH=$R/src ~/.vgar-wsl/bin/python $R/scripts/g1_component_kit.py --kit ~/rt1/g1 --out ~/rt1/g1/components --lock
PYTHONPATH=$R/src ~/.vgar-wsl/bin/python $R/scripts/g1_component_kit.py --kit ~/rt1/g1 --out ~/rt1/g1/components --score
```

## 4. Đếm task held-out cho D3-1 (Task 7, bước 5)

Kiểm mọi dòng bằng `validate_task` như `prepare_dataset` (dừng nếu có dòng lỗi), đếm theo đường dẫn file trong patch, không in nội dung. Kết quả và mỗi dòng trong `results/heldout_access.log` có `parquet_sha256`; ghi lại hash này cùng hai con số.

```bash
PYTHONPATH=$R/src ~/.vgar-wsl/bin/python $R/scripts/count_heldout_eligible.py ~/w9/dataset/test-00000-of-00001.parquet
```

## 5. Embedding và frontier trên 50 task dev (Task 8)

```bash
# venv tạo bằng uv, không có pip; torch lấy từ index PyTorch, phần còn lại từ PyPI (CodeRankEmbed cần einops)
uv pip install --python ~/.vgar-wsl/bin/python torch --index-url https://download.pytorch.org/whl/cu121
uv pip install --python ~/.vgar-wsl/bin/python sentence-transformers einops
~/.vgar-wsl/bin/python -c "import torch, sentence_transformers as s; print(torch.__version__, torch.cuda.is_available(), s.__version__)"
~/.vgar-wsl/bin/python -c "from huggingface_hub import model_info; print(model_info('nomic-ai/CodeRankEmbed').sha)"
PYTHONPATH=$R/src ~/.vgar-wsl/bin/python $R/ablation_matrix/run_r1_ablation.py ~/rt1 ~/rt1/data/manifests/w10-dev-50-gold.json \
  --out ~/rt1/results/r1_emb50 --allow-fallback-counter --prune \
  --embedding-model nomic-ai/CodeRankEmbed --embedding-revision <sha> --embedding-cache ~/rt1/emb_cache | tee ~/rt1/r1_emb50.log
```

`--embedding-revision` phải là SHA 40 ký tự (không nhận `main` hay tag). Tiền tố truy vấn lấy theo model (CodeRankEmbed có tiền tố, jina-v2-code không có); model khác phải truyền `--embedding-query-prefix`. Model, revision và tiền tố được ghi vào `summary.json` (khóa `embedding`). Nếu bị ngắt, chạy lại cùng lệnh với `--resume`; nếu đổi model, revision hay tiền tố thì `--resume` sẽ dừng, khi đó dùng `--out` mới.

Ghi lại phiên bản `sentence-transformers`, `torch` và SHA của model. Kiểm tra: 50/50 SUCCEEDED; 9 cấu hình cũ trùng `~/rt1/results/r1_50/summary.json`.

## 6. Freeze và held-out (Task 9–10)

Sau mục 2–5: Claude viết `docs/protocol_freeze_r1_heldout.md`; nhóm duyệt; người dùng tạo annotated tag `protocol-freeze-r1`; rồi tạo manifest bằng `scripts/prepare_manifest.py --split heldout --allow-heldout --protocol r1 ...` (file `verified-<rev12>-heldout-r1-<count>.json`; của repair là `...-heldout-repair-...`) và chạy R1 với `--allow-heldout` đúng một lần.
