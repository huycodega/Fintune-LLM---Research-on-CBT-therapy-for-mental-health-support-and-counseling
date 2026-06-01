import { useState, useEffect, useRef } from "react";
import { api } from "../api.js";

const TRIAGE_LABEL = {
  L0: "Emergency",
  L1: "High risk",
  L2: "Pending clinician review",
  L3: "Safe",
};

function CrisisResources({ res }) {
  if (!res) return null;
  return (
    <div className="banner crisis">
      <strong>Crisis resources</strong>
      <div style={{ marginTop: 10 }}>
        {Object.values(res).map((r) => (
          <div key={r.name} style={{ marginBottom: 8 }}>
            <b>{r.name}</b>
            <br />
            <span className="mono">{r.phone} · {r.available}</span>
            <br />
            <a href={r.url} target="_blank" rel="noreferrer">
              {r.url}
            </a>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Chat() {
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);
  const pollRef = useRef(null);

  async function loadHistory() {
    try {
      const r = await api.mySessions();
      setHistory(r.sessions || []);
    } catch {}
  }
  useEffect(() => {
    loadHistory();
    return () => clearInterval(pollRef.current);
  }, []);

  function startPolling(sid) {
    clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const s = await api.mySession(sid);
        if (s.status === "answered" || s.status === "rejected") {
          clearInterval(pollRef.current);
          setResult((prev) => ({ ...prev, outcome: "answered", delivered: s }));
          loadHistory();
        }
      } catch {}
    }, 4000);
  }

  async function send() {
    if (!msg.trim()) return;
    setBusy(true);
    setResult(null);
    try {
      const r = await api.chat(msg.trim());
      setResult(r);
      if (r.outcome === "pending_review") startPolling(r.session_id);
      loadHistory();
    } catch (e) {
      setResult({ outcome: "error", message: e.message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="shell" style={{ paddingTop: 30, paddingBottom: 60 }}>
      <div className="eyebrow">Patient-facing</div>
      <h1 className="title">Share what's on your mind</h1>
      <p className="sub">
        The system classifies your message for safety first. Sensitive
        situations are reviewed by a clinician before any reply reaches
        you — AI does not respond on its own in those cases.
      </p>

      <div className="card">
        <label>Your message</label>
        <textarea
          rows={4}
          value={msg}
          onChange={(e) => setMsg(e.target.value)}
          placeholder="e.g. I keep thinking I'm going to fail and ruin everything..."
        />
        <div style={{ marginTop: 14 }}>
          <button className="btn accent" onClick={send} disabled={busy}>
            {busy && <span className="spinner" />}
            Send
          </button>
        </div>
      </div>

      {result && (
        <div className="card">
          {result.outcome === "error" && (
            <div className="banner crisis">Error: {result.message}</div>
          )}

          {result.triage && (
            <div style={{ marginBottom: 14 }}>
              <span className={`chip ${result.triage.triage_level}`}>
                <span className="dot" />
                {result.triage.triage_level} ·{" "}
                {TRIAGE_LABEL[result.triage.triage_level]}
              </span>
            </div>
          )}

          {result.outcome === "crisis" && (
            <>
              <div className="banner crisis">{result.message}</div>
              <CrisisResources res={result.crisis_resources} />
            </>
          )}

          {result.outcome === "pending_review" && !result.delivered && (
            <>
              <div className="banner wait">
                <span className="spinner" />
                {result.message}
              </div>
              <p className="muted">
                This page will update automatically when the clinician
                responds.
              </p>
              {result.crisis_resources && (
                <CrisisResources res={result.crisis_resources} />
              )}
            </>
          )}

          {result.outcome === "answered" && result.delivered && (
            <>
              <div className="banner ok">
                A clinician has reviewed and approved the response.
              </div>
              <div className="draft sel">
                <div className="meta">
                  Technique: {result.delivered.final_technique}
                </div>
                <div>{result.delivered.final_reply}</div>
              </div>
            </>
          )}

          {result.outcome === "answered" && result.final && (
            <>
              <div className="banner ok">
                Response ({result.triage.triage_level} — safe, sent
                automatically and logged for clinical review).
              </div>
              <div className="draft sel">
                <div className="meta">
                  Technique: {result.final.technique}
                </div>
                <div>{result.final.response}</div>
              </div>
              {result.drafts && result.drafts.length > 1 && (
                <details style={{ marginTop: 14 }}>
                  <summary className="mono" style={{ cursor: "pointer" }}>
                    See {result.drafts.length - 1} alternative response(s)
                  </summary>
                  {result.drafts.slice(1).map((d, i) => (
                    <div className="draft" key={i} style={{ marginTop: 10 }}>
                      <div className="meta">Technique: {d.technique}</div>
                      <div>{d.response}</div>
                    </div>
                  ))}
                </details>
              )}
            </>
          )}
        </div>
      )}

      {history.length > 0 && (
        <div className="card">
          <div className="eyebrow">Your history</div>
          {history.map((h) => (
            <div className="qrow" key={h.id} style={{ cursor: "default" }}>
              <span className={`chip ${h.triage_level || "L3"}`}>
                <span className="dot" />
                {h.triage_level}
              </span>
              <span className="msg">{h.final_technique || h.status}</span>
              <span className="who2">{h.status}</span>
              <span className="mono" style={{ fontSize: 11 }}>
                {(h.created_at || "").slice(5, 16).replace("T", " ")}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
