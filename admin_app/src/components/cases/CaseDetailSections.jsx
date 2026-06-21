import { Avatar, fmtDateTime } from "../../ui.jsx";
import { CaseRiskBadge, CaseStatusBadge } from "./CaseBadges.jsx";

export function CaseUserInfo({ user = {}, onProfile }) {
  return <section className="case-detail-section"><h3>Thông tin người dùng</h3>
    <div className="case-user-card"><Avatar name={user.display_name || user.full_name || "U"} size={44} />
      <div><b>{user.full_name || user.display_name || "Người dùng đã ẩn danh"}</b>
        <small>{[user.age && `${user.age} tuổi`, user.gender].filter(Boolean).join(" · ") || "—"}</small>
        <small>{user.email || user.email_masked || "—"} · {user.phone || user.phone_masked || "—"}</small></div>
      <button className="btn sm" onClick={onProfile}>Hồ sơ</button></div>
  </section>;
}

export function CaseSignalList({ signals = [] }) {
  return <section className="case-detail-section"><h3>Tín hiệu phát hiện</h3>
    {!signals.length ? <p className="muted">Chưa có signal.</p> : <div className="signal-list">{signals.map(signal =>
      <div className="signal-item" key={signal.id || signal.signal_code}>
        <div><b>{signal.signal_code}</b><small>{signal.category} · {signal.detected_by}</small></div>
        <CaseRiskBadge value={signal.risk_level} />
        <strong>{signal.confidence != null ? `${Math.round(signal.confidence * 100)}%` : "—"}</strong>
      </div>)}</div>}
  </section>;
}

export function CaseActionList({ actions = [] }) {
  return <section className="case-detail-section"><h3>Hành động đề xuất</h3>
    {!actions.length ? <p className="muted">Chưa có hành động.</p> : actions.map(action =>
      <div className="case-action" key={action.id}><span className="action-icon">✓</span>
        <div><b>{String(action.action_type).replaceAll("_", " ")}</b>
          <small>{action.due_at ? `Hạn ${fmtDateTime(action.due_at)}` : "Không có hạn"}</small></div>
        <span className={`case-badge action-${action.status}`}>{action.status}</span></div>)}
  </section>;
}

export function CaseTimeline({ history = [] }) {
  return <section className="case-detail-section"><h3>Lịch sử xử lý</h3>
    {!history.length ? <p className="muted">Chưa có lịch sử.</p> : <div className="case-timeline">{history.map(event =>
      <div className="case-timeline-item" key={event.id}><span />
        <div><b>{String(event.event_type).replaceAll("_", " ")}</b>
          <small>{event.actor_name || "System"} · {fmtDateTime(event.created_at)}</small>
          {event.from_status && <div><CaseStatusBadge value={event.from_status} /> → <CaseStatusBadge value={event.to_status} /></div>}
        </div></div>)}</div>}
  </section>;
}

export function CaseNotes({ notes = [], onAdd }) {
  return <section className="case-detail-section"><div className="section-title-row"><h3>Ghi chú</h3>
    <button className="text-button" onClick={onAdd}>+ Thêm ghi chú</button></div>
    {!notes.length ? <p className="muted">Chưa có ghi chú được phép hiển thị.</p> : notes.map(note =>
      <article className="case-note" key={note.id}><div><b>{note.author_name || "Chuyên viên"}</b>
        <time>{fmtDateTime(note.created_at)}</time></div><p>{note.content}</p></article>)}
  </section>;
}
