# Kho tri thức cho trợ lý CyberHub

Đây là **dữ liệu nghiệp vụ được kiểm soát**, không phải hướng dẫn cài đặt. `ai/documents.py` đọc từ thư mục này (hoặc `CYBERHUB_KNOWLEDGE_ROOT` đã cấu hình). Đừng chuyển chỗ các file vai trò nếu chưa cập nhật loader và kiểm thử.

| Thư mục | Người được phục vụ |
|---|---|
| `customer/` | Khách hàng đăng nhập. |
| `staff/` | Nhân viên/Bếp/Thủ kho theo quyền của phiên. |
| `manager/` | Quản lý được cấp quyền. |
| `admin/` | Quản trị viên được cấp quyền. |
| `shared/` | Các vai trò phù hợp theo metadata của từng file. |

Mỗi tài liệu có đúng tám trường frontmatter: `id`, `title`, `audience`, `status`, `version`, `language`, `updated_at`, `tags`. Chỉ tài liệu `APPROVED` mới được đưa vào chỉ mục; `manager/revenue-policy.md` hiện là `DRAFT` và không được dùng để trả lời. `README.md` này cũng không được lập chỉ mục.

Khi sửa nội dung: đối chiếu nghiệp vụ với service/migration hiện tại, cập nhật `version` và `updated_at`, kiểm tra `audience` và trạng thái duyệt, rồi chạy test loader/RAG. Trợ lý không được tự thực hiện nạp tiền, thanh toán hay thay đổi kho. Việc đổi nội dung có thể khiến Gemini tạo lại embedding khi khởi động hoặc tải lại; xem [runbook RAG](../guides/RAG_5A_RUNBOOK.md).

Thiết kế và báo cáo thử nghiệm RAG theo các bước cũ nằm ở [tư liệu lịch sử](../../history/docs/knowledge-base/README.md).
