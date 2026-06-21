import DateRangePicker from "../shared/DateRangePicker.jsx";
import { EmptyState } from "../shared/States.jsx";
import { fmtDateTime } from "../../ui.jsx";
import { CasePriorityBadge, CaseRiskBadge, CaseStatusBadge } from "./CaseBadges.jsx";

export function CaseStatsCards({ stats = {} }) {
  const cards = [
    ["new", "📥", "Ca mới", "purple"], ["critical", "🚨", "Khẩn cấp", "red"],
    ["monitoring", "◉", "Đang theo dõi", "amber"], ["closed", "✓", "Đã đóng", "green"],
  ];
  return <div className="case-stats">{cards.map(([key, icon, label, color]) => (
    <article className="dashboard-kpi" key={key}><div className={`stat-icon ${color}`}>{icon}</div>
      <div className="dashboard-kpi-copy"><span>{label}</span><strong>{stats[key] ?? 0}</strong></div></article>
  ))}</div>;
}

export function CaseFilters({ value, specialists = [], onChange }) {
  const set = (key) => (event) => onChange({ ...value, [key]: event.target.value, page: 1 });
  return <div className="case-filters">
    <select className="select" value={value.priority} onChange={set("priority")}>
      <option value="">Tất cả priority</option><option value="critical">Critical</option>
      <option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option>
    </select>
    <select className="select" value={value.status} onChange={set("status")}>
      <option value="">Tất cả trạng thái</option>{["new","viewed","assigned","monitoring","escalated","closed"].map(
        item => <option key={item} value={item}>{item}</option>)}
    </select>
    <select className="select" value={value.specialist_id} onChange={set("specialist_id")}>
      <option value="">Tất cả chuyên viên</option>{specialists.map(item =>
        <option key={item.id} value={item.id}>{item.display_name}</option>)}
    </select>
    <select className="select" value={value.source_type} onChange={set("source_type")}>
      <option value="">Tất cả nguồn</option><option value="ai_message">AI Message</option>
      <option value="screening">Screening</option><option value="manual">Manual</option>
    </select>
    <DateRangePicker value={value} onChange={(range) => onChange({ ...value, ...range, page: 1 })} />
  </div>;
}

export function CaseTable({ rows, selectedId, onSelect }) {
  if (!rows.length) return <EmptyState title="Không có ca phù hợp"
    description="Thử thay đổi bộ lọc hoặc khoảng thời gian." />;
  return <div className="table-scroll"><table className="table case-table">
    <thead><tr><th><input type="checkbox" aria-label="Chọn tất cả" /></th><th>Mã ca</th>
      <th>Người dùng</th><th>Tín hiệu</th><th>Priority</th><th>Risk</th>
      <th>Thời gian</th><th>Trạng thái</th><th>Chuyên viên</th><th /></tr></thead>
    <tbody>{rows.map(item => <tr key={item.id} className={selectedId === item.id ? "selected" : ""}
      onClick={() => onSelect(item.id)}>
      <td onClick={event => event.stopPropagation()}><input type="checkbox" aria-label={`Chọn ${item.case_code}`} /></td>
      <td><b>{item.case_code}</b></td>
      <td><div className="masked-user"><b>{item.user?.display_name || item.user_masked || "Ẩn danh"}</b>
        <small>{item.user?.email_masked || item.email_masked || "Thông tin đã che"}</small></div></td>
      <td className="signal-cell">{item.detected_signal_summary || "—"}</td>
      <td><CasePriorityBadge value={item.priority} /></td><td><CaseRiskBadge value={item.risk_level} /></td>
      <td className="nowrap">{fmtDateTime(item.created_at)}</td><td><CaseStatusBadge value={item.status} /></td>
      <td>{item.assigned_specialist?.display_name || item.specialist_name || "Chưa phân công"}</td>
      <td><button className="icon-button" aria-label="Xem chi tiết">→</button></td>
    </tr>)}</tbody>
  </table></div>;
}
