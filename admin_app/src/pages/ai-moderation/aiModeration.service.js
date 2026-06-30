import { getToken } from "../../api.js";

// Same base as the rest of the admin app (Railway in prod / local-against-prod
// via VITE_API_BASE). The previous relative "/api/..." hit a dead local proxy.
const API_BASE = import.meta.env.VITE_API_BASE || "";

async function request(path, { method = "GET", body } = {}) {
  const headers = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}/api/admin/ai-moderation${path}`, {
    method, headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  const payload = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = payload.detail || payload.message || payload.error;
    throw new Error(typeof detail === "string" ? detail : `Request failed (${res.status})`);
  }
  return payload;
}

// Map the backend's snake_case moderation item to the shape the UI expects.
function mapItem(it) {
  if (!it) return null;
  const msgs = it.messages || [];
  const userContent = (msgs.find((m) => m.sender === "user") || msgs[0] || {}).content || "";
  const aiResponse = it.draft?.response || "";
  return {
    id: it.id,
    sessionId: it.id,
    riskLevel: it.risk_level,
    status: it.status,
    createdAt: it.created_at,
    reviewedAt: it.reviewed_at || null,
    reviewedBy: it.claimed_by?.name || null,
    user: {
      fullName: it.user?.name, username: it.user?.name,
      email: it.user?.masked_email, userCode: null,
    },
    userName: it.user?.name,
    userEmail: it.user?.masked_email,
    contentSummary: userContent.slice(0, 120),
    userContent,
    aiResponse,
    editedResponse: it.edited_response || "",
    aiNote: it.ai_note || "",
    moderatorNote: it.moderator_note || "",
    checklist: it.checklist || {},
    histories: it.histories || it.revisions || [],
    agentTrace: it.agent_trace || null,
    reasoning: it.reasoning || null,
    retrievedIds: it.retrieved_ids || [],
    drafts: (it.drafts && it.drafts.length)
      ? it.drafts.map((d) => ({
          id: d.id, idx: d.idx, technique: d.technique,
          preflightPass: d.preflight_pass !== false,
          rationale: d.rationale, plan: d.plan, response: d.response,
        }))
      : (it.draft
          ? [{ id: `${it.id}-d`, idx: 0, technique: it.draft.model_name,
               preflightPass: true, response: it.draft.response }]
          : []),
  };
}

function mapStats(s) {
  return {
    totalPending: s?.pending ?? 0,
    highRisk: s?.escalations ?? 0,
    reviewedToday: s?.resolved_today ?? 0,
    needImprovement: s?.in_review ?? 0,
  };
}

export const aiModerationApi = {
  stats: async () => mapStats(await request("/stats")),

  sessions: async (params = {}) => {
    const data = await request("/items");
    let items = (data.items || []).map(mapItem);
    const q = String(params.search || "").toLowerCase();
    if (q) items = items.filter((it) =>
      [it.sessionId, it.userName, it.userEmail, it.contentSummary]
        .some((v) => String(v || "").toLowerCase().includes(q)));
    if (params.riskLevel) items = items.filter((it) => it.riskLevel === params.riskLevel);
    items.sort((a, b) => {
      const av = a.createdAt || "", bv = b.createdAt || "";
      return params.sortOrder === "asc" ? (av > bv ? 1 : -1) : (av < bv ? 1 : -1);
    });
    const total = items.length;
    const limit = Number(params.limit || 10);
    const page = Number(params.page || 1);
    const totalPages = Math.max(1, Math.ceil(total / limit));
    return {
      items: items.slice((page - 1) * limit, page * limit),
      pagination: { page, limit, total, totalPages },
    };
  },

  detail: async (id) => mapItem(await request(`/items/${id}`)),
  history: async () => {
    const data = await request("/history");
    return data.items || [];
  },
  approve: (id, draftIdx) =>
    request(`/items/${id}/approve`, { method: "PATCH", body: { draft_idx: draftIdx ?? null } }),
  reject: (id, reason) => request(`/items/${id}/reject`, { method: "PATCH", body: { note: reason } }),
  editResponse: (id, editedResponse, note) =>
    request(`/items/${id}/edit-response`, { method: "PATCH", body: { response: editedResponse, note } }),
  needImprovement: (id, reason) =>
    request(`/items/${id}/need-improvement`, { method: "PATCH", body: { note: reason } }),
  // Clinician Copilot — advisory AI assist (summarize | suggest | explain | soap | ask).
  copilot: (id, action, question = "") =>
    request(`/items/${id}/copilot`, { method: "POST", body: { action, question } }),
};
