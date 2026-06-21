import { Avatar, fmtDateTime } from "../../ui.jsx";
import { CaseRiskBadge, CaseStatusBadge } from "./CaseBadges.jsx";

export function CaseUserInfo({ user = {}, onProfile }) {
  return <section className="case-detail-section"><h3>User information</h3>
    <div className="case-user-card"><Avatar name={user.display_name || user.full_name || "U"} size={44} />
      <div><b>{user.full_name || user.display_name || "Anonymized user"}</b>
        <small>{[user.age && `${user.age} yrs`, user.gender].filter(Boolean).join(" · ") || "—"}</small>
        <small>{user.email || user.email_masked || "—"} · {user.phone || user.phone_masked || "—"}</small></div>
      <button className="btn sm" onClick={onProfile}>Profile</button></div>
  </section>;
}

export function CaseSignalList({ signals = [] }) {
  return <section className="case-detail-section"><h3>Detected signals</h3>
    {!signals.length ? <p className="muted">No signals.</p> : <div className="signal-list">{signals.map(signal =>
      <div className="signal-item" key={signal.id || signal.signal_code}>
        <div><b>{signal.signal_code}</b><small>{signal.category} · {signal.detected_by}</small></div>
        <CaseRiskBadge value={signal.risk_level} />
        <strong>{signal.confidence != null ? `${Math.round(signal.confidence * 100)}%` : "—"}</strong>
      </div>)}</div>}
  </section>;
}

export function CaseActionList({ actions = [] }) {
  return <section className="case-detail-section"><h3>Suggested actions</h3>
    {!actions.length ? <p className="muted">No actions yet.</p> : actions.map(action =>
      <div className="case-action" key={action.id}><span className="action-icon">✓</span>
        <div><b>{String(action.action_type).replaceAll("_", " ")}</b>
          <small>{action.due_at ? `Due ${fmtDateTime(action.due_at)}` : "No due date"}</small></div>
        <span className={`case-badge action-${action.status}`}>{action.status}</span></div>)}
  </section>;
}

export function CaseTimeline({ history = [] }) {
  return <section className="case-detail-section"><h3>Activity history</h3>
    {!history.length ? <p className="muted">No history.</p> : <div className="case-timeline">{history.map(event =>
      <div className="case-timeline-item" key={event.id}><span />
        <div><b>{String(event.event_type).replaceAll("_", " ")}</b>
          <small>{event.actor_name || "System"} · {fmtDateTime(event.created_at)}</small>
          {event.from_status && <div><CaseStatusBadge value={event.from_status} /> → <CaseStatusBadge value={event.to_status} /></div>}
        </div></div>)}</div>}
  </section>;
}

export function CaseNotes({ notes = [], onAdd }) {
  return <section className="case-detail-section"><div className="section-title-row"><h3>Note</h3>
    <button className="text-button" onClick={onAdd}>+ Add note</button></div>
    {!notes.length ? <p className="muted">No notes available to display.</p> : notes.map(note =>
      <article className="case-note" key={note.id}><div><b>{note.author_name || "Specialist"}</b>
        <time>{fmtDateTime(note.created_at)}</time></div><p>{note.content}</p></article>)}
  </section>;
}
