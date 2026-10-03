# Contract phối hợp M1/M3 — M2 W5–6

Không thay public M1 ContextPayload, không thêm schema_version. Metadata evaluation đặt ở sidecar/wrapper riêng.

## M2 → M1

Gửi `results/retrieval/<run_id>/m1_requests/<instance_id>.json`: instance/repository/base_commit/query/query_hash/corpus_hash/budget_tokens/token_policy/candidates. Candidates có canonical ID, path/qname, parent/range, source hash và base snippet. **Không chứa developer patch/gold labels/hints/test_patch**.

M1 phải retrieve từ source trước sửa cùng commit, issue nguyên bản, cùng corpus filtering/window policy hoặc tái dùng candidate map; không dùng source HEAD hiện tại. Module name mặc định bỏ tiền tố `src/`, `__init__` cuối; qualified symbol khác cần thống nhất trước, không sửa gold để khớp output sai.

ID nội bộ phân biệt các AST definitions trùng qname bằng suffix `@definition:start:end`; qname `symbol` vẫn giữ nguyên. Mapping từ M1 phải dùng path + qname + defining span để chọn đúng getter/setter/registered handler; không chỉ ghép qname hay node ID fixture.

## M1 → M2

Một file `data/m1_exports/<instance_id>.json` có dạng:

```json
{
  "instance_id": "INSTANCE_ID_THAT",
  "repository": "owner/repo",
  "base_commit": "40_HEX_SHA",
  "query_hash": "sha256:FROM_REQUEST",
  "corpus_hash": "sha256:FROM_REQUEST",
  "context": {
    "graph_version": "CONCRETE_GRAPH_SNAPSHOT_ID",
    "anchor_ids": ["REAL_ANCHOR_ID"],
    "items": [
      {
        "node_id": "REAL_M1_NODE_ID",
        "path": "package/module.py",
        "symbol": "package.module.function",
        "range": {"start_line": 1, "start_col": 0, "end_line": 2, "end_col": 15},
        "snippet": "def function():\n    return True",
        "relevance_score": 0.8,
        "graph_distance": 1,
        "graph_rationale": ["REAL_RETRIEVAL_REASON"],
        "confidence": 0.9,
        "token_count": 12
      }
    ],
    "total_token_count": 12,
    "token_budget": 4000,
    "truncated": false
  }
}
```

Đây chỉ là minh họa shape, **không phải output benchmark**. Range/snippet/token phải lấy thật; lines 1-based, cols 0-based UTF-8 bytes, end exclusive. `total_token_count=sum(items.token_count) ≤ budget`. Adapter đối chiếu snippets với source base rồi recount chung bằng bytes/4; Graph/BM25 đều đo **packed context**, không so với ranking BM25 không giới hạn.

M1 score/confidence phải 0..1; BM25 raw score không nhét vào các field đó. M2 dùng schema ranked riêng, không giả graph_distance/rationale cho baseline. `graph_version` không thay `base_commit` hay `corpus_hash`.

## Checklist debug với M1

- [ ] Cùng IDs/commits/query hashes, corpus filtering và token policy.
- [ ] Symbol qname trùng canonical name; decorator/nested/class method được phân biệt.
- [ ] Source range đúng byte columns, snippet đúng base source, không phải patched code.
- [ ] Added-only/deleted/renamed/module edits có disposition rõ, không ép gold function giả.
- [ ] Empty context hợp lệ; chưa có graph hits không đồng nghĩa export missing.
- [ ] 25 exports thật, validation không lỗi; paired table đủ eligible tasks.
- [ ] Cùng xem ≥10 inspection cases và ghi người xác nhận/ngày/nhận xét.

## Checklist với M3

- [ ] Xác nhận snapshot dataset và subset chung 50–100 task, lấy 25 từ tập đó hoặc đồng thuận pilot hiện tại.
- [ ] Xác nhận multi-file definition (≥2 source Python, không test/docs).
- [ ] Không trộn benchmark repair environment viability với retrieval chạy source-only: hiện tại không có bằng chứng tests benchmark chạy được.
- [ ] Thống nhất cách công bố mean/denominator/failures/token estimate; không claim score repair.

Output VGAR W3–4 cung cấp builder/ranges/contracts và recorder pattern nhưng chưa có task-aware graph retrieval W5–6; không đánh dấu checklist phối hợp đã xong chỉ vì adapter unit tests PASS.
