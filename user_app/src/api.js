// User app API client (v4). Locks expected_role to "user".
// Backend v4 also returns consent_required / intake_required flags
// on login + /me, which the app reads to decide which screen to show.
const TOKEN_KEY = "cbt_user_token";
const USER_KEY = "cbt_user_user";
const EXPECTED_ROLE = "user";

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
    method,
    headers,
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
  me: () => req("/me"),
  consent: () => req("/consent", { method: "POST", body: { accepted: true } }),
  submitIntake: (raw_text) =>
    req("/intake", { method: "POST", body: { raw_text } }),
  getIntake: () => req("/my/intake"),
  health: () => req("/health"),
  chat: (message, opts = {}) =>
    req("/chat", { method: "POST", body: { message, ...opts } }),
  mySessions: () => req("/my/sessions"),
  mySession: (sid) => req(`/my/session/${sid}`),
};
