export default function StatisticCard({ icon, title, value, hint, tone = "blue" }) {
  return (
    <article className="sm-stat-card">
      <div className={"sm-stat-icon " + tone}>{icon}</div>
      <div><span>{title}</span><strong>{value}</strong><small>{hint}</small></div>
    </article>
  );
}
