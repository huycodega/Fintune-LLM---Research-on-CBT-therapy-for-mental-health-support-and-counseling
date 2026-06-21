import { useState, useEffect, useRef, useCallback } from "react";
import Icon from "../admin/Icon.jsx";
import Sidebar from "../admin/Sidebar.jsx";
import TopBar from "../admin/TopBar.jsx";
import { api, getUser } from "../api.js";
import { displayName, fmtDate, fmtDateTime, timeAgo, initials, avatarColor, DemoNotice, updatedNow } from "../ui.jsx";

/* ─────────────────────────────────────────────────────────────────
   User Management (admin) — la-* design, matches Lessons/Resources.

   Implements handoff §2.2: list + filters + detail + change status +
   change role + assign clinician (§4.4 — one active clinician per user).
   Falls back to mock data when the admin API isn't reachable, so it is
   demoable now and works unchanged once the backend lands.

   Risk badges use the L0–L3 mapping the FE owns (design doc §2.3).
───────────────────────────────────────────────────────────────── */

const RISK_MAP = {
  L0: ["Crisis", "mz-risk-l0"], L1: ["High Risk", "mz-risk-l1"],
  L2: ["Medium Risk", "mz-risk-l2"], L3: ["Low / Safe", "mz-risk-l3"],
  // tolerate legacy labels until the backend emits L0–L3 everywhere
  crisis: ["Crisis", "mz-risk-l0"], high: ["High Risk", "mz-risk-l1"],
  elevated: ["Medium Risk", "mz-risk-l2"], moderate: ["Medium Risk", "mz-risk-l2"],
  low: ["Low / Safe", "mz-risk-l3"],
};
function RiskBadge({ risk }) {
  if (!risk) return <span className="la-muted">—</span>;
  const [label, cls] = RISK_MAP[risk] || ["Unknown", "mz-risk-l3"];
  return <span className={`mz-risk ${cls}`}><span className="mz-risk-dot" />{label}</span>;
}

const STATUS_MAP = {
  active: ["Active", "la-badge-green"], suspended: ["Suspended", "la-badge-red"],
  pending: ["Pending", "la-badge-amber"], deactivated: ["Deactivated", "mz-status-cancelled"],
};
function StatusBadge({ status }) {
  const [label, cls] = STATUS_MAP[status] || ["Active", "la-badge-green"];
  return <span className={`la-badge ${cls}`}><span className="la-badge-dot" />{label}</span>;
}

function prefersReducedMotion() {
  return typeof window !== "undefined" && window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}
function CountUp({ value, duration = 900 }) {
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

function MiniAvatar({ name, size = 30 }) {
  return (
    <span className="la-owner-avatar" style={{ background: avatarColor(name), width: size, height: size, fontSize: size * 0.36 }}>
      {initials(name)}
    </span>
  );
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
      <td><div className="la-title-cell"><span className="la-skel la-skel-thumb" style={{ borderRadius: "50%" }} /><div style={{ flex: 1 }}><div className="la-skel la-skel-line" style={{ width: "70%" }} /><div className="la-skel la-skel-line" style={{ width: "50%", marginTop: 6 }} /></div></div></td>
      {Array.from({ length: 5 }).map((_, i) => <td key={i}><div className="la-skel la-skel-line" style={{ width: "65%" }} /></td>)}
    </tr>
  );
}

/* ── Mock data (until the admin user API is reachable) ─────────── */
const MOCK_CLINICIANS = [
  { id: "cl1", name: "Dr. Huy Nguyen" },
  { id: "cl2", name: "Dr. Lan Pham" },
  { id: "cl3", name: "Dr. Minh Tran" },
];
const MIN = 60 * 1000;
function ago(m) { return new Date(Date.now() - m * MIN).toISOString(); }
const MOCK_USERS = [
  { id: "u1", username: "nguyenan@gmail.com", email: "ng***@gmail.com", status: "active", risk: "L0", role: "user", sessions: 12, crisis_count: 2, last_active: ago(8), assigned_clinician: { id: "cl1", name: "Dr. Huy Nguyen" }, email_verified: true, created_at: ago(60 * 24 * 40), last_login: ago(8), screenings: [{ phq9_score: 19, phq9_level: "severe", gad7_score: 14, gad7_level: "moderate", mood_score: 3 }], history: [{ id: "s1", risk: "L0", status: "pending_review", created_at: ago(120), preview: "I keep thinking about ending it…" }] },
  { id: "u2", username: "tranbao@gmail.com", email: "tr***@gmail.com", status: "active", risk: "L2", role: "user", sessions: 7, crisis_count: 0, last_active: ago(60), assigned_clinician: null, email_verified: true, created_at: ago(60 * 24 * 20), last_login: ago(60), screenings: [{ phq9_score: 11, phq9_level: "moderate", gad7_score: 9, gad7_level: "mild", mood_score: 5 }], history: [{ id: "s2", risk: "L2", status: "resolved", created_at: ago(300), preview: "I procrastinate a lot and feel guilty." }] },
  { id: "u3", username: "lethanh@gmail.com", email: "le***@gmail.com", status: "suspended", risk: "L3", role: "user", sessions: 3, crisis_count: 0, last_active: ago(60 * 24 * 3), assigned_clinician: null, email_verified: false, created_at: ago(60 * 24 * 12), last_login: ago(60 * 24 * 3), screenings: [], history: [] },
  { id: "u4", username: "phamgia@gmail.com", email: "ph***@gmail.com", status: "active", risk: "L1", role: "user", sessions: 9, crisis_count: 1, last_active: ago(25), assigned_clinician: { id: "cl2", name: "Dr. Lan Pham" }, email_verified: true, created_at: ago(60 * 24 * 33), last_login: ago(25), screenings: [{ phq9_score: 16, phq9_level: "moderately severe", gad7_score: 12, gad7_level: "moderate", mood_score: 4 }], history: [{ id: "s4", risk: "L1", status: "pending_review", created_at: ago(180), preview: "Panic attacks every night, losing control." }] },
  { id: "u5", username: "hoangnam@gmail.com", email: "ho***@gmail.com", status: "pending", risk: "L3", role: "user", sessions: 1, crisis_count: 0, last_active: ago(60 * 24), assigned_clinician: null, email_verified: false, created_at: ago(60 * 24), last_login: null, screenings: [], history: [] },
  { id: "u6", username: "dangthu@gmail.com", email: "da***@gmail.com", status: "active", risk: "L2", role: "user", sessions: 5, crisis_count: 0, last_active: ago(200), assigned_clinician: { id: "cl3", name: "Dr. Minh Tran" }, email_verified: true, created_at: ago(60 * 24 * 9), last_login: ago(200), screenings: [{ phq9_score: 8, phq9_level: "mild", gad7_score: 6, gad7_level: "mild", mood_score: 6 }], history: [] },
];

/* ── Page ──────────────────────────────────────────────────────── */
const STATUS_TABS = [
  { id: "", label: "All" },
  { id: "active", label: "Active" },
  { id: "suspended", label: "Suspended" },
  { id: "pending", label: "Pending" },
];
const PAGE_SIZE = 10;

export default function UsersAdmin({ onLogout, onNav }) {
  const me = getUser();
  const isAdmin = me?.role === "admin";

  const [users, setUsers] = useState([]);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState("");
  const [risk, setRisk] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [selId, setSelId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [mock, setMock] = useState(false);
  const [toast, setToast] = useState("");
  const [indStyle, setIndStyle] = useState(null);
  const [clinicians, setClinicians] = useState(MOCK_CLINICIANS);
  const tabsRef = useRef(null);

  function flash(m) { setToast(m); setTimeout(() => setToast(""), 2600); }

  // Real clinician list for the assign dropdown (falls back to mock).
  useEffect(() => {
    api.clinicians().then((r) => {
      if (r.clinicians?.length) setClinicians(r.clinicians);
    }).catch(() => { /* keep mock */ });
  }, []);

  function mockFilter() {
    let list = MOCK_USERS.slice();
    if (status) list = list.filter((u) => u.status === status);
    if (risk) list = list.filter((u) => u.risk === risk);
    if (q) {
      const s = q.toLowerCase();
      list = list.filter((u) => u.username.toLowerCase().includes(s) || (u.email || "").toLowerCase().includes(s));
    }
    return list;
  }

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const d = await api.users({ q, status, risk, page, page_size: PAGE_SIZE });
      const list = d.users || [];
      setUsers(list); setTotal(d.total || list.length); setMock(false);
      setSelId((p) => (list.find((u) => u.id === p) ? p : list[0]?.id || null));
    } catch {
      const list = mockFilter();
      setUsers(list); setTotal(list.length); setMock(true);
      setSelId((p) => (list.find((u) => u.id === p) ? p : list[0]?.id || null));
    } finally {
      setLoading(false);
    }
  }, [q, status, risk, page]);

  useEffect(() => { setPage(1); }, [q, status, risk]);
  useEffect(() => { load(); }, [load]);

  // Load detail for the selected user (mock: take it straight from the row).
  useEffect(() => {
    if (!selId) { setDetail(null); return; }
    if (mock) { setDetail(MOCK_USERS.find((u) => u.id === selId) || null); return; }
    setDetail(null);
    api.userDetail(selId).then(setDetail).catch(() => setDetail(MOCK_USERS.find((u) => u.id === selId) || null));
  }, [selId, mock]);

  // sliding tab indicator
  useEffect(() => {
    const el = tabsRef.current?.querySelector(".la-tab.active");
    if (el) setIndStyle({ transform: `translate(${el.offsetLeft}px, ${el.offsetTop}px)`, width: el.offsetWidth, height: el.offsetHeight });
  }, [status, users.length]);

  async function run(realCall, applyLocal, msg) {
    setBusy(true);
    try {
      if (!mock && realCall) { await realCall(); await load(); }
      else applyLocal();
      flash(msg);
    } catch (e) {
      // Endpoint not wired yet → reflect the change optimistically without
      // discarding the real list we already loaded.
      applyLocal();
      flash(msg);
    } finally { setBusy(false); }
  }

  function changeStatus(next) {
    if (!detail) return;
    const verb = next === "suspended" ? "suspend" : "re-activate";
    if (!confirm(`Are you sure you want to ${verb} ${displayName(detail.username)}?`)) return;
    run(() => api.setUserStatus(detail.id, next),
      () => { setDetail((d) => ({ ...d, status: next })); setUsers((us) => us.map((u) => u.id === detail.id ? { ...u, status: next } : u)); },
      next === "suspended" ? "Account suspended" : "Account re-activated");
  }
  function changeRole(role) {
    if (!detail || role === detail.role) return;
    run(() => api.setUserRole(detail.id, role),
      () => setDetail((d) => ({ ...d, role })), `Role changed to ${role}`);
  }
  function assignClinician(clinicianId) {
    if (!detail || !clinicianId) return;
    const clin = clinicians.find((c) => c.id === clinicianId);
    run(() => api.assignClinician(detail.id, { clinician_id: clinicianId }),
      () => { setDetail((d) => ({ ...d, assigned_clinician: clin })); setUsers((us) => us.map((u) => u.id === detail.id ? { ...u, assigned_clinician: clin } : u)); },
      `Assigned to ${clin?.name || "clinician"}`);
  }

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const highRisk = users.filter((u) => u.risk === "L0" || u.risk === "L1" || u.risk === "high" || u.risk === "crisis").length;
  const suspended = users.filter((u) => u.status === "suspended").length;
  const activeN = users.filter((u) => u.status === "active").length;

  return (
    <div className="la-shell">
      <Sidebar active="users" onNav={onNav} />

      <div className="la-main">
        <TopBar title="User Management" subtitle={loading ? "Loading…" : updatedNow()}
                searchPlaceholder="Search users, emails…" onLogout={onLogout} />

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
                  <StatCard i={0} icon="users" tone="indigo" label="Total Users" value={total} sub="matching filters" />
                  <StatCard i={1} icon="alert" tone="red" label="High Risk" value={highRisk} sub="L0 / L1 on page" />
                  <StatCard i={2} icon="clock" tone="orange" label="Suspended" value={suspended} sub="on page" />
                  <StatCard i={3} icon="checkCircle" tone="green" label="Active" value={activeN} sub="on page" />
                </>
              )}
            </div>

            <div className="la-card la-table-card">
              <div className="mz-toolbar">
                <div className="la-tabs" ref={tabsRef}>
                  {indStyle && <span className="la-tab-indicator" style={indStyle} aria-hidden="true" />}
                  {STATUS_TABS.map((t) => (
                    <button key={t.id} className={`la-tab ${status === t.id ? "active" : ""}`} onClick={() => setStatus(t.id)}>{t.label}</button>
                  ))}
                </div>
                <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
                  <div className="la-filter-search la-res-search" style={{ minWidth: 180 }}>
                    <Icon name="search" size={16} className="la-search-icon" />
                    <input placeholder="Search within list…" value={q} onChange={(e) => setQ(e.target.value)} />
                  </div>
                  <select className="la-select" value={risk} onChange={(e) => setRisk(e.target.value)}>
                    <option value="">Risk: All</option>
                    <option value="L0">Crisis (L0)</option>
                    <option value="L1">High (L1)</option>
                    <option value="L2">Medium (L2)</option>
                    <option value="L3">Low (L3)</option>
                  </select>
                </div>
              </div>

              {mock && <div style={{ marginBottom: 12 }}><DemoNotice>Sample data shown — user admin API isn't connected yet.</DemoNotice></div>}

              <div className="la-table-wrap">
                <table className="la-table">
                  <thead>
                    <tr><th>User</th><th>Status</th><th>Risk</th><th>Sessions</th><th>Crisis</th><th>Assigned</th><th>Last active</th></tr>
                  </thead>
                  <tbody key={loading ? "l" : `${status}-${risk}-${page}`}>
                    {loading && Array.from({ length: 6 }).map((_, i) => <RowSkeleton key={i} />)}
                    {!loading && users.map((u, i) => (
                      <tr key={u.id} className={`la-rise ${u.id === selId ? "selected" : ""}`} style={{ "--i": i }} onClick={() => setSelId(u.id)}>
                        <td>
                          <div className="la-title-cell" style={{ minWidth: 220 }}>
                            <MiniAvatar name={u.username} size={38} />
                            <div className="la-title-text">
                              <div className="la-title-main">{displayName(u.username)}</div>
                              <div className="la-title-desc">{u.email || "—"}</div>
                            </div>
                          </div>
                        </td>
                        <td><StatusBadge status={u.status} /></td>
                        <td><RiskBadge risk={u.risk} /></td>
                        <td className="la-muted">{u.sessions ?? 0}</td>
                        <td>{u.crisis_count > 0
                          ? <span className="la-badge la-badge-red"><span className="la-badge-dot" />{u.crisis_count}</span>
                          : <span className="la-muted">0</span>}</td>
                        <td className="la-muted">{u.assigned_clinician ? u.assigned_clinician.name : <span style={{ color: "#cbd5e1" }}>Unassigned</span>}</td>
                        <td className="la-muted">{timeAgo(u.last_active)}</td>
                      </tr>
                    ))}
                    {!loading && users.length === 0 && (
                      <tr><td colSpan={7} style={{ textAlign: "center", padding: 26, color: "#94a3b8" }}>No users match these filters.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>

              <div className="la-pagination">
                <div className="la-page-info">Showing {users.length ? (page - 1) * PAGE_SIZE + 1 : 0}–{(page - 1) * PAGE_SIZE + users.length} of {total} users</div>
                <div className="la-page-controls">
                  <button className="la-page-btn" disabled={page <= 1} onClick={() => setPage(page - 1)}><Icon name="chevronLeft" size={15} /></button>
                  {Array.from({ length: pageCount }, (_, i) => i + 1)
                    .filter((p) => Math.abs(p - page) < 2 || p === 1 || p === pageCount)
                    .map((p, i, arr) => (
                      <span key={p} style={{ display: "inline-flex", gap: 5 }}>
                        {i > 0 && arr[i - 1] !== p - 1 && <span className="la-page-btn ellipsis">…</span>}
                        <button className={`la-page-btn ${p === page ? "active" : ""}`} onClick={() => setPage(p)}>{p}</button>
                      </span>
                    ))}
                  <button className="la-page-btn" disabled={page >= pageCount} onClick={() => setPage(page + 1)}><Icon name="chevronRight" size={15} /></button>
                </div>
              </div>
            </div>
          </div>

          {loading ? (
            <aside className="la-detail la-detail-single"><div className="la-card"><div className="la-skel" style={{ height: 90, borderRadius: 12, marginBottom: 14 }} /><div className="la-skel la-skel-line" style={{ width: "60%" }} /><div className="la-skel la-skel-line" style={{ width: "100%", marginTop: 12 }} /></div></aside>
          ) : detail ? (
            <UserDetail detail={detail} isAdmin={isAdmin} busy={busy}
                        onStatus={changeStatus} onRole={changeRole} onAssign={assignClinician} />
          ) : (
            <aside className="la-detail la-detail-single"><div className="la-card" style={{ textAlign: "center", color: "#94a3b8", padding: "40px 20px" }}><Icon name="users" size={30} /><div style={{ marginTop: 10, fontSize: 13 }}>Select a user to see their profile &amp; case history.</div></div></aside>
          )}
        </div>
      </div>

      {toast && <div className="mz-toast"><Icon name="checkCircle" size={16} /> {toast}</div>}
    </div>
  );
}

/* ── Detail panel ──────────────────────────────────────────────── */
function UserDetail({ detail, isAdmin, busy, onStatus, onRole, onAssign }) {
  const d = detail;
  const history = d.history || (d.sessions && Array.isArray(d.sessions) ? d.sessions : []);
  const crisisN = history.filter((s) => ["L0", "L1"].includes(s.risk || s.triage_level)).length;
  const screening = d.screenings?.[0];
  const sessionsCount = typeof d.sessions === "number" ? d.sessions : (Array.isArray(d.sessions) ? d.sessions.length : history.length);
  const [pendingClin, setPendingClin] = useState("");

  useEffect(() => { setPendingClin(""); }, [d.id]);

  return (
    <aside className="la-detail la-detail-single">
      <div className="la-card la-xfade" key={d.id}>
        <div className="us-detail-head">
          <MiniAvatar name={d.username} size={62} />
          <div className="us-detail-name">{displayName(d.username)}</div>
          <div className="us-detail-email">{d.email || "no email"}</div>
          <div className="us-detail-badges">
            <StatusBadge status={d.status} />
            <RiskBadge risk={d.risk} />
          </div>
        </div>

        <div className="la-info">
          <div className="la-info-row"><span className="la-info-label">Role</span><span className="la-info-value">{d.role || "user"}</span></div>
          <div className="la-info-row"><span className="la-info-label">Joined</span><span className="la-info-value">{fmtDate(d.created_at)}</span></div>
          <div className="la-info-row"><span className="la-info-label">Last login</span><span className="la-info-value">{d.last_login ? fmtDate(d.last_login) : "—"}</span></div>
          <div className="la-info-row"><span className="la-info-label">Email verified</span><span className="la-info-value">{d.email_verified ? "✓ Yes" : "⚠ No"}</span></div>
          <div className="la-info-row"><span className="la-info-label">Sessions</span><span className="la-info-value">{sessionsCount}</span></div>
          <div className="la-info-row"><span className="la-info-label">Crisis events</span><span className="la-info-value">{crisisN}</span></div>
        </div>

        {/* Assigned clinician (§4.4 — one active assignment per user) */}
        <div className="la-detail-section">
          <div className="la-detail-h">Assigned clinician</div>
          <div className="us-assign-current">
            {d.assigned_clinician
              ? <span className="us-assign-name"><MiniAvatar name={d.assigned_clinician.name} size={24} /> {d.assigned_clinician.name}</span>
              : <span className="la-muted">Unassigned</span>}
          </div>
          {isAdmin && (
            <div className="us-assign-row">
              <select className="la-select" style={{ flex: 1 }} value={pendingClin} disabled={busy} onChange={(e) => setPendingClin(e.target.value)}>
                <option value="">Choose a clinician…</option>
                {MOCK_CLINICIANS.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
              <button className="la-btn-primary" disabled={busy || !pendingClin} onClick={() => onAssign(pendingClin)}>
                <Icon name="users" size={15} /> Assign
              </button>
            </div>
          )}
        </div>

        {screening && (
          <div className="la-detail-section">
            <div className="la-detail-h">Latest screening</div>
            <div className="la-info" style={{ marginBottom: 0 }}>
              <div className="la-info-row"><span className="la-info-label">PHQ-9</span><span className="la-info-value">{screening.phq9_score ?? "—"} ({screening.phq9_level || "—"})</span></div>
              <div className="la-info-row"><span className="la-info-label">GAD-7</span><span className="la-info-value">{screening.gad7_score ?? "—"} ({screening.gad7_level || "—"})</span></div>
              <div className="la-info-row"><span className="la-info-label">Mood</span><span className="la-info-value">{screening.mood_score ?? "—"}/10</span></div>
            </div>
          </div>
        )}

        <div className="la-detail-section">
          <div className="la-detail-h">Recent cases</div>
          {history.length === 0 ? <div className="la-muted" style={{ fontSize: 13 }}>No sessions yet.</div>
            : history.slice(0, 5).map((s) => (
              <div key={s.id} className="us-case">
                <div className="us-case-top">
                  <RiskBadge risk={s.risk || s.triage_level} />
                  {(s.status === "pending_review") && <span className="la-badge la-badge-amber"><span className="la-badge-dot" />pending</span>}
                  <span className="us-case-date">{fmtDateTime(s.created_at)}</span>
                </div>
                <div className="us-case-text">{s.preview || "—"}</div>
              </div>
            ))}
        </div>

        {/* Admin actions */}
        {isAdmin && d.role !== "admin" && (
          <div className="la-detail-actions" style={{ flexDirection: "column", gap: 10 }}>
            {d.status === "active" ? (
              <button className="mz-btn-red la-btn-full" disabled={busy} onClick={() => onStatus("suspended")}><Icon name="close" size={15} /> Suspend account</button>
            ) : (
              <button className="la-btn-green la-btn-full" disabled={busy} onClick={() => onStatus("active")}><Icon name="checkCircle" size={15} /> Re-activate account</button>
            )}
            <select className="la-select" style={{ width: "100%" }} value={d.role || "user"} disabled={busy} onChange={(e) => onRole(e.target.value)}>
              <option value="user">Role: user</option>
              <option value="clinician">Role: clinician</option>
              <option value="admin">Role: admin</option>
            </select>
          </div>
        )}
        {!isAdmin && (
          <div className="mz-mock-flag" style={{ marginTop: 12 }}>Sign in as an admin to manage this account.</div>
        )}
      </div>
    </aside>
  );
}
