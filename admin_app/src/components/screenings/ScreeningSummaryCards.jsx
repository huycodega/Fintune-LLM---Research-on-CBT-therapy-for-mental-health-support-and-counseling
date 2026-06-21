import StatisticCard from "../shared/StatisticCard.jsx";
export default function ScreeningSummaryCards({ summary = {}, loading }) {
  const value = item => loading ? "..." : item;
  return (
    <section className="sm-stats">
      <StatisticCard icon="▣" tone="blue" title="Today's Screenings" value={value(summary.today ?? 0)} hint="Screenings submitted today" />
      <StatisticCard icon="↗" tone="green" title="Completion Rate" value={value((summary.completion_rate ?? 0) + "%")} hint="Current completion ratio" />
      <StatisticCard icon="!" tone="red" title="High Risk" value={value(summary.high_risk ?? 0)} hint={(summary.high_risk_percent ?? 0) + "% of screenings"} />
      <StatisticCard icon="◉" tone="amber" title="Average Score" value={value(summary.average_score ?? 0)} hint="Across current screening records" />
    </section>
  );
}
