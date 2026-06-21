import { getToken } from "../api.js";

// Same base as api.js: empty in dev (Vite proxy) or the Railway URL in
// prod/local-against-prod via VITE_API_BASE — so the service-based pages
// (dashboard, cases, screening) hit the same backend as the rest of the app.
const API_BASE = import.meta.env.VITE_API_BASE || "";

export class ApiError extends Error {
  constructor(message, status, payload) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

export function query(params = {}) {
  const value = new URLSearchParams(
    Object.entries(params).filter(([, item]) => item !== "" && item != null)
  ).toString();
  return value ? `?${value}` : "";
}

export async function adminRequest(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...options.headers };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${API_BASE}/api/admin${path}`, {
    ...options,
    headers,
    body: options.body && typeof options.body !== "string"
      ? JSON.stringify(options.body) : options.body,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = payload.detail || payload.message;
    const message = Array.isArray(detail)
      ? detail.map((item) => item.msg || String(item)).join("; ")
      : detail || `Request failed (${response.status})`;
    throw new ApiError(message, response.status, payload);
  }
  return payload.data ?? payload;
}
