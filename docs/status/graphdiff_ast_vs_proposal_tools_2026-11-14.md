# GraphDiff (§7) trên Python: module `ast` so với công cụ của proposal

Ngày 14/11/2026. Người chạy: TV2 (mô phỏng giúp TV3, chủ Layer 4). Đây là thí nghiệm mô phỏng trên dữ liệu nhân tạo, không phải bảng GD1 của plan.

## 1. Câu hỏi

Proposal §7.3 nêu pipeline: [1] RefactoringMiner, [2] UTango-style, [3] GumTree / DAT-GumTree, [4] chuyển AST edit thành graph edit, [5] chấm confidence. Code hiện có của TV3 (`bb25fff3`) dùng module `ast` của Python cho L4-4 (`src/vgar/graph/ast_diff.py`) và dulwich cho L4-1 (`src/vgar/graph/history.py`).

Thí nghiệm trả lời hai câu hỏi trên Python:

1. Về tốc độ, `ast` so với RefactoringMiner 3.2.0 và GumTree 4.1.0 thế nào?
2. Về hiệu quả, cách nào tách bản sửa lỗi khỏi refactor và thay đổi định dạng tốt hơn?

## 2. Thiết lập

**Bộ commit có nhãn.** Lấy 17 bug của `shopflow-ground-truth`. Mỗi bug có 4 biến thể, tổng cộng 68 commit được đánh giá:

| Biến thể | Commit chứa |
|---|---|
| `pure` | Chỉ bản sửa lỗi |
| `format` | Bản sửa lỗi + thay đổi định dạng ở một hàm khác: thêm comment, đổi nháy kép thành nháy đơn. Đã kiểm tra AST không đổi. |
| `refactor` | Bản sửa lỗi + một trong 8 refactor ở file khác: đổi tên hàm (×2), tách hàm, di chuyển hàm, đổi tên tham số, đổi tên class, đổi tên biến, gộp hàm vào nơi gọi. Code sau refactor vẫn import và chạy được. |
| `refactor+format` | Cả hai loại nhiễu trên |

Nhãn được tính từ những thay đổi đã cài: mỗi dòng đổi được ánh xạ về hàm bao quanh nó. Không có công cụ nào đang được so tham gia vào việc gán nhãn.

**Lịch sử thật.** 30 commit first-parent gần nhất của repo này có chạm file `.py`, gồm 212 cặp file. Bộ này chỉ dùng để đo tốc độ và mức trùng khớp, vì không có nhãn.

**Ba cấu hình.** Cả ba cùng dùng chung bước 4–5:
- ánh xạ edit về mức hàm (`path::Class.method` hoặc `path::<module>`);
- bỏ các hàm mà một refactor phát hiện được có liên quan;
- bỏ các hàm chỉ thay đổi vì tham chiếu tới tên đã đổi.

| Cấu hình | Bước 3 (edit) | Bước 1 (refactor) |
|---|---|---|
| `ast` | `diff_python_commit` của TV3 | Cặp ADDED/REMOVED có thân hàm giống hệt |
| Proposal | GumTree 4.1.0 (`python-treesitter-ng`) | RefactoringMiner 3.2.0 |
| Kết hợp | `diff_python_commit` của TV3 | RefactoringMiner 3.2.0 |

**Thước đo.** Precision, recall và F1 ở mức hàm cho tập "hàm sửa lỗi" còn lại sau khi lọc.

## 3. Kết quả

### 3.1 Tách bản sửa lỗi khỏi nhiễu

Đơn vị là F1. Recall bằng 1.00 ở mọi ô.

| Cấu hình | pure | format | refactor | refactor+format | Tổng P | **Tổng F1** |
|---|---:|---:|---:|---:|---:|---:|
| `ast` | 1.00 | 1.00 | 0.76 | 0.76 | 0.76 | **0.86** |
| GumTree + RefactoringMiner | 1.00 | 0.69 | 0.88 | 0.73 | 0.68 | **0.81** |
| `ast` + RefactoringMiner | 1.00 | 1.00 | 0.88 | 0.88 | 0.88 | **0.94** |

Nguồn của các dương tính giả (FP):
- **`ast`:** 24 FP, đều đến từ tách hàm, gộp hàm, đổi tên tham số, đổi tên biến, và dòng import mới khi di chuyển hàm.
- **GumTree + RefactoringMiner:** 26 FP do định dạng (tree-sitter giữ comment và ký tự dấu nháy) và 10 FP do refactor.
- **Kết hợp:** 10 FP, gồm phần gộp hàm mà RefactoringMiner bỏ sót và dòng import khi di chuyển hàm.

### 3.2 Phát hiện refactor (bước 1)

| Loại (số commit có nhãn) | `ast`, thân giống hệt | RefactoringMiner 3.2.0 |
|---|---:|---:|
| Đổi tên hàm (12) | 12 | 12 |
| Đổi tên class (4) | 4 | 4 |
| Di chuyển hàm (4) | 4 | 4 |
| Tách hàm (2) | 0 | 2 |
| Đổi tên tham số (6) | 0 | 6 |
| Đổi tên biến (4) | 0 | 4 |
| Gộp hàm vào nơi gọi (2) | 0 | 0 |
| **Recall / precision** | **0.59 / 1.00** | **0.94 / 0.80** |

Precision của RefactoringMiner thấp hơn vì 8 mục "Change Attribute/Variable Type". Đây là hệ quả có thật của việc đổi tên class nhưng nằm ngoài nhãn. Trên 17 commit `pure`, RefactoringMiner không báo refactor nào, nên bộ lọc không giấu mất bản sửa lỗi nào.

### 3.3 Tốc độ

| | Bộ có nhãn | 30 commit thật (212 file) |
|---|---|---|
| `ast` (chạy trong tiến trình Python) | trung vị 13 ms/commit | 30 s tổng (riêng 1 commit 48 file: 22 s) |
| RefactoringMiner | 1.48 s/commit (một JVM mỗi commit); 0.06 s/commit nếu một JVM chạy `-bc` qua 135 commit | 165 s |
| GumTree | 0.59 s/file, trong đó 0.47 s khởi động JVM, khoảng 0.12 s diff thật; 1.21 s/commit | 249 s |

Trên lịch sử thật, `ast` tìm được 4 cặp đổi tên/di chuyển, còn RefactoringMiner tìm được 15 cặp, trùng 3 cặp khi so theo tên.
- Cặp thứ tư (`require_trusted_fixture`, chuyển từ `pipeline.py` sang `deadline.py`) RefactoringMiner cũng báo, nhưng dưới dạng "Move Class `pipeline.__module__` → `deadline.__module__`". Vì vậy cả 4 cặp `ast` tìm được đều có trong kết quả của RefactoringMiner.
- 11 cặp chỉ RefactoringMiner thấy phần lớn là đổi tên kèm sửa thân hàm, loại mà `ast` không bắt được. Chưa có nhãn để xác nhận các cặp này đúng.
- Bản đầu của script không đếm loại "Move Class", nên đã báo nhầm "chỉ trùng 1 cặp". Lỗi đã được sửa.

## 4. Giới hạn

- **Dữ liệu nhân tạo:** repo nhỏ (shopflow), mỗi commit nhiều nhất 1 refactor và 1 thay đổi định dạng. Nhãn tạo theo cách cài, không phải nhãn tay theo L4-7.
- **Recall 1.00 có một phần do cách dựng:** refactor được đặt ở file khác với file có bug. Chưa thử trường hợp refactor và sửa lỗi nằm trong cùng một hàm, và chưa thử trường hợp RefactoringMiner báo nhầm refactor ngay trên hàm sửa lỗi.
- **Bước 2 (UTango) chưa được kiểm tra**, vì không có công cụ chạy được cho Python.
- **Bước 4–5 là code của thí nghiệm**, không phải L4-5/L4-6 của TV3. Lần chạy đầu có một lỗi ở bước ghép: khi RefactoringMiner báo đổi tên class, các method chưa được đánh dấu theo. Lỗi đã được sửa bằng cùng quy tắc với phía `ast`.

## 5. Đề xuất cho TV3 (L4)

1. Giữ `ast` (`diff_python_commit`) làm nền cho L4-4/L4-5: nhanh, không bị nhiễu định dạng, và khớp trực tiếp với id node trong graph.
2. Thêm RefactoringMiner cho L4-2. Chạy một JVM bằng `-bc` cho cả cửa sổ lịch sử. Gọi thẳng `java -cp lib\* org.refactoringminer.RefactoringMiner`, vì `RefactoringMiner.bat` vượt giới hạn độ dài dòng lệnh của `cmd`.
3. Chỉ dùng GumTree làm thuật toán thứ hai cho `algorithm_agreement` (§7.4). Khi đó cần lọc node `comment` và các thay đổi chỉ khác dấu nháy. Vị trí GumTree 4.1 trả về tính theo **ký tự**, không theo byte.
4. L4-7 (bộ commit gán nhãn tay từ lịch sử thật) vẫn cần làm để có con số GD1.

## 6. Chạy lại

Script nằm ở `scripts/graphdiff_bench/`. Thư mục làm việc là `VGAR_GRAPHDIFF_WORK`, mặc định `%TEMP%\vgar-graphdiff-bench`, nằm ngoài repo.

```powershell
$env:VGAR_GRAPHDIFF_WORK = "$env:TEMP\vgar-graphdiff-bench"
.venv\Scripts\python scripts\graphdiff_bench\bench_build.py
# Giải nén RefactoringMiner-3.2.0.zip vào $env:VGAR_GRAPHDIFF_WORK\tools\rm
# và gumtree-4.1.0.zip vào $env:VGAR_GRAPHDIFF_WORK\tools\gt (bản phát hành trên GitHub). JDK 21: VGAR_JAVA_HOME.
.venv\Scripts\python scripts\graphdiff_bench\run_java_tools.py
.venv\Scripts\python scripts\graphdiff_bench\evaluate.py
```

- `bench_build.py` cho cùng SHA ở mỗi lần chạy, vì tác giả và ngày commit đã cố định.
- Mẫu lịch sử thật là 30 commit gần nhất tại HEAD lúc chạy. Danh sách SHA đã dùng nằm trong `graphdiff_bench_2026-11-14/gold.json`.
- Dữ liệu của lần chạy này nằm trong `docs/status/graphdiff_bench_2026-11-14/`:
  - `gold.json`: nhãn;
  - `timings.json`: thời gian;
  - `detail.json`: dự đoán của từng cấu hình trên từng commit;
  - `report_raw.md`;
  - `refactoringminer_outputs.tar.gz`.
- Kết quả GumTree (48 MB) không lưu; có thể tạo lại bằng script.

## 7. Câu hỏi để đối chiếu với các bài báo khác

Tên bài báo ghi theo trí nhớ. Cần mở bản gốc để kiểm tra tác giả, năm, con số và phạm vi trước khi trích dẫn.

### A. Phát hiện refactor (bước 1)

1. RefactoringMiner 2.0 (Tsantalis và cộng sự, TSE 2020) báo precision/recall rất cao trên Java. Ở đây, trên Python, ta đo được recall 0.94 và precision 0.80. Khoảng cách này do ngôn ngữ, do dữ liệu nhân tạo, hay do cách định nghĩa nhãn (các mục "Change Type" là hệ quả của refactor)?
2. PyRef (Atwi và cộng sự, SCAM 2021) là công cụ phát hiện refactor riêng cho Python. Nó hỗ trợ những loại nào, độ chính xác báo cáo bao nhiêu, và có bắt được Inline Method mà RefactoringMiner 3.2.0 bỏ sót ở đây không?
3. Có bài báo nào đánh giá riêng phần hỗ trợ Python của RefactoringMiner 3.x (độ phủ từng loại refactor, refactor xuyên file) không?
4. Heuristic "thân hàm giống hệt" của phía `ast` (precision 1.00, recall 0.59) tương ứng với hướng nào trong tài liệu, ví dụ origin analysis (Godfrey & Zou, TSE 2005)? Các hướng đó xử lý đổi tên kèm sửa thân hàm thế nào?

### B. AST diff (bước 3)

5. GumTree (Falleri và cộng sự, ASE 2014) và DAT, tức tối ưu siêu tham số cho AST diff (Martinez và cộng sự, TSE 2023), chủ yếu được đánh giá trên Java. Có nghiên cứu nào đánh giá GumTree với tree-sitter Python và cách loại comment hay định dạng không?
6. RefactoringMiner AST diff (Alikhanifard & Tsantalis, TOSEM 2024) tuyên bố tốt hơn GumTree nhờ nhận biết refactor, và proposal §7.3 bước [3] có nhắc tới nó. Có nên thử nó làm thuật toán diff thứ hai thay cho GumTree?
7. Thí nghiệm này đo ở mức hàm, còn GumTree thường được đánh giá ở mức action/node. Nghiên cứu nào đánh giá ở mức method/entity, ví dụ ChangeDistiller (Fluri và cộng sự, TSE 2007), để so sánh trực tiếp được với output `UPDATE_METHOD_BODY` mà proposal mong muốn?

### C. Commit lẫn lộn và thay đổi không thiết yếu (bước 2)

8. Kawrykow & Robillard (ICSE 2011) đo tỉ lệ thay đổi không thiết yếu (non-essential changes) trên lịch sử thật là bao nhiêu? Tỉ lệ "1 nhiễu mỗi commit" ở đây có đại diện cho thực tế không?
9. Herzig & Zeller (MSR 2013) cho biết tỉ lệ commit lẫn lộn là bao nhiêu? Flexeme (Pârţachi và cộng sự, FSE 2020), SmartCommit (Shen và cộng sự, FSE 2021) và UTango (Li và cộng sự, FSE 2022) dùng thước đo gì? Có công cụ nào chạy được với Python để làm baseline cho bước [2] không?
10. Các nghiên cứu trên tạo commit lẫn lộn nhân tạo bằng cách ghép các commit nguyên tử. Cách dựng bộ dữ liệu ở đây (cài refactor và định dạng có kiểm soát) có tương đương không, và họ thừa nhận giới hạn gì về tính hợp lệ?

### D. Tác động xuống các bước sau (§7.5)

11. Các bộ dữ liệu sửa lỗi như Defects4J (Sobreira và cộng sự phân tích, SANER 2018) và SWE-bench: bao nhiêu phần trăm patch gốc chứa refactor hoặc thay đổi định dạng? Điều đó ảnh hưởng thế nào tới việc đánh giá sửa lỗi, đúng như tình huống proposal §7.1 nêu?
12. Có bài báo nào đo được rằng làm sạch lịch sử commit giúp retrieval, repair hoặc defect prediction tốt hơn? Ví dụ, Herzig & Zeller cho thấy commit lẫn lộn làm lệch defect prediction. Đây là "downstream impact" mà §7.5 yêu cầu.

### E. Tốc độ và tính hợp lệ

13. Các bài báo về RefactoringMiner và GumTree báo cáo thời gian chạy mỗi commit hoặc mỗi file là bao nhiêu? So với 0.06 s/commit (một JVM) và 0.12 s/file đo được ở đây thì thế nào?
14. Khi không có nhãn tay, các nghiên cứu xây "oracle" bằng cách nào, ví dụ nhiều công cụ cùng đồng ý kèm người kiểm tra như RefactoringMiner đã làm? Có nên dùng cách đó cho 30 commit thật, nơi `ast` và RefactoringMiner chỉ trùng 1 cặp?
15. Tài liệu có khuyến nghị cỡ mẫu và quy trình gán nhãn (số người gán, Cohen's kappa) cho bộ commit gán nhãn tay như L4-7 không?

## 8. Trả lời đã kiểm tra (14/11)

Chỉ ghi những gì đã đối chiếu được với nguồn hoặc với số đo của thí nghiệm này. "Chưa xác nhận" nghĩa là chưa tìm thấy nguồn, không có nghĩa là sai.

| # | Trả lời | Nguồn / căn cứ |
|---|---|---|
| 1 | RefactoringMiner 2.0 trên Java: P 99.6%, R 94%; bản trước: 98%/87%. Precision 0.80 ở đây là số đo trên dữ liệu nhân tạo: 8 FP là "Change Attribute/Variable Type" đi kèm đổi tên class, tức hệ quả có thật nhưng nằm ngoài nhãn (nhãn chỉ ghi refactor gốc). | RM 2.0 (TSE 2020); `detail.json` |
| 2 | PyRef phát hiện refactor mức method trong Python: P 89.6%, R 76.1%, so với RefactoringMiner bản chuyển sang Python. Có nguồn ghi 9 loại, có nguồn ghi 11 loại. **Chưa xác nhận** có Inline Method. | Atwi et al., SCAM 2021 |
| 3 | Bài TOSEM của Alikhanifard & Tsantalis (arXiv 2024, tạp chí 2025) là công cụ AST diff có nhận biết refactor, kèm benchmark 800 commit sửa lỗi (Defects4J) và 188 commit refactor. Đây không phải bài về hỗ trợ Python. Parser Python trong jar 3.2.0 là ANTLR. Không tìm thấy bài báo riêng đánh giá phần Python của RefactoringMiner. Bài gần nhất là ActRef (arXiv 2025), một công cụ khác: P 0.80, R 0.92 trên 1,914 refactor Python. | arXiv 2403.05939; nội dung file jar; arXiv 2505.06553 |
| 4 | Phía `ast` bỏ sót 14/34 refactor. Cả 14 thuộc 4 loại mà so khớp thân giống hệt không xử lý được: tách hàm, gộp hàm, đổi tên tham số, đổi tên biến. Liên hệ với origin analysis (Godfrey & Zou) còn chờ đọc bài. | `report_raw.md` |
| 5 | GumTree 4.1 với tree-sitter Python sinh 17 FP do comment và dấu nháy. Không thấy tùy chọn bỏ qua comment trong CLI đã dùng. Không tìm thấy bài đánh giá GumTree riêng trên tree-sitter Python. | Số đo; `run_java_tools.py` |
| 6 | Slide của tác giả: RefactoringMiner AST diff đạt P 99.6%, R 99.2% trên commit refactor, GumTree greedy khoảng 84%/70%. Cần lấy số từ bài TOSEM trước khi trích. Proposal §7.3 liệt kê ngang hàng "GumTree / DAT-GumTree / RefactoringMiner AST diff", không xếp thứ tự ưu tiên. | Slide Tsantalis; proposal dòng 713–714 |
| 7 | UTango: Li, Wang, Nguyen, ESEC/FSE 2022, tên đầy đủ "UTANGO: Untangling Commits with Context-aware, Graph-based, Code Change Clustering Learning Model". KGCompass (arXiv 2503.21710) và ARISE (Seddik & Fard, arXiv 2605.03117) là định vị lỗi và sửa lỗi, nên thước đo không so trực tiếp với diff thay đổi. | Các trang bài báo |
| 8 | Kawrykow & Robillard: tối đa 15.5% số lần cập nhật method chỉ gồm thay đổi không thiết yếu (có bài khác trích 2–15%). Bộ dữ liệu ở đây có 50% commit chứa refactor và 50% chứa định dạng, tức **nhiều nhiễu hơn thực tế**. Hai tỉ lệ khác đơn vị đếm (commit và lần cập nhật method) nên không quy ra được "gấp bao nhiêu lần". | ICSE 2011 |
| 9 | Herzig & Zeller: tối đa 15% bản sửa lỗi bị lẫn lộn, và ít nhất 16.5% (bài MSR) / 16.6% (abstract) số file bị gán nhầm với bug. Bản mở rộng ở Empirical Software Engineering 2016 ghi 6–15%. UTango được đánh giá trên C# và Java, không có Python. | MSR 2013; EMSE 2016; FSE 2022 |
| 10 | Ghép hai commit thật (kiểu Flexeme/UTango) và cài một nhiễu có kiểm soát (cách ở đây) bổ trợ nhau. Lưu ý: L4-7 trong plan yêu cầu nhãn tay trên commit thật; dữ liệu nhân tạo không thay thế được. | Plan L4-7 |
| 11 | SWE-bench (Jimenez et al., ICLR 2024): theo một nguồn thứ cấp, patch gốc trung bình sửa 32.8 dòng trên 1.7 file và 3 hàm; **chưa kiểm tra lại với Table 1**. Không có con số đã công bố về tỉ lệ patch chứa refactor hay định dạng trong SWE-bench hoặc Defects4J. | Cần đối chiếu Table 1 |
| 12 | Herzig & Zeller đo mức gán nhầm file với bug, có ảnh hưởng tới defect prediction. Họ không đo retrieval hay repair. ARISE và KGCompass không nghiên cứu việc làm sạch lịch sử commit. Chưa tìm thấy bài đo tác động của GraphDiff lên retrieval hay repair. | Như trên |
| 13 | Thời gian ở đây: RefactoringMiner 0.06 s/commit khi chia đều trong một JVM (repo nhỏ); 1.48 s/commit khi mỗi commit một JVM (repo nhỏ); 5.5 s/commit trên lịch sử thật. Con số cuối gồm cả khởi động JVM lẫn commit lớn hơn, nên không phải toàn bộ là chi phí JVM. Bài TOSEM chỉ nói thời gian "tương đương các công cụ nhanh" (theo abstract). | `timings.json` |
| 14 | Trên 30 commit thật, cả 4 cặp `ast` tìm được đều có trong kết quả RefactoringMiner (xem 3.3). Muốn có precision/recall trên commit thật thì vẫn cần nhãn tay. Nếu dùng LLM để chấm, đó chỉ là công cụ hỗ trợ, không thay nhãn tay. | `report_raw.md` |
| 15 | Công thức Cochran với p=0.5, e=0.10, độ tin cậy 95% cho n≈96. Thang κ theo Landis & Koch (1977): 0.61–0.80 là đồng thuận đáng kể, trên 0.80 là gần như hoàn hảo. | Tính trực tiếp; Landis & Koch |
