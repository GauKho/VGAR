# TV3 · Lịch sử commit cho GraphDiff và retrieval

`read_commit_history` đọc Git objects cục bộ từ SHA commit của snapshot. Kết quả giữ SHA commit, các SHA cha, thời điểm, tiêu đề và từng thay đổi file với path, mode và Git object ID hai phía. L4-2 có thể lấy blob trước và sau từ các object ID này.

Quy ước hiện tại duyệt tối đa `max_commits` theo first parent, kể từ commit đã ghim. Thay đổi ở merge được tính từ cây của cha thứ nhất. Root commit được so với cây rỗng. Đổi tên xuất hiện dưới dạng xóa và thêm path. Nếu một object dùng trong phép so sánh bị thiếu, hàm báo lỗi để caller xử lý lịch sử thiếu.

TV2 có thể truyền `change_counts` và `history_label` vào `GraphContextRetriever` hiện có. Mỗi path được đếm một lần cho mỗi commit chạm đến nó trong cửa sổ. Label lưu SHA, giới hạn và quy ước first parent. Dùng SHA khớp revision của graph để cửa sổ không chứa commit sau snapshot.

```python
from vgar.graph.history import read_commit_history
from vgar.graph.retrieval import GraphContextRetriever

history = read_commit_history(repo_root, revision=graph_revision, max_commits=50)
retriever = GraphContextRetriever(
    graph, repo_root, count_tokens=count_tokens, counter_label=counter_label,
    change_counts=history.change_counts, history_label=history.history_label,
)
```

Extra `history` cài Dulwich cho pipeline lịch sử. Trong môi trường đã có VGAR và pytest, có thể cài phiên bản được ghim rồi chạy kiểm thử.

```powershell
python -m pip install dulwich==1.2.18
python -B -m pytest -q tests/test_commit_history.py tests/test_graph_retrieval.py
```

## AST diff Python từ commit

`diff_python_commit` lấy `CommitChange` từ L4-1 và đọc hai Git blob đã ghim của từng file `.py`. Mỗi kết quả giữ `FileVersion` hai phía và các edit `ADDED`, `REMOVED`, `MODIFIED` theo tên đầy đủ của class, hàm hoặc method trong file. Với `MODIFIED`, `changed_parts` cho biết declaration hoặc body đã đổi. Vị trí dòng được giữ cho cả hai phiên bản. Các câu lệnh ngoài định nghĩa có cờ thay đổi riêng.

```python
from vgar.graph.ast_diff import diff_python_commit
from vgar.graph.history import read_commit_history

commit, = read_commit_history(repo_root, revision=revision, max_commits=1).commits
file_diffs = diff_python_commit(repo_root, commit)
```

So sánh dùng `ast` của Python đang chạy và bỏ qua vị trí dòng khi so cấu trúc. Hàm lồng được tính trong body của hàm bao ngoài. Các định nghĩa lặp cùng tên được so theo thứ tự. Khi các câu lệnh và định nghĩa có thể ghép duy nhất đổi thứ tự thực thi, diff ghi thay đổi module hoặc body class tương ứng. Đổi tên hoặc chuyển file hiện ra thành thêm và xóa. Nhận diện refactoring, ánh xạ node ID và so sánh với GumTree/DAT-GumTree vẫn thuộc các mốc tiếp theo.

```powershell
python -B -m pytest -q tests/test_python_ast_diff.py tests/test_commit_history.py
```
