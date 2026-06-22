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

function ReviewEditor({ detail, busy, onApprove, onReject, onEditResponse, onNeedImprovement }) {
  const drafts = detail.drafts || [];
  const [idx, setIdx] = useState(0);
  const [editText, setEditText] = useState("");
  const [note, setNote] = useState("");
  const [library, setLibrary] = useState([]);
  const [reasonMode, setReasonMode] = useState(null);   // "reject" | "improve"
  const [reason, setReason] = useState("");

  // Reset when a different session is opened.
  useEffect(() => {
    setIdx(0);
    setEditText(drafts[0]?.response ?? detail.aiResponse ?? "");
    setNote(""); setReasonMode(null); setReason("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [detail.id]);

  // Load the published library so recommendations are swappable.
  useEffect(() => {
    Promise.all([api.lessons().catch(() => ({})), api.resources().catch(() => ({}))])
      .then(([L, R]) => setLibrary([
        ...(L.lessons || []).filter((l) => l.status === "published")
          .map((l) => ({ kind: "lesson", id: l.id, title: l.title, duration: l.duration })),
        ...(R.resources || []).filter((r) => r.status !== "draft")
          .map((r) => ({ kind: "resource", id: r.id, title: r.title, type: r.type })),
      ]));
  }, []);

  function selectDraft(i) { setIdx(i); setEditText(drafts[i]?.response ?? ""); }

  const { body: replyBody, recs } = parseFooter(editText, library);
  function removeRec(item) {
    setEditText(buildReply(replyBody, recs.filter((r) => !(r.kind === item.kind && r.id === item.id))));
  }
  function addRec(item) {
    if (!item || recs.some((r) => r.kind === item.kind && r.id === item.id)) return;
    setEditText(buildReply(replyBody, [...recs, item]));
  }

  const original = drafts[idx]?.response ?? detail.aiResponse ?? "";
  const changed = editText.trim() !== (original || "").trim();

  return (
    <section className="am-detail-card am-actions-card">
      <h3>Review &amp; respond</h3>

      {drafts.length > 0 && (
        <div className="am-drafts">
          {drafts.map((d, i) => (
            <button type="button" key={d.id || i}
                    className={`am-draft-card ${i === idx ? "sel" : ""}`}
                    onClick={() => selectDraft(i)}>
              <div className="am-draft-meta">
                <b>{d.technique || `Option ${i + 1}`}</b>
                {d.preflightPass === false && <span className="am-draft-warn">⚠ preflight</span>}
                {i === idx && <span className="am-draft-sel">✓ selected</span>}
              </div>
              <p className="am-draft-resp">{d.response}</p>
            </button>
          ))}
        </div>
      )}

      <label className="am-field">
        <span>Response to patient {drafts.length > 0 ? `(option ${idx + 1})` : ""}</span>
        <textarea rows={5} value={editText} onChange={(e) => setEditText(e.target.value)} />
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
        </div>
      )}

      <label className="am-field">
        <span>Moderator note (optional)</span>
        <textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} />
      </label>

      <div className="am-action-grid">
        {/* When the moderator has edited the text or its recommendations, the
            primary button SENDS THOSE EDITS (what-you-see-is-what-the-user-
            gets). Only a pristine draft uses the fast approve-as-is path. */}
        <button type="button" className="am-primary-btn" disabled={busy}
                onClick={() => changed
                  ? onEditResponse(editText, note || "Approved with edits")
                  : onApprove(drafts[idx]?.idx)}>
          {changed ? "Approve with edits ✎" : `Approve option ${idx + 1}`}
        </button>
        <button type="button" className="am-edit-btn" disabled={busy || !changed}
                onClick={() => onEditResponse(editText, note || "Edited by moderator")}>
          Send edited reply{changed ? " ✎" : ""}
        </button>
        <button type="button" className="am-danger-btn" disabled={busy} onClick={() => setReasonMode("reject")}>Reject</button>
        <button type="button" className="am-warning-btn" disabled={busy} onClick={() => setReasonMode("improve")}>Need improvement</button>
      </div>

      {reasonMode && (
        <div className="am-action-editor">
          <div className="am-action-editor-head">
            <strong>{reasonMode === "reject" ? "Reject session" : "Mark as Need Improvement"}</strong>
            <button type="button" onClick={() => setReasonMode(null)}>Close</button>
          </div>
          <label>
            <span>{reasonMode === "reject" ? "Reason" : "What needs improvement?"}</span>
            <textarea rows={3} value={reason} onChange={(e) => setReason(e.target.value)} required />
          </label>
          <div className="am-action-editor-actions">
            <button type="button" className="am-ghost-btn" onClick={() => setReasonMode(null)} disabled={busy}>Cancel</button>
            <button type="button" className="am-primary-btn" disabled={busy}
                    onClick={() => { (reasonMode === "reject" ? onReject : onNeedImprovement)(reason); setReasonMode(null); }}>
              {busy ? "Saving..." : "Submit"}
            </button>
          </div>
        </div>
      )}
    </section>
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

      <ReviewEditor
        detail={detail}
        busy={busy}
        onApprove={onApprove}
        onReject={onReject}
        onEditResponse={onEditResponse}
        onNeedImprovement={onNeedImprovement}
      />
    </aside>
  );
}
