import { fmtDateTime } from "../../ui.jsx";

function RecentTable({ title, rows, columns, onViewAll, empty = "No data" }) {
  return (
    <section className="panel dashboard-table-card">
      <div className="panel-head"><div className="panel-title">{title}</div>
        <button className="text-button" onClick={onViewAll}>View all →</button></div>
      {!rows.length ? <div className="compact-empty">{empty}</div> : (
        <div className="table-scroll"><table className="table compact-table">
          <thead><tr>{columns.map((col) => <th key={col.key}>{col.label}</th>)}</tr></thead>
          <tbody>{rows.slice(0, 6).map((row, index) => (
            <tr key={row.id || index}>{columns.map((col) => (
              <td key={col.key}>{col.render ? col.render(row) : row[col.key] ?? "—"}</td>
            ))}</tr>
          ))}</tbody>
        </table></div>
      )}
    </section>
  );
}

const risk = (row) => <span className={`case-badge risk-${(row.risk_level || "L3").toLowerCase()}`}>{row.risk_level || "—"}</span>;
const time = (row) => fmtDateTime(row.created_at);

export function RecentCasesTable({ rows, onViewAll }) {
  return <RecentTable title="Recent risk cases" rows={rows} onViewAll={onViewAll}
    columns={[{ key: "case_code", label: "Case code" }, { key: "user_masked", label: "User" },
      { key: "risk", label: "Risk", render: risk }, { key: "time", label: "Time", render: time }]} />;
}
export function RecentScreeningsTable({ rows, onViewAll }) {
  return <RecentTable title="Recent screenings" rows={rows} onViewAll={onViewAll}
    columns={[{ key: "user_masked", label: "User" }, { key: "screening_type", label: "Type" },
      { key: "risk", label: "Risk", render: risk }, { key: "time", label: "Time", render: time }]} />;
}
export function PendingModerationsTable({ rows, onViewAll }) {
  return <RecentTable title="AI pending moderation" rows={rows} onViewAll={onViewAll}
    columns={[{ key: "queue_code", label: "Code" }, { key: "user_masked", label: "User" },
      { key: "risk", label: "Risk", render: risk }, { key: "status", label: "Status" }]} />;
}
export function RecentActivities({ rows, onViewAll }) {
  return <RecentTable title="Recent activity" rows={rows} onViewAll={onViewAll}
    columns={[{ key: "actor_name", label: "Actor" }, { key: "action", label: "Action" },
      { key: "module", label: "Module" }, { key: "time", label: "Time", render: time }]} />;
}
