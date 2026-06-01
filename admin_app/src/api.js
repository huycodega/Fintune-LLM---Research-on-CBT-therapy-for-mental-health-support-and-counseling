// Admin app API client (v4). Locks expected_role to "admin".
const TOKEN_KEY = "cbt_admin_token";
const USER_KEY = "cbt_admin_user";
const EXPECTED_ROLE = "admin";

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
  const res = await fetch(`/api${path}`, {
    method, headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Error ${res.status}`);
  return data;
}

export const api = {
  login: (username, password) =>
    req("/login", {
      method: "POST",
      body: { username, password, expected_role: EXPECTED_ROLE },
    }),
  health: () => req("/health"),
  queue: () => req("/admin/queue"),
  adminSession: (sid) => req(`/admin/session/${sid}`),
  review: (sid, payload) =>
    req(`/admin/review/${sid}`, { method: "POST", body: payload }),
  stats: () => req("/admin/stats"),
  audit: () => req("/admin/audit"),
  dpoExport: () => req("/admin/dpo-export", { method: "POST" }),
};
