import { useEffect, useState } from "react";
import { Avatar, fmtDateTime } from "../../ui.jsx";
import { CHECKLIST_ITEMS } from "./aiModeration.types.js";
import RiskLevelBadge from "./RiskLevelBadge.jsx";

function Checklist({ checklist = {} }) {
  return (
    <div className="am-checklist">
      {CHECKLIST_ITEMS.map((item) => (
        <label key={item.key} className={checklist[item.key] ? "checked" : ""}>
          <input type="checkbox" checked={!!checklist[item.key]} readOnly />
          <span>{item.label}</span>
        </label>
      ))}
    </div>
  );
}

function ActionEditor({ mode, currentResponse, busy, onCancel, onSubmit }) {
  const [reason, setReason] = useState("");
  const [editedResponse, setEditedResponse] = useState(currentResponse || "");
  const [note, setNote] = useState("");

  useEffect(() => {
    setReason("");
    setEditedResponse(currentResponse || "");
    setNote("");
  }, [mode, currentResponse]);

  if (!mode) return null;

  const title = {
    reject: "Reject session",
    edit: "Edit AI response",
    improve: "Mark as Need Improvement",
  }[mode];

  function submit(event) {
    event.preventDefault();
    if (mode === "edit") onSubmit({ editedResponse, note });
    else onSubmit({ reason });
  }

  return (
    <form className="am-action-editor" onSubmit={submit}>
      <div className="am-action-editor-head">
        <strong>{title}</strong>
        <button type="button" onClick={onCancel}>Close</button>
      </div>

      {mode === "edit" ? (
        <>
          <label>
            <span>Edited Response</span>
            <textarea rows={5} value={editedResponse} onChange={(event) => setEditedResponse(event.target.value)} required />
          </label>
          <label>
            <span>Moderator note</span>
            <textarea rows={3} value={note} onChange={(event) => setNote(event.target.value)} required />
          </label>
        </>
      ) : (
        <label>
          <span>Reason</span>
          <textarea rows={4} value={reason} onChange={(event) => setReason(event.target.value)} required />
        </label>
      )}

      <div className="am-action-editor-actions">
        <button type="button" className="am-ghost-btn" onClick={onCancel} disabled={busy}>Cancel</button>
        <button type="submit" className="am-primary-btn" disabled={busy}>{busy ? "Saving..." : "Submit"}</button>
      </div>
    </form>
  );
}

export default function ModerationDetailPanel({
  detail,
  loading,
  error,
  busy,
  onApprove,
  onReject,
  onEditResponse,
  onNeedImprovement,
}) {
  const [mode, setMode] = useState(null);

  useEffect(() => setMode(null), [detail?.id]);

  async function submitAction(payload) {
    if (mode === "reject") await onReject(payload.reason);
    if (mode === "edit") await onEditResponse(payload.editedResponse, payload.note);
    if (mode === "improve") await onNeedImprovement(payload.reason);
    setMode(null);
  }

  if (loading) {
    return <aside className="am-detail-panel"><div className="am-state">Loading session details...</div></aside>;
  }

  if (error) {
    return <aside className="am-detail-panel"><div className="am-state error">{error}</div></aside>;
  }

  if (!detail) {
    return <aside className="am-detail-panel"><div className="am-state">Select a session to view moderation details.</div></aside>;
  }

  const user = detail.user || {};
  const fullName = user.fullName || detail.userName || user.username || "Unknown user";
  const userMeta = user.userCode || user.email || detail.userCode || detail.userEmail || detail.userId;

  return (
    <aside className="am-detail-panel">
      <section className="am-detail-card">
        <div className="am-detail-title">
          <div>
            <span>Session ID</span>
            <h2>{detail.sessionId}</h2>
          </div>
          <RiskLevelBadge level={detail.riskLevel} />
        </div>

        <div className="am-user-profile">
          <Avatar name={fullName} size={44} className="am-avatar" />
          <div>
            <strong>{fullName}</strong>
            <small>{userMeta}</small>
          </div>
        </div>

        <div className="am-info-grid">
          <span>Created At</span><strong>{fmtDateTime(detail.createdAt)}</strong>
          <span>Reviewed At</span><strong>{fmtDateTime(detail.reviewedAt)}</strong>
          <span>Reviewed By</span><strong>{detail.reviewedBy || "-"}</strong>
        </div>
      </section>

      <section className="am-detail-card">
        <h3>User content</h3>
        <p className="am-copy-block">{detail.userContent}</p>
      </section>

      <section className="am-detail-card">
        <h3>AI response</h3>
        <p className="am-copy-block">{detail.aiResponse}</p>
        {detail.editedResponse && (
          <>
            <h3>Edited Response</h3>
            <p className="am-copy-block edited">{detail.editedResponse}</p>
          </>
        )}
      </section>

      <section className="am-detail-card">
        <h3>Moderation checklist</h3>
        <Checklist checklist={detail.checklist} />
      </section>

      <section className="am-detail-card">
        <h3>AI note / Moderator note</h3>
        <div className="am-note-stack">
          <p><b>AI note</b>{detail.aiNote || "-"}</p>
          <p><b>Moderator note</b>{detail.moderatorNote || "-"}</p>
        </div>
      </section>

      {(detail.drafts || []).length > 0 && (
        <section className="am-detail-card">
          <h3>Draft responses</h3>
          <div className="am-history">
            {detail.drafts.map((draft) => (
              <div className="am-history-item" key={draft.id || draft.idx}>
                <strong>{draft.technique || `Draft ${draft.idx + 1}`}</strong>
                <span>{draft.preflightPass === false ? "Preflight failed" : "Preflight passed"}</span>
                {draft.rationale && <p>{draft.rationale}</p>}
                {draft.plan && <p>{draft.plan}</p>}
                <p>{draft.response}</p>
              </div>
            ))}
          </div>
        </section>
      )}

      {detail.agentTrace && (
        <section className="am-detail-card">
          <h3>Agent trace</h3>
          <pre className="am-copy-block">{JSON.stringify(detail.agentTrace, null, 2)}</pre>
        </section>
      )}

      {(detail.retrievedIds || []).length > 0 && (
        <section className="am-detail-card">
          <h3>Retrieved context IDs</h3>
          <p className="am-copy-block">{detail.retrievedIds.join(", ")}</p>
        </section>
      )}

      <section className="am-detail-card">
        <h3>Moderation history</h3>
        <div className="am-history">
          {(detail.histories || []).map((item) => (
            <div className="am-history-item" key={item.id}>
              <strong>{item.action}</strong>
              <span>{fmtDateTime(item.createdAt)}</span>
              <p>{item.note || "No note"}</p>
            </div>
          ))}
          {!(detail.histories || []).length && <p className="am-muted">No moderation history.</p>}
        </div>
      </section>

      <section className="am-detail-card am-actions-card">
        <div className="am-action-grid">
          <button type="button" className="am-primary-btn" disabled={busy} onClick={onApprove}>Approve</button>
          <button type="button" className="am-ghost-btn" disabled={busy} onClick={() => setMode("edit")}>Edit Response</button>
          <button type="button" className="am-danger-btn" disabled={busy} onClick={() => setMode("reject")}>Reject</button>
          <button type="button" className="am-warning-btn" disabled={busy} onClick={() => setMode("improve")}>Mark as Need Improvement</button>
        </div>

        <ActionEditor
          mode={mode}
          currentResponse={detail.editedResponse || detail.aiResponse}
          busy={busy}
          onCancel={() => setMode(null)}
          onSubmit={submitAction}
        />
      </section>
    </aside>
  );
}
