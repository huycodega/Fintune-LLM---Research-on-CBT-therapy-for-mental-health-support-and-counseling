// Admin app API client (v4). Locks expected_role to "admin".
const TOKEN_KEY = "cbt_admin_token";
const USER_KEY = "cbt_admin_user";
const EXPECTED_ROLE = "admin";

// Base URL of the backend. Empty in dev → "/api" hits the Vite proxy.
// In production (Vercel) set VITE_API_BASE to the Railway backend URL.
const API_BASE = import.meta.env.VITE_API_BASE || "";

export function getToken() { return localStorage.getItem(TOKEN_KEY); }
export function getUser() {
  try { return JSON.parse(localStorage.getItem(USER_KEY)); }
  catch { return null; }
}
export function setSession(token, user) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}
export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

async function req(path, { method = "GET", body } = {}) {
  const headers = { "Content-Type": "application/json" };
  const t = getToken();
  if (t) headers["Authorization"] = `Bearer ${t}`;
  const res = await fetch(`${API_BASE}/api${path}`, {
    method, headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = data.detail;
    const msg = Array.isArray(detail)
      ? detail.map((e) => e.msg || JSON.stringify(e)).join("; ")
      : (typeof detail === "string" ? detail : `Error ${res.status}`);
    throw new Error(msg);
  }
  return data;
}

function qs(params) {
  const s = new URLSearchParams(
    Object.entries(params || {}).filter(([, v]) => v !== "" && v != null)
  ).toString();
  return s ? `?${s}` : "";
}

export const api = {
  login: (username, password) =>
    req("/login", {
      method: "POST",
      body: { username, password, expected_role: EXPECTED_ROLE },
    }),
  health: () => req("/health"),

  // --- case handling (review queue) ---
  queue: () => req("/admin/queue"),
  adminSession: (sid) => req(`/admin/session/${sid}`),
  review: (sid, payload) =>
    req(`/admin/review/${sid}`, { method: "POST", body: payload }),
  stats: () => req("/admin/stats"),
  audit: () => req("/admin/audit"),
  dpoExport: () => req("/admin/dpo-export", { method: "POST" }),

  // --- dashboard ---
  overview: () => req("/admin/overview"),

  // --- user management ---
  users: (params) => req(`/admin/users${qs(params)}`),
  userDetail: (uid) => req(`/admin/users/${uid}`),
  setUserStatus: (uid, status, reason = "") =>
    req(`/admin/users/${uid}/status`, {
      method: "POST", body: { status, reason },
    }),
  setUserRole: (uid, role) =>
    req(`/admin/users/${uid}/role`, { method: "POST", body: { role } }),

  // --- crisis oversight ---
  crisis: (windowDays = 30) => req(`/admin/crisis?window_days=${windowDays}`),

  // --- lessons (LessonsAdmin) ---
  lessons: () => req("/admin/lessons"),
  createLesson: (payload) =>
    req("/admin/lessons", { method: "POST", body: payload }),
  updateLesson: (lid, payload) =>
    req(`/admin/lessons/${lid}`, { method: "PATCH", body: payload }),
  deleteLesson: (lid) =>
    req(`/admin/lessons/${lid}`, { method: "DELETE" }),

  // --- resources (ResourcesAdmin) ---
  resources: () => req("/admin/resources"),
  createResource: (payload) =>
    req("/admin/resources", { method: "POST", body: payload }),
  updateResource: (rid, payload) =>
    req(`/admin/resources/${rid}`, { method: "PATCH", body: payload }),
  deleteResource: (rid) =>
    req(`/admin/resources/${rid}`, { method: "DELETE" }),
};
