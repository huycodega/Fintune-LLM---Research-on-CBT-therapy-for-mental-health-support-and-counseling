import { fmtDateTime } from "../../ui.jsx";

function RecentTable({ title, rows, columns, onViewAll, empty = "Chưa có dữ liệu" }) {
  return (
    <section className="panel dashboard-table-card">
      <div className="panel-head"><div className="panel-title">{title}</div>
        <button className="text-button" onClick={onViewAll}>Xem tất cả →</button></div>
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
  return <RecentTable title="Ca rủi ro gần đây" rows={rows} onViewAll={onViewAll}
    columns={[{ key: "case_code", label: "Mã ca" }, { key: "user_masked", label: "Người dùng" },
      { key: "risk", label: "Risk", render: risk }, { key: "time", label: "Thời gian", render: time }]} />;
}
export function RecentScreeningsTable({ rows, onViewAll }) {
  return <RecentTable title="Sàng lọc gần đây" rows={rows} onViewAll={onViewAll}
    columns={[{ key: "user_masked", label: "Người dùng" }, { key: "screening_type", label: "Loại" },
      { key: "risk", label: "Risk", render: risk }, { key: "time", label: "Thời gian", render: time }]} />;
}
export function PendingModerationsTable({ rows, onViewAll }) {
  return <RecentTable title="AI chờ kiểm duyệt" rows={rows} onViewAll={onViewAll}
    columns={[{ key: "queue_code", label: "Mã" }, { key: "user_masked", label: "Người dùng" },
      { key: "risk", label: "Risk", render: risk }, { key: "status", label: "Trạng thái" }]} />;
}
export function RecentActivities({ rows, onViewAll }) {
  return <RecentTable title="Hoạt động gần đây" rows={rows} onViewAll={onViewAll}
    columns={[{ key: "actor_name", label: "Người thực hiện" }, { key: "action", label: "Hành động" },
      { key: "module", label: "Module" }, { key: "time", label: "Thời gian", render: time }]} />;
}
