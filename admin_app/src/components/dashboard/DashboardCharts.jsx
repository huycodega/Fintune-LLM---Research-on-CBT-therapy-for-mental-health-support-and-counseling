const configs = [
  ["screening_trend", "Screening trend"],
  ["risk_distribution", "Risk distribution"],
  ["case_status_distribution", "Case status"],
  ["ai_moderation_statistics", "AI Moderation statistics"],
  ["resource_usage", "Resource usage"],
  ["cbt_completion", "CBT completion"],
];

function valueOf(item) {
  return Number(item.value ?? item.count ?? item.total ?? 0);
}

// Per-category colours so charts aren't a wall of one purple.
const CATEGORY_COLORS = {
  risk_distribution:        { L0: "#ef4444", L1: "#f97316", L2: "#f59e0b", L3: "#22c55e" },
  case_status_distribution: { New: "#6366f1", Monitoring: "#f59e0b", Closed: "#22c55e" },
  ai_moderation_statistics: { Pending: "#f59e0b", Resolved: "#22c55e" },
};
const SERIES_GRAD = {
  screening_trend: ["#6366f1", "#c7d2fe"],
  resource_usage:  ["#14b8a6", "#99f6e4"],
  cbt_completion:  ["#8b5cf6", "#ddd6fe"],
};
function barBg(key, label) {
  const c = CATEGORY_COLORS[key]?.[label];
  if (c) return `linear-gradient(180deg, ${c}, ${c}aa)`;
  const [a, b] = SERIES_GRAD[key] || ["#818cf8", "#c7d2fe"];
  return `linear-gradient(180deg, ${a}, ${b})`;
}

function MiniChart({ chart, chartKey }) {
  if (!chart?.available) return <div className="chart-unavailable">Data not available yet</div>;
  const series = chart.series || [];
  if (!series.length) return <div className="chart-unavailable">No data in this period</div>;
  const max = Math.max(...series.map(valueOf), 1);
  const allZero = series.every((s) => valueOf(s) === 0);
  return (
    <div className="mini-chart">
      {series.slice(-12).map((item, index) => {
        const v = valueOf(item);
        const label = item.label || item.date || "";
        return (
          <div className="mini-chart-column" key={label || index} title={`${label}: ${v}`}>
            <b className="mini-chart-val">{v}</b>
            <span style={{ height: `${allZero ? 4 : Math.max(6, (v / max) * 100)}%`,
                           background: barBg(chartKey, label) }} />
            <small>{label}</small>
          </div>
        );
      })}
    </div>
  );
}

export default function DashboardCharts({ charts }) {
  return (
    <div className="dashboard-charts">
      {configs.map(([key, title]) => (
        <section className="panel chart-card" key={key}>
          <div className="panel-head"><div className="panel-title">{title}</div></div>
          <MiniChart chart={charts[key]} chartKey={key} />
        </section>
      ))}
    </div>
  );
}
