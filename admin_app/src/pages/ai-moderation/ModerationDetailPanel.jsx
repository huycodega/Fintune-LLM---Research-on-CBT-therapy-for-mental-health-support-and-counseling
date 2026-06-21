import { useEffect, useState } from "react";
import { Avatar, fmtDateTime } from "../../ui.jsx";
import { api } from "../../api.js";
import { CHECKLIST_ITEMS } from "./aiModeration.types.js";
import RiskLevelBadge from "./RiskLevelBadge.jsx";

/* "From your library" recommendation editor — lets the moderator swap the
   lessons/resources attached to the reply. Parsed line-by-line and matched by
   exact title (footer order), identical to the user app's parser. */
const REC_MARKER = "From your library";
const REC_LINE_RE = /^\s*-\s*(lesson|resource)\s*:\s*(.+?)\s*(?:\(([^)]*)\)|\[([^\]]*)\])?\s*$/i;

function parseFooter(text, library) {
  const t = text || "";
  const i = t.indexOf(REC_MARKER);
  const body = i === -1 ? t : t.slice(0, i).trimEnd();
  const footer = i === -1 ? "" : t.slice(i);
  const recs = [];
  for (const line of footer.split("\n")) {
    const m = line.match(REC_LINE_RE);
    if (!m) continue;
    const kind = m[1].toLowerCase();
    const title = m[2].trim();
    const found = (library || []).find((it) => it.kind === kind && it.title &&
      it.title.trim().toLowerCase() === title.toLowerCase());
    if (found && !recs.some((r) => r.kind === found.kind && r.id === found.id)) recs.push(found);
  }
  return { body, recs };
}
function recLine(r) {
  return r.kind === "lesson"
    ? `- Lesson: ${r.title}${r.duration ? ` (${r.duration})` : ""}`
    : `- Resource: ${r.title}${r.type ? ` [${r.type}]` : ""}`;
}
function buildReply(body, recs) {
  if (!recs.length) return body;
  return body.trimEnd() + "\n\n" + REC_MARKER + ", these might help:\n"
    + recs.map(recLine).join("\n");
}

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
  const [library, setLibrary] = useState([]);

  useEffect(() => {
    setReason("");
    setEditedResponse(currentResponse || "");
    setNote("");
  }, [mode, currentResponse]);

  // Load the published library so recommendations are swappable.
  useEffect(() => {
    if (mode !== "edit") return;
    Promise.all([api.lessons().catch(() => ({})), api.resources().catch(() => ({}))])
      .then(([L, R]) => {
        setLibrary([
          ...(L.lessons || []).filter((l) => l.status === "published")
            .map((l) => ({ kind: "lesson", id: l.id, title: l.title, duration: l.duration })),
          ...(R.resources || []).filter((r) => r.status !== "draft")
            .map((r) => ({ kind: "resource", id: r.id, title: r.title, type: r.type })),
        ]);
      });
  }, [mode]);

  const { body: replyBody, recs } = parseFooter(editedResponse, library);
  function removeRec(item) {
    setEditedResponse(buildReply(replyBody, recs.filter((r) => !(r.kind === item.kind && r.id === item.id))));
  }
  function addRec(item) {
    if (!item || recs.some((r) => r.kind === item.kind && r.id === item.id)) return;
    setEditedResponse(buildReply(replyBody, [...recs, item]));
  }

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

          {library.length > 0 && (
            <div className="rec-editor">
              <span className="am-rec-label">Recommended materials (sent with the reply)</span>
              <div className="rec-chips">
                {recs.map((r) => (
                  <span key={r.kind + r.id} className="rec-chip">
                    <span>{r.kind === "lesson" ? "📘" : "📗"}</span>
                    {r.title}
                    <button type="button" className="rec-chip-x" onClick={() => removeRec(r)} aria-label="Remove">✕</button>
                  </span>
                ))}
                {recs.length === 0 && <span className="rec-empty">No materials attached.</span>}
              </div>
              <select className="la-input" value=""
                      onChange={(e) => { addRec(library.find((x) => x.kind + x.id === e.target.value)); e.target.value = ""; }}>
                <option value="">＋ Add a lesson / resource…</option>
                {library
                  .filter((it) => !recs.some((r) => r.kind === it.kind && r.id === it.id))
                  .map((it) => (
                    <option key={it.kind + it.id} value={it.kind + it.id}>
                      {it.kind === "lesson" ? "Lesson" : "Resource"}: {it.title}
                    </option>
                  ))}
              </select>
              <p className="rec-hint">Edits are sent to the patient when you Submit.</p>
            </div>
          )}

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
