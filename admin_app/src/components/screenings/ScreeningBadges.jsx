const riskMeta = {
  L0: ["Critical", "critical"], L1: ["High", "high"],
  L2: ["Medium", "medium"], L3: ["Low", "low"],
};
const statusMeta = {
  completed: "Completed", pending: "Pending", in_progress: "In Progress",
  expired: "Expired", cancelled: "Cancelled",
};
export function RiskBadge({ value }) {
  const meta = riskMeta[value] || [value || "-", "low"];
  return <span className={"sm-badge risk-" + meta[1]}>{value} · {meta[0]}</span>;
}
export function ScreeningStatusBadge({ value }) {
  return <span className={"sm-badge status-" + value}>{statusMeta[value] || value || "-"}</span>;
}
