# MindCare AI — User Management & AI Moderation Database

README này giới thiệu nhanh thiết kế cơ sở dữ liệu cho hai module quản trị của MindCare AI,
đã **reconcile với hệ thống Agent CBT v4 đang chạy** (safety gate L0–L3, ReAct 6 tool, HITL review).

- **User Management**: quản lý người dùng ứng dụng, hồ sơ PII, trạng thái rủi ro, phân công chuyên viên.
- **AI Moderation**: lưu hội thoại nhiều lượt, hàng đợi kiểm duyệt, lịch sử quyết định của chuyên viên.

Thiết kế đầy đủ: [user-management-ai-moderation-database-design.md](./user-management-ai-moderation-database-design.md).
Triển khai: SQLAlchemy models `backend/app/db/models_admin.py`, migration `backend/migrations/versions/0006_user_mgmt_ai_moderation.py`.

## Mục tiêu thiết kế

- Tách người dùng ứng dụng khỏi tài khoản quản trị (RBAC: Admin, Manager, Clinician).
- Hỗ trợ một phiên chat có nhiều lượt trao đổi (`ai_messages`).
- Kiểm duyệt theo từng phản hồi AI thay vì theo toàn bộ session.
- Mã hóa PII/PHI (AES-256-GCM) và ghi audit cho mọi thao tác nhạy cảm.
- Giữ lịch sử bất biến, không ghi đè quyết định hoặc nội dung đã kiểm duyệt.

## 4 điểm reconcile quan trọng với Agent

> Bản thiết kế gốc đã được chỉnh để khớp với hành vi Agent thực tế:

1. **L0/L1 không sinh phản hồi AI** → `review_queue.ai_message_id` để **nullable**, thêm cột `kind` (`ai_review` vs `user_escalation`). Ca khủng hoảng (L0) / nguy cơ cao (L1) vào queue qua `user_escalation` với tin nhắn người dùng.
2. **Tránh trùng tên `risk_level`** → DB chỉ chứa `L0`–`L3`; biến định tuyến RAG của Agent đổi tên thành `retrieval_tier` (không lưu DB).
3. **Không lưu `severity`** (critical/high/moderate/low) → derive từ `risk_level` lúc runtime.
4. **Bảng `conversations` đã tồn tại** → dùng làm header phiên; `ai_messages` trỏ về `conversation_id`.

## Kiến trúc dữ liệu

```text
User Management
users ─┬ user_profiles
       ├ screenings
       ├ conversations ─ ai_messages
       └ specialist_assignments ─ admin_users

Administration & RBAC
admin_users ─ roles ─ role_permissions ─ permissions
     ├ moderation_reviews
     ├ ai_response_revisions
     └ audit_trail

AI Moderation
conversations ─ ai_messages ─ review_queue
                     │             └ moderation_reviews
                     └ ai_response_revisions
```

## Các bảng chính

| Nhóm | Bảng | Trách nhiệm |
|---|---|---|
| User | `users` | Tài khoản người dùng ứng dụng |
| User | `user_profiles` | Hồ sơ PII đã mã hóa |
| User | `screenings` | PHQ-9, GAD-7, mức rủi ro |
| User | `specialist_assignments` | Lịch sử phân công chuyên viên |
| User | `user_memory` | Ngữ cảnh dài hạn của người dùng |
| RBAC | `admin_users` | Tài khoản Admin/Manager/Clinician |
| RBAC | `roles`, `permissions`, `role_permissions` | Phân quyền |
| RBAC | `audit_trail` | Nhật ký quản trị append-only |
| Moderation | `conversations` | Header phiên chat |
| Moderation | `ai_messages` | Toàn bộ tin nhắn user/AI |
| Moderation | `drafts` | Phương án phản hồi AI sinh (+ `source_user_message_id`) |
| Moderation | `moderation_queue` | Trạng thái kiểm duyệt từng phản hồi AI (per-message; thay `review_queue` legacy session-keyed) |
| Moderation | `moderation_reviews` | Checklist + quyết định bất biến |
| Moderation | `ai_response_revisions` | Phiên bản phản hồi đã chỉnh sửa |

## Quy ước mức rủi ro

| Mã | Ý nghĩa | Queue |
|---|---|---|
| `L0` | Khủng hoảng/khẩn cấp | `user_escalation`, SLA ngắn nhất |
| `L1` | Rủi ro cao | `user_escalation`, SLA ngắn |
| `L2` | Rủi ro trung bình | `ai_review`, ưu tiên trung bình |
| `L3` | Rủi ro thấp/thông thường | auto hoặc `ai_review` nếu escalate |

Số càng nhỏ thì càng nguy hiểm. DB/API chỉ dùng `L0`–`L3`; frontend mapping sang nhãn/màu.

## Checklist kiểm duyệt bắt buộc (approve/edit)

Đồng cảm · Không chẩn đoán bệnh · Dựa trên CBT · Nội dung an toàn · Khuyến nghị gặp chuyên gia khi cần · Không tư vấn thuốc · Không khẳng định quá mức khả năng AI.

## Bảo mật dữ liệu

- `content_enc`, email, SĐT, địa chỉ, ghi chú nhạy cảm dùng AES-256-GCM.
- Mật khẩu chỉ lưu Argon2id/bcrypt hash. Email dùng blind index để chống trùng mà không giải mã.
- API danh sách chỉ trả dữ liệu masking, không giải mã nội dung chat.
- `audit_trail` chỉ cho `INSERT`. Dữ liệu nghiệp vụ dùng soft delete.

## Ràng buộc quan trọng

- Một user chỉ có một `specialist_assignment` active.
- Một phản hồi AI chỉ có một queue item; L0/L1 vào queue qua `user_escalation` (ai_message_id NULL).
- `ai_messages.parent_message_id` phải trỏ tới tin nhắn user cùng session.
- Hai Clinician không thể đồng thời quyết định cùng một queue item (optimistic lock theo `version`).
- Approve/edit phải vượt checklist bắt buộc. Review và revision cũ không được ghi đè.

## API liên quan

```text
GET    /api/admin/users
GET    /api/admin/users/{id}
POST   /api/admin/users
POST   /api/admin/users/{id}/status
POST   /api/admin/users/{id}/assign-clinician

GET    /api/admin/ai-moderation/stats
GET    /api/admin/ai-moderation/items
GET    /api/admin/ai-moderation/items/{queue_item_id}
PATCH  /api/admin/ai-moderation/items/{queue_item_id}/claim
PATCH  /api/admin/ai-moderation/items/{queue_item_id}/approve
PATCH  /api/admin/ai-moderation/items/{queue_item_id}/edit-response
PATCH  /api/admin/ai-moderation/items/{queue_item_id}/reject
PATCH  /api/admin/ai-moderation/items/{queue_item_id}/need-improvement
```

`queue_item_id` là `review_queue.id`. Route `/sessions/{id}` cũ chỉ giữ tạm (deprecated).

## Tiêu chí hoàn thành

- Migration chạy được cả `upgrade` và `downgrade` trên bản sao dữ liệu.
- Không mất lịch sử hội thoại hoặc quyết định moderation khi backfill.
- Test ranh giới đăng nhập `users` vs `admin_users`; test concurrency claim/resolve queue.
- Test L0/L1 vẫn tạo được queue dù không có AI reply.
- Truy vấn danh sách dùng index, không quét plaintext/JSONB để lọc trạng thái.
