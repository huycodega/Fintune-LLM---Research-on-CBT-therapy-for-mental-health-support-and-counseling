import { useState, useEffect, useRef } from "react";
import Icon from "../admin/Icon.jsx";
import Sidebar from "../admin/Sidebar.jsx";
import TopBar from "../admin/TopBar.jsx";
import { api } from "../api.js";
import { DemoNotice, updatedNow, initials, avatarColor } from "../ui.jsx";

/* ─────────────────────────────────────────────────────────────────
   AI Content Moderation (admin) — reference dashboard layout.

   Data flow unchanged: loads from the documented endpoints (design doc
   §7) and falls back to representative demo data when they 404. Backend
   L0–L3 risk codes are mapped to High / Medium / Low for display (§2.3).
───────────────────────────────────────────────────────────────── */

const RISK = {
  High:   { label: "High",   cls: "mz-risk-high" },
  Medium: { label: "Medium", cls: "mz-risk-med" },
  Low:    { label: "Low",    cls: "mz-risk-low" },
};
const L_TO_RISK = { L0: "High", L1: "High", L2: "Medium", L3: "Low" };

const STATUS = {
  pending:          ["Pending", "mz-st-pending"],
  approved:         ["Approved", "mz-st-approved"],
  rejected:         ["Rejected", "mz-st-rejected"],
  need_improvement: ["Needs Improvement", "mz-st-needs"],
};
function statusOf(item) {
  const s = item.status;
  if (s === "approved") return "approved";
  if (s === "rejected") return "rejected";
  if (s === "need_improvement") return "need_improvement";
  if (s === "resolved") return item.resolution === "reject" ? "rejected" : "approved";
  return "pending";
}

const CHECKLIST = [
  ["empathy",              "Empathy"],
  ["no_diagnosis",         "No Diagnosis"],
  ["cbt_based",            "CBT-Based"],
  ["safety",               "Safety"],
  ["recommend_specialist", "Recommend Specialist Support"],
];
const REQUIRED = ["empathy", "no_diagnosis", "cbt_based", "safety"];

function prefersReducedMotion() {
  return typeof window !== "undefined" && window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/* ── Count-up ──────────────────────────────────────────────────── */
function CountUp({ value, duration = 950 }) {
  const [display, setDisplay] = useState(value);
  const raf = useRef(0);
  useEffect(() => {
    const target = parseInt(String(value), 10);
    if (Number.isNaN(target) || prefersReducedMotion()) { setDisplay(value); return; }
    const start = performance.now();
    const tick = (now) => {
      const p = Math.min((now - start) / duration, 1);
      setDisplay(String(Math.round(target * (1 - Math.pow(1 - p, 3))).toLocaleString("en-US")));
      if (p < 1) raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [value, duration]);
  return <>{display}</>;
}

/* ── Demo data (until backend §7 ships) ────────────────────────── */
const FULL_CONTENT = "I feel completely exhausted. Work, studying, and family pressure make me overwhelmed. I feel useless and sometimes think everything would be better if I disappeared.";
const FULL_AI = "I'm sorry you're feeling this way. These feelings can be very heavy and can make everything feel stuck. I'm here to listen and support you.\n\nYou can try taking a slow breath, focus on something around you, and remind yourself that you do not have to handle this alone. If these feelings continue or become stronger, please reach out to someone you trust or a mental health professional.";

function mk(id, name, uid, risk, summary, status, time, extra = {}) {
  return {
    id, userName: name, userId: uid, risk, summary, status, time,
    userContent: extra.userContent || summary,
    aiResponse: extra.aiResponse || "Thank you for sharing how you feel. Let's take this one small step at a time — would you like to try a short grounding exercise together?",
    topic: extra.topic || "General wellbeing",
    duration: extra.duration || "18 minutes",
    aiChecklist: extra.aiChecklist || { empathy: "pass", no_diagnosis: "pass", cbt_based: "pass", safety: "pass", recommend_specialist: "pass" },
    aiNotes: extra.aiNotes || "The response is appropriate, empathetic, and grounded in CBT techniques.",
    history: extra.history || [
      { reviewer: "System", system: true, badge: "Automatically Screened", badgeCls: "mz-st-pending", desc: "Safety gate completed with no blocking signals.", time: "14/06/2024 " + time },
    ],
  };
}

const MOCK_ITEMS = [
  mk("S04218", "Minh Anh", "U0223", "High", "User shows severe stress, negative thoughts about self...", "pending", "10:15", {
    userContent: FULL_CONTENT, aiResponse: FULL_AI,
    topic: "Depression, negative thoughts", duration: "28 minutes",
    aiChecklist: { empathy: "pass", no_diagnosis: "pass", cbt_based: "pass", safety: "pass", recommend_specialist: "warn" },
    aiNotes: "The response is generally appropriate, but should provide clearer guidance for contacting emergency or professional support.",
    history: [
      { reviewer: "Minh Anh (Admin)", badge: "Approved", badgeCls: "mz-st-approved", desc: "Content is appropriate, safe, and supportive for the user.", time: "14/06/2024 10:20" },
      { reviewer: "System", system: true, badge: "Automatically Flagged", badgeCls: "mz-st-needs", desc: "Detected keywords: 'disappear', 'do not want to continue'.", time: "14/06/2024 10:15" },
    ],
  }),
  mk("S04217", "Trần Quang Huy", "U0187", "Medium", "Worried about work, losing motivation for a long time...", "pending", "10:03", { topic: "Work stress, motivation", duration: "21 minutes" }),
  mk("S04216", "Lê Thanh Tâm", "U0312", "Medium", "Tired, poor sleep, academic pressure for a long time...", "pending", "09:52", { topic: "Sleep, academic pressure", duration: "19 minutes" }),
  mk("S04215", "Phạm Gia Bảo", "U0456", "Low", "Mild stress, needs stress reduction advice...", "pending", "09:41", { topic: "Stress management", duration: "12 minutes" }),
  mk("S04214", "Nguyễn Hoài An", "U0099", "High", "Mentions self-harm intent and says there is no way forward...", "pending", "09:28", {
    topic: "Self-harm risk", duration: "31 minutes",
    aiChecklist: { empathy: "pass", no_diagnosis: "pass", cbt_based: "pass", safety: "warn", recommend_specialist: "warn" },
    aiNotes: "High-risk language detected — escalate to a specialist and surface crisis resources immediately.",
  }),
  mk("S04213", "Đỗ Minh Khoa", "U0265", "Medium", "Difficulty concentrating, worries about the future, lack of confidence...", "approved", "09:12", { topic: "Anxiety, confidence", duration: "17 minutes" }),
  mk("S04212", "Vũ Thùy Linh", "U0045", "Low", "Needs relaxation techniques and emotional control support...", "approved", "08:55", { topic: "Relaxation, emotion control", duration: "14 minutes" }),
  mk("S04211", "Hoàng Nam", "U0377", "High", "Prolonged sadness, feeling hopeless...", "pending", "08:43", {
    topic: "Depression", duration: "26 minutes",
    aiChecklist: { empathy: "pass", no_diagnosis: "pass", cbt_based: "pass", safety: "pass", recommend_specialist: "warn" },
  }),
  mk("S04210", "Đặng Thu Trang", "U0123", "Medium", "Family conflict, suppressed emotions...", "pending", "08:31", { topic: "Family conflict", duration: "23 minutes" }),
  mk("S04209", "Trịnh Quốc Đạt", "U0501", "Low", "Wants to improve sleep and daily habits...", "approved", "08:20", { topic: "Sleep, habits", duration: "11 minutes" }),
];

const MOCK_STATS = { pending: 42, approved_today: 128, rejected: 11, needs_improvement: 23 };

/* Map a real API queue item (L0–L3, messages, draft) → display shape. */
function fromApi(it) {
  const lastUser = [...(it.messages || [])].reverse().find((m) => m.sender === "user");
  const t = it.created_at ? new Date(it.created_at) : null;
  return {
    id: String(it.id),
    userName: it.user?.name || "User",
    userId: it.user?.masked_email || "—",
    risk: L_TO_RISK[it.risk_level] || "Low",
    summary: lastUser ? lastUser.content : "",
    status: statusOf(it),
    time: t && !isNaN(t) ? t.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" }) : "—",
    userContent: lastUser ? lastUser.content : "",
    aiResponse: it.draft?.response || "",
    topic: it.kind === "user_escalation" ? "Escalation — no AI reply" : "AI review",
    duration: "—",
    aiChecklist: { empathy: "pass", no_diagnosis: "pass", cbt_based: "pass", safety: "pass", recommend_specialist: it.risk_level === "L0" || it.risk_level === "L1" ? "warn" : "pass" },
    aiNotes: "",
    history: (it.revisions || []).map((r) => ({ reviewer: r.edited_by || "Reviewer", badge: "Edited", badgeCls: "mz-st-needs", desc: r.response, time: r.created_at || "" })),
    kind: it.kind,
    _apiId: it.id,
  };
}

/* ── Small atoms ───────────────────────────────────────────────── */
function RiskBadge({ risk, big }) {
  const r = RISK[risk] || RISK.Low;
  return <span className={`mz-risk ${r.cls} ${big ? "mz-risk-big" : ""}`}><span className="mz-risk-dot" />{r.label}</span>;
}
function StatusBadge({ item }) {
  const [label, cls] = STATUS[statusOf(item)] || STATUS.pending;
  return <span className={`mz-st ${cls}`}>{label}</span>;
}
function Avatar({ name, size = 36 }) {
  return <span className="mz-avatar" style={{ background: avatarColor(name), width: size, height: size, fontSize: size * 0.36 }}>{initials(name)}</span>;
}

function KpiCard({ icon, tone, label, value, trend, down, i }) {
  return (
    <div className="la-stat la-rise" style={{ "--i": i }}>
      <div className={`la-stat-icon tone-${tone}`}><Icon name={icon} size={22} /></div>
      <div className="la-stat-body">
        <div className="la-stat-label">{label}</div>
        <div className="la-stat-value"><CountUp value={String(value)} /></div>
        <div className={`la-stat-sub ${down ? "mz-trend-down" : "mz-trend-up"}`}>
          <Icon name={down ? "arrowDown" : "arrowUp"} size={12} />{trend} vs yesterday
        </div>
      </div>
    </div>
  );
}

function RowSkeleton() {
  return (
    <tr className="la-skel-row">
      <td className="la-check-cell"><div className="la-skel" style={{ width: 17, height: 17, borderRadius: 5, margin: "0 auto" }} /></td>
      <td><div className="la-skel la-skel-line" style={{ width: "70%" }} /></td>
      <td><div className="la-title-cell"><span className="la-skel la-skel-thumb" style={{ borderRadius: "50%" }} /><div style={{ flex: 1 }}><div className="la-skel la-skel-line" style={{ width: "70%" }} /><div className="la-skel la-skel-line" style={{ width: "45%", marginTop: 6 }} /></div></div></td>
      {Array.from({ length: 4 }).map((_, i) => <td key={i}><div className="la-skel la-skel-line" style={{ width: "65%" }} /></td>)}
    </tr>
  );
}

/* ── Queue row ─────────────────────────────────────────────────── */
function QueueRow({ item, idx, selected, onSelect }) {
  return (
    <tr className={`la-rise ${selected ? "selected" : ""}`} style={{ "--i": idx }} onClick={() => onSelect(item.id)}>
      <td className="la-check-cell" onClick={(e) => e.stopPropagation()}>
        <input type="checkbox" className="la-check" checked={selected} onChange={() => onSelect(item.id)} />
      </td>
      <td><span className="mz-sid">{item.id}</span></td>
      <td>
        <div className="la-title-cell" style={{ minWidth: 150 }}>
          <Avatar name={item.userName} />
          <div className="la-title-text">
            <div className="la-title-main">{item.userName}</div>
            <div className="la-title-desc">{item.userId}</div>
          </div>
        </div>
      </td>
      <td><RiskBadge risk={item.risk} /></td>
      <td><div className="mz-summary">{item.summary}</div></td>
      <td><StatusBadge item={item} /></td>
      <td className="la-muted mz-time">{item.time}</td>
    </tr>
  );
}

/* ── Evaluation checklist ──────────────────────────────────────── */
function Checklist({ checks, onToggle, readOnly }) {
  return (
    <div className="mz-check-list">
      {CHECKLIST.map(([key, label]) => {
        const pass = checks[key];
        return (
          <button key={key} type="button" className={`mz-check-row ${pass ? "pass" : "warn"}`}
                  disabled={readOnly} onClick={() => onToggle(key)}>
            <span className="mz-check-label">{label}</span>
            <span className="mz-check-icon"><Icon name={pass ? "checkCircle" : "alert"} size={17} /></span>
          </button>
        );
      })}
    </div>
  );
}

/* ── Review history ────────────────────────────────────────────── */
function ReviewHistory({ items }) {
  return (
    <div className="mz-history">
      <div className="mz-card-head">
        <div className="mz-history-title">Review History</div>
        <button className="mz-link-btn">View Full History</button>
      </div>
      <div className="mz-history-list">
        {items.map((h, i) => (
          <div key={i} className="mz-history-item" style={{ "--i": i }}>
            <span className={`mz-history-avatar ${h.system ? "system" : ""}`}>
              {h.system ? <Icon name="sparkle" size={15} /> : initials(h.reviewer)}
            </span>
            <div className="mz-history-body">
              <div className="mz-history-top">
                <b>{h.reviewer}</b>
                <span className={`mz-st ${h.badgeCls || "mz-st-pending"}`}>{h.badge}</span>
                <span className="mz-history-time">{h.time}</span>
              </div>
              <div className="mz-history-desc">{h.desc}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Detail / review panel (right column inside the board) ─────── */
function DetailPanel({ item, busy, onApprove, onEdit, onReject, onNeedImprovement }) {
  const seed = () => Object.fromEntries(CHECKLIST.map(([k]) => [k, (item.aiChecklist?.[k] || "pass") === "pass"]));
  const [checks, setChecks] = useState(seed);
  const [editing, setEditing] = useState(false);
  const [draftText, setDraftText] = useState(item.aiResponse || "");
  const resolved = item.status !== "pending" && item.status !== "claimed";

  useEffect(() => { setChecks(seed()); setEditing(false); setDraftText(item.aiResponse || ""); }, [item.id]); // eslint-disable-line

  const canApprove = REQUIRED.every((k) => checks[k]);
  const toggle = (k) => !resolved && setChecks((c) => ({ ...c, [k]: !c[k] }));

  return (
    <div className="mz-detail-inner la-xfade" key={item.id}>
      <div className="mz-detail-bar">
        <div className="mz-detail-title">Session Details: {item.id} <RiskBadge risk={item.risk} /></div>
        <div className="mz-detail-time">Time: 14/06/2024 {item.time}</div>
      </div>

      <div className="mz-cards3">
        <div className="mz-mini la-rise" style={{ "--i": 0 }}>
          <div className="mz-mini-head"><Icon name="users" size={15} /> User Content</div>
          <p className="mz-mini-text">{item.userContent}</p>
          <div className="mz-mini-foot">
            <div><span>Topic:</span> {item.topic}</div>
            <div><span>Session Duration:</span> {item.duration}</div>
          </div>
        </div>

        <div className="mz-mini la-rise" style={{ "--i": 1 }}>
          <div className="mz-mini-head"><Icon name="sparkle" size={15} /> AI Response</div>
          {editing ? (
            <textarea className="mz-textarea" rows={8} value={draftText} onChange={(e) => setDraftText(e.target.value)} />
          ) : item.aiResponse ? (
            <p className="mz-mini-text mz-pre">{item.aiResponse}</p>
          ) : (
            <div className="mz-escalation"><div className="mz-escalation-icon"><Icon name="alert" size={18} /></div>
              <div><div className="mz-escalation-title">No AI reply</div><div className="mz-escalation-text">Handled by the safety gate — needs specialist outreach.</div></div></div>
          )}
          <button className="mz-link-btn mz-mini-link"><Icon name="external" size={14} /> View Full Response</button>
        </div>

        <div className="mz-mini la-rise" style={{ "--i": 2 }}>
          <div className="mz-mini-head"><Icon name="shieldCheck" size={15} /> Evaluation Checklist</div>
          <Checklist checks={checks} onToggle={toggle} readOnly={resolved} />
          <div className="mz-ai-notes">
            <div className="mz-ai-notes-label">AI Notes</div>
            <p>{item.aiNotes || "No additional notes."}</p>
          </div>
        </div>
      </div>

      <div className="mz-actions2 la-rise" style={{ "--i": 3 }}>
        {resolved ? (
          <div className="mz-resolved-tag"><Icon name="checkCircle" size={15} /> {STATUS[statusOf(item)][0]}</div>
        ) : editing ? (
          <>
            <button className="mz-act mz-act-green" disabled={busy} onClick={() => onEdit(item, draftText, checks)}><Icon name="check" size={16} /> Save &amp; Approve</button>
            <button className="mz-act mz-act-ghost" disabled={busy} onClick={() => { setEditing(false); setDraftText(item.aiResponse || ""); }}><Icon name="close" size={16} /> Cancel</button>
          </>
        ) : (
          <>
            <button className="mz-act mz-act-green" disabled={busy || !canApprove}
                    title={canApprove ? "" : "Confirm the required checklist items first"}
                    onClick={() => onApprove(item, checks)}><Icon name="check" size={16} /> Approve</button>
            <button className="mz-act mz-act-indigo" disabled={busy} onClick={() => setEditing(true)}><Icon name="pencil" size={16} /> Edit</button>
            <button className="mz-act mz-act-red" disabled={busy} onClick={() => onReject(item, checks)}><Icon name="close" size={16} /> Reject</button>
            <button className="mz-act mz-act-amber" disabled={busy} onClick={() => onNeedImprovement(item, checks)}><Icon name="flag" size={16} /> Flag for Improvement</button>
          </>
        )}
      </div>

      <ReviewHistory items={item.history || []} />
    </div>
  );
}

function DetailSkeleton() {
  return (
    <div className="mz-detail-inner">
      <div className="la-skel la-skel-line" style={{ width: "45%", height: 18, marginBottom: 16 }} />
      <div className="mz-cards3">
        {[0, 1, 2].map((i) => <div className="mz-mini" key={i}><div className="la-skel la-skel-line" style={{ width: "55%" }} /><div className="la-skel" style={{ height: 110, borderRadius: 10, marginTop: 12 }} /></div>)}
      </div>
      <div className="la-skel" style={{ height: 44, borderRadius: 12, marginTop: 16 }} />
    </div>
  );
}

/* ── Page ──────────────────────────────────────────────────────── */
const PAGE_SIZE = 10;

export default function ModerationAdmin({ onLogout, onNav }) {
  const [items, setItems] = useState([]);
  const [stats, setStats] = useState(MOCK_STATS);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [mock, setMock] = useState(false);
  const [tab, setTab] = useState("all");
  const [riskF, setRiskF] = useState("All");
  const [typeF, setTypeF] = useState("All");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [toast, setToast] = useState("");
  const [indStyle, setIndStyle] = useState(null);
  const tabsRef = useRef(null);

  async function load() {
    setLoading(true);
    try {
      const r = await api.moderationItems();
      const list = (r.items || []).map(fromApi);
      setItems(list);
      setStats(r.stats ? { pending: r.stats.pending, approved_today: r.stats.resolved_today, rejected: r.stats.rejected || 0, needs_improvement: r.stats.in_review || 0 } : MOCK_STATS);
      setMock(false);
      setSelected((p) => (p && list.some((i) => i.id === p) ? p : list[0]?.id ?? null));
    } catch {
      setItems(MOCK_ITEMS);
      setStats(MOCK_STATS);
      setMock(true);
      setSelected((p) => (p && MOCK_ITEMS.some((i) => i.id === p) ? p : MOCK_ITEMS[0].id));
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { load(); }, []);
  useEffect(() => { setPage(1); }, [tab, riskF, typeF, q]);

  useEffect(() => {
    const el = tabsRef.current?.querySelector(".la-tab.active");
    if (el) setIndStyle({ transform: `translate(${el.offsetLeft}px, ${el.offsetTop}px)`, width: el.offsetWidth, height: el.offsetHeight });
  }, [tab, items.length]);

  function flash(msg) { setToast(msg); setTimeout(() => setToast(""), 2600); }
  function patchLocal(id, changes) {
    setItems((list) => list.map((i) => (i.id === id ? { ...i, ...changes } : i)));
  }
  async function run(realCall, id, localChanges, msg) {
    setBusy(true);
    try {
      if (!mock && realCall) { await realCall(); await load(); }
      else patchLocal(id, localChanges);
      flash(msg);
    } catch {
      patchLocal(id, localChanges);
      flash(msg);
    } finally { setBusy(false); }
  }

  const apiId = (it) => it._apiId ?? it.id;
  const onApprove = (it, checks) =>
    run(() => api.moderationApprove(apiId(it), { checklist: checks }), it.id, { status: "approved" }, "Response approved & sent");
  const onEdit = (it, response, checks) =>
    run(() => api.moderationEditResponse(apiId(it), { response, checklist: checks }), it.id, { status: "approved", aiResponse: response }, "Edited response approved");
  const onReject = (it, checks) =>
    run(() => api.moderationReject(apiId(it), { checklist: checks }), it.id, { status: "rejected" }, "Response rejected");
  const onNeedImprovement = (it, checks) =>
    run(() => api.moderationNeedImprovement(apiId(it), { checklist: checks }), it.id, { status: "need_improvement" }, "Flagged for improvement");

  const filtered = items.filter((it) => {
    if (tab !== "all" && statusOf(it) !== tab) return false;
    if (riskF !== "All" && it.risk !== riskF) return false;
    if (q) { const s = q.toLowerCase(); if (!(`${it.id} ${it.userName} ${it.userId} ${it.summary}`.toLowerCase().includes(s))) return false; }
    return true;
  });
  const total = filtered.length;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const visible = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const current = items.find((i) => i.id === selected) || null;

  return (
    <div className="la-shell">
      <Sidebar active="moderation" onNav={onNav} />

      <div className="la-main">
        <TopBar title="AI Content Moderation" subtitle={loading ? "Loading…" : updatedNow()}
                searchPlaceholder="Search users, email, phone…" onLogout={onLogout} />

        <div className="la-content mz-mod-content">
          {/* KPI cards (full width) */}
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
                <KpiCard i={0} icon="clock" tone="indigo" label="Pending Review" value={stats.pending} trend="+15" />
                <KpiCard i={1} icon="checkCircle" tone="green" label="Approved Today" value={stats.approved_today} trend="+18.4%" />
                <KpiCard i={2} icon="xCircle" tone="red" label="Rejected" value={stats.rejected} trend="-8.3%" down />
                <KpiCard i={3} icon="flag" tone="orange" label="Needs Improvement" value={stats.needs_improvement} trend="+5" />
              </>
            )}
          </div>

          {/* Board: full-width toolbar, then table | detail */}
          <div className="la-card mz-board">
            <div className="mz-toolbar2">
              <div className="la-tabs" ref={tabsRef}>
                {indStyle && <span className="la-tab-indicator" style={indStyle} aria-hidden="true" />}
                {[["all", "All"], ["pending", "Pending"], ["approved", "Approved"], ["rejected", "Rejected"]].map(([id, label]) => (
                  <button key={id} className={`la-tab ${tab === id ? "active" : ""}`} onClick={() => setTab(id)}>{label}</button>
                ))}
              </div>
              <div className="mz-filters">
                <div className="la-select-group"><label>Risk Level</label>
                  <select className="la-select" value={riskF} onChange={(e) => setRiskF(e.target.value)}>
                    <option value="All">All Levels</option><option>High</option><option>Medium</option><option>Low</option>
                  </select>
                </div>
                <div className="la-select-group"><label>Feedback Type</label>
                  <select className="la-select" value={typeF} onChange={(e) => setTypeF(e.target.value)}>
                    <option value="All">All Types</option><option>AI Review</option><option>Escalation</option>
                  </select>
                </div>
                <div className="la-filter-search mz-search"><Icon name="search" size={16} className="la-search-icon" />
                  <input placeholder="Search sessions, users…" value={q} onChange={(e) => setQ(e.target.value)} />
                </div>
              </div>
            </div>

            {mock && <div className="mz-demo-wrap"><DemoNotice>Sample data shown — moderation API isn't connected yet.</DemoNotice></div>}

            <div className="mz-split">
              {/* Table */}
              <div className="mz-table-col">
                <div className="la-table-wrap">
                  <table className="la-table mz-table2">
                    <thead>
                      <tr>
                        <th className="la-check-cell"><input type="checkbox" className="la-check" readOnly /></th>
                        <th>Session ID</th><th>User</th><th>Risk Level</th><th>Content Summary</th><th>Status</th><th>Time</th>
                      </tr>
                    </thead>
                    <tbody key={`${tab}-${riskF}-${page}`}>
                      {loading && Array.from({ length: 8 }).map((_, i) => <RowSkeleton key={i} />)}
                      {!loading && visible.map((it, i) => (
                        <QueueRow key={it.id} item={it} idx={i} selected={it.id === selected} onSelect={setSelected} />
                      ))}
                      {!loading && visible.length === 0 && (
                        <tr><td colSpan={7} style={{ textAlign: "center", padding: 26, color: "#94a3b8" }}>No sessions match these filters.</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
                <div className="la-pagination mz-pagination">
                  <div className="la-page-info">Showing {visible.length ? (page - 1) * PAGE_SIZE + 1 : 0}–{(page - 1) * PAGE_SIZE + visible.length} of {total} sessions</div>
                  <div className="la-page-controls">
                    <button className="la-page-btn" disabled={page <= 1} onClick={() => setPage(page - 1)}><Icon name="chevronLeft" size={15} /></button>
                    {Array.from({ length: Math.min(pageCount, 5) }, (_, i) => i + 1).map((p) => (
                      <button key={p} className={`la-page-btn ${p === page ? "active" : ""}`} onClick={() => setPage(p)}>{p}</button>
                    ))}
                    <button className="la-page-btn" disabled={page >= pageCount} onClick={() => setPage(page + 1)}><Icon name="chevronRight" size={15} /></button>
                  </div>
                </div>
              </div>

              {/* Detail */}
              <div className="mz-detail-col">
                {loading ? <DetailSkeleton /> : current ? (
                  <DetailPanel item={current} busy={busy}
                               onApprove={onApprove} onEdit={onEdit} onReject={onReject} onNeedImprovement={onNeedImprovement} />
                ) : null}
              </div>
            </div>
          </div>
        </div>
      </div>

      {toast && <div className="mz-toast"><Icon name="checkCircle" size={16} /> {toast}</div>}
    </div>
  );
}
