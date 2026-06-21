import { RISK_META } from "./aiModeration.types.js";

export default function RiskLevelBadge({ level }) {
  const meta = RISK_META[level] || RISK_META.L0;
  return <span className={`am-risk-badge ${meta.tone}`}>{meta.label}</span>;
}
