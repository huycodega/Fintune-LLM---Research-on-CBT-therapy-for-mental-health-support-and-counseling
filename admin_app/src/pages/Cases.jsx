import { useState, useEffect } from "react";
import { api } from "../api.js";
import { Avatar, StatCard, Empty, displayName, timeAgo } from "../ui.jsx";
import AppShell from "../admin/AppShell.jsx";

const REC_MARKER = "From your library";

/* Split a reply into body + recommended library items, parsing the footer
   line-by-line and matching by EXACT title (kept in footer order) so the
   clinician's chips stay in sync with the user app's identical parser. */
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

export default function Cases({ onNav, onLogout }) {
  const [queue, setQueue] = useState([]);
  const [active, setActive] = useState(null);

  function refresh() {
    api.queue().then((r) => setQueue(r.queue || [])).catch(() => {});
  }
  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 8000);
    return () => clearInterval(t);
  }, []);

  const l1 = queue.filter((q) => q.triage_level === "L1").length;
  const l2 = queue.filter((q) => q.triage_level === "L2").length;

  return (
    <AppShell active="cases" onNav={onNav} onLogout={onLogout}
              title="Intervention Cases" subtitle="Human-in-the-loop review queue">
      {active ? (
        <ReviewPanel sid={active} onDone={() => { setActive(null); refresh(); }} />
      ) : (
    <>
      <div className="stat-row">
        <StatCard icon="cases" color="purple" value={queue.length} label="Cases in queue" />
        <StatCard icon="alert" color="amber" value={l1} label="High priority (L1)" />
        <StatCard icon="message" color="blue" value={l2} label="Moderate (L2)" />
      </div>

      <div className="panel">
        <div className="panel-head"><div className="panel-title">Human-in-the-loop review queue</div></div>
        {queue.length === 0 ? (
          <Empty icon="🎉" text="No cases pending review. The queue is clear." />
        ) : (
          <table className="table">
            <thead>
              <tr><th>Priority</th><th>User</th><th>Message</th><th>Triage</th><th>Waiting</th><th></th></tr>
            </thead>
            <tbody>
              {queue.map((q) => (
                <tr key={q.session_id} onClick={() => setActive(q.session_id)}>
                  <td><span className={`pill ${q.priority === 1 ? "red" : "gray"}`}>
                    {q.priority === 1 ? "Urgent" : `P${q.priority ?? "—"}`}</span></td>
                  <td>
                    <div className="cell-user">
                      <Avatar name={q.username} />
                      <div className="cell-name">{displayName(q.username)}</div>
                    </div>
                  </td>
                  <td style={{ maxWidth: 320, color: "var(--ink-soft)" }}>
                    <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {q.user_input}
                    </div>
                  </td>
                  <td><span className={`pill ${q.triage_level}`}>{q.triage_level}</span></td>
                  <td style={{ color: "var(--ink-soft)" }}>{timeAgo(q.created_at)}</td>
                  <td><button className="btn sm primary">Review →</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
      )}
    </AppShell>
  );
}

function ReviewPanel({ sid, onDone }) {
  const [sess, setSess] = useState(null);
  const [idx, setIdx] = useState(0);
  const [editText, setEditText] = useState("");
  const [editTech, setEditTech] = useState("");
  const [busy, setBusy] = useState(false);
  const [library, setLibrary] = useState([]);

  useEffect(() => {
    api.adminSession(sid).then((s) => {
      setSess(s);
      if (s.drafts?.length) { setEditText(s.drafts[0].response); setEditTech(s.drafts[0].technique); }
    });
  }, [sid]);

  // Load the published library so recommendations are swappable.
  useEffect(() => {
    Promise.all([api.lessons().catch(() => ({})), api.resources().catch(() => ({}))])
      .then(([L, R]) => {
        setLibrary([
          ...(L.lessons || []).filter((l) => l.status === "published")
            .map((l) => ({ kind: "lesson", id: l.id, title: l.title, duration: l.duration })),
          ...(R.resources || []).filter((r) => r.status !== "draft")
            .map((r) => ({ kind: "resource", id: r.id, title: r.title, type: r.type })),
        ]);
      });
  }, []);

  const { body: replyBody, recs } = parseFooter(editText, library);
  function removeRec(item) {
    setEditText(buildReply(replyBody, recs.filter((r) => !(r.kind === item.kind && r.id === item.id))));
  }
  function addRec(item) {
    if (!item || recs.some((r) => r.kind === item.kind && r.id === item.id)) return;
    setEditText(buildReply(replyBody, [...recs, item]));
  }

  if (!sess) return <div className="loading">Loading case…</div>;
  const drafts = sess.drafts || [];
  const noDraft = drafts.length === 0;

  async function act(decision) {
    setBusy(true);
    try {
      // If the clinician changed the selected draft (e.g. swapped a recommended
      // lesson), "Approve" must carry those edits — otherwise the original draft
      // goes out and the change is lost. So a modified approve is sent as an edit.
      const draft = (!noDraft && drafts[idx]) ? drafts[idx] : null;
      const changed = draft
        ? (editText.trim() !== (draft.response || "").trim() || editTech !== (draft.technique || ""))
        : true;
      const effective = (decision === "approve" && changed) ? "edit" : decision;
      const payload = { decision: effective, chosen_idx: idx };
      if (effective === "edit") { payload.edited_response = editText; payload.edited_technique = editTech; }
      await api.review(sid, payload);
      onDone();
    } catch (e) { alert("Error: " + e.message); }
    finally { setBusy(false); }
  }

  return (
    <div className="split">
      <div className="panel">
        <div className="panel-head">
          <button className="btn sm" onClick={onDone}>← Back to queue</button>
          <div className="panel-tools">
            <span className={`pill ${sess.triage_level}`}>{sess.triage_level}</span>
          </div>
        </div>

        <div style={{ padding: 18 }}>
          <div className="banner info" style={{ marginBottom: 14 }}>
            <b>Patient message:</b><br />{sess.user_input}
          </div>

          {sess.analysis && (
            <div className="timeline-text" style={{ marginBottom: 14 }}>
              <b>Analysis</b> — emotion: {sess.analysis.emotion || "—"} · severity: {sess.analysis.severity || "—"} ·
              distortions: {sess.analysis.cognitive_distortions || "—"}
              {sess.analysis.agent_trace && <> · <span className="pill purple">agent ({sess.analysis.agent_trace.length} steps)</span></>}
            </div>
          )}

          {noDraft ? (
            <div className="banner crisis">
              Level <b>{sess.triage_level}</b> — no AI draft was generated. Write the reply directly
              below (sends as an edit) or reject to contact the patient out-of-band.
            </div>
          ) : (
            <>
              <div className="detail-section-title">AI drafts — not yet sent</div>
              {drafts.map((d, i) => (
                <div key={i} className={`draft-card ${i === idx ? "sel" : ""}`}
                     onClick={() => { setIdx(i); setEditText(d.response); setEditTech(d.technique); }}>
                  <div className="draft-meta">
                    <span className="pill gray">Option {i + 1}</span>
                    <span className="pill blue">{d.technique}</span>
                    {!d.preflight_pass && <span className="pill amber">⚠ preflight</span>}
                    {i === idx && <span className="pill green">✓ selected</span>}
                  </div>
                  <div className="draft-resp">{d.response}</div>
                  <div className="draft-clin">
                    <b>Rationale:</b> {d.rationale || "—"}<br />
                    <b>Plan:</b> {d.plan || "—"}
                  </div>
                </div>
              ))}
            </>
          )}

          <label className="field-label">Technique</label>
          <input className="input" style={{ width: "100%" }} value={editTech}
                 onChange={(e) => setEditTech(e.target.value)} />
          <label className="field-label">Message to patient</label>
          <textarea className="textarea" rows={4} value={editText}
                    onChange={(e) => setEditText(e.target.value)} />

          {library.length > 0 && (
            <div className="rec-editor">
              <label className="field-label">Recommended materials (sent with the reply)</label>
              <div className="rec-chips">
                {recs.map((r) => (
                  <span key={r.kind + r.id} className="rec-chip">
                    <span>{r.kind === "lesson" ? "📘" : "📗"}</span>
                    {r.title}
                    <button type="button" className="rec-chip-x" onClick={() => removeRec(r)}
                            aria-label="Remove">✕</button>
                  </span>
                ))}
                {recs.length === 0 && <span className="rec-empty">No materials attached.</span>}
              </div>
              <select className="input" value=""
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
              <p className="rec-hint">Edited materials are sent via <b>Approve</b> or <b>Send edited reply</b>.</p>
            </div>
          )}

          <div style={{ marginTop: 16, display: "flex", gap: 10, flexWrap: "wrap" }}>
            {!noDraft && (
              <button className="btn green" disabled={busy} onClick={() => act("approve")}>
                ✅ Approve option {idx + 1}
              </button>
            )}
            <button className="btn primary" disabled={busy} onClick={() => act("edit")}>
              ✏️ Send edited reply
            </button>
            <button className="btn red" disabled={busy} onClick={() => act("reject")}>
              ⛔ Reject (contact directly)
            </button>
          </div>
        </div>
      </div>

      {/* intake snapshot */}
      <div className="panel detail">
        <div className="panel-head"><div className="panel-title">Context</div></div>
        <div className="detail-body">
          <div className="detail-row"><span className="k">Triage</span>
            <span className="v">{sess.triage_level}</span></div>
          <div className="detail-row"><span className="k">Severity</span>
            <span className="v">{sess.severity || "—"}</span></div>
          <div className="detail-row"><span className="k">Confidence</span>
            <span className="v">{sess.confidence != null ? Number(sess.confidence).toFixed(2) : "—"}</span></div>
          {sess.triage_reason && (
            <>
              <div className="detail-section-title">Triage reason</div>
              <div className="timeline-text">{sess.triage_reason}</div>
            </>
          )}
          {sess.intake_snapshot && (
            <>
              <div className="detail-section-title">Intake snapshot</div>
              <div className="timeline-text">
                <b>Presenting:</b> {sess.intake_snapshot.presenting || "—"}<br />
                <b>Reason:</b> {sess.intake_snapshot.reason || "—"}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
