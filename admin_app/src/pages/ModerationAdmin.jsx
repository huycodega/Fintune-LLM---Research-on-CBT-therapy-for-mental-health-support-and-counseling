import { useState, useEffect, useRef } from "react";
import Icon from "../admin/Icon.jsx";
import Sidebar from "../admin/Sidebar.jsx";
import TopBar from "../admin/TopBar.jsx";
import { api } from "../api.js";

/* ─────────────────────────────────────────────────────────────────
   AI Moderation queue (admin).

   The backend API (design doc §7) is not wired yet, so this page
   loads from the documented endpoints and falls back to representative
   mock data when they 404 — it "just works" once the API lands.

   FE owns the L0–L3 → label/colour mapping (design doc §2.3).
───────────────────────────────────────────────────────────────── */

const RISK = {
  L0: { label: "Crisis",      cls: "mz-risk-l0" },
  L1: { label: "High Risk",   cls: "mz-risk-l1" },
  L2: { label: "Medium Risk", cls: "mz-risk-l2" },
  L3: { label: "Low / Safe",  cls: "mz-risk-l3" },
};
const STATUS_LABEL = {
  pending:          "Pending",
  claimed:          "In Review",
  need_improvement: "Needs Work",
  resolved:         "Resolved",
  cancelled:        "Cancelled",
};
const CHECKLIST = [
  ["empathy",              "Empathetic & supportive tone"],
  ["no_diagnosis",         "No clinical diagnosis given"],
  ["cbt_based",            "Grounded in CBT techniques"],
  ["safe_response",        "Safe — no harmful content"],
  ["referral_when_needed", "Refers to a human when needed"],
  ["no_medication_advice", "No medication advice"],
  ["no_overclaiming",      "No over-claiming / false promises"],
];
const EMPTY_CHECKS = Object.fromEntries(CHECKLIST.map(([k]) => [k, false]));

function prefersReducedMotion() {
  return typeof window !== "undefined" && window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/* ── Count-up (shared behaviour with LessonsAdmin) ─────────────── */
function CountUp({ value, duration = 900 }) {
  const [display, setDisplay] = useState(value);
  const raf = useRef(0);
  useEffect(() => {
    const target = parseInt(String(value), 10);
    if (Number.isNaN(target) || prefersReducedMotion()) { setDisplay(value); return; }
    const start = performance.now();
    const tick = (now) => {
      const p = Math.min((now - start) / duration, 1);
      setDisplay(String(Math.round(target * (1 - Math.pow(1 - p, 3)))));
      if (p < 1) raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [value, duration]);
  return <>{display}</>;
}

/* ── Mock data (until backend §7 ships) ────────────────────────── */
const MIN = 60 * 1000;
function inMin(m) { return new Date(Date.now() + m * MIN).toISOString(); }
function agoMin(m) { return new Date(Date.now() - m * MIN).toISOString(); }

const MOCK_ITEMS = [
  {
    id: "q1", conversation_id: "c1", kind: "user_escalation", status: "pending",
    risk_level: "L0", priority: 95, sla_due_at: inMin(3), created_at: agoMin(2),
    claimed_by: null, user: { name: "Student #4821", masked_email: "ng***@gmail.com" },
    messages: [
      { id: "m1", sender: "user", content: "I don't think I can keep going. Everything feels pointless and I keep thinking about ending it.", risk_level: "L0", created_at: agoMin(2) },
    ],
    draft: null, revisions: [],
  },
  {
    id: "q2", conversation_id: "c2", kind: "user_escalation", status: "claimed",
    risk_level: "L1", priority: 80, sla_due_at: inMin(18), created_at: agoMin(12),
    claimed_by: { name: "Dr. Huy" }, user: { name: "Student #3310", masked_email: "tr***@gmail.com" },
    messages: [
      { id: "m2", sender: "user", content: "I've been having panic attacks every night and I feel like I'm losing control. I don't know who to talk to.", risk_level: "L1", created_at: agoMin(12) },
    ],
    draft: null, revisions: [],
  },
  {
    id: "q3", conversation_id: "c3", kind: "ai_review", status: "pending",
    risk_level: "L2", priority: 55, sla_due_at: inMin(180), created_at: agoMin(40),
    claimed_by: null, user: { name: "Student #2087", masked_email: "le***@gmail.com" },
    messages: [
      { id: "m3a", sender: "user", content: "I keep procrastinating on everything and then hate myself for it. How do I stop?", risk_level: "L2", created_at: agoMin(41) },
    ],
    draft: {
      response: "It sounds really frustrating to feel caught in that loop — you're not alone in this. One CBT idea is to notice the thought \"I have to do it all perfectly\" and gently challenge it. Try breaking one task into a 5-minute first step, and notice how you feel afterwards. What's one small task you could start with today?",
      confidence: 0.82, model_name: "cbt-qwen2.5-7b-v2",
    },
    revisions: [],
  },
  {
    id: "q4", conversation_id: "c4", kind: "ai_review", status: "pending",
    risk_level: "L3", priority: 40, sla_due_at: inMin(360), created_at: agoMin(80),
    claimed_by: null, user: { name: "Student #1190", masked_email: "ph***@gmail.com" },
    messages: [
      { id: "m4a", sender: "user", content: "What are some breathing exercises I can do before an exam?", risk_level: "L3", created_at: agoMin(81) },
    ],
    draft: {
      response: "Great question! A simple one is 4-7-8 breathing: breathe in for 4 counts, hold for 7, and exhale slowly for 8. Repeating it 3–4 times can calm your nervous system before an exam. Would you like a short grounding exercise too?",
      confidence: 0.91, model_name: "cbt-qwen2.5-7b-v2",
    },
    revisions: [],
  },
  {
    id: "q5", conversation_id: "c5", kind: "ai_review", status: "need_improvement",
    risk_level: "L2", priority: 50, sla_due_at: inMin(-25), created_at: agoMin(120),
    claimed_by: { name: "Dr. Huy" }, user: { name: "Student #0934", masked_email: "do***@gmail.com" },
    messages: [
      { id: "m5a", sender: "user", content: "I haven't slept properly in weeks and it's affecting my studies.", risk_level: "L2", created_at: agoMin(121) },
    ],
    draft: {
      response: "You should try melatonin supplements, they fix insomnia fast.",
      confidence: 0.61, model_name: "cbt-qwen2.5-7b-v2",
    },
    revisions: [
      { id: "r1", revision_no: 1, response: "Sleep trouble can really wear you down. A few CBT-for-insomnia ideas: keep a consistent wake time, and if you can't sleep after 20 minutes, get up and do something calm. Would you like to build a small wind-down routine together?", edited_by: "Dr. Huy", created_at: agoMin(30) },
    ],
  },
];

const MOCK_STATS = { pending: 0, in_review: 0, escalations: 0, resolved_today: 14 };

/* ── Small UI atoms ────────────────────────────────────────────── */
function RiskBadge({ level, big }) {
  const r = RISK[level] || RISK.L3;
  return <span className={`mz-risk ${r.cls} ${big ? "mz-risk-big" : ""}`}><span className="mz-risk-dot" />{r.label}</span>;
}

function SlaPill({ due, resolved }) {
  const [, force] = useState(0);
  useEffect(() => {
    if (resolved) return;
    const t = setInterval(() => force((n) => n + 1), 30000);
    return () => clearInterval(t);
  }, [resolved]);
  if (resolved) return <span className="mz-sla mz-sla-done">Done</span>;
  const diff = new Date(due).getTime() - Date.now();
  const mins = Math.round(Math.abs(diff) / MIN);
  const txt = mins >= 60 ? `${Math.floor(mins / 60)}h ${mins % 60}m` : `${mins}m`;
  if (diff <= 0) return <span className="mz-sla mz-sla-over"><Icon name="alert" size={11} /> Overdue {txt}</span>;
  const cls = diff < 10 * MIN ? "mz-sla-warn" : "mz-sla-ok";
  return <span className={`mz-sla ${cls}`}><Icon name="clock" size={11} /> {txt} left</span>;
}

function StatCard({ icon, tone, label, value, sub, i = 0 }) {
  return (
    <div className="la-stat la-rise" style={{ "--i": i }}>
      <div className={`la-stat-icon tone-${tone}`}><Icon name={icon} size={22} /></div>
      <div className="la-stat-body">
        <div className="la-stat-label">{label}</div>
        <div className="la-stat-value"><CountUp value={String(value)} /></div>
        <div className="la-stat-sub">{sub}</div>
      </div>
    </div>
  );
}

function RowSkeleton() {
  return (
    <tr className="la-skel-row">
      <td><div className="la-title-cell"><span className="la-skel la-skel-thumb" /><div style={{ flex: 1 }}><div className="la-skel la-skel-line" style={{ width: "80%" }} /><div className="la-skel la-skel-line" style={{ width: "55%", marginTop: 6 }} /></div></div></td>
      {Array.from({ length: 5 }).map((_, i) => <td key={i}><div className="la-skel la-skel-line" style={{ width: "70%" }} /></td>)}
    </tr>
  );
}

/* ── Queue row ─────────────────────────────────────────────────── */
function QueueRow({ item, idx, selected, onSelect }) {
  const lastUser = [...item.messages].reverse().find((m) => m.sender === "user");
  const preview = item.draft ? item.draft.response : (lastUser ? lastUser.content : "");
  return (
    <tr className={`la-rise ${selected ? "selected" : ""}`} style={{ "--i": idx }} onClick={() => onSelect(item.id)}>
      <td>
        <div className="la-title-cell" style={{ minWidth: 260 }}>
          <span className={`mz-kind-thumb ${item.kind === "user_escalation" ? "mz-kind-esc" : "mz-kind-ai"}`}>
            <Icon name={item.kind === "user_escalation" ? "alert" : "sparkle"} size={18} />
          </span>
          <div className="la-title-text">
            <div className="la-title-main">{item.user.name}</div>
            <div className="la-title-desc mz-clip">{preview}</div>
          </div>
        </div>
      </td>
      <td><RiskBadge level={item.risk_level} /></td>
      <td><span className="mz-type">{item.kind === "user_escalation" ? "User Escalation" : "AI Review"}</span></td>
      <td><SlaPill due={item.sla_due_at} resolved={item.status === "resolved"} /></td>
      <td><span className={`mz-status mz-status-${item.status}`}>{STATUS_LABEL[item.status] || item.status}</span></td>
      <td onClick={(e) => e.stopPropagation()}>
        <button className="la-btn-ghost mz-row-btn" onClick={() => onSelect(item.id)}>
          {item.kind === "user_escalation" ? "Open" : "Review"} <Icon name="chevronRight" size={14} />
        </button>
      </td>
    </tr>
  );
}

/* ── Conversation thread ───────────────────────────────────────── */
function Thread({ messages, draft }) {
  return (
    <div className="mz-thread">
      {messages.map((m) => (
        <div key={m.id} className={`mz-msg mz-msg-${m.sender}`}>
          <div className="mz-msg-meta">{m.sender === "user" ? "User" : "AI"}{m.risk_level && m.sender === "user" ? ` · ${RISK[m.risk_level]?.label}` : ""}</div>
          <div className="mz-bubble">{m.content}</div>
        </div>
      ))}
      {draft && (
        <div className="mz-msg mz-msg-ai">
          <div className="mz-msg-meta">AI draft · {Math.round(draft.confidence * 100)}% confidence</div>
          <div className="mz-bubble mz-bubble-draft">{draft.response}</div>
        </div>
      )}
    </div>
  );
}

/* ── Detail / review panel ─────────────────────────────────────── */
function ReviewPanel({ item, busy, onClaim, onApprove, onEdit, onReject, onNeedImprovement, onAssign }) {
  const isEscalation = item.kind === "user_escalation";
  const isL0L1 = item.risk_level === "L0" || item.risk_level === "L1";
  const claimed = item.status === "claimed" || item.status === "need_improvement";
  const resolved = item.status === "resolved" || item.status === "cancelled";

  const [checks, setChecks] = useState(EMPTY_CHECKS);
  const [editing, setEditing] = useState(false);
  const [draftText, setDraftText] = useState(item.draft?.response || "");
  const [note, setNote] = useState("");

  // reset local review state whenever a different item is opened
  useEffect(() => {
    setChecks(EMPTY_CHECKS);
    setEditing(false);
    setDraftText(item.draft?.response || "");
    setNote("");
  }, [item.id]);

  const required = ["empathy", "no_diagnosis", "cbt_based", "safe_response", "no_medication_advice", "no_overclaiming"];
  const canDecide = required.every((k) => checks[k]) && (isL0L1 ? checks.referral_when_needed : true);

  return (
    <aside className="la-detail">
      <div className="la-card la-xfade" key={item.id}>
        <div className="la-card-eyebrow" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span>Moderation Item</span>
          <SlaPill due={item.sla_due_at} resolved={resolved} />
        </div>

        <div className="mz-detail-head">
          <RiskBadge level={item.risk_level} big />
          <span className={`mz-status mz-status-${item.status}`}>{STATUS_LABEL[item.status] || item.status}</span>
        </div>
        <div className="mz-detail-user">
          <Icon name="users" size={14} /> {item.user.name}
          <span className="mz-detail-email">{item.user.masked_email}</span>
        </div>

        <Thread messages={item.messages} draft={!editing ? item.draft : null} />

        {/* Edited draft preview / editor */}
        {!isEscalation && editing && (
          <div className="mz-edit">
            <div className="la-detail-h">Edit response</div>
            <textarea className="mz-textarea" value={draftText} onChange={(e) => setDraftText(e.target.value)} rows={6} />
          </div>
        )}

        {item.revisions?.length > 0 && (
          <div className="mz-revisions">
            <div className="la-detail-h">Revisions</div>
            {item.revisions.map((r) => (
              <div key={r.id} className="mz-rev">
                <div className="mz-rev-meta">v{r.revision_no} · {r.edited_by}</div>
                <div className="mz-rev-text">{r.response}</div>
              </div>
            ))}
          </div>
        )}

        {/* Escalation: no AI reply to review */}
        {isEscalation ? (
          <div className="mz-escalation">
            <div className="mz-escalation-icon"><Icon name="alert" size={20} /></div>
            <div>
              <div className="mz-escalation-title">No AI reply — needs specialist outreach</div>
              <div className="mz-escalation-text">
                This {RISK[item.risk_level]?.label} case was handled deterministically by the safety gate.
                A clinician must reach out to the student directly.
              </div>
            </div>
          </div>
        ) : (
          /* AI review: safety checklist */
          <div className="mz-checklist">
            <div className="la-detail-h">Safety checklist</div>
            {CHECKLIST.map(([key, label]) => {
              const isReq = required.includes(key) || (isL0L1 && key === "referral_when_needed");
              return (
                <label key={key} className={`mz-check ${checks[key] ? "on" : ""}`}>
                  <input type="checkbox" checked={checks[key]}
                         disabled={!claimed || resolved}
                         onChange={(e) => setChecks((c) => ({ ...c, [key]: e.target.checked }))} />
                  <span className="mz-check-box"><Icon name="check" size={12} stroke={2.6} /></span>
                  <span className="mz-check-label">{label}{isReq && <span className="mz-req">required</span>}</span>
                </label>
              );
            })}
          </div>
        )}

        {/* Reviewer note */}
        {!resolved && (
          <textarea className="mz-textarea mz-note" placeholder="Reviewer note (optional)…"
                    value={note} onChange={(e) => setNote(e.target.value)} rows={2} />
        )}

        {/* Actions */}
        <div className="mz-actions">
          {resolved ? (
            <div className="mz-resolved-tag"><Icon name="checkCircle" size={15} /> Resolved</div>
          ) : !claimed ? (
            <button className="la-btn-primary la-btn-full" disabled={busy} onClick={() => onClaim(item)}>
              <Icon name="shield" size={15} /> Claim to {isEscalation ? "handle" : "review"}
            </button>
          ) : isEscalation ? (
            <>
              <button className="la-btn-green la-btn-full" disabled={busy} onClick={() => onAssign(item)}>
                <Icon name="phone" size={15} /> Mark specialist contacted
              </button>
            </>
          ) : (
            <>
              <div className="mz-action-row">
                <button className="la-btn-green la-btn-grow" disabled={busy || !canDecide}
                        title={canDecide ? "" : "Complete the required checklist first"}
                        onClick={() => onApprove(item, checks, note)}>
                  <Icon name="checkCircle" size={15} /> Approve
                </button>
                {editing ? (
                  <button className="la-btn-primary la-btn-grow" disabled={busy || !canDecide}
                          onClick={() => onEdit(item, draftText, checks, note)}>
                    <Icon name="check" size={15} /> Save edit
                  </button>
                ) : (
                  <button className="la-btn-outline la-btn-grow" disabled={busy} onClick={() => setEditing(true)}>
                    <Icon name="pencil" size={15} /> Edit
                  </button>
                )}
              </div>
              <div className="mz-action-row">
                <button className="mz-btn-amber la-btn-grow" disabled={busy} onClick={() => onNeedImprovement(item, checks, note)}>
                  <Icon name="arrowUp" size={15} /> Request improvement
                </button>
                <button className="mz-btn-red la-btn-grow" disabled={busy} onClick={() => onReject(item, checks, note)}>
                  <Icon name="close" size={15} /> Reject
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </aside>
  );
}

/* ── Page ──────────────────────────────────────────────────────── */
export default function ModerationAdmin({ onLogout, onNav }) {
  const [items, setItems] = useState([]);
  const [stats, setStats] = useState(MOCK_STATS);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [mock, setMock] = useState(false);
  const [filter, setFilter] = useState("open"); // open | all | escalation
  const [toast, setToast] = useState("");

  function computeStats(list) {
    return {
      pending: list.filter((i) => i.status === "pending").length,
      in_review: list.filter((i) => i.status === "claimed" || i.status === "need_improvement").length,
      escalations: list.filter((i) => i.kind === "user_escalation" && i.status !== "resolved").length,
      resolved_today: MOCK_STATS.resolved_today,
    };
  }

  async function load() {
    setLoading(true);
    try {
      const r = await api.moderationItems();
      const list = r.items || [];
      setItems(list);
      setStats(r.stats || computeStats(list));
      setMock(false);
      setSelected((p) => (p && list.some((i) => i.id === p) ? p : list[0]?.id ?? null));
    } catch {
      // Backend §7 not wired yet → demo with mock data.
      setItems(MOCK_ITEMS);
      setStats(computeStats(MOCK_ITEMS));
      setMock(true);
      setSelected((p) => (p && MOCK_ITEMS.some((i) => i.id === p) ? p : MOCK_ITEMS[0].id));
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { load(); }, []);

  function flash(msg) { setToast(msg); setTimeout(() => setToast(""), 2600); }

  // Local mutation used in mock mode (and optimistic feel in real mode).
  function patchLocal(id, changes) {
    setItems((list) => {
      const next = list.map((i) => (i.id === id ? { ...i, ...changes } : i));
      setStats(computeStats(next));
      return next;
    });
  }

  async function run(realCall, id, localChanges, msg) {
    setBusy(true);
    try {
      if (!mock && realCall) { await realCall(); await load(); }
      else patchLocal(id, localChanges);
      flash(msg);
    } catch (e) {
      // If the real endpoint isn't there yet, degrade to local mock behaviour.
      patchLocal(id, localChanges);
      setMock(true);
      flash(msg);
    } finally {
      setBusy(false);
    }
  }

  const onClaim = (it) =>
    run(() => api.moderationClaim(it.id), it.id, { status: "claimed", claimed_by: { name: "You" } }, "Item claimed");
  const onApprove = (it, checks, note) =>
    run(() => api.moderationApprove(it.id, { checklist: checks, note }), it.id,
      { status: "resolved", resolution: "approve" }, "Response approved & sent");
  const onEdit = (it, response, checks, note) =>
    run(() => api.moderationEditResponse(it.id, { response, checklist: checks, note }), it.id,
      { status: "resolved", resolution: "edit", draft: { ...it.draft, response } }, "Edited response approved");
  const onReject = (it, checks, note) =>
    run(() => api.moderationReject(it.id, { checklist: checks, note }), it.id,
      { status: "resolved", resolution: "reject" }, "Response rejected");
  const onNeedImprovement = (it, checks, note) =>
    run(() => api.moderationNeedImprovement(it.id, { checklist: checks, note }), it.id,
      { status: "need_improvement" }, "Sent back for improvement");
  const onAssign = (it) =>
    run(() => api.moderationApprove(it.id, { resolution: "approve" }), it.id,
      { status: "resolved", resolution: "approve" }, "Specialist contact recorded");

  const visible = items.filter((i) => {
    if (filter === "open") return i.status !== "resolved" && i.status !== "cancelled";
    if (filter === "escalation") return i.kind === "user_escalation";
    return true;
  });
  const current = items.find((i) => i.id === selected) || null;

  return (
    <div className="la-shell">
      <Sidebar active="moderation" onNav={onNav} />

      <div className="la-main">
        <TopBar
          title="AI Moderation"
          subtitle={loading ? "Loading…" : `${stats.pending} pending · ${stats.escalations} escalations`}
          searchPlaceholder="Search messages, users, risk…"
          onLogout={onLogout}
          onNav={onNav}
        />

        <div className="la-content">
          <div className="la-content-left">
            <div className="la-stats">
              {loading ? [0, 1, 2, 3].map((i) => (
                <div key={i} className="la-stat la-rise" style={{ "--i": i }}>
                  <div className="la-skel la-skel-icon" />
                  <div className="la-stat-body" style={{ flex: 1 }}>
                    <div className="la-skel la-skel-line" style={{ width: "60%" }} />
                    <div className="la-skel la-skel-line" style={{ width: "40%", height: 22, margin: "8px 0" }} />
                  </div>
                </div>
              )) : (
                <>
                  <StatCard i={0} icon="clock" tone="orange" label="Pending Review" value={stats.pending} sub="awaiting a reviewer" />
                  <StatCard i={1} icon="sparkle" tone="indigo" label="In Review" value={stats.in_review} sub="currently claimed" />
                  <StatCard i={2} icon="alert" tone="red" label="Escalations" value={stats.escalations} sub="L0 / L1 — specialist" />
                  <StatCard i={3} icon="checkCircle" tone="green" label="Resolved Today" value={stats.resolved_today} sub="across all reviewers" />
                </>
              )}
            </div>

            <div className="la-card la-table-card">
              <div className="mz-toolbar">
                <div className="la-tabs">
                  {[["open", "Open queue"], ["escalation", "Escalations"], ["all", "All"]].map(([id, label]) => (
                    <button key={id} className={`la-tab ${filter === id ? "active" : ""} ${id === "escalation" ? "la-tab-urgent" : ""}`}
                            onClick={() => setFilter(id)}>{label}</button>
                  ))}
                </div>
                {mock && <span className="mz-mock-flag"><Icon name="alert" size={12} /> Demo data — API §7 not wired yet</span>}
              </div>

              <div className="la-table-wrap">
                <table className="la-table">
                  <thead>
                    <tr><th>User &amp; message</th><th>Risk</th><th>Type</th><th>SLA</th><th>Status</th><th>Action</th></tr>
                  </thead>
                  <tbody>
                    {loading && Array.from({ length: 5 }).map((_, i) => <RowSkeleton key={i} />)}
                    {!loading && visible.map((it, i) => (
                      <QueueRow key={it.id} item={it} idx={i} selected={it.id === selected} onSelect={setSelected} />
                    ))}
                    {!loading && visible.length === 0 && (
                      <tr><td colSpan={6} style={{ textAlign: "center", padding: 26, color: "#94a3b8" }}>Queue is clear 🎉</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {loading ? (
            <aside className="la-detail"><div className="la-card"><div className="la-skel la-skel-line" style={{ width: "40%", marginBottom: 14 }} /><div className="la-skel" style={{ height: 120, borderRadius: 12 }} /></div></aside>
          ) : current ? (
            <ReviewPanel
              item={current} busy={busy}
              onClaim={onClaim} onApprove={onApprove} onEdit={onEdit}
              onReject={onReject} onNeedImprovement={onNeedImprovement} onAssign={onAssign}
            />
          ) : null}
        </div>
      </div>

      {toast && <div className="mz-toast"><Icon name="checkCircle" size={16} /> {toast}</div>}
    </div>
  );
}
