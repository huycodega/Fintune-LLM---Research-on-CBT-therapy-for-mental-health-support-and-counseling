const ago = (hours) => new Date(Date.now() - hours * 3600000).toISOString();
const ahead = (hours) => new Date(Date.now() + hours * 3600000).toISOString();

export const mockCases = [
  {
    id: "case-001", case_code: "CASE-9821", source_type: "ai_message",
    user: { id: "U0223", display_name: "minh_anh", email_masked: "min***@email.com", phone_masked: "09*****123" },
    detected_signal_summary: "SELF_HARM_INTENT · Ý định tự làm hại bản thân",
    priority: "critical", risk_level: "L0", status: "new", assigned_specialist: null,
    ai_confidence: 0.96, sla_due_at: ago(1), created_at: ago(2), version: 1,
    source: { content_masked: "Tôi cảm thấy không thể tiếp tục và đang nghĩ đến việc làm hại mình…", created_at: ago(2), session_id: "SES-2401" },
    signals: [
      { id: "sig-1", signal_code: "SELF_HARM_INTENT", category: "self_harm", risk_level: "L0", confidence: 0.96, detected_by: "safety_model" },
      { id: "sig-2", signal_code: "HOPELESSNESS", category: "depression", risk_level: "L1", confidence: 0.89, detected_by: "rule" },
    ],
    actions: [
      { id: "act-1", action_type: "notify_specialist", status: "pending", due_at: ago(1) },
      { id: "act-2", action_type: "hotline", status: "in_progress", due_at: ahead(1) },
      { id: "act-3", action_type: "safety_plan", status: "pending", due_at: ahead(2) },
    ],
    notes: [], attachments: [],
    history: [{ id: "hist-1", event_type: "created", actor_name: "System", created_at: ago(2) }],
  },
  {
    id: "case-002", case_code: "CASE-9814", source_type: "screening",
    user: { id: "U0312", display_name: "thanh_tam", email_masked: "tam***@email.com", phone_masked: "08*****456" },
    detected_signal_summary: "PHQ9_SEVERE · Điểm PHQ-9 ở mức nghiêm trọng",
    priority: "high", risk_level: "L1", status: "monitoring",
    assigned_specialist: { id: "S0001", display_name: "Le Thanh Lan" },
    ai_confidence: 0.88, sla_due_at: ahead(4), created_at: ago(18), version: 2,
    source: { screening_type: "PHQ-9", score: 24, risk_level: "L1", created_at: ago(18) },
    signals: [{ id: "sig-3", signal_code: "PHQ9_SEVERE", category: "depression", risk_level: "L1", confidence: 0.88, detected_by: "screening" }],
    actions: [{ id: "act-4", action_type: "follow_up", status: "in_progress", due_at: ahead(4) }],
    notes: [{ id: "note-1", author_name: "clinician", content: "Đã liên hệ và thống nhất lịch theo dõi.", created_at: ago(10) }],
    attachments: [],
    history: [
      { id: "hist-2", event_type: "created", actor_name: "System", created_at: ago(18) },
      { id: "hist-3", event_type: "assigned", actor_name: "clinician", created_at: ago(16), from_status: "viewed", to_status: "assigned" },
    ],
  },
  {
    id: "case-003", case_code: "CASE-9788", source_type: "manual",
    user: { id: "U0187", display_name: "quang_huy", email_masked: "huy***@email.com", phone_masked: "07*****789" },
    detected_signal_summary: "PANIC_EPISODE · Cơn hoảng loạn tái diễn",
    priority: "medium", risk_level: "L2", status: "closed",
    assigned_specialist: { id: "S0001", display_name: "Le Thanh Lan" },
    ai_confidence: 0.79, sla_due_at: ago(20), created_at: ago(72), closed_at: ago(24), version: 4,
    source: {}, signals: [{ id: "sig-4", signal_code: "PANIC_EPISODE", category: "panic", risk_level: "L2", confidence: 0.79, detected_by: "admin" }],
    actions: [{ id: "act-5", action_type: "contact_user", status: "completed", due_at: ago(48) }],
    notes: [], attachments: [],
    history: [
      { id: "hist-4", event_type: "created", actor_name: "clinician", created_at: ago(72) },
      { id: "hist-5", event_type: "closed", actor_name: "clinician", created_at: ago(24), from_status: "monitoring", to_status: "closed" },
    ],
  },
];

export const mockScreenings = [
  { id: "screen-1", user_masked: "minh_anh", screening_type: "PHQ-9", risk_level: "L1", score: 24, created_at: ago(3) },
  { id: "screen-2", user_masked: "thanh_tam", screening_type: "GAD-7", risk_level: "L2", score: 14, created_at: ago(26) },
];
export const mockModerations = [
  { id: "mod-1", queue_code: "MOD-1042", user_masked: "minh_anh", risk_level: "L0", status: "pending", created_at: ago(1) },
  { id: "mod-2", queue_code: "MOD-1039", user_masked: "thanh_tam", risk_level: "L1", status: "pending", created_at: ago(5) },
];
export const mockActivities = [
  { id: "audit-1", actor_name: "clinician", action: "assigned case", module: "cases", created_at: ago(1) },
  { id: "audit-2", actor_name: "System", action: "risk detected", module: "screenings", created_at: ago(3) },
  { id: "audit-3", actor_name: "clinician", action: "reviewed AI response", module: "moderation", created_at: ago(5) },
];

export const mockCharts = {
  screening_trend: { available: true, series: [{ label: "T2", value: 3 }, { label: "T3", value: 5 }, { label: "T4", value: 4 }, { label: "T5", value: 7 }, { label: "T6", value: 6 }, { label: "T7", value: 8 }] },
  risk_distribution: { available: true, series: [{ label: "L0", value: 1 }, { label: "L1", value: 2 }, { label: "L2", value: 4 }, { label: "L3", value: 9 }] },
  case_status_distribution: { available: true, series: [{ label: "New", value: 1 }, { label: "Theo dõi", value: 1 }, { label: "Close", value: 1 }] },
  ai_moderation_statistics: { available: true, series: [{ label: "Chờ", value: 2 }, { label: "Duyệt", value: 8 }, { label: "Cải thiện", value: 3 }] },
  resource_usage: { available: false, series: [] },
  cbt_completion: { available: false, series: [] },
};
