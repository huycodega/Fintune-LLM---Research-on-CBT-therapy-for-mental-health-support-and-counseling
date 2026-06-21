# Codex Activity Log

Short repo-local log of changes made by Codex.

## 2026-06-15 20:36:18 +07:00

- Summary: Install Codex activity logging
- Files: AGENTS.md, .codex/log_codex.ps1, .codex/codex-log.md
- Verification: Created helper and project instructions
- Notes: Backend AI pipeline logging from the previous misread was removed.

## 2026-06-21 18:25:00 +07:00

- Summary: Designed backend/database for Dashboard and Case Management
- Files: docs/DB-DASHBOARD-CASE.md
- Verification: Checked 13 required sections, Markdown fences, UTF-8 content, and git status
- Notes: Design only; no backend implementation or existing schema changed

## 2026-06-21 19:05:14 +07:00

- Summary: Built Dashboard and Case Management admin UI
- Files: admin_app/src/App.jsx, admin_app/src/styles.css, admin_app/src/components/dashboard, admin_app/src/components/cases, admin_app/src/components/shared, admin_app/src/services, admin_app/src/types
- Verification: npm ci; npm run build (Vite production build passed, 52 modules)
- Notes: Uses live API by default; VITE_ADMIN_DATA_MODE=mock provides empty-state contract while new backend endpoints are unavailable

## 2026-06-21 19:27:49 +07:00

- Summary: Added populated mock data for Dashboard and Case Management
- Files: admin_app/src/services/mockAdminData.js, admin_app/src/services/dashboardApi.js, admin_app/src/services/casesApi.js
- Verification: npm run build passed (53 modules)
- Notes: Mock cases reuse existing demo usernames and support filters plus assign/escalate/close/reopen/note in memory

## 2026-06-21 20:03:00 +07:00

- Summary: Linked Dashboard and Case mock data to User Management
- Files: admin_app/src/services/mockAdminData.js, admin_app/src/services/dashboardApi.js, admin_app/src/services/casesApi.js, admin_app/src/App.jsx, admin_app/src/pages/Users.jsx, admin_app/src/components/cases/CaseManagementPage.jsx
- Verification: Verified shared user IDs and API linkage; npm run build passed (53 modules)
- Notes: Dashboard user KPIs read /admin/users/stats; Case profile navigation selects the matching user; assign/close update mock user state

## 2026-06-21 22:44:57 +07:00

- Summary: Integrated AI Moderation into admin dashboard
- Files: admin_app/src/pages/ai-moderation, admin_app/src/App.jsx, admin_app/src/styles.css, admin_app/src/components/dashboard/DashboardPage.jsx, admin_app/src/services/dashboardApi.js
- Verification: npm run build passed (61 modules)
- Notes: Sidebar now includes AI Moderation; Dashboard pending moderation links and mock KPI/list read the moderation mock API

## 2026-06-21 23:01:54 +07:00

- Summary: Removed legacy Crisis Control navigation
- Files: admin_app/src/App.jsx
- Verification: Confirmed no Crisis Control route/import; npm run build passed (60 modules)
- Notes: L0/L1 remain available through Case Management and AI Moderation

