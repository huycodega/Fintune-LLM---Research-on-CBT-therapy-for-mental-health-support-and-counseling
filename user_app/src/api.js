// User app API client (v4). Locks expected_role to "user".
// Backend v4 also returns consent_required / intake_required flags
// on login + /me, which the app reads to decide which screen to show.
const TOKEN_KEY = "cbt_user_token";
const USER_KEY = "cbt_user_user";
const EXPECTED_ROLE = "user";

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
    method,
    headers,
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

export const api = {
  // ---- auth ----
  login: (username, password) =>
    req("/login", {
      method: "POST",
      body: { username, password, expected_role: EXPECTED_ROLE },
    }),
  googleAuth: (credential) =>
    req("/auth/google", {
      method: "POST",
      body: { credential, expected_role: EXPECTED_ROLE },
    }),
  register: (email, password) =>
    req("/register", { method: "POST", body: { email, password } }),
  verifyOtp: (email, otp) =>
    req("/verify-otp", { method: "POST", body: { email, otp } }),
  resendOtp: (email) =>
    req("/resend-otp", { method: "POST", body: { email } }),
  me: () => req("/me"),
  consent: () => req("/consent", { method: "POST", body: { accepted: true } }),
  submitIntake: (raw_text) =>
    req("/intake", { method: "POST", body: { raw_text } }),
  getIntake: () => req("/my/intake"),
  health: () => req("/health"),

  // ---- chat (multi-turn; pass conversation_id to continue a thread) ----
  chat: (message, opts = {}) =>
    req("/chat", { method: "POST", body: { message, ...opts } }),
  mySessions: () => req("/my/sessions"),
  mySession: (sid) => req(`/my/session/${sid}`),

  // ---- conversations (tasktab) ----
  listConversations: () => req("/conversations"),
  createConversation: () => req("/conversations", { method: "POST" }),
  getConversation: (cid) => req(`/conversations/${cid}`),
  renameConversation: (cid, title) =>
    req(`/conversations/${cid}`, { method: "PATCH", body: { title } }),
  deleteConversation: (cid) =>
    req(`/conversations/${cid}`, { method: "DELETE" }),

  // ---- memory ----
  myMemory: () => req("/memory"),

  // ---- screening ----
  submitScreening: (data) =>
    req("/screening", { method: "POST", body: data }),
  screeningHistory: (limit = 20) =>
    req(`/screening/history?limit=${limit}`),
  latestScreening: () => req("/screening/latest"),
  screeningToday: () => req("/screening/today"),

  // ---- learning content (BaiHoc / TaiNguyen) ----
  lessons: (params = {}) => {
    const q = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== "" && v != null)
    ).toString();
    return req(`/lessons${q ? `?${q}` : ""}`);
  },
  lesson: (lid) => req(`/lessons/${lid}`),
  resources: (params = {}) => {
    const q = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== "" && v != null)
    ).toString();
    return req(`/resources${q ? `?${q}` : ""}`);
  },
  resource: (rid) => req(`/resources/${rid}`),

  // ---- per-user lesson progress ----
  lessonProgress: () => req("/my/lesson-progress"),
  setLessonProgress: (lid, body) =>
    req(`/my/lesson-progress/${lid}`, { method: "POST", body }),

  // ---- expert consultation ----
  experts: () => req("/experts"),
  expertAvailability: (eid) => req(`/experts/${eid}/availability`),
  bookAppointment: (body) =>
    req("/appointments", { method: "POST", body }),
  myAppointments: () => req("/my/appointments"),
  changeAppointment: (aid, body) =>
    req(`/my/appointments/${aid}`, { method: "PATCH", body }),
  cancelAppointment: (aid) =>
    req(`/my/appointments/${aid}`, { method: "DELETE" }),
};
