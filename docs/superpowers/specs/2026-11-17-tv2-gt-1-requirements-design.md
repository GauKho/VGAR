# TV2 · GT-1 phần còn lại: Requirement, Constraint, UserStory, Actor (17/11/2026)

> Plan 2 tuần, task GT-1 ([P] dòng 299–323, 621–630). Phần đã làm: `docs/superpowers/specs/2026-11-09-tv2-gt-1-g-task-design.md`.
> Luật dưới đây là **quyết định của nhóm, chốt 16/11**. Proposal chỉ định nghĩa kiểu; §6.6 yêu cầu MVP "không cần NLP phức tạp", nên chỉ dùng luật trên văn bản, không dùng NLP hay LLM.

## 1. Đơn vị và tiền xử lý

- Bỏ khối code có rào (```` ``` ````), comment HTML `<!-- … -->` (gợi ý của mẫu issue), dòng bắt đầu bằng 4 dấu cách hoặc tab (code thụt lề), dòng traceback và dòng lỗi.
- Tiêu đề `Expected` đứng một mình (`Expected:`) cũng mở mục Expected. Mục kết thúc ở dòng trống sau nội dung hoặc ở tiêu đề `#` kế tiếp.
- Tách câu theo dòng, rồi theo `.`, `!`, `?` theo sau là khoảng trắng. Bỏ câu dài hơn 300 ký tự. Gộp câu trùng.
- Mỗi câu chỉ ra **một** loại node, theo thứ tự ưu tiên: UserStory → Constraint → Requirement.

## 2. Luật sinh node

| Node | Luật | Thuộc tính |
|---|---|---|
| **UserStory** | Mẫu `As a/an <actor>, I want/would like/need …` (phần `so that …` nếu có) | `text`, `actor` |
| **Actor** | Cụm `<actor>` của UserStory, gộp trùng theo chữ thường | `name` |
| **Constraint** | Câu có ràng buộc phiên bản (`Python 3.8`, `numpy>=1.20`, `pkg==2.0`) hoặc câu cấm (`must not`, `should not`, `shouldn't`, `mustn't`, `without breaking`, `backward(s) compatible/compatibility`) | `text`, `kind` = `version` hoặc `prohibition` |
| **Requirement** | Câu nằm dưới tiêu đề `Expected behavior/behaviour/result/output/outcome`, hoặc câu có `should`, `must`, `expected`, `needs to` | `text`, `source` = `expected_section` hoặc `modal` |

## 3. Luật sinh cạnh

| Cạnh | Luật | Confidence |
|---|---|---|
| `MENTIONS` Issue → 4 node mới | Như các fact khác của GT-1 | UserStory 0.7; Requirement, Constraint 0.6; Actor 0.5 |
| `TRACES_TO` Requirement → Component | Dùng lại luật Issue → Component, nhưng chỉ với các anchor có chữ khớp (`matched_text`) nằm trong câu của Requirement; `anchor_count` | điểm anchor cao nhất |
| `DEPENDS_ON` Requirement → Requirement | Câu Requirement mở đầu bằng `this/that/it/which` và có `requires`/`depends on` → nối tới Requirement ngay trước nó | 0.5 |
| `CONFLICTS_WITH` Requirement → Requirement | Câu Requirement có `conflicts with`/`contradicts` → nối tới Requirement ngay trước nó | 0.5 |

Câu tham chiếu ngược (`This requires …`) không có động từ khuyết thiếu, nên cũng được tính là Requirement (`source` = `follow_up`), nhưng chỉ khi đứng ngay sau một Requirement; nếu không, `DEPENDS_ON` không bao giờ sinh được.

**Thay đổi so với luật chốt 16/11:** bỏ `instead of` khỏi luật `CONFLICTS_WITH`. Trong bug report, cụm này gần như luôn nằm trong một câu ("should return X instead of Y"), không chỉ tới requirement thứ hai, nên sẽ sinh cạnh sai.

## 4. Schema

- `MENTIONS` thêm đích Requirement, Constraint, UserStory, Actor.
- Thuộc tính bắt buộc: Requirement, Constraint, UserStory `text`; Actor `name`. `TRACES_TO` Requirement → Component bắt buộc `anchor_count` như Issue → Component.
- Bốn loại node có producer `overlay`. Profile overlay lên `task-overlay-v12-requirements`.

## 5. Giới hạn dự kiến

- Issue của SWE-bench là bug report: Requirement và Constraint sẽ có ở một phần issue; UserStory, Actor, `DEPENDS_ON`, `CONFLICTS_WITH` dự kiến gần như bằng 0.
- Luật theo từ khóa: câu có `should` mô tả hành vi hiện tại ("it should be noted…") cũng thành Requirement. Chưa có nhãn tay để đo precision.
