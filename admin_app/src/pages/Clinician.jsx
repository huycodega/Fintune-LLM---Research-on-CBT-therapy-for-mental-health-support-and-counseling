import { useState, useEffect } from "react";
import { api } from "../api.js";

function Stats() {
  const [s, setS] = useState(null);
  useEffect(() => {
    api.stats().then(setS).catch(() => {});
  }, []);
  if (!s) return null;
  return (
    <div className="stat-grid" style={{ marginBottom: 18 }}>
      <div className="stat">
        <div className="n">{s.total_sessions}</div>
        <div className="l">Total sessions</div>
      </div>
      <div className="stat">
        <div className="n">{s.pending_review}</div>
        <div className="l">Pending review</div>
      </div>
      <div className="stat">
        <div className="n">{s.by_triage_level?.L0 || 0}</div>
        <div className="l">Crisis (L0)</div>
      </div>
      <div className="stat">
        <div className="n">
          {Object.keys(s.technique_distribution || {}).length}
        </div>
        <div className="l">Techniques used</div>
      </div>
    </div>
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
      if (s.drafts?.length) {
        setEditText(s.drafts[0].response);
        setEditTech(s.drafts[0].technique);
      }
    });
  }, [sid]);

  if (!sess) return <div className="card">Loading…</div>;

  const drafts = sess.drafts || [];
  const noDraft = drafts.length === 0;

  async function act(decision) {
    setBusy(true);
    try {
      const payload = { decision, chosen_idx: idx };
      if (decision === "edit") {
        payload.edited_response = editText;
        payload.edited_technique = editTech;
      }
      await api.review(sid, payload);
      onDone();
    } catch (e) {
      alert("Error: " + e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <div className="eyebrow">Human-in-the-loop · clinician review</div>
        <span className={`chip ${sess.triage_level}`}>
          <span className="dot" />
          {sess.triage_level}
        </span>
      </div>

      <h1 className="title" style={{ fontSize: 24, marginTop: 8 }}>
        Step 5 — Clinician decides
      </h1>

      <div className="banner wait" style={{ marginTop: 12 }}>
        <b className="mono">Patient message:</b>
        <div style={{ marginTop: 6 }}>{sess.user_input}</div>
      </div>

      {sess.intake_snapshot && (
        <details style={{ margin: "10px 0 14px" }}>
          <summary className="mono" style={{ cursor: "pointer",
                fontSize: 11, letterSpacing: ".15em",
                textTransform: "uppercase", color: "var(--ink-soft)" }}>
            Intake snapshot
          </summary>
          <p className="muted" style={{ marginTop: 8 }}>
            <b>Demographics:</b> {JSON.stringify(sess.intake_snapshot.demographics) || "—"}<br/>
            <b>Presenting:</b> {sess.intake_snapshot.presenting || "—"}<br/>
            <b>Reason:</b> {sess.intake_snapshot.reason || "—"}
          </p>
        </details>
      )}

      {sess.analysis && (
        <p className="muted" style={{ marginBottom: 14 }}>
          <b>Analysis:</b> emotion {sess.analysis.emotion} · severity{" "}
          {sess.analysis.severity} · distortions:{" "}
          {sess.analysis.cognitive_distortions} · hint:{" "}
          {sess.analysis.technique_hint}
        </p>
      )}

      <p className="muted mono" style={{ marginBottom: 4 }}>
        Triage: {sess.triage_reason} · confidence ={" "}
        {Number(sess.confidence).toFixed(2)}
      </p>

      <div className="divider" />

      {noDraft ? (
        <div className="banner crisis">
          Level <b>{sess.triage_level}</b> — no AI draft was generated.
          Write the reply directly below (decision = edit) or reject to
          contact the patient out-of-band.
        </div>
      ) : (
        <>
          <div className="eyebrow">
            Step 3 — AI drafts ({drafts.length}). NOT yet sent to patient.
          </div>
          {drafts.map((d, i) => (
            <div
              className={"draft" + (i === idx ? " sel" : "")}
              key={i}
              onClick={() => {
                setIdx(i);
                setEditText(d.response);
                setEditTech(d.technique);
              }}
              style={{ cursor: "pointer" }}
            >
              <div className="meta">
                Option {i + 1} · Technique: {d.technique}
                {!d.preflight_pass && " · ⚠ preflight fail"}
                {d.hallucination_score < 0.1 && " · ⚠ grounding low"}
                {i === idx ? " · ✓ selected" : ""}
              </div>
              <div>{d.response}</div>
              <div className="clin">
                <b>Rationale</b>
                <br />
                {d.rationale || "—"}
                <br />
                <b>Plan</b>
                <br />
                {d.plan || "—"}
              </div>
            </div>
          ))}
        </>
      )}

      <div className="divider" />
      <div className="eyebrow">Edit before sending (optional)</div>
      <label>Technique</label>
      <input
        value={editTech}
        onChange={(e) => setEditTech(e.target.value)}
        style={{ marginBottom: 12 }}
      />
      <label>Message to patient</label>
      <textarea
        rows={4}
        value={editText}
        onChange={(e) => setEditText(e.target.value)}
      />

      <div style={{ marginTop: 18, display: "flex", gap: 10,
                     flexWrap: "wrap" }}>
        {!noDraft && (
          <button className="btn accent" disabled={busy}
                   onClick={() => act("approve")}>
            Approve option {idx + 1}
          </button>
        )}
        <button className="btn" disabled={busy} onClick={() => act("edit")}>
          Send edited reply
        </button>
        <button className="btn danger" disabled={busy}
                 onClick={() => act("reject")}>
          Reject (contact directly)
        </button>
        <button className="btn ghost" onClick={onDone}>
          Back to queue
        </button>
      </div>
    </div>
  );
}

export default function Clinician() {
  const [queue, setQueue] = useState([]);
  const [active, setActive] = useState(null);
  const [tab, setTab] = useState("queue");
  const [audit, setAudit] = useState([]);

  function refresh() {
    api.queue().then((r) => setQueue(r.queue || [])).catch(() => {});
  }
  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 6000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (tab === "audit")
      api.audit().then((r) => setAudit(r.audit || [])).catch(() => {});
  }, [tab]);

  if (active) {
    return (
      <div className="shell" style={{ paddingTop: 26, paddingBottom: 60 }}>
        <ReviewPanel
          sid={active}
          onDone={() => { setActive(null); refresh(); }}
        />
      </div>
    );
  }

  return (
    <div className="shell" style={{ paddingTop: 26, paddingBottom: 60 }}>
      <div className="eyebrow">Clinician dashboard · RBAC: admin</div>
      <h1 className="title">Step 4 — Review queue</h1>
      <p className="sub">
        L1, L2, and flagged sessions require clinician review before any
        response is delivered to the patient.
      </p>

      <Stats />

      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <button
          className={"btn sm " + (tab === "queue" ? "accent" : "ghost")}
          onClick={() => setTab("queue")}
        >
          Queue ({queue.length})
        </button>
        <button
          className={"btn sm " + (tab === "audit" ? "accent" : "ghost")}
          onClick={() => setTab("audit")}
        >
          Audit trail
        </button>
      </div>

      {tab === "queue" && (
        <div className="card">
          {queue.length === 0 && (
            <p className="muted">No sessions pending review. 🎉</p>
          )}
          {queue.map((q) => (
            <div className="qrow" key={q.session_id}
                  onClick={() => setActive(q.session_id)}>
              <span className={`chip ${q.triage_level}`}>
                <span className="dot" />
                {q.triage_level}
              </span>
              <span className="msg">{q.user_input}</span>
              <span className="who2">{q.username}</span>
              <button className="btn sm">Review →</button>
            </div>
          ))}
        </div>
      )}

      {tab === "audit" && (
        <div className="card">
          <div className="eyebrow">Compliance audit trail (latest)</div>
          {audit.map((a) => (
            <div
              key={a.id}
              className="mono"
              style={{
                fontSize: 12, padding: "8px 0",
                borderBottom: "1px solid var(--line)",
                color: "var(--ink-soft)",
              }}
            >
              <b style={{ color: "var(--ink)" }}>{a.action}</b> · {a.actor} ·{" "}
              {(a.ts || "").slice(5, 19).replace("T", " ")}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
