# Hướng dẫn gán nhãn GraphDiff (L4-7) và chạy GD1 (14/11/2026)

Nguồn: proposal §7.5 dòng 753–760 (giao thức gán nhãn tay), spec `docs/superpowers/specs/2026-11-14-layer4-graphdiff-design.md` §6–§7.

**Số GD1 chỉ có sau khi người gán nhãn xong.** Số của benchmark 14/11 (`docs/status/graphdiff_ast_vs_proposal_tools_2026-11-14.md`, 68 commit tổng hợp) là dữ liệu tổng hợp, **không phải GD1**.

## 1. Chuẩn bị (người dùng tự chạy, WSL cho repo nặng)

R1 runner tải tarball nên không có lịch sử git. GraphDiff cần clone đầy đủ lịch sử:

```bash
mkdir -p ~/vgar-clones && cd ~/vgar-clones
# một lần cho mỗi repo trong manifest R1 (owner/name -> owner__name)
git clone https://github.com/<owner>/<name>.git <owner>__<name>
```

Kiểm tra: mỗi `base_commit` của manifest phải có trong clone (`git cat-file -t <base_commit>` in ra `commit`). Task nào thiếu clone hoặc thiếu commit được ghi vào `sample.json` (`skipped_tasks`), không bị bỏ qua lặng lẽ.

## 2. Tạo mẫu và bảng gán nhãn

```bash
python scripts/graphdiff_label_kit.py --manifest <manifest R1 .json> --git-root ~/vgar-clones \
    --out results/graphdiff_labels --window 50 --target 100 --seed 0
```

Kết quả:
- `sheet.csv`: mỗi dòng là một thực thể mà raw diff đánh dấu (hàm, method, class, biến toàn cục hoặc module), chỉ code production (file test bị loại). Cột: `row_id, split, repo, commit, subject, path, entity, node_id, before_code, after_code, diff_link, label, annotator, note`.
- `sample.json`: seed, hash manifest, danh sách commit, split của từng commit, tỉ lệ commit có subject kiểu fix, task bị bỏ qua và lý do.

Quy tắc lấy mẫu: cửa sổ first-parent 50 commit kết thúc ở `base_commit` của mỗi task (không bao giờ sau nó); bỏ merge, bỏ commit không đổi file `.py` hoặc đổi hơn 10 file `.py`; phân tầng theo số file `.py` (1, 2–3, 4–10); 60–70% commit có subject khớp `fix|bug|issue|error`. Chia **theo commit** trước khi gán nhãn: `dev` 40%, `eval` 60%.

Bảng **không** chứa dự đoán của GraphDiff, để người gán nhãn không bị ảnh hưởng. Đừng mở `graph_edits.jsonl` trước khi gán nhãn xong.

## 3. Bốn nhãn của proposal (+ `unsure`)

Điền cột `label` bằng đúng một giá trị: `bug-fix`, `refactor`, `formatting`, `unrelated`, `unsure`. Đọc `subject`, `before_code`, `after_code`; khi cần ngữ cảnh, mở `diff_link`.

| Nhãn | Khi nào | Ví dụ Python |
|---|---|---|
| `bug-fix` | Thay đổi hành vi của thực thể này để sửa lỗi mà commit nói tới (hoặc rõ ràng là sửa lỗi) | `if subtotal > LIMIT:` → `if subtotal >= LIMIT:` trong commit "Fix free shipping threshold" |
| `refactor` | Đổi cấu trúc nhưng giữ nguyên hành vi: đổi tên, chuyển hàm, tách/gộp hàm, chỉ cập nhật chỗ gọi theo tên mới | `return helper(x)` → `return assist(x)` sau khi `helper` được đổi tên thành `assist` |
| `formatting` | Chỉ đổi trình bày: khoảng trắng, xuống dòng, kiểu dấu nháy, comment, docstring | Thêm `# TODO`, sửa chính tả docstring, chạy black |
| `unrelated` | Thay đổi hành vi thật nhưng không liên quan tới mục đích của commit | Commit "Fix parser crash" nhưng cũng thêm log `logger.debug(...)` vào hàm export, hoặc thêm một tính năng nhỏ khác |
| `unsure` | Không quyết định được sau khi xem diff đầy đủ | Ghi lý do vào `note` |

Quy tắc phụ:
- Một thực thể vừa có sửa lỗi vừa có formatting → `bug-fix` (nhãn theo phần thay đổi hành vi).
- Dòng `module` (entity là tên module): xét các câu lệnh cấp module ngoài hàm/class (import, câu lệnh chạy khi import). Thêm/bớt import chỉ vì đổi tên → `refactor`.
- Commit có subject không nói gì ("update", "wip"): dùng diff để đoán mục đích; nếu không đoán được, thực thể thay đổi hành vi → `unsure`.
- Ghi tên mình vào `annotator`.

**Hai người gán nhãn** cho ít nhất 20% số commit (chọn các commit đầu tiên của bảng theo thứ tự `row_id`). Người thứ hai thêm dòng mới y hệt dòng gốc (cùng `row_id`) với `label` và `annotator` của mình. Bộ đánh giá tính Cohen's κ trên các dòng có hai nhãn.

## 4. Chạy GraphDiff trên các commit đã lấy mẫu

Với mỗi (repo, `base_commit`) trong mẫu, cần graph snapshot ở đúng `base_commit` (graph do R1 runner build, hoặc build bằng `PythonGraphBuilder` với `repo_key=<owner>__<name>`, source root `src`). Sau đó:

```bash
# A. đầy đủ (RefactoringMiner + ast)
python scripts/graphdiff.py ~/vgar-clones/<owner>__<name> --graph <graph.json|graph.db> --max-commits 50 \
    --rm-home /abs/RefactoringMiner-3.2.0 --java-home /abs/jdk-21 --out results/graphdiff/<key>/full
# C. chỉ ast (không truyền RefactoringMiner, và bỏ các biến VGAR_REFACTORINGMINER_*)
python scripts/graphdiff.py ~/vgar-clones/<owner>__<name> --graph <graph> --max-commits 50 \
    --out results/graphdiff/<key>/ast_only
```

RefactoringMiner do người dùng chạy. Chạy tay một lần cho cả cửa sổ rồi dùng chế độ precomputed:

```bash
java -classpath "/abs/RefactoringMiner-3.2.0/lib/*" org.refactoringminer.RefactoringMiner \
    -bc <clone> <cha của commit cũ nhất trong cửa sổ> <base_commit> -json <out>/<base_commit>.json 2> <out>/<base_commit>.stderr.txt
echo '{"tool_version": "3.2.0"}' > <out>/metadata.json
python scripts/graphdiff.py <clone> --graph <graph> --rm-output <out> --out results/graphdiff/<key>/full
```

Chưa kiểm tra bằng JVM thật: `-bc <start> <end>` có tính `start` hay không (code giả định không tính). Nên thử trên một repo 3 commit trước khi chạy lớn. Commit trong cửa sổ không có output RefactoringMiner sẽ dùng `ast`, và lý do được đếm trong `summary.json` (`refactoringminer_fallbacks`).

## 5. Tính GD1

```bash
python scripts/evaluate_graphdiff.py --sheet results/graphdiff_labels/sheet.csv \
    --full results/graphdiff/*/full --ast-only results/graphdiff/*/ast_only --out results/graphdiff_gd1
```

Mặc định chỉ dùng split `eval`. Commit nào của bảng không có trong lần chạy GraphDiff nào (thiếu thư mục `--full`, hoặc cửa sổ ngắn hơn) bị loại khỏi phép tính, được liệt kê trong `uncovered_commits`, và script trả mã lỗi 1. Dùng `--split dev` khi chỉnh trọng số/ngưỡng; báo cáo khi đó có tiêu đề "development split, not GD1". Không chỉnh trọng số hay `τ` trên split `eval` rồi báo cáo trên chính nó.

## 6. Downstream trên retrieval (proposal dòng 760)

```bash
# chạy trong WSL như ma trận R1 ngày 11/11; ba thư mục out riêng
python ablation_matrix/run_r1_ablation.py <root> <manifest> --out <out>/none --allow-fallback-counter
python ablation_matrix/run_r1_ablation.py <root> <manifest> --out <out>/raw --allow-fallback-counter --history raw --git-root ~/vgar-clones
python ablation_matrix/run_r1_ablation.py <root> <manifest> --out <out>/graphdiff --allow-fallback-counter --history graphdiff --git-root ~/vgar-clones
python ablation_matrix/run_r1_ablation.py --compare-history <out>/none <out>/raw <out>/graphdiff
```

Khi có `--history`, chỉ chạy arm `task_trace` (R-A2), mọi cấu hình retrieval khác giữ nguyên (trọng số `recent_change_frequency` 0.1). Lần chạy `none` là lần chạy R1 bình thường (mọi arm); `--compare-history` chỉ so arm `task_trace` của ba thư mục trên cùng các task. Kết quả rỗng hoặc âm cũng được báo cáo đúng như vậy (proposal dòng 1445: "or document failure cases").
