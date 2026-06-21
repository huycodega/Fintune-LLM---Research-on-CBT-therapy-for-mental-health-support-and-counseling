const riskLabels = { L0: "Crisis", L1: "High Risk", L2: "Medium Risk", L3: "Low Risk" };
const statusLabels = {
  new: "Mới", viewed: "Đã xem", assigned: "Đã phân công",
  monitoring: "Đang theo dõi", escalated: "Đã chuyển cấp", closed: "Đã đóng",
};
const priorityLabels = { critical: "Khẩn cấp", high: "Cao", medium: "Trung bình", low: "Thấp" };

export function CaseRiskBadge({ value }) {
  return <span className={`case-badge risk-${String(value || "L3").toLowerCase()}`}>
    {value || "—"} · {riskLabels[value] || "Unknown"}</span>;
}
export function CasePriorityBadge({ value }) {
  return <span className={`case-badge priority-${value || "low"}`}>
    {priorityLabels[value] || value || "—"}</span>;
}
export function CaseStatusBadge({ value }) {
  return <span className={`case-badge status-${value || "new"}`}>
    {statusLabels[value] || value || "—"}</span>;
}
