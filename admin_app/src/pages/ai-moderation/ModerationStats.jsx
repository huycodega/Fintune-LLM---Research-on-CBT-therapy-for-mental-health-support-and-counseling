function StatIcon({ tone }) {
  return <span className={`am-stat-icon ${tone}`} />;
}

function StatCard({ title, value, hint, tone }) {
  return (
    <article className="am-stat-card">
      <StatIcon tone={tone} />
      <div>
        <span>{title}</span>
        <strong>{value ?? "-"}</strong>
        <small>{hint}</small>
      </div>
    </article>
  );
}

export default function ModerationStats({ stats, loading }) {
  return (
    <section className="am-stats">
      <StatCard
        tone="blue"
        title="Pending moderation"
        value={loading ? "..." : stats?.totalPending ?? 0}
        hint="Sessions waiting in review"
      />
      <StatCard
        tone="red"
        title="High-risk sessions"
        value={loading ? "..." : stats?.highRisk ?? 0}
        hint="L0/L1 need review now"
      />
      <StatCard
        tone="green"
        title="Reviewed today"
        value={loading ? "..." : stats?.reviewedToday ?? 0}
        hint="Approved, rejected, or edited"
      />
      <StatCard
        tone="amber"
        title="Need improvement"
        value={loading ? "..." : stats?.needImprovement ?? 0}
        hint="Moderator requested changes"
      />
    </section>
  );
}
