# Kho tri thức CyberHub — Đợt 5A, bước 1 và 2

Kho này chứa hướng dẫn nghiệp vụ tĩnh cho trợ lý RAG. Phạm vi hiện tại là tài liệu
Markdown và model Python; chưa có loader, embedding, chỉ mục, LLM, API hoặc chat UI.
Không cần API key, MySQL hay thư viện AI để sử dụng các model.

## Nội dung và trạng thái

| Tài liệu | Đối tượng | Trạng thái |
|---|---|---|
| [Thuật ngữ](shared/glossary.md) | Tất cả vai trò | APPROVED |
| [Câu hỏi chung](shared/faq.md) | Tất cả vai trò | APPROVED |
| [Chính sách vai trò](shared/role-policy.md) | Nhân sự | DRAFT — chờ Đợt 0 |
| [Tài khoản và avatar](customer/account-guide.md) | Khách hàng | APPROVED |
| [Thành viên](customer/membership-policy.md) | Khách hàng | APPROVED |
| [Ưu đãi cho khách](customer/promotion-policy.md) | Khách hàng | APPROVED |
| [Vận hành máy](staff/machine-operation.md) | Nhân viên, quản lý, admin | APPROVED |
| [Quản lý khách hàng](staff/customer-management.md) | Nhân viên, quản lý, admin | APPROVED |
| [Nạp tiền](staff/top-up-process.md) | Nhân viên, quản lý, admin | APPROVED |
| [Thanh toán](staff/payment-process.md) | Nhân viên, quản lý, admin | APPROVED |
| [Chính sách doanh thu](manager/revenue-policy.md) | Quản lý, admin | DRAFT — chờ Đợt 0 |
| [Quản lý khuyến mãi](manager/promotion-management.md) | Quản lý, admin | APPROVED |
| [Quản lý nhân viên](admin/employee-management.md) | Admin | APPROVED |
| [Cấu hình thành viên](admin/system-configuration.md) | Admin | APPROVED |

`APPROVED` ở bản khởi đầu đánh dấu nội dung đối chiếu được với nghiệp vụ đang có
và quyết định đã chốt, không xác nhận hệ thống RAG đã chạy. Chủ nghiệp vụ cần duyệt
lại khi thay đổi quy trình. Các tài liệu DRAFT giữ lại chính sách đã thống nhất
nhưng chưa nghiệm thu Đợt 0; tuyệt đối không đưa chúng vào chỉ mục phục vụ hỏi đáp.

Không index README này, tài liệu bàn giao tổng thể, toàn bộ thư mục `docs`, mã nguồn,
file cấu hình, thông tin đăng nhập, ảnh bằng chứng hoặc dữ liệu khách hàng thật.
Các đường dẫn tại mục “Nguồn đối chiếu” chỉ để người biên soạn kiểm tra, không phải
chỉ dẫn cho loader tự đọc thêm file ngoài kho tri thức.

## Quy ước tài liệu

Mỗi tài liệu nghiệp vụ có YAML frontmatter:

```yaml
---
id: staff-payment-process
title: Quy trình thanh toán phiên chơi
audience:
  - STAFF
  - MANAGER
  - ADMIN
status: APPROVED
version: 1
language: vi
updated_at: 2026-11-09
tags:
  - payment
  - invoice
---
```

- `id`: duy nhất toàn kho, chữ thường, số và dấu gạch ngang.
- `audience`: danh sách vai trò được phép đọc, khai báo tường minh; tên thư mục
  chỉ để tổ chức, không thay thế metadata và không tự cấp quyền kế thừa.
- Không có vai trò `SHARED`; nội dung chung liệt kê đủ vai trò cần dùng.
- `status`: `DRAFT`, `APPROVED` hoặc `ARCHIVED`. Bản tương lai chỉ index `APPROVED`.
- `version`: số nguyên dương, tăng khi nội dung hoặc đối tượng được phép đọc đổi.
- `language`: `vi` hoặc `en`. Đợt này biên soạn tiếng Việt; chưa có bản dịch EN.
- `updated_at`: ngày ISO `YYYY-MM-DD`, lịch Việt Nam.
- `tags`: danh sách từ khóa, không dùng làm quyền truy cập.

Chính sách tiền/điểm trong tài liệu phải ghi rõ mốc mặc định có thể cấu hình.
Hỏi số dư, máy trống, doanh thu hoặc ưu đãi đang có cần API được phân quyền ở bước
sau; tài liệu không phải ảnh chụp dữ liệu hiện tại. Ví dụ số tiền chỉ có tính minh họa.

## Hợp đồng model Python

Module: `src/cyberhub_manager/ai/models.py`. Chỉ dùng thư viện chuẩn Python 3.11+.

| Model | Ý nghĩa |
|---|---|
| `AIAccessContext` | Danh tính và phạm vi được backend xác thực, ngôn ngữ trả lời |
| `KnowledgeDocument` | Metadata và nội dung một tài liệu |
| `KnowledgeChunk` | Một đoạn văn bản có nguồn, đối tượng, ngôn ngữ, phiên bản |
| `Citation` | Nguồn tham khảo gồm document ID, chunk ID, tiêu đề, mục, đường dẫn, phiên bản |
| `AssistantAnswer` | Nội dung trả lời, tuple trích dẫn và cờ `grounded` |

Các model dùng `dataclass(frozen=True)` và tuple, kiểm tra dữ liệu đầu vào bằng
`ValueError`. Không tự đọc file, gọi mạng, truy vấn DB hoặc tự cấp quyền.

Ánh xạ cho loader ở bước 3: frontmatter `id` → `document_id`, `updated_at` →
`datetime.date`, `audience`/`tags` → tuple. `source` lấy từ đường dẫn file thực,
tương đối với thư mục này, dùng `/`, ví dụ `staff/payment-process.md`.
Không nhận đường dẫn nguồn từ người dùng để mở file tùy ý. Kiểm tra symlink và
đường dẫn thực có thuộc knowledge root hay không thuộc trách nhiệm loader bước 3.

`AIAccessContext.actor_id` là `employees.id` cho nhân sự và `accounts.id` cho
`CUSTOMER`. Luôn lưu cùng `role` để tránh nhầm ID ở hai bảng. Khách chỉ đọc hướng
dẫn của khách và nội dung chung; model này không thay thế kiểm tra quyền sở hữu
thông tin cá nhân qua API. `store_ids=()` không cấp quyền xem dữ liệu cửa hàng,
kể cả ADMIN; phạm vi cụ thể phải do backend xác thực. Không nhận role/store từ
payload do trình duyệt tự khai.

`Citation` phải do backend tạo từ chunk đã được phép truy xuất. Model chỉ kiểm tra
cấu trúc, không chứng minh nguồn tồn tại hoặc kết luận LLM đúng. `grounded=True`
phải có trích dẫn; fallback `grounded=False` có tuple trích dẫn rỗng. Kiểm tra độ
đúng của câu trả lời và nguồn thuộc các bước retrieval/evaluation tiếp theo.

Ví dụ tạo context nội bộ (không phải endpoint cấp quyền):

```python
from cyberhub_manager.ai import AIAccessContext, AssistantAnswer

access = AIAccessContext(actor_id=1, role="STAFF", store_ids=(1,))
fallback = AssistantAnswer(
    answer="Chưa tìm thấy thông tin đã được phê duyệt cho câu hỏi này.",
    citations=(),
    grounded=False,
)
```

## Bàn giao cho người làm Đợt 0 và bước tiếp theo

1. Người làm Đợt 0 xác nhận chính sách doanh thu đúng với route, service và UI.
2. Rà soát hai tài liệu DRAFT; khi đạt nghiệm thu mới cập nhật trạng thái,
   ngày và tăng phiên bản.
3. Bước 3 viết loader theo hợp đồng trên: chỉ nhận Markdown nghiệp vụ hợp lệ,
   chỉ đưa APPROVED vào pipeline; không coi kiểm tra model là kiểm tra quyền.
4. Các bước tiếp theo thêm chunking, retrieval lọc quyền, embedding và LLM.
5. Khi nối Flask, adapter backend tạo context từ session đã xác thực lại.

Lần cập nhật này chưa sửa xác thực, doanh thu, migration hoặc service đang vận hành.

Kiểm tra model và cấu trúc kho tài liệu:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_ai_models.py tests/unit/test_ai_knowledge_base.py -q
```
