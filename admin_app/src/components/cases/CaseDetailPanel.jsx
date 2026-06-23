import { createPortal } from "react-dom";
import { LoadingState, ErrorState } from "../shared/States.jsx";
import { fmtDateTime } from "../../ui.jsx";
import { CasePriorityBadge, CaseRiskBadge, CaseStatusBadge } from "./CaseBadges.jsx";
import { CaseUserInfo, CaseSignalList, CaseActionList, CaseTimeline, CaseNotes } from "./CaseDetailSections.jsx";

function SourceContext({ item }) {
  const source = item.source || {};
  return <section className="case-detail-section"><h3>Detection source</h3>
    {item.source_type === "screening" ? <div className="source-box">
      <b>{source.screening_type || "Screening"}</b><p>Score: {source.score ?? "—"}</p>
      <CaseRiskBadge value={source.risk_level || item.risk_level} />
    </div> : item.source_type === "ai_message" ? <div className="source-box">
      <b>Source message</b><p>{source.content || source.content_masked || "Content not authorized for display by the API."}</p>
      <small>{fmtDateTime(source.created_at)} {source.session_id && `· Session ${source.session_id}`}</small>
    </div> : <div className="source-box"><b>Manually created case</b><p>{item.detected_signal_summary || "—"}</p></div>}
  </section>;
}

export default function CaseDetailPanel({
  open, detail, history, loading, error, busy, onClose, onAction, onProfile,
}) {
  if (!open) return null;
  const overdue = detail?.sla_due_at && new Date(detail.sla_due_at) < new Date() && detail.status !== "closed";
  return createPortal(<>
    <button className="drawer-scrim" onClick={onClose} aria-label="Close details" />
    <aside className="case-drawer">
    <div className="case-drawer-head"><div>{detail && <><div className="eyebrow">CASE DETAIL</div>
      <h2>{detail.case_code}</h2></>}</div>
      <div className="drawer-head-actions">{detail && <CasePriorityBadge value={detail.priority} />}
        <button className="icon-button" onClick={onClose}>×</button></div></div>
    {loading ? <LoadingState label="Loading case details…" /> :
      error ? <ErrorState message={error.message} forbidden={error.status === 403} /> :
      !detail ? <ErrorState message="Case not found." /> : <>
        <div className="case-drawer-actions">
          {detail.status === "new" && <button className="btn" disabled={busy} onClick={() => onAction("view")}>Mark as viewed</button>}
          {detail.status !== "closed" && <><button className="btn primary" disabled={busy} onClick={() => onAction("assign")}>Assign</button>
            <button className="btn red-soft" disabled={busy} onClick={() => onAction("escalate")}>Escalate</button>
            <button className="btn" disabled={busy} onClick={() => onAction("close")}>Close case</button></>}
          {detail.status === "closed" && <button className="btn primary" disabled={busy} onClick={() => onAction("reopen")}>Reopen case</button>}
          <button className="btn" disabled={busy} onClick={() => onAction("note")}>+ Note</button>
        </div>
        <div className="case-drawer-scroll">
          <div className="case-overview-strip"><CaseRiskBadge value={detail.risk_level} />
            <CaseStatusBadge value={detail.status} /><span>AI confidence <b>{detail.ai_confidence != null ? `${Math.round(detail.ai_confidence * 100)}%` : "—"}</b></span>
            <span className={overdue ? "overdue" : ""}>SLA <b>{fmtDateTime(detail.sla_due_at)}</b></span></div>
          {overdue && <div className="banner crisis">This case is past its SLA and needs priority handling.</div>}
          <CaseUserInfo user={detail.user} onProfile={() => onProfile?.(detail.user?.id)} />
          <SourceContext item={detail} />
          <CaseSignalList signals={detail.signals} />
          <CaseActionList actions={detail.actions} />
          <CaseTimeline history={history} />
          <CaseNotes notes={detail.notes} onAdd={() => onAction("note")} />
          {!!detail.attachments?.length && <section className="case-detail-section"><h3>Attachments</h3>
            {detail.attachments.map(file => <div className="attachment-row" key={file.id}>
              <span>📎</span><div><b>{file.file_name || "Encrypted file"}</b><small>{file.mime_type} · {file.size_bytes} bytes</small></div>
            </div>)}</section>}
        </div>
      </>}
  </aside>
  </>, document.body);
}
