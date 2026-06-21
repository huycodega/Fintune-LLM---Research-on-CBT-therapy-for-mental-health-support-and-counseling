import { adminRequest, query } from "./http.js";
import { mockCases } from "./mockAdminData.js";

const clone = (value) => JSON.parse(JSON.stringify(value));
const findCase = (id) => mockCases.find(item => item.id === id);
const addHistory = (item, type, fromStatus) => {
  item.history.unshift({
    id: "hist-" + crypto.randomUUID(), event_type: type, actor_name: "clinician",
    from_status: fromStatus, to_status: item.status, created_at: new Date().toISOString(),
  });
  item.version += 1;
  return clone(item);
};
const transition = (id, status, eventType) => {
  const item = findCase(id);
  if (!item) return null;
  const previous = item.status;
  item.status = status;
  return addHistory(item, eventType, previous);
};

export const mockCasesApi = {
  list: async (params = {}) => {
    const q = String(params.q || "").toLowerCase();
    let items = mockCases.filter(item =>
      (!q || [item.case_code, item.user.display_name, item.user.email_masked]
        .some(value => String(value).toLowerCase().includes(q))) &&
      (!params.priority || item.priority === params.priority) &&
      (!params.status || item.status === params.status) &&
      (!params.source_type || item.source_type === params.source_type) &&
      (!params.specialist_id || item.assigned_specialist?.id === params.specialist_id) &&
      (!params.from || new Date(item.created_at) >= new Date(params.from)) &&
      (!params.to || new Date(item.created_at) <= new Date(params.to + "T23:59:59"))
    );
    const page = Number(params.page || 1);
    const pageSize = Number(params.page_size || 20);
    return { items: clone(items.slice((page - 1) * pageSize, page * pageSize)),
      total: items.length, page, page_size: pageSize };
  },
  stats: async () => ({
    new: mockCases.filter(item => item.status === "new").length,
    critical: mockCases.filter(item => item.priority === "critical" && item.status !== "closed").length,
    monitoring: mockCases.filter(item => item.status === "monitoring").length,
    closed: mockCases.filter(item => item.status === "closed").length,
    specialists: [{ id: "S0001", display_name: "Le Thanh Lan" }],
  }),
  detail: async (id) => clone(findCase(id)),
  history: async (id) => ({ items: clone(findCase(id)?.history || []), total: findCase(id)?.history.length || 0 }),
  update: async (id, body) => transition(id, body.status, "status_changed"),
  assign: async (id, body) => {
    const item = findCase(id);
    await adminRequest("/users/" + item.user.id + "/assign-specialist", {
      method: "POST", body: { specialist_id: body.specialist_id },
    }).catch(() => null);
    item.assigned_specialist = { id: body.specialist_id, display_name: "Le Thanh Lan" };
    return transition(id, "assigned", "assigned");
  },
  escalate: async (id) => transition(id, "escalated", "escalated"),
  close: async (id) => {
    const item = findCase(id);
    await adminRequest("/users/" + item.user.id + "/mark-resolved", {
      method: "PATCH", body: { note: "Case closed from Case Management" },
    }).catch(() => null);
    item.closed_at = new Date().toISOString();
    return transition(id, "closed", "closed");
  },
  reopen: async (id) => {
    const item = findCase(id);
    item.closed_at = null;
    return transition(id, "monitoring", "reopened");
  },
  addNote: async (id, body) => {
    const item = findCase(id);
    item.notes.unshift({ id: "note-" + crypto.randomUUID(), author_name: "clinician",
      content: body.content, created_at: new Date().toISOString() });
    return addHistory(item, "note_added", item.status);
  },
};

const normalizePage = (payload, params) => ({
  items: payload.items || payload.cases || [], total: payload.total || 0,
  page: payload.page || params.page || 1, page_size: payload.page_size || params.page_size || 20,
});

const liveCasesApi = {
  list: async (params = {}) => normalizePage(await adminRequest("/cases" + query(params)), params),
  stats: () => adminRequest("/cases/stats"),
  detail: (id) => adminRequest("/cases/" + id),
  history: (id, params) => adminRequest("/cases/" + id + "/history" + query(params)),
  update: (id, body) => adminRequest("/cases/" + id, { method: "PATCH", body }),
  assign: (id, body) => adminRequest("/cases/" + id + "/assign", { method: "POST", body }),
  escalate: (id, body) => adminRequest("/cases/" + id + "/escalate", { method: "POST", body }),
  close: (id, body) => adminRequest("/cases/" + id + "/close", { method: "POST", body }),
  reopen: (id, body) => adminRequest("/cases/" + id + "/reopen", { method: "POST", body }),
  addNote: (id, body) => adminRequest("/cases/" + id + "/note", { method: "POST", body }),
};

export const casesApi =
  import.meta.env.VITE_ADMIN_DATA_MODE === "mock" ? mockCasesApi : liveCasesApi;