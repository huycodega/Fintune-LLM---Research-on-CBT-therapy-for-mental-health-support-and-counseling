import { adminRequest, query } from "./http.js";

const riskMap = {
  high: "L1", elevated: "L2", moderate: "L2", low: "L3",
  critical: "L0", L0: "L0", L1: "L1", L2: "L2", L3: "L3",
};
const notes = new Map();

function ageFrom(dateOfBirth) {
  if (!dateOfBirth) return null;
  const date = new Date(dateOfBirth);
  const now = new Date();
  let age = now.getFullYear() - date.getFullYear();
  if (now < new Date(now.getFullYear(), date.getMonth(), date.getDate())) age -= 1;
  return age;
}

function normalize(user, screening) {
  const rawRisk = screening.risk_level || screening.risk || user.risk || "low";
  const riskLevel = Number(user.crisis_count || 0) > 0 ? "L0" : riskMap[rawRisk] || "L3";
  const sourceStatus = screening.status || screening.handling_status || "resolved";
  const status = {
    resolved: "completed", completed: "completed", open: "pending",
    pending: "pending", in_progress: "in_progress", expired: "expired", cancelled: "cancelled",
  }[sourceStatus] || "pending";
  const phq9 = screening.phq9_score ?? null;
  const gad7 = screening.gad7_score ?? null;
  const score = phq9 ?? gad7 ?? screening.score ?? 0;
  return {
    id: screening.id,
    screening_id: screening.id,
    user_id: user.id,
    user: {
      id: user.id,
      full_name: user.full_name || user.fullName || user.username,
      username: user.username,
      email: user.email,
      phone: user.phone,
      gender: user.gender || null,
      age: ageFrom(user.date_of_birth || user.dateOfBirth),
    },
    screening_date: screening.screened_at || screening.created_at || user.last_active,
    assessment_type: phq9 != null ? "PHQ-9" : gad7 != null ? "GAD-7" : "Screening",
    score,
    risk_level: riskLevel,
    status,
    answers: screening.answers || (screening.note ? [{ question: "Screening note", answer: screening.note }] : []),
    note: notes.get(screening.id) || "",
    ai_assessment: {
      risk_summary: { L0: "Critical Risk", L1: "High Depression Risk", L2: "Medium Risk", L3: "Low Risk" }[riskLevel],
      emotions: riskLevel === "L0" || riskLevel === "L1" ? ["Sadness", "Hopelessness"] : riskLevel === "L2" ? ["Anxiety", "Stress"] : ["Stable"],
      recommendation: riskLevel === "L0" ? "Immediate specialist intervention is required."
        : riskLevel === "L1" ? "Assign a specialist and arrange an early follow-up."
        : riskLevel === "L2" ? "Monitor symptoms and recommend a CBT follow-up."
        : "Continue routine monitoring.",
    },
    breakdown: {
      depression: phq9 ?? 0,
      anxiety: gad7 ?? 0,
      stress: Math.max(0, 10 - Number(screening.mood_score ?? user.mood_score ?? 10)),
    },
  };
}

async function allRows() {
  const usersPayload = await adminRequest("/users" + query({ page: 1, page_size: 100 }));
  const users = usersPayload.users || usersPayload.items || [];
  const histories = await Promise.all(users.map(async user => {
    const payload = await adminRequest("/users/" + user.id + "/screening-history" + query({ page: 1, limit: 100 }))
      .catch(() => ({ items: [] }));
    return (payload.items || payload.screenings || payload.history || []).map(row => normalize(user, row));
  }));
  return histories.flat();
}

function applyFilters(rows, params) {
  const term = String(params.search || "").trim().toLowerCase();
  let result = rows.filter(item =>
    (!term || [item.id, item.user_id, item.user.full_name, item.user.email, item.assessment_type]
      .some(value => String(value || "").toLowerCase().includes(term))) &&
    (!params.risk_level || item.risk_level === params.risk_level) &&
    (!params.status || item.status === params.status) &&
    (!params.from || new Date(item.screening_date) >= new Date(params.from)) &&
    (!params.to || new Date(item.screening_date) <= new Date(params.to + "T23:59:59"))
  );
  const key = params.sort_by || "screening_date";
  const order = params.sort_order === "asc" ? 1 : -1;
  result.sort((a, b) => String(a[key] ?? "").localeCompare(String(b[key] ?? "")) * order);
  return result;
}

export const screeningsApi = {
  list: async (params = {}) => {
    const filtered = applyFilters(await allRows(), params);
    const page = Number(params.page || 1);
    const pageSize = Number(params.page_size || 10);
    return {
      items: filtered.slice((page - 1) * pageSize, page * pageSize),
      total: filtered.length, page, page_size: pageSize,
    };
  },
  detail: async id => (await allRows()).find(item => item.id === id) || null,
  summary: async () => {
    const rows = await allRows();
    const completed = rows.filter(item => item.status === "completed");
    const highRisk = rows.filter(item => ["L0", "L1"].includes(item.risk_level));
    const today = new Date().toDateString();
    return {
      today: rows.filter(item => new Date(item.screening_date).toDateString() === today).length,
      completion_rate: rows.length ? Math.round(completed.length / rows.length * 1000) / 10 : 0,
      high_risk: highRisk.length,
      high_risk_percent: rows.length ? Math.round(highRisk.length / rows.length * 1000) / 10 : 0,
      average_score: rows.length ? Math.round(rows.reduce((sum, item) => sum + Number(item.score || 0), 0) / rows.length * 10) / 10 : 0,
    };
  },
  analytics: async () => {
    const rows = await allRows();
    return {
      risk_distribution: ["L0", "L1", "L2", "L3"].map(level => ({
        label: level, value: rows.filter(item => item.risk_level === level).length,
      })),
      completion_trend: rows.slice().sort((a, b) => new Date(a.screening_date) - new Date(b.screening_date))
        .map(item => ({ label: new Date(item.screening_date).toLocaleDateString("en-GB", { day: "2-digit", month: "short" }), value: item.status === "completed" ? 100 : 0 })),
    };
  },
  addNote: async (id, content) => { notes.set(id, content); return { id, content }; },
  exportCsv: async params => applyFilters(await allRows(), params),
};
