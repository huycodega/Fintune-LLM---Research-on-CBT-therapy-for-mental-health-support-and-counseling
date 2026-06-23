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

function MiniChart({ chart }) {
  if (!chart?.available) return <div className="chart-unavailable">Data not available yet</div>;
  const series = chart.series || [];
  if (!series.length) return <div className="chart-unavailable">No data in this period</div>;
  const max = Math.max(...series.map(valueOf), 1);
  const allZero = series.every((s) => valueOf(s) === 0);
  return (
    <div className="mini-chart">
      {series.slice(-12).map((item, index) => {
        const v = valueOf(item);
        return (
          <div className="mini-chart-column" key={item.label || item.date || index}
               title={`${item.label || item.date}: ${v}`}>
            <b className="mini-chart-val">{v}</b>
            <span className={v === max && !allZero ? "is-peak" : ""}
                  style={{ height: `${allZero ? 4 : Math.max(6, (v / max) * 100)}%` }} />
            <small>{item.label || item.date || ""}</small>
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
          <MiniChart chart={charts[key]} />
        </section>
      ))}
    </div>
  );
}
