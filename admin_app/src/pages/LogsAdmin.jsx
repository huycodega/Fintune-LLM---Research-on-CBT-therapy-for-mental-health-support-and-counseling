import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Icon from "../admin/Icon.jsx";
import Sidebar from "../admin/Sidebar.jsx";
import TopBar from "../admin/TopBar.jsx";
import { api } from "../api.js";
import { DemoNotice, updatedNow } from "../ui.jsx";

const BEFORE = { role: "user", status: "active", phone: "0987654321" };
const AFTER = { role: "counselor", status: "active", phone: "0987654321" };
const USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36";

const DEMO_LOGS = [
  ["log-01", "19/06/2026 09:15:33", "Admin", "Administrator", "Update User", "U0223 - Minh Anh", "113.160.22.45", "Chrome 125 / Windows 11", "Success"],
  ["log-02", "19/06/2026 09:12:08", "Trần Quang Huy", "Administrator", "Login", "-", "203.162.4.18", "Safari 17.5 / iOS 17.5", "Success"],
  ["log-03", "19/06/2026 09:08:47", "System", "System", "Export Data", "User report", "10.0.0.15", "API Client", "Success"],
  ["log-04", "19/06/2026 09:07:21", "Admin", "Administrator", "Delete User Data", "U0187 - Trần Quang Huy", "113.160.22.45", "Chrome 125 / Windows 11", "Success"],
  ["log-05", "19/06/2026 09:05:11", "Unknown", "Unidentified", "Failed Login", "admin", "171.244.33.12", "Chrome 124 / Windows 10", "Failed"],
  ["log-06", "19/06/2026 09:03:55", "Lê Thanh Tâm", "Administrator", "Update Role", "U0312 - Lê Thanh Tâm", "117.0.56.201", "Edge 125 / Windows 11", "Success"],
  ["log-07", "19/06/2026 09:02:31", "Phạm Gia Bảo", "Administrator", "Create User", "U0456 - Phạm Gia Bảo", "123.18.45.67", "Chrome 125 / Windows 11", "Success"],
  ["log-08", "19/06/2026 08:59:44", "System", "System", "Backup Data", "Database", "10.0.0.15", "Backup Service", "Success"],
  ["log-09", "19/06/2026 08:57:10", "Unknown", "Unidentified", "Unauthorized Access", "/api/admin/users", "198.51.100.23", "curl/7.81.0", "Warning"],
  ["log-10", "19/06/2026 08:55:02", "Đỗ Minh Khoa", "Administrator", "Approve Post", "P0123 - Stress while studying...", "113.177.9.34", "Chrome 125 / Windows 11", "Success"],
].map(([id, time, actor, role, action, target, ip, device, status], index) => ({
  id, time, actor, role, action, target, ip, device, status,
  traceId: index === 0 ? "a8f7c2e9b1d44f3a" : `7cf4b21e4a0d${String(index).padStart(4, "0")}`,
  userAgent: device.includes("Chrome 125") ? USER_AGENT : device,
  method: action.startsWith("Update") ? "PUT" : action.startsWith("Delete") ? "DELETE" : "POST",
  path: index === 0 ? "/api/admin/users/U0223" : `/api/admin/audit/${id}`,
  result: status === "Success" ? "200 OK" : status === "Failed" ? "401 FAILED" : "403 WARNING",
  processingTime: index === 0 ? "320ms" : `${180 + index * 17}ms`,
  before: index === 0 ? BEFORE : null,
  after: index === 0 ? AFTER : null,
}));

const CRITICAL = [
  { time: "09:07", title: "Failed Login", description: "171.244.33.12", tone: "danger" },
  { time: "08:57", title: "Unauthorized Access", description: "198.51.100.23", tone: "warning" },
  { time: "07:45", title: "Delete User Data", description: "U0099 - Nguyễn Hoài An", tone: "danger" },
];

function reducedMotion() {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
}

function CountUp({ value, duration = 850 }) {
  const [display, setDisplay] = useState(reducedMotion() ? value : "0");
  const raf = useRef(0);
  useEffect(() => {
    const target = Number(String(value).replace(/,/g, ""));
    if (!Number.isFinite(target) || reducedMotion()) { setDisplay(value); return undefined; }
    const start = performance.now();
    const tick = (now) => {
      const progress = Math.min((now - start) / duration, 1);
      const next = Math.round(target * (1 - Math.pow(1 - progress, 3)));
      setDisplay(next.toLocaleString("en-US"));
      if (progress < 1) raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [value, duration]);
  return display;
}

function humanize(value) {
  return String(value || "System Event").replace(/[_-]+/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatAuditTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value || "-";
  return date.toLocaleString("en-GB", { hour12: false }).replace(",", "");
}

function auditToLog(row, index) {
  const action = humanize(row.action);
  const lowered = action.toLowerCase();
  // Backend now derives severity server-side; fall back to text matching for
  // any legacy rows that predate the field.
  const severity = row.severity || (lowered.includes("failed") ? "failed" : lowered.includes("unauthorized") ? "warning" : "success");
  const status = severity === "failed" ? "Failed" : severity === "warning" ? "Warning" : "Success";
  const target = row.resource_type ? `${humanize(row.resource_type)}${row.resource_id ? ` - ${String(row.resource_id).slice(0, 8)}` : ""}` : "-";
  const detail = row.detail && Object.keys(row.detail).length ? row.detail : null;
  return {
    id: row.id || `audit-${index}`, time: formatAuditTime(row.ts), actor: row.actor || "System",
    role: humanize(row.role || "System"), action, target, ip: row.ip || "-",
    device: row.user_agent || "API Client", status,
    traceId: String(row.id || `trace-${index}`).replace(/-/g, "").slice(0, 16),
    userAgent: row.user_agent || "API Client",
    method: lowered.includes("delete") ? "DELETE" : lowered.includes("update") ? "PUT" : "POST",
    path: `/api/admin/${row.resource_type || "audit"}${row.resource_id ? `/${row.resource_id}` : ""}`,
    result: status === "Success" ? "200 OK" : status === "Failed" ? "401 FAILED" : "403 WARNING",
    processingTime: "-", before: null, after: detail,
  };
}

// Maps the API stats payload to the four headline cards (label/icon/tone are
// fixed; value + trend come from the backend).
function statCardsFromApi(stats) {
  if (!stats) return null;
  const t = stats.trends || {};
  const fmt = (n) => Number(n || 0).toLocaleString("en-US");
  const pct = (k) => `${(t[k]?.pct ?? 0)}%`;
  const dir = (k) => (t[k]?.direction === "down" ? "down" : "up");
  return [
    { icon: "bars", tone: "purple", label: "Total Events Today", value: fmt(stats.total_events), trend: pct("total_events"), direction: dir("total_events") },
    { icon: "lock", tone: "orange", label: "Failed Logins", value: fmt(stats.failed_logins), trend: pct("failed_logins"), direction: dir("failed_logins") },
    { icon: "shieldCheck", tone: "blue", label: "Admin Actions", value: fmt(stats.admin_actions), trend: pct("admin_actions"), direction: dir("admin_actions") },
    { icon: "download", tone: "green", label: "Data Exports", value: fmt(stats.data_exports), trend: pct("data_exports"), direction: dir("data_exports") },
  ];
}

function StatCard({ icon, tone, label, value, trend, direction, index }) {
  return <article className="lg-stat lg-rise" style={{ "--i": index }}>
    <span className={`lg-stat-icon ${tone}`}><Icon name={icon} size={23} /></span>
    <div><div className="lg-stat-label">{label}</div><div className="lg-stat-value"><CountUp value={value} /></div>
      <div className={`lg-stat-trend ${direction === "down" ? "down" : "up"}`}><Icon name={direction === "down" ? "arrowDown" : "arrowUp"} size={12} />{trend} vs yesterday</div>
    </div>
  </article>;
}

function Actor({ row }) {
  const initials = row.actor.split(/\s+/).map((part) => part[0]).slice(0, 2).join("").toUpperCase();
  return <div className="lg-actor"><span className={`lg-actor-avatar ${row.actor === "System" ? "system" : row.actor === "Unknown" ? "unknown" : ""}`}>{row.actor === "System" ? <img src="/mindcare-mascot.svg" alt="" /> : initials}</span><span><b>{row.actor}</b><small>{row.role}</small></span></div>;
}

function StatusBadge({ status }) {
  return <span className={`lg-status ${status.toLowerCase()}`}><i />{status}</span>;
}

function JsonBlock({ label, value }) {
  return <div className="lg-json-wrap"><div className="lg-detail-label">{label}</div><pre>{JSON.stringify(value || {}, null, 2)}</pre></div>;
}

function DetailPanel({ row, onClose }) {
  return <section className="lg-detail-card lg-panel-in" key={row.id}>
    <div className="lg-side-title"><h2>Event Details</h2><button onClick={onClose} aria-label="Close event details"><Icon name="close" size={18} /></button></div>
    <div className="lg-detail-body lg-xfade">
      <h3>Request Information</h3>
      <dl className="lg-detail-grid">
        <dt>Time</dt><dd>{row.time}</dd><dt>Trace ID</dt><dd className="mono">{row.traceId}</dd>
        <dt>IP</dt><dd>{row.ip}</dd><dt>Device</dt><dd>{row.device}</dd>
        <dt>User Agent</dt><dd className="wide">{row.userAgent}</dd>
        <dt>Method</dt><dd className="wide"><span className={`lg-method ${row.method.toLowerCase()}`}>{row.method}</span><span className="mono">{row.path}</span></dd>
        <dt>Result</dt><dd><span className={`lg-result ${row.status.toLowerCase()}`}>{row.result}</span></dd>
        <dt>Processing Time</dt><dd>{row.processingTime}</dd>
      </dl>
      <div className="lg-change-section"><h3>Data Changes</h3>
        {row.before || row.after ? <><JsonBlock label="Before Change" value={row.before} /><JsonBlock label="After Change" value={row.after} /></> : <div className="lg-no-change">No structured data changes were recorded for this event.</div>}
      </div>
    </div>
  </section>;
}

// Derive critical events from the real audit log (failed / warning rows).
// Falls back to the sample list only when running on demo data.
function criticalFrom(logs, demo) {
  if (demo) return CRITICAL;
  return logs
    .filter((row) => row.status === "Failed" || row.status === "Warning")
    .slice(0, 6)
    .map((row) => ({
      time: (row.time || "").split(" ")[1] || row.time || "",
      title: row.action,
      description: row.target && row.target !== "-" ? row.target : row.ip,
      tone: row.status === "Failed" ? "danger" : "warning",
    }));
}

function CriticalEvents({ logs, demo }) {
  const items = criticalFrom(logs, demo);
  return <section className="lg-critical lg-panel-in"><div className="lg-side-title"><h2>Recent Critical Events</h2></div>
    {items.length === 0
      ? <p className="lg-critical-empty">No critical events recorded.</p>
      : <div className="lg-critical-list">{items.map((item, index) => <div className="lg-critical-item" style={{ "--i": index }} key={`${item.time}-${item.title}-${index}`}>
          <span className={`lg-critical-icon ${item.tone}`}>{item.tone === "warning" ? <Icon name="alert" size={15} /> : <span />}</span>
          <time>{item.time}</time><div><b>{item.title}</b><small>{item.description}</small></div>
        </div>)}</div>}
    {items.length > 0 && <button className="lg-critical-btn">View All Critical Events <Icon name="chevronRight" size={15} /></button>}
  </section>;
}

function StatSkel() {
  return (
    <article className="lg-stat">
      <div className="la-skel la-skel-icon" />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="la-skel la-skel-line" style={{ width: "55%" }} />
        <div className="la-skel la-skel-line" style={{ width: "42%", height: 22, margin: "6px 0" }} />
        <div className="la-skel la-skel-line" style={{ width: "60%" }} />
      </div>
    </article>
  );
}
// Keeps the real page frame (stat grid, filter bar, table, side panel) and
// shimmers each part, matching the loading style used on every other page.
function LoadingView() {
  return (
    <>
      <div className="la-content-left">
        <section className="lg-stats">
          {Array.from({ length: 4 }, (_, i) => <StatSkel key={i} />)}
        </section>
        <section className="lg-filterbar">
          {Array.from({ length: 5 }, (_, i) => <div className="la-skel" key={i} style={{ height: 37, borderRadius: 9 }} />)}
        </section>
        <section className="lg-table-card" style={{ padding: 14 }}>
          {Array.from({ length: 8 }, (_, i) => <div className="la-skel la-skel-line" key={i} style={{ height: 22, margin: "12px 0" }} />)}
        </section>
      </div>
      <aside className="la-detail-single">
        <div className="lg-detail-card" style={{ padding: 15 }}>
          <div className="la-skel la-skel-line" style={{ width: "50%", marginBottom: 14 }} />
          <div className="la-skel" style={{ height: 330, borderRadius: 12 }} />
        </div>
        <div className="lg-critical" style={{ padding: 15, marginTop: 16 }}>
          <div className="la-skel la-skel-line" style={{ width: "45%", marginBottom: 12 }} />
          <div className="la-skel" style={{ height: 150, borderRadius: 12 }} />
        </div>
      </aside>
    </>
  );
}

export default function LogsAdmin({ onLogout, onNav }) {
  const [logs, setLogs] = useState([]);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [demo, setDemo] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [eventType, setEventType] = useState("All");
  const [actor, setActor] = useState("All");
  const [severity, setSeverity] = useState("All");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [menu, setMenu] = useState(null);
  const [stats, setStats] = useState(null);

  const load = useCallback(async (refresh = false) => {
    refresh ? setRefreshing(true) : setLoading(true);
    try {
      // Pull a generous window; filtering + pagination stay client-side so the
      // existing table UX is unchanged. Stats come from the same payload.
      const payload = await api.logs({ page_size: 200 });
      const live = (payload.logs || []).map(auditToLog);
      const rows = live.length ? live : DEMO_LOGS;
      setLogs(rows); setStats(payload.stats || null);
      setSelected((current) => rows.find((row) => row.id === current?.id) || rows[0] || null); setDemo(!live.length);
    } catch (error) {
      console.error("System logs API unavailable:", error);
      setLogs(DEMO_LOGS); setSelected((current) => DEMO_LOGS.find((row) => row.id === current?.id) || DEMO_LOGS[0]); setDemo(true); setStats(null);
    } finally {
      setLoading(false); setRefreshing(false);
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  const actors = useMemo(() => ["All", ...new Set(logs.map((row) => row.actor))], [logs]);
  const eventTypes = useMemo(() => ["All", ...new Set(logs.map((row) => row.action))], [logs]);
  const filtered = useMemo(() => logs.filter((row) => {
    const query = search.trim().toLowerCase();
    return (eventType === "All" || row.action === eventType) && (actor === "All" || row.actor === actor) &&
      (severity === "All" || row.status === severity) && (!query || `${row.ip} ${row.target}`.toLowerCase().includes(query));
  }), [logs, eventType, actor, severity, search]);
  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize));
  const visible = filtered.slice((page - 1) * pageSize, page * pageSize);
  useEffect(() => { setPage(1); }, [eventType, actor, severity, search, pageSize]);

  const filterPanel = <><label>Event type<select value={eventType} onChange={(event) => setEventType(event.target.value)}>{eventTypes.map((value) => <option key={value}>{value}</option>)}</select></label><label>Severity<select value={severity} onChange={(event) => setSeverity(event.target.value)}><option>All</option><option>Success</option><option>Failed</option><option>Warning</option></select></label><button onClick={() => setPage(1)}>Apply Filters</button></>;

  return <div className="la-shell lg-shell">
    {mobileOpen && <button className="lg-nav-scrim" onClick={() => setMobileOpen(false)} aria-label="Close navigation" />}
    <Sidebar active="logs" onNav={onNav} mobileOpen={mobileOpen} onClose={() => setMobileOpen(false)} />
    <main className="la-main lg-main">
      <TopBar title="System Logs" subtitle={updatedNow()} searchPlaceholder="Search users, email, phone..." onLogout={onLogout}
        onMenu={() => setMobileOpen(true)} filterPanel={filterPanel} />
      <div className={`la-content ${(selected || loading) ? "" : "la-content-nopanel"} lg-content`}>{loading ? <LoadingView /> : <>
        <div className="la-content-left">
          {demo && <div style={{ marginBottom: 12 }}><DemoNotice>Sample data shown — audit log API isn't connected yet.</DemoNotice></div>}
          <section className="lg-stats">
            {(statCardsFromApi(stats) || [
              { icon: "bars", tone: "purple", label: "Total Events Today", value: "12,842", trend: "18.6%", direction: "up" },
              { icon: "lock", tone: "orange", label: "Failed Logins", value: "48", trend: "12.5%", direction: "down" },
              { icon: "shieldCheck", tone: "blue", label: "Admin Actions", value: "324", trend: "9.4%", direction: "up" },
              { icon: "download", tone: "green", label: "Data Exports", value: "27", trend: "3.7%", direction: "down" },
            ]).map((card, index) => <StatCard key={card.label} {...card} index={index} />)}
          </section>
          <section className="lg-filterbar lg-rise" style={{ "--i": 4 }}>
            <label className="lg-time-filter"><span>Time Range</span><button><span>19/06/2026 00:00 - 19/06/2026 23:59</span><Icon name="calendar" size={16} /></button></label>
            <label><span>Event Type</span><select value={eventType} onChange={(event) => setEventType(event.target.value)}>{eventTypes.map((value) => <option key={value}>{value}</option>)}</select></label>
            <label><span>Actor</span><select value={actor} onChange={(event) => setActor(event.target.value)}>{actors.map((value) => <option key={value}>{value}</option>)}</select></label>
            <label><span>Severity</span><select value={severity} onChange={(event) => setSeverity(event.target.value)}><option>All</option><option>Success</option><option>Failed</option><option>Warning</option></select></label>
            <label className="lg-log-search"><span>&nbsp;</span><div><Icon name="search" size={15} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search by IP or object..." /></div></label>
          </section>
          <section className="lg-table-card">
            <div className="lg-table-scroll" key={page}><table className="lg-table"><thead><tr>{["Time", "Actor", "Action", "Target", "IP", "Device", "Status", "Details"].map((heading) => <th key={heading}>{heading}</th>)}</tr></thead>
              <tbody>{visible.map((row, index) => <tr key={row.id} className={selected?.id === row.id ? "selected" : ""} style={{ "--i": index }} onClick={() => setSelected(row)}>
                <td>{row.time}</td><td><Actor row={row} /></td><td><b>{row.action}</b></td><td>{row.target}</td><td className="mono">{row.ip}</td><td>{row.device}</td><td><StatusBadge status={row.status} /></td>
                <td className="lg-menu-cell" onClick={(event) => event.stopPropagation()}><button className="lg-dots" onClick={() => setMenu(menu === row.id ? null : row.id)} aria-label={`Actions for ${row.action}`}><Icon name="dots" size={18} /></button>{menu === row.id && <div className={`lg-row-menu ${index >= visible.length - 2 ? "up" : ""}`}><button onClick={() => { setSelected(row); setMenu(null); }}>View details</button><button onClick={() => { navigator.clipboard?.writeText(row.traceId); setMenu(null); }}>Copy trace ID</button></div>}</td>
              </tr>)}</tbody></table>{!visible.length && <div className="lg-empty">No events match the selected filters.</div>}</div>
            <div className="lg-pagination"><span>Showing {filtered.length ? (page - 1) * pageSize + 1 : 0} to {Math.min(page * pageSize, filtered.length)} of {demo ? "12,842" : filtered.length.toLocaleString("en-US")} events</span><div className="lg-page-controls"><button onClick={() => setPage(1)} aria-label="First page"><Icon name="chevronsLeft" size={14} /></button><button onClick={() => setPage(Math.max(1, page - 1))} aria-label="Previous page"><Icon name="chevronLeft" size={14} /></button>{[1, 2, 3].map((number) => <button key={number} className={page === number ? "active" : ""} onClick={() => setPage(Math.min(number, pageCount))}>{number}</button>)}<span>...</span><button onClick={() => setPage(pageCount)}>{demo ? "1,285" : pageCount}</button><button onClick={() => setPage(Math.min(pageCount, page + 1))} aria-label="Next page"><Icon name="chevronRight" size={14} /></button></div><select value={pageSize} onChange={(event) => setPageSize(Number(event.target.value))}><option value={10}>10 / page</option><option value={20}>20 / page</option><option value={50}>50 / page</option></select></div>
          </section>
        </div>
        <aside className="la-detail la-detail-single">{selected && <DetailPanel row={selected} onClose={() => setSelected(null)} />}<CriticalEvents logs={logs} demo={demo} /></aside>
      </>}</div>
    </main>
  </div>;
}
