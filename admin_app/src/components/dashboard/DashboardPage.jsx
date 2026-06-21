import { useCallback, useEffect, useState } from "react";
import { dashboardApi } from "../../services/dashboardApi.js";
import { LoadingState, ErrorState } from "../shared/States.jsx";
import DateRangePicker from "../shared/DateRangePicker.jsx";
import DashboardSummaryCards, { AttentionRequired } from "./DashboardSummaryCards.jsx";
import DashboardCharts from "./DashboardCharts.jsx";
import {
  RecentCasesTable, RecentScreeningsTable, PendingModerationsTable, RecentActivities,
} from "./DashboardTables.jsx";

const initialRange = { from: "", to: "" };
const list = (value) => value?.items || value || [];

export default function DashboardPage({ onNav }) {
  const [range, setRange] = useState(initialRange);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const params = { ...range, timezone: "Asia/Bangkok" };
      const [summary, charts, cases, screenings, moderations, activities] = await Promise.all([
        dashboardApi.summary({ timezone: params.timezone, active_days: 30 }),
        dashboardApi.charts({ ...params, granularity: "day" }),
        dashboardApi.recentCases({ limit: 6 }), dashboardApi.recentScreenings({ limit: 6 }),
        dashboardApi.pendingModerations({ limit: 6 }), dashboardApi.recentActivities({ limit: 6 }),
      ]);
      setData({ summary, charts, cases: list(cases), screenings: list(screenings),
        moderations: list(moderations), activities: list(activities) });
    } catch (err) { setError(err); }
  }, [range]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="module-page">
      <div className="module-toolbar">
        <div><h1>Overview</h1><p>Monitor the operational health of MindCare AI</p></div>
        <div className="module-toolbar-actions"><DateRangePicker value={range} onChange={setRange} />
          <button className="btn" onClick={load}>↻ Refresh</button></div>
      </div>
      {error ? <ErrorState message={error.message} forbidden={error.status === 403} onRetry={load} />
        : !data ? <LoadingState label="Building dashboard…" /> : <>
          <DashboardSummaryCards summary={data.summary} />
          <AttentionRequired items={[...data.cases, ...data.moderations, ...data.screenings]
            .filter(item => ["L0", "L1"].includes(item.risk_level) &&
              (item.overdue || item.status === "pending" || !item.assigned_specialist))
            .map(item => ({ ...item, label: item.case_code || item.queue_code || item.screening_type || "High-risk signal",
              user_masked: item.user_masked || item.user?.display_name }))}
            onNavigate={() => onNav("cases")} />
          <DashboardCharts charts={data.charts} />
          <div className="dashboard-tables">
            <RecentCasesTable rows={data.cases} onViewAll={() => onNav("cases")} />
            <RecentScreeningsTable rows={data.screenings} onViewAll={() => onNav("users")} />
            <PendingModerationsTable rows={data.moderations} onViewAll={() => onNav("moderation")} />
            <RecentActivities rows={data.activities} />
          </div>
        </>}
    </div>
  );
}
