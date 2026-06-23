import { adminRequest, query } from "./http.js";

// Map a VALIDATED PHQ-9 / GAD-7 severity band to the admin L-risk convention.
// A screening score alone (no active suicidal statement) never implies L0 —
// that's a chat-crisis signal, not a questionnaire result — so we cap at L1.
const LEVEL_RISK = {
  normal: "L3", mild: "L3", moderate: "L2",
  moderately_severe: "L1", severe: "L1",
};
const LEVEL_LABEL = {
  normal: "Minimal", mild: "Mild", moderate: "Moderate",
  moderately_severe: "Moderately severe", severe: "Severe",
};

function ageFrom(dateOfBirth) {
  if (!dateOfBirth) return null;
  const date = new Date(dateOfBirth);
  const now = new Date();
  let age = now.getFullYear() - date.getFullYear();
  if (now < new Date(now.getFullYear(), date.getMonth(), date.getDate())) age -= 1;
  return age;
}

function normalize(user, screening) {
  const sourceStatus = screening.status || screening.handling_status || "resolved";
  const status = {
    resolved: "completed", completed: "completed", open: "pending",
    pending: "pending", in_progress: "in_progress", expired: "expired", cancelled: "cancelled",
  }[sourceStatus] || "pending";
  const phq9 = screening.phq9_score ?? null;
  const gad7 = screening.gad7_score ?? null;
  const phqLevel = screening.phq9_level || null;
  const gadLevel = screening.gad7_level || null;
  const isPhq = phq9 != null;
  const score = phq9 ?? gad7 ?? screening.score ?? 0;

  // Risk comes from the screening's OWN validated severity band — the worse of
  // the two instruments present — NOT from the user's chat crisis count.
  const risks = [phqLevel, gadLevel].filter(Boolean).map((l) => LEVEL_RISK[l] || "L3");
  let riskLevel = risks.length ? risks.slice().sort()[0] : "L3";  // L0<L1<L2<L3
  // PHQ-9 item 9 (thoughts of self-harm) endorsed → crisis/emergency (L0),
  // mirroring the Reports classifier so both views agree.
  const phqAnswers = Array.isArray(screening.phq9_answers) ? screening.phq9_answers : [];
  const selfHarm = phqAnswers.length >= 9 && Number(phqAnswers[8]) > 0;
  if (selfHarm) riskLevel = "L0";
  const primaryLevel = isPhq ? phqLevel : gadLevel;
  const bandLabel = LEVEL_LABEL[primaryLevel] || "Screening";
  const instrument = isPhq ? "depression" : "anxiety";

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
    notes: screening.admin_notes || [],
    // Clinical interpretation grounded in the validated band (not fabricated).
    ai_assessment: {
      risk_summary: selfHarm
        ? `Critical — PHQ-9 item 9 (thoughts of self-harm) endorsed (score ${score})`
        : `${bandLabel} ${instrument} — ${isPhq ? "PHQ-9" : "GAD-7"} score ${score}`,
      emotions: selfHarm ? ["Self-harm risk"] : [`${bandLabel} ${instrument}`],
      recommendation: selfHarm
        ? "Thoughts of self-harm were endorsed — prioritise immediate clinician review and safety follow-up."
        : riskLevel === "L1"
        ? "Score in the elevated range — assign a specialist and arrange an early follow-up."
        : riskLevel === "L2"
        ? "Moderate range — monitor symptoms and recommend a CBT follow-up."
        : "Within the low/normal range — continue routine monitoring.",
    },
    breakdown: {
      depression: phq9 ?? 0,
      anxiety: gad7 ?? 0,
      mood: Number(screening.mood_score ?? user.mood_score ?? 0),
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
    // Completion trend = number of screenings completed per day (real volume).
    const byDay = {};
    rows.forEach((item) => {
      const key = new Date(item.screening_date).toISOString().slice(0, 10);
      byDay[key] = (byDay[key] || 0) + 1;
    });
    const completion_trend = Object.keys(byDay).sort().map((key) => ({
      label: new Date(key).toLocaleDateString("en-GB", { day: "2-digit", month: "short" }),
      value: byDay[key],
    }));
    return {
      risk_distribution: ["L0", "L1", "L2", "L3"].map(level => ({
        label: level, value: rows.filter(item => item.risk_level === level).length,
      })),
      completion_trend,
    };
  },
  addNote: async (id, content) =>
    adminRequest("/screenings/" + id + "/note", { method: "POST", body: { content } }),
  exportCsv: async params => applyFilters(await allRows(), params),
};
