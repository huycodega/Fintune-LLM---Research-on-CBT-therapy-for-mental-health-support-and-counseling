import { useState, useEffect } from "react";
import { api } from "../api.js";
import { Avatar, StatCard, Empty, displayName, timeAgo } from "../ui.jsx";
import AppShell from "../admin/AppShell.jsx";

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

  useEffect(() => {
    api.adminSession(sid).then((s) => {
      setSess(s);
      if (s.drafts?.length) { setEditText(s.drafts[0].response); setEditTech(s.drafts[0].technique); }
    });
  }, [sid]);

  if (!sess) return <div className="loading">Loading case…</div>;
  const drafts = sess.drafts || [];
  const noDraft = drafts.length === 0;

  async function act(decision) {
    setBusy(true);
    try {
      const payload = { decision, chosen_idx: idx };
      if (decision === "edit") { payload.edited_response = editText; payload.edited_technique = editTech; }
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
