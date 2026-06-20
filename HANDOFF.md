# HANDOFF — Module mới (User Mgmt + AI Moderation + Chat UX + Embedder offload)

> Tài liệu này dành cho **Đức (Backend)** và **Việt (Frontend)** để code tiếp các chức năng
> dựa trên phần Huy vừa đẩy lên `dev`. Phần lõi Agent/Safety đã xong; phần còn lại là
> **persistence + API + UI** quanh schema mới.

Cập nhật: 2026-06-18 · Người đẩy: Huy (Agent/Safety/RAG).

---

## 0. Tóm tắt 3 nhóm thay đổi

| Nhóm | File chính | Trạng thái |
|---|---|---|
| **DB User Mgmt + AI Moderation** | `backend/docs/*.md`, `backend/app/db/models_admin.py`, `backend/migrations/versions/0006_*.py` | Schema + migration xong (đã chạy `alembic upgrade head` OK). **Chưa wire vào API.** |
| **Chat UX animations** | `user_app/src/pages/Chat.jsx`, `user_app/src/styles.css` | Đã xong, chạy được (mock). |
| **Embedder offload Modal** | `modal/embedder_service.py`, `backend/app/services/embedder.py`, `backend/app/core/config.py` | Code xong. **Cần `modal deploy`.** |

---

## 1. CHO BACKEND (Đức)

### 1.1. Đọc trước
- Thiết kế chi tiết: [`backend/docs/user-management-ai-moderation-database-design.md`](backend/docs/user-management-ai-moderation-database-design.md)
- Tổng quan: [`backend/docs/README-DB-USER-AI.md`](backend/docs/README-DB-USER-AI.md)

### 1.2. Đã có sẵn
- **10 bảng mới** (ORM: `backend/app/db/models_admin.py`): `roles`, `permissions`, `role_permissions`, `admin_users`, `user_profiles`, `specialist_assignments`, `ai_messages`, `moderation_queue`, `moderation_reviews`, `ai_response_revisions`.
- **Migration `0006`** additive, non-breaking — bảng cũ (`sessions`, `review_queue` legacy) vẫn chạy. `downgrade` đầy đủ.

### 1.3. Việc cần code (theo thứ tự)
1. **Wire `models_admin` vào `migrations/env.py`** (`target_metadata`) để autogenerate thấy bảng mới.
2. **Seed RBAC**: tạo 3 role (`admin`/`manager`/`clinician`) + permissions + map. Chuyển tài khoản `users.role IN ('admin','clinician')` sang `admin_users`.
3. **Cutover `chat.py` → ghi per-message** (thay vì `sessions` cũ):
   - Mỗi lượt: tạo `ai_messages` (user) + (nếu có) `ai_messages` (ai, `parent_message_id` trỏ user).
   - Gán `risk_level` L0–L3 từ `safety_gate`.
   - Tạo `moderation_queue` theo bảng map dưới.
4. **Admin API** (xem mục 7 trong design doc): `/api/admin/users*`, `/api/admin/ai-moderation/items*` (claim / approve / edit-response / reject / need-improvement). `queue_item_id` = `moderation_queue.id`.

### 1.4. ⚠️ 5 quy tắc BẮT BUỘC tuân thủ (đã reconcile với Agent)
| # | Quy tắc |
|---|---|
| 1 | **L0/L1 KHÔNG có AI reply** → `moderation_queue.ai_message_id` = NULL, `kind='user_escalation'`, anchor vào `user_message_id`. Đã có CHECK ràng buộc. |
| 2 | DB chỉ lưu `risk_level` ∈ {L0,L1,L2,L3}. Biến định tuyến RAG của Agent là `retrieval_tier` (`normal`/`elevated`) — **không lưu DB**. |
| 3 | **Không lưu `severity`** (critical/high/…) — derive: L0→critical, L1→high, L2→moderate, L3→low. |
| 4 | `ai_messages` trỏ về `conversations.id` (bảng `conversations` đã có = header phiên). |
| 5 | Map outcome Agent → `ai_messages.moderation_status` + `moderation_queue`: |

**Bảng map outcome → moderation:**
| Agent outcome | `moderation_status` | `moderation_queue` |
|---|---|---|
| L3 auto_sent | `not_required` | không tạo (hoặc random theo cấu hình) |
| L2 pending_review | `pending` | `kind='ai_review'`, priority TB |
| `escalate_to_clinician` | `pending` | `kind='ai_review'`, priority cao |
| `needs_clarification` | `not_required` | không tạo |
| **L0 / L1** | (không có ai_message) | `kind='user_escalation'`, ai_message_id NULL, priority khẩn |

### 1.5. Embedder offload (ops)
- `embedder.embed()` giờ gọi Modal nếu `MODAL_EMBEDDER_ENDPOINT` set (derive từ `MODAL_WORKSPACE`), fallback local.
- Deploy: `modal deploy modal/embedder_service.py` → backend hết nạp bge-m3 2.2GB → nhẹ, vừa free tier (Railway).

---

## 2. CHO FRONTEND (Việt)

### 2.1. Đã thêm sẵn — Chat animations (dùng được luôn)
File: [`user_app/src/pages/Chat.jsx`](user_app/src/pages/Chat.jsx) + [`user_app/src/styles.css`](user_app/src/styles.css). Tất cả **CSS/SVG thuần, không thêm dependency, tôn trọng `prefers-reduced-motion`**.

| Hiệu ứng | Component / class |
|---|---|
| Empty state (mascot vẫy + halo) trước tin nhắn đầu | `<EmptyState>` · `.ai-empty*` |
| "AI thinking" loader (label shimmer + dots) | `<TypingBubble>` · `.ai-thinking*` |
| Mascot idle "breathing" | class `.mascot-idle` (truyền vào `<Mascot>`) |
| Bubble entrance + AI glow khi trả lời | `.ai-bubble-user` / `.ai-bubble-ai` |
| Crisis box đọc hotline từ backend | render theo `r.crisis_resources` |

> Bản redesign landing/login (của Việt, commit `3da2819`) đã được giữ nguyên — animations chat nằm trên nền đó.

### 2.2. Việc cần code — Admin/Moderation UI (admin_app)
Dựng giao diện cho clinician duyệt, gọi API ở mục 1.3.4:
- **Danh sách queue**: `GET /api/admin/ai-moderation/items` (sort priority/SLA). Hiển thị badge risk + đếm SLA.
- **Chi tiết**: `GET .../items/{queue_item_id}` → hội thoại + draft + revisions.
- **Thao tác**: claim → checklist (7 tiêu chí) → approve / edit-response / reject / need-improvement.
- **User management**: `GET /api/admin/users`, chi tiết, đổi status, gán clinician.

### 2.3. ⚠️ Quy ước hiển thị (FE chịu trách nhiệm mapping)
- DB/API **chỉ trả mã `L0`–`L3`**. Frontend tự map sang nhãn + màu:
  | Mã | Nhãn | Gợi ý màu |
  |---|---|---|
  | `L0` | Crisis | đỏ đậm |
  | `L1` | High Risk | đỏ/cam |
  | `L2` | Medium Risk | vàng |
  | `L3` | Low / Safe | xanh |
- Checklist approve (7 boolean): empathy · no_diagnosis · cbt_based · safe_response · referral_when_needed · no_medication_advice · no_overclaiming. **Approve/edit chỉ bật khi đủ tiêu chí.**
- Queue `kind='user_escalation'` (L0/L1) → KHÔNG có AI reply để duyệt; UI hiển thị "cần chuyên gia tiếp cận" thay vì panel duyệt câu trả lời.

---

## 3. Cách chạy thử local

```bash
# Backend + DB stack
docker compose up -d
docker exec cbt_backend alembic upgrade head   # áp migration 0006

# Frontend
cd user_app  && npm run dev   # http://localhost:5173
cd admin_app && npm run dev   # http://localhost:5174
```

- AI thật cần Modal: `modal deploy modal/{safety,llm,agent,embedder,reranker}_service.py` rồi đặt `MODAL_WORKSPACE` trong `.env`. Không deploy → AI chạy mock, **triage L0–L3 vẫn thật** (regex).
- `docker-compose.yml` của Huy đang trỏ HF cache sang `D:/...` (máy Huy) — **không commit**; mỗi người tự chỉnh mount theo máy mình.
