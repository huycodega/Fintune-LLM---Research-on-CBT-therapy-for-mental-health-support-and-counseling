import { useState, useEffect } from "react";
import { api } from "../api.js";
import { Avatar, StatCard, Empty, displayName, fmtDateTime } from "../ui.jsx";
import AppShell from "../admin/AppShell.jsx";

const VIEW_TABS = [
  { id: "open", label: "Open" },
  { id: "all", label: "All" },
  { id: "L0", label: "Crisis (L0)" },
  { id: "L1", label: "High risk (L1)" },
];

export default function Crisis({ onNav, onLogout }) {
  const [data, setData] = useState(null);
  const [view, setView] = useState("open");
  const [windowDays, setWindowDays] = useState(30);
  const [search, setSearch] = useState("");

  function load() {
    api.crisis(windowDays).then(setData).catch(() => setData({ crisis: [], counts: {} }));
  }
  useEffect(() => { load(); const t = setInterval(load, 12000); return () => clearInterval(t); },
    [windowDays]); // eslint-disable-line

  const all = data?.crisis || [];
  const c = data?.counts || {};

  let rows = all;
  if (view === "open") rows = all.filter((r) => !r.resolved);
  else if (view === "L0") rows = all.filter((r) => r.triage_level === "L0");
  else if (view === "L1") rows = all.filter((r) => r.triage_level === "L1");
  if (search) {
    const q = search.toLowerCase();
    rows = rows.filter((r) => r.username.toLowerCase().includes(q) ||
      (r.preview || "").toLowerCase().includes(q));
  }

  return (
    <AppShell active="crisis" onNav={onNav} onLogout={onLogout}
              title="Crisis Control" subtitle="L0/L1 escalations across all accounts"
              searchPlaceholder="Search name or message…" searchValue={search} onSearch={setSearch}>
      <div className="stat-row">
        <StatCard icon="alert" color="red" value={c.open ?? 0} label="Open crisis cases" />
        <StatCard icon="shield" color="amber" value={c.L0 ?? 0} label="L0 — crisis" />
        <StatCard icon="shieldCheck" color="blue" value={c.L1 ?? 0} label="L1 — high risk" />
        <StatCard icon="bars" color="purple" value={c.total ?? 0} label={`Total (${windowDays}d)`} />
      </div>

      <div className="panel">
        <div className="panel-head">
          <div className="filter-tabs">
            {VIEW_TABS.map((t) => (
              <button key={t.id} className={`filter-tab ${view === t.id ? "active" : ""}`}
                      onClick={() => setView(t.id)}>{t.label}</button>
            ))}
          </div>
          <div className="panel-tools">
            <select className="select" value={windowDays}
                    onChange={(e) => setWindowDays(Number(e.target.value))}>
              <option value={7}>Last 7 days</option>
              <option value={30}>Last 30 days</option>
              <option value={90}>Last 90 days</option>
            </select>
          </div>
        </div>

        {rows.length === 0 ? (
          <Empty icon="🕊️" text="No crisis cases in this view. That's good news." />
        ) : (
          <table className="table">
            <thead>
              <tr><th>Level</th><th>User</th><th>Flagged message</th>
                <th>Reason</th><th>State</th><th>When</th></tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.session_id} style={{ cursor: "default" }}>
                  <td><span className={`pill ${r.triage_level}`}>{r.triage_level}</span></td>
                  <td>
                    <div className="cell-user">
                      <Avatar name={r.username} />
                      <div className="cell-name">{displayName(r.username)}</div>
                    </div>
                  </td>
                  <td style={{ maxWidth: 300, color: "var(--ink-soft)" }}>
                    <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {r.preview}
                    </div>
                  </td>
                  <td style={{ maxWidth: 200, fontSize: 12, color: "var(--ink-faint)" }}>
                    <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {r.reason || "—"}
                    </div>
                  </td>
                  <td>{r.resolved
                    ? <span className="pill green"><span className="dot" />Handled</span>
                    : <span className="pill red"><span className="dot" />Open</span>}</td>
                  <td style={{ color: "var(--ink-soft)", whiteSpace: "nowrap" }}>{fmtDateTime(r.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="banner info" style={{ marginTop: 16 }}>
        L0 cases never receive an AI reply — the user is shown crisis resources immediately.
        L1 cases are routed to a clinician. Both appear here so admins retain full oversight.
      </div>
    </AppShell>
  );
}
