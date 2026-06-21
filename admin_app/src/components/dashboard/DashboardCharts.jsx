const configs = [
  ["screening_trend", "Xu hướng sàng lọc"],
  ["risk_distribution", "Phân bố rủi ro"],
  ["case_status_distribution", "Trạng thái ca"],
  ["ai_moderation_statistics", "Thống kê AI Moderation"],
  ["resource_usage", "Mức sử dụng tài nguyên"],
  ["cbt_completion", "Hoàn thành CBT"],
];

function valueOf(item) {
  return Number(item.value ?? item.count ?? item.total ?? 0);
}

function MiniChart({ chart }) {
  if (!chart?.available) return <div className="chart-unavailable">Data not available yet</div>;
  const series = chart.series || [];
  if (!series.length) return <div className="chart-unavailable">Chưa có dữ liệu trong kỳ</div>;
  const max = Math.max(...series.map(valueOf), 1);
  return (
    <div className="mini-chart">
      {series.slice(-12).map((item, index) => (
        <div className="mini-chart-column" key={item.label || item.date || index}
             title={`${item.label || item.date}: ${valueOf(item)}`}>
          <span style={{ height: `${Math.max(5, valueOf(item) / max * 100)}%` }} />
          <small>{item.label || item.date || ""}</small>
        </div>
      ))}
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
