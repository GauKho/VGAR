# Review các task mở lại — VGAR tuần 3–6

Đợt này tiếp tục mục 6 của hướng dẫn, base Git `a60f7b1d`, không mở audit/architecture task khác. Reviewer: Codex tự review, không phải owner sign-off. Không commit/push.

## 1. Những thay đổi thực sự

| File | Thay đổi | Ràng buộc vẫn giữ |
|---|---|---|
| `src/vgar/graph/builder.py` | Thêm occurrence vào ID chỉ khi một class lặp cùng resolved base target | Giữ hai cạnh INHERITS và mro positions, ID cạnh bình thường không đổi, validator không bị bỏ |
| `src/vgar/graph/grounding.py` | Finder sở hữu bản sao của File/Class/Function/Method/Test dùng grounding, không giữ caller-owned records | Full input graph vẫn validate; anchor matching/scoring không đổi |
| `src/vgar/graph/task_overlay.py` | Không deepcopy toàn graph; giữ scalar header, repository, relevant nodes và tập base IDs; validate base một lần và từng overlay delta | Issue/base edge collisions, endpoint types, graph version, provenance vẫn kiểm; caller mutation không đổi snapshot |
| `src/vgar/graph/retrieval.py` | Private ownership transfer cho subprocess evaluation; default vẫn deepcopy | Không đổi public MCP schemas/ranking/token budget/source proof |
| `src/vgar/evaluation/retrieval/worker.py` | Chỉ worker này bật `_take_ownership=True` trên snapshot fresh/local, sau đó không mutate graph | Task isolation, deadline300s, nguồn/pinned counter/gold policy không đổi |
| `tests/test_pending_graph_failures.py` | Reproducer repeated base/alias, IDs deterministic | Không xóa runtime-invalid source fixtures của Pylint |
| `tests/test_retrieval_snapshot_memory.py` | Cold metadata copy bound, snapshot ownership/parity, edge collisions và invalid unused base | Test memory là fixture JSON-compatible; không thay benchmark corpus bằng fixture |

Constructor overlay không giữ toàn bộ callsites/edges, nhưng vẫn lưu tập IDs O(N+E). Không tuyên bố memory O(1), hoàn thiện tất cả static resolution, hoặc loại mọi chi phí journal/SQLite. Delta chỉ dùng MENTIONS/REPRODUCES; base đã validate và snapshot riêng không bị thay đổi. Không dùng compact delta validation để bỏ full base validation.

## 2. Kiểm chứng và giới hạn

- Pylint real task SUCCEEDED43,3s; diagnostic chỉ ra `Cat(Animal, Animal)` trong `doc/data/messages/d/duplicate-bases/bad.py`. RED/GREEN/evidence theo PROGRESS.
- Django hai task SUCCEEDED152,9s/146,9s ở run mới, **không sửa rename code**. WinError5 chưa tái hiện: chưa xác định handle/process/ACL nguyên nhân và không gọi durable fix.
- Sympy16597 SUCCEEDED247,2s, BUILD_GRAPH176,60s/PREPARE45,09s, peakRSS2.980.835.328bytes. Đây là task retrieval thật, không model inference, không repair PASS.
- Targeted memory/overlay/grounding/retrieval59tests PASS. Full recorder ổn định365passed/4skip102,69s; before=after9ca9fc18…. Evidence `artifacts/fixes/w3-w6/reopened/snapshot-full-suite/20261007T112734572936Z-da791aaa6072446ca8b9184e92a80a7d.json`.
- Lượt recorder trước ERROR dù pytest PASS vì tài liệu bị agent sửa giữa source preflights. Không bỏ guards; artifact ERROR giữ nguyên. Phương pháp tiếp theo phải giữ toàn bộ files đứng yên trong suite, không chỉ `.py`.
- Jedi đã có ba timeout pilot lịch sử và diagnostic native crash; dừng phương pháp đó, no-Jedi chính đã được người dùng duyệt. Không tuyên bố Jedi đã fix.
- Source fingerprint của retrieval và M2 source preflight khác scope; không dùng benchmark fingerprint để suy rằng tài liệu luôn có thể sửa giữa full recorder.

Hai Sympy còn lại và paired25 chưa có kết quả ở thời điểm viết phần này; terminal/coverage mới phải đọc ở PROGRESS và hướng dẫn mục6.3. Không trộn thành công các run một-task vào population đo của run19/25 cũ. Cache hit/miss phải ghi rõ, không gọi warm-cache latency là cold-start.

**Terminal supersedes đoạn trên:** run25mới23SUCCEEDED/2WinError5, complete=true/exit1; comparator23pairs COMPARED_PARTIAL/exit1. All6historicalfailed cases PASS trongrunmới; Django13212/13344failEXTRACT_TREE. Cold17318/20438timeoutearlyinRETRIEVE sau~240sBUILD+~50sPREPARE; warm3Sympy128,6/129,3/135,9sPASS. Có6hit17miss, maxRSS6.580.867.072bytes≈6,13GiB. Minimum20có nhưng target25/ownerapproval chưađủ. Dừng directrename group đã>=3knownfailures vàJedi3timeouts; khôngphỏngđoánrootWinhandle/đổiACL hoặcẩnnegativeGraphmetrics. Closureanalysis25rawhash/17overlaprank+metrics/10manualauditparity PASS, sourcecodekhôngđổi saubenchmark; đây khôngrepair/ownerPASS. Khôngjobcònchạy.

## 3. Owner review cần con người

| Owner | Nội dung cần xác nhận | Trạng thái |
|---|---|---|
| M1 | Occurrence identity của repeated base/alias; subset snapshot và full-base/delta validation; limitations no-Jedi | Chờ owner |
| M2 | Same population/query/corpus/gold/counter guards; paired denominators/partial coverage; cold/warm cache interpretation | Chờ owner |
| M3 | Tool consumers vẫn default isolated retriever; task_handle/lease/context contract từ đợt trước giữ nguyên | Chờ owner |

Environment readiness50–100/smoke3, real-model repair, fine-tuning, incremental/full graph engineering và tuần7–16 không được triển khai trong đợt này. Các việc cần người hoặc authority khác không được tick thay bằng tự review.
