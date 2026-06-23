import { timeAgo } from "../../ui.jsx";

const cards = [
  ["total_users", "👥", "Total users", "purple"],
  ["active_users", "●", "Active users", "green"],
  ["high_risk_users", "⚠", "High-risk users", "red"],
  ["today_screenings", "📝", "Today's screenings", "blue"],
  ["pending_ai_moderations", "🤖", "AI pending moderation", "amber"],
  ["open_cases", "📋", "Open cases", "red"],
  ["published_resources", "📚", "Published resources", "green"],
  ["active_cbt_lessons", "◫", "Active CBT lessons", "purple"],
];

function metric(value) {
  return typeof value === "object" && value !== null
    ? { value: value.value ?? 0, change: value.change_percent }
    : { value: value ?? 0, change: null };
}

export default function DashboardSummaryCards({ summary }) {
  return (
    <div className="dashboard-kpis">
      {cards.map(([key, icon, label, color]) => {
        const item = metric(summary[key]);
        return (
          <article className="dashboard-kpi" key={key}>
            <div className={`stat-icon ${color}`}>{icon}</div>
            <div className="dashboard-kpi-copy">
              <span>{label}</span><strong>{Number(item.value).toLocaleString("vi-VN")}</strong>
            </div>
            {item.change != null && (
              <small className={item.change >= 0 ? "trend-up" : "trend-down"}>
                {item.change >= 0 ? "↑" : "↓"} {Math.abs(item.change)}%
              </small>
            )}
          </article>
        );
      })}
    </div>
  );
}

export function AttentionRequired({ items = [], onNavigate }) {
  return (
    <section className="panel attention-panel">
      <div className="panel-head">
        <div><div className="panel-title">Needs immediate attention</div>
          <div className="panel-caption">High-priority signals past SLA</div></div>
        <span className="attention-count">{items.length}</span>
      </div>
      {items.length === 0 ? (
        <div className="compact-empty">No alerts needing immediate action.</div>
      ) : items.slice(0, 6).map((item) => (
        <button className="attention-item" key={item.id} onClick={() => onNavigate?.(item)}>
          <span className={`attention-mark ${item.risk_level || "L1"}`} />
          <span><b>{item.label || item.type}</b><small>{item.user_masked || "Anonymized user"}</small></span>
          <span className={`case-badge risk-${(item.risk_level || "L1").toLowerCase()}`}>
            {item.risk_level || "L1"}
          </span>
          <time>{item.time_ago || timeAgo(item.created_at) || "—"}</time>
          <span>→</span>
        </button>
      ))}
    </section>
  );
}
