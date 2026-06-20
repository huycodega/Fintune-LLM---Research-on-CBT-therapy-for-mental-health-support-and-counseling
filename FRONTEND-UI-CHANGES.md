# Frontend UI — Redesign & Admin Modules (Việt)

> Tổng hợp các phần Frontend đã làm trên nhánh `dev`. Tất cả thay đổi **chỉ ở UI/UX + animation + wiring API client**, không đụng backend logic, không đổi API contract, giữ nguyên route/exports.
>
> Cập nhật: 2026-06-20.

## 0. Tóm tắt

| Nhóm | App | Trạng thái |
|---|---|---|
| Landing + Login/Register redesign | `user_app` | ✅ Xong, build pass |
| Soft-motion layer cho 7 trang user | `user_app` | ✅ Xong |
| CBT Lessons Management (redesign + animation) | `admin_app` | ✅ Xong (demo fallback) |
| Resource Management (redesign + animation) | `admin_app` | ✅ Xong (demo fallback) |
| **AI Moderation** (mới) | `admin_app` | ✅ Xong (demo fallback) |
| **User Management + Assign Clinician** (mới) | `admin_app` | ✅ Xong (demo fallback) |

Tất cả animation tôn trọng `prefers-reduced-motion`. Icon dùng **SVG inline** (không phụ thuộc Flaticon/asset ngoài, sạch bản quyền, animate được).

---

## 1. User app (`user_app`)

### 1.1. Landing (trang chủ chưa đăng nhập) — `src/pages/Landing.jsx`
- Hero gradient mesh + orbs trôi + lưới mờ, tiêu đề **gradient shimmer**, mascot trong vòng xoay / blob biến hình, chip rating, bong bóng nổi.
- Bộ **icon SVG duotone** mới (`src/components/FeatureIcon.jsx`): shield / chat / book / lotus / chart / folder / trend.
- **Scroll-reveal** (IntersectionObserver), **count-up** số liệu, **3D tilt** thẻ Features theo chuột, nút quét sáng, navbar đổ bóng khi cuộn.

### 1.2. Auth — `src/pages/Login.jsx`, `src/pages/Register.jsx`, `src/components/AuthLayout.jsx`
- Bố cục **2 cột**: panel thương hiệu (gradient + orbs + mascot + trust list) | form card (entrance, focus ring).
- Định nghĩa các class nút/banner còn thiếu: `.btn accent/ghost/full`, `.banner crisis` (giúp cả Consent/Intake đẹp hơn).

### 1.3. Soft-motion layer (Home, Screening, AI Support, Lessons, Resources, Profile, Settings)
- Driven ở `src/App.jsx`: page fade + **staggered card reveal** mỗi lần đổi trang.
- Hover thẻ dịu, indicator active của sidebar, focus ring input, nút primary có bóng + active press.

---

## 2. Admin app (`admin_app`) — hệ thiết kế `la-*` (dark navy + indigo)

Sidebar/TopBar dùng chung: `src/admin/Sidebar.jsx`, `src/admin/TopBar.jsx`, `src/admin/Icon.jsx`.
Routing: `src/App.jsx` render các trang `la-*` full-shell qua `LA_PAGES`.

### 2.1. CBT Lessons Management — `src/pages/LessonsAdmin.jsx`
- Count-up stats, **staggered reveal** thẻ/hàng, hover lift, **accent dòng được chọn**, mini line chart **draw-on**, thanh completion-rate **fill**, detail panel **cross-fade**, **skeleton shimmer**.
- Hero detail **đổi theo bài** được chọn.

### 2.2. Resource Management — `src/pages/ResourcesAdmin.jsx`
- Filter tabs có **indicator trượt** + cross-fade list khi đổi tab.
- Checkbox **pop**, hotline banner **pulse**, **Usage Count** count-up, detail panel slide-in/cross-fade, urgent-row **red accent grow**.

### 2.3. AI Moderation (mới) — `src/pages/ModerationAdmin.jsx`
Theo design doc §5 + §7, FE chịu trách nhiệm mapping **L0–L3** (§2.3):

| Mã | Nhãn | Màu |
|---|---|---|
| L0 | Crisis | đỏ đậm |
| L1 | High Risk | cam/đỏ |
| L2 | Medium Risk | vàng |
| L3 | Low / Safe | xanh |

- Queue list: badge risk + **SLA countdown** (đỏ nhấp nháy khi overdue) + loại (`ai_review` / `user_escalation`) + status; filter Open/Escalations/All.
- Detail: thread hội thoại + AI draft + revisions; **checklist 7 tiêu chí** (empathy, no_diagnosis, cbt_based, safe_response, referral_when_needed, no_medication_advice, no_overclaiming) — Approve/Edit chỉ bật khi đủ tiêu chí bắt buộc.
- **Quy tắc #1**: `kind='user_escalation'` (L0/L1, không có AI reply) → hiển thị *"needs specialist outreach"* thay vì panel duyệt.
- Actions: claim → approve / edit-response / reject / need-improvement.

### 2.4. User Management + Assign Clinician (mới) — `src/pages/UsersAdmin.jsx`
- List + filter (status tabs + risk L0–L3 + search), detail (hồ sơ, screening, lịch sử ca).
- **Đổi status** (suspend/re-activate), **đổi role**, và **gán clinician** (§4.4: mỗi user tối đa 1 phân công active).

---

## 3. API client (`admin_app/src/api.js`)
Đã thêm các method theo design doc §7 (chưa wire backend):
- `assignClinician`, `moderationStats/Items/Item/Claim/Approve/EditResponse/Reject/NeedImprovement`.

## 4. ⚠️ Lưu ý cho Backend (Đức)
- Các API mới (`/api/admin/ai-moderation/*`, `/api/admin/users/*/assign-clinician`) **chưa wire** → các trang admin tự **fallback demo data** (có cờ *"Demo data"*), thao tác CRUD chạy local; khi backend xong, FE **tự dùng API thật** (try real → fallback). Không cần sửa FE.
- **Thiếu** endpoint *list clinicians* — tạm dùng danh sách mock cho dropdown gán clinician. Đề xuất thêm `GET /api/admin/clinicians`.
- Endpoint **resolve cho `user_escalation`** (clinician đã liên hệ) chưa có trong doc — tạm dùng `approve`.

## 5. Chạy thử
```bash
cd user_app  && npm install && npm run dev   # http://localhost:5173
cd admin_app && npm install && npm run dev   # http://localhost:5174
```
Build kiểm tra: `npm run build` (cả 2 app pass sạch, 0 warning).
