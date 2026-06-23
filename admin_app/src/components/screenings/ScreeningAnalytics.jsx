const RISK_COLORS = { L0: "#dc2626", L1: "#ef4444", L2: "#f59e0b", L3: "#10b981" };

export default function ScreeningAnalytics({ data }) {
  if (!data) return null;
  const risk = data.risk_distribution || [];
  const trend = (data.completion_trend || []).slice(-14);
  const total = risk.reduce((s, r) => s + (r.value || 0), 0) || 1;

  return (
    <section className="sm-analytics">
      <div className="sm-chart-card">
        <h3>Risk distribution</h3>
        <div className="sm-donut-legend">
          {risk.length === 0 && <p className="sm-page-info">No screenings yet.</p>}
          {risk.map((r) => (
            <div key={r.label} className="sm-legend-item">
              <span className="sm-legend-dot" style={{ background: RISK_COLORS[r.label] || "#94a3b8" }} />
              {r.label} — {r.value} ({Math.round((r.value / total) * 100)}%)
            </div>
          ))}
        </div>
      </div>

      <div className="sm-chart-card">
        <h3>Completion trend</h3>
        {trend.length === 0 ? (
          <p className="sm-page-info">No data yet.</p>
        ) : (() => {
          const max = Math.max(...trend.map((t) => t.value || 0), 1);
          return (
            <div className="sm-trend-chart">
              {trend.map((t, i) => (
                <div className="sm-trend-col" key={i} title={`${t.label}: ${t.value}`}>
                  <b>{t.value}</b>
                  <span style={{ height: `${Math.max(8, ((t.value || 0) / max) * 100)}%` }} />
                  <small>{t.label}</small>
                </div>
              ))}
            </div>
          );
        })()}
      </div>
    </section>
  );
}
