import { LoadingState, ErrorState } from "../shared/States.jsx";
import { fmtDateTime } from "../../ui.jsx";
import { CasePriorityBadge, CaseRiskBadge, CaseStatusBadge } from "./CaseBadges.jsx";
import { CaseUserInfo, CaseSignalList, CaseActionList, CaseTimeline, CaseNotes } from "./CaseDetailSections.jsx";

function SourceContext({ item }) {
  const source = item.source || {};
  return <section className="case-detail-section"><h3>Nguồn phát hiện</h3>
    {item.source_type === "screening" ? <div className="source-box">
      <b>{source.screening_type || "Screening"}</b><p>Điểm: {source.score ?? "—"}</p>
      <CaseRiskBadge value={source.risk_level || item.risk_level} />
    </div> : item.source_type === "ai_message" ? <div className="source-box">
      <b>Tin nhắn nguồn</b><p>{source.content || source.content_masked || "Nội dung không được API cấp quyền hiển thị."}</p>
      <small>{fmtDateTime(source.created_at)} {source.session_id && `· Session ${source.session_id}`}</small>
    </div> : <div className="source-box"><b>Ca tạo thủ công</b><p>{item.detected_signal_summary || "—"}</p></div>}
  </section>;
}

export default function CaseDetailPanel({
  open, detail, history, loading, error, busy, onClose, onAction, onProfile,
}) {
  if (!open) return null;
  const overdue = detail?.sla_due_at && new Date(detail.sla_due_at) < new Date() && detail.status !== "closed";
  return <aside className="case-drawer">
    <div className="case-drawer-head"><div>{detail && <><div className="eyebrow">CASE DETAIL</div>
      <h2>{detail.case_code}</h2></>}</div>
      <div className="drawer-head-actions">{detail && <CasePriorityBadge value={detail.priority} />}
        <button className="icon-button" onClick={onClose}>×</button></div></div>
    {loading ? <LoadingState label="Đang tải chi tiết ca…" /> :
      error ? <ErrorState message={error.message} forbidden={error.status === 403} /> :
      !detail ? <ErrorState message="Không tìm thấy Case." /> : <>
        <div className="case-drawer-actions">
          {detail.status === "new" && <button className="btn" disabled={busy} onClick={() => onAction("view")}>Đánh dấu đã xem</button>}
          {detail.status !== "closed" && <><button className="btn primary" disabled={busy} onClick={() => onAction("assign")}>Phân công</button>
            <button className="btn red-soft" disabled={busy} onClick={() => onAction("escalate")}>Chuyển cấp</button>
            <button className="btn" disabled={busy} onClick={() => onAction("close")}>Đóng ca</button></>}
          {detail.status === "closed" && <button className="btn primary" disabled={busy} onClick={() => onAction("reopen")}>Mở lại ca</button>}
          <button className="btn" disabled={busy} onClick={() => onAction("note")}>+ Ghi chú</button>
        </div>
        <div className="case-drawer-scroll">
          <div className="case-overview-strip"><CaseRiskBadge value={detail.risk_level} />
            <CaseStatusBadge value={detail.status} /><span>AI confidence <b>{detail.ai_confidence != null ? `${Math.round(detail.ai_confidence * 100)}%` : "—"}</b></span>
            <span className={overdue ? "overdue" : ""}>SLA <b>{fmtDateTime(detail.sla_due_at)}</b></span></div>
          {overdue && <div className="banner crisis">Ca đã quá hạn SLA và cần được ưu tiên xử lý.</div>}
          <CaseUserInfo user={detail.user} onProfile={() => onProfile?.(detail.user?.id)} />
          <SourceContext item={detail} />
          <CaseSignalList signals={detail.signals} />
          <CaseActionList actions={detail.actions} />
          <CaseTimeline history={history} />
          <CaseNotes notes={detail.notes} onAdd={() => onAction("note")} />
          {!!detail.attachments?.length && <section className="case-detail-section"><h3>Tệp đính kèm</h3>
            {detail.attachments.map(file => <div className="attachment-row" key={file.id}>
              <span>📎</span><div><b>{file.file_name || "Tệp đã mã hóa"}</b><small>{file.mime_type} · {file.size_bytes} bytes</small></div>
            </div>)}</section>}
        </div>
      </>}
  </aside>;
}
