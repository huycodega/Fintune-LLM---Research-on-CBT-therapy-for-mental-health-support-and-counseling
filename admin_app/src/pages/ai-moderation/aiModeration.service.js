import { getToken } from "../../api.js";

function qs(params) {
  const value = new URLSearchParams(
    Object.entries(params || {}).filter(([, v]) => v !== "" && v != null)
  ).toString();
  return value ? `?${value}` : "";
}

async function request(path, { method = "GET", body } = {}) {
  const headers = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`/api/admin/ai-moderation${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  const payload = await res.json().catch(() => ({}));
  if (!res.ok || payload.success === false) {
    const detail = payload.message || payload.error || payload.detail;
    throw new Error(typeof detail === "string" ? detail : `Request failed (${res.status})`);
  }
  return payload.data;
}

export const aiModerationApi = {
  stats: () => request("/stats"),
  sessions: (params) => request(`/sessions${qs(params)}`),
  detail: (id) => request(`/sessions/${id}`),
  approve: (id) => request(`/sessions/${id}/approve`, { method: "PATCH" }),
  reject: (id, reason) => request(`/sessions/${id}/reject`, { method: "PATCH", body: { reason } }),
  editResponse: (id, editedResponse, note) =>
    request(`/sessions/${id}/edit-response`, { method: "PATCH", body: { editedResponse, note } }),
  needImprovement: (id, reason) =>
    request(`/sessions/${id}/need-improvement`, { method: "PATCH", body: { reason } }),
};
