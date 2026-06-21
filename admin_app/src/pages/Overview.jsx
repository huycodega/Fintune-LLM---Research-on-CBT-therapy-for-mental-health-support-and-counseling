import { useState, useEffect } from "react";
import { api } from "../api.js";
import { StatCard, Empty } from "../ui.jsx";
import AppShell from "../admin/AppShell.jsx";

export default function Overview({ onNav, onLogout }) {
  const [o, setO] = useState(null);
  const [stats, setStats] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.overview().then(setO).catch((e) => setErr(e.message));
    api.stats().then(setStats).catch(() => {});
  }, []);

  const byLevel = stats?.by_triage_level || {};

  return (
    <AppShell active="overview" onNav={onNav} onLogout={onLogout}
              title="Overview" subtitle="System health & key metrics">
      {err ? <Empty icon="⚠️" text={err} /> : !o ? <div className="loading">Loading overview…</div> : (
    <>
      <div className="stat-row">
        <StatCard icon="users" color="purple" value={o.total_users} label="Total users" />
        <StatCard icon="checkCircle" color="green" value={o.active_7d} label="Active (7 days)" />
        <StatCard icon="cases" color="amber" value={o.pending_review} label="Cases pending review" />
        <StatCard icon="alert" color="red" value={o.crisis_open} label="Open crisis cases" />
        <StatCard icon="lock" color="blue" value={o.suspended_users} label="Suspended accounts" />
      </div>

      <div className="split">
        <div className="panel">
          <div className="panel-head"><div className="panel-title">Triage distribution</div></div>
          <div style={{ padding: 18 }}>
            {["L0", "L1", "L2", "L3"].map((lv) => {
              const total = Object.values(byLevel).reduce((a, b) => a + b, 0) || 1;
              const n = byLevel[lv] || 0;
              const pct = Math.round((n / total) * 100);
              const labels = { L0: "Crisis (no AI)", L1: "High — clinician", L2: "Moderate", L3: "Routine" };
              return (
                <div key={lv} style={{ marginBottom: 14 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                    <span><span className={`pill ${lv}`} style={{ marginRight: 8 }}>{lv}</span>
                      <span style={{ color: "var(--ink-soft)", fontSize: 13 }}>{labels[lv]}</span></span>
                    <b>{n}</b>
                  </div>
                  <div style={{ height: 8, background: "var(--bg)", borderRadius: 6, overflow: "hidden" }}>
                    <div style={{ width: `${pct}%`, height: "100%",
                      background: lv === "L0" ? "var(--red)" : lv === "L1" ? "var(--amber)"
                        : lv === "L2" ? "var(--blue)" : "var(--green)" }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="panel">
          <div className="panel-head"><div className="panel-title">Quick actions</div></div>
          <div style={{ padding: 18, display: "flex", flexDirection: "column", gap: 10 }}>
            <button className="btn primary block" onClick={() => onNav("cases")}>
              📋 Handle {o.pending_review} pending case{o.pending_review === 1 ? "" : "s"}
            </button>
            <button className="btn red block" onClick={() => onNav("crisis")}>
              🚨 Review {o.crisis_open} open crisis case{o.crisis_open === 1 ? "" : "s"}
            </button>
            <button className="btn block" onClick={() => onNav("users")}>
              👥 Manage users
            </button>
            <div className="banner info" style={{ marginTop: 6 }}>
              Total sessions processed: <b>{stats?.total_sessions ?? "—"}</b>
            </div>
          </div>
        </div>
      </div>
    </>
      )}
    </AppShell>
  );
}
