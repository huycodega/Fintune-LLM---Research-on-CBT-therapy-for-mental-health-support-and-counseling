import { useState, useEffect, useMemo } from "react";
import { api } from "../api.js";

/* Journey — time-bound wellness roadmaps. Each is a set of small steps the
   user ticks off as they go; the page charts the progress of each journey. */

const TIMEFRAMES = ["3 days", "1 week", "2 weeks", "1 month"];

function fmtDay(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return isNaN(d) ? "" : d.toLocaleDateString("en-GB",
    { day: "2-digit", month: "short" });
}

/* Circular progress ring (SVG, theme-aware via currentColor). */
function ProgressRing({ pct, size = 54 }) {
  const r = (size - 8) / 2;
  const c = 2 * Math.PI * r;
  const off = c - (pct / 100) * c;
  return (
    <svg width={size} height={size} className="rm-ring" viewBox={`0 0 ${size} ${size}`}>
      <circle cx={size / 2} cy={size / 2} r={r} className="rm-ring-track"
        fill="none" strokeWidth="6" />
      <circle cx={size / 2} cy={size / 2} r={r} className="rm-ring-fill"
        fill="none" strokeWidth="6" strokeLinecap="round"
        strokeDasharray={c} strokeDashoffset={off}
        transform={`rotate(-90 ${size / 2} ${size / 2})`} />
      <text x="50%" y="50%" dy="0.35em" textAnchor="middle" className="rm-ring-label">
        {pct}%
      </text>
    </svg>
  );
}

/* Cumulative completion over time — an area line built from step done_at
   timestamps. Falls back to a step-completion bar when there's <2 data. */
function ProgressChart({ steps }) {
  const done = steps.filter((s) => s.done && s.done_at)
    .map((s) => new Date(s.done_at)).sort((a, b) => a - b);
  const total = steps.length || 1;
  const W = 260, H = 90, pad = 8;

  if (done.length < 2) {
    // Simple segmented bar of completion
    const pctDone = Math.round(steps.filter((s) => s.done).length / total * 100);
    return (
      <div className="rm-chart">
        <div className="rm-bar">
          <div className="rm-bar-fill" style={{ width: `${pctDone}%` }} />
        </div>
        <div className="rm-chart-cap">
          {steps.filter((s) => s.done).length} of {total} steps done
        </div>
      </div>
    );
  }
  const t0 = done[0].getTime();
  const t1 = done[done.length - 1].getTime();
  const span = Math.max(t1 - t0, 1);
  const pts = done.map((d, i) => {
    const x = pad + ((d.getTime() - t0) / span) * (W - 2 * pad);
    const y = H - pad - ((i + 1) / total) * (H - 2 * pad);
    return [x, y];
  });
  // start baseline at first point's x
  const path = `M ${pad},${H - pad} L ${pts.map((p) => p.join(",")).join(" L ")}`;
  const area = `${path} L ${pts[pts.length - 1][0]},${H - pad} Z`;
  return (
    <div className="rm-chart">
      <svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="rm-line">
        <path d={area} className="rm-line-area" />
        <path d={path} className="rm-line-stroke" fill="none" strokeWidth="2.5" />
        {pts.map((p, i) => <circle key={i} cx={p[0]} cy={p[1]} r="3" className="rm-line-dot" />)}
      </svg>
      <div className="rm-chart-cap">
        {fmtDay(done[0].toISOString())} → {fmtDay(done[done.length - 1].toISOString())} ·
        {" "}{done.length}/{total} steps
      </div>
    </div>
  );
}

function RoadmapCard({ rm, onToggle, onStatus, onDelete }) {
  const [open, setOpen] = useState(rm.status === "active");
  const pct = rm.progress?.pct ?? 0;
  return (
    <div className={`rm-card rm-${rm.status}`}>
      <button className="rm-card-head" onClick={() => setOpen((o) => !o)}>
        <ProgressRing pct={pct} />
        <div className="rm-card-meta">
          <div className="rm-card-title">{rm.title}</div>
          <div className="rm-card-sub">
            <span className="rm-chip">{rm.timeframe}</span>
            {rm.status === "completed" && <span className="rm-chip rm-chip-done">✓ Completed</span>}
            {rm.status === "archived" && <span className="rm-chip rm-chip-arch">Archived</span>}
          </div>
        </div>
        <span className={`rm-caret ${open ? "open" : ""}`}>›</span>
      </button>

      {open && (
        <div className="rm-card-body">
          {rm.goal && <div className="rm-goal">🎯 {rm.goal}</div>}
          <ProgressChart steps={rm.steps || []} />
          <ul className="rm-steps">
            {(rm.steps || []).map((s, i) => (
              <li key={i} className={s.done ? "rm-step done" : "rm-step"}>
                <button className="rm-check" onClick={() => onToggle(rm.id, i)}
                  aria-label={s.done ? "Mark not done" : "Mark done"}>
                  {s.done ? "✓" : ""}
                </button>
                <div className="rm-step-text">
                  <span>{s.text}</span>
                  {s.when && <span className="rm-when">{s.when}</span>}
                </div>
              </li>
            ))}
          </ul>
          <div className="rm-actions">
            {rm.status !== "completed" && (
              <button className="rm-act" onClick={() => onStatus(rm.id, "completed")}>Mark complete</button>
            )}
            {rm.status !== "archived" ? (
              <button className="rm-act" onClick={() => onStatus(rm.id, "archived")}>Archive</button>
            ) : (
              <button className="rm-act" onClick={() => onStatus(rm.id, "active")}>Reactivate</button>
            )}
            <button className="rm-act rm-act-del" onClick={() => onDelete(rm.id)}>Delete</button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function LoTrinh() {
  const [roadmaps, setRoadmaps] = useState(null);
  const [goal, setGoal] = useState("");
  const [tf, setTf] = useState("2 weeks");
  const [busy, setBusy] = useState(false);

  const load = () =>
    api.listRoadmaps().then((r) => setRoadmaps(r.roadmaps || [])).catch(() => setRoadmaps([]));
  useEffect(() => { load(); }, []);

  async function create() {
    const g = goal.trim();
    if (!g || busy) return;
    setBusy(true);
    try {
      await api.createRoadmap(g, tf);
      setGoal("");
      await load();
    } catch { /* keep the draft */ }
    setBusy(false);
  }

  async function toggle(rid, idx) {
    setRoadmaps((rms) => rms); // optimistic no-op; refetch below
    try { const u = await api.toggleRoadmapStep(rid, idx);
      setRoadmaps((rms) => rms.map((r) => r.id === rid ? u : r)); } catch {}
  }
  async function status(rid, s) {
    try { const u = await api.setRoadmapStatus(rid, s);
      setRoadmaps((rms) => rms.map((r) => r.id === rid ? u : r)); } catch {}
  }
  async function del(rid) {
    if (!window.confirm("Delete this journey? This can't be undone.")) return;
    try { await api.deleteRoadmap(rid);
      setRoadmaps((rms) => rms.filter((r) => r.id !== rid)); } catch {}
  }

  const active = useMemo(() => (roadmaps || []).filter((r) => r.status !== "archived"), [roadmaps]);
  const archived = useMemo(() => (roadmaps || []).filter((r) => r.status === "archived"), [roadmaps]);

  return (
    <div className="page rm-page">
      <div className="page-head">
        <h1>Your Journey</h1>
        <p className="page-sub">
          Turn a goal into a gentle, time-bound roadmap. Tick off small steps
          and watch your progress build.
        </p>
      </div>

      <div className="rm-create">
        <input className="rm-input" placeholder="What would you like to work on? (e.g. sleep better, worry less before exams)"
          value={goal} onChange={(e) => setGoal(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && create()} />
        <select className="rm-tf" value={tf} onChange={(e) => setTf(e.target.value)}>
          {TIMEFRAMES.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <button className="rm-create-btn" onClick={create} disabled={busy || !goal.trim()}>
          {busy ? "Building…" : "Create roadmap"}
        </button>
      </div>

      {roadmaps === null ? (
        <div className="rm-empty">Loading…</div>
      ) : active.length === 0 && archived.length === 0 ? (
        <div className="rm-empty">
          No journeys yet. Create one above — or ask in chat, e.g.
          <em> "give me a 2-week plan to sleep better."</em>
        </div>
      ) : (
        <>
          {active.map((r) => (
            <RoadmapCard key={r.id} rm={r} onToggle={toggle} onStatus={status} onDelete={del} />
          ))}
          {archived.length > 0 && (
            <div className="rm-arch-head">Archived</div>
          )}
          {archived.map((r) => (
            <RoadmapCard key={r.id} rm={r} onToggle={toggle} onStatus={status} onDelete={del} />
          ))}
        </>
      )}
    </div>
  );
}
