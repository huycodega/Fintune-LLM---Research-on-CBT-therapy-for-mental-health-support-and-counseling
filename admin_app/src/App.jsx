import { useState, useEffect } from "react";
import { getUser, clearSession, api } from "./api.js";
import { initials, displayName } from "./ui.jsx";
import Login from "./pages/Login.jsx";
import Overview from "./pages/Overview.jsx";
import Cases from "./pages/Cases.jsx";
import Crisis from "./pages/Crisis.jsx";
import UsersAdmin from "./pages/UsersAdmin.jsx";
import ModerationAdmin from "./pages/ModerationAdmin.jsx";
import LessonsAdmin from "./pages/LessonsAdmin.jsx";
import ResourcesAdmin from "./pages/ResourcesAdmin.jsx";

/* Self-contained la-* pages bring their own dark-navy shell. */
const LA_PAGES = {
  users:      UsersAdmin,
  moderation: ModerationAdmin,
  lessons:    LessonsAdmin,
  resources:  ResourcesAdmin,
};

const NAV = [
  { id: "overview",   icon: "📊", label: "Overview" },
  { id: "users",      icon: "👥", label: "User management" },
  { id: "cases",      icon: "📋", label: "Cases to handle", badgeKey: "pending" },
  { id: "crisis",     icon: "🚨", label: "Crisis control", badgeKey: "crisis" },
  { id: "moderation", icon: "🤖", label: "AI Moderation" },
  { id: "lessons",    icon: "📚", label: "CBT Lessons" },
  { id: "resources",  icon: "🗂️", label: "Resources" },
];

const PAGE_META = {
  overview: { title: "Overview", sub: "System health & key metrics" },
  users:    { title: "User management", sub: "Accounts, status & per-user case history" },
  cases:    { title: "Cases to handle", sub: "Human-in-the-loop review queue" },
  crisis:   { title: "Crisis control", sub: "L0/L1 escalations across all accounts" },
};

function Sidebar({ page, onNav, badges }) {
  return (
    <aside className="admin-sidebar">
      <div className="admin-logo">
        <div className="admin-logo-icon">🌿</div>
        <div className="admin-logo-text">MindCare AI<small>Admin console</small></div>
      </div>

      <nav className="admin-nav">
        {NAV.map((n) => {
          const badge = n.badgeKey ? badges[n.badgeKey] : 0;
          return (
            <button key={n.id}
                    className={`admin-nav-item ${page === n.id ? "active" : ""}`}
                    onClick={() => onNav(n.id)}>
              <span className="admin-nav-icon">{n.icon}</span>
              {n.label}
              {badge > 0 && <span className="admin-nav-badge">{badge}</span>}
            </button>
          );
        })}
      </nav>

      <div className="admin-companion">
        <div className="admin-companion-title">Clinical oversight</div>
        <div className="admin-companion-text">
          Every crisis case and account action is logged for compliance.
        </div>
      </div>
    </aside>
  );
}

function Topbar({ page, user, onLogout, search, onSearch }) {
  const [menu, setMenu] = useState(false);
  const meta = PAGE_META[page] || {};
  const showSearch = page === "users" || page === "crisis";
  return (
    <header className="admin-topbar">
      <div>
        <div className="admin-page-title">{meta.title}</div>
        <div className="admin-page-sub">{meta.sub}</div>
      </div>

      {showSearch && (
        <div className="admin-search">
          <span className="admin-search-icon">🔍</span>
          <input placeholder="Search name or email…" value={search}
                 onChange={(e) => onSearch(e.target.value)} />
        </div>
      )}

      <button className="admin-topbar-btn" style={{ marginLeft: showSearch ? 0 : "auto" }}
              title="Notifications">
        🔔<span className="admin-topbar-badge">3</span>
      </button>

      <div className="admin-profile-menu-wrap">
        <button className="admin-profile" onClick={() => setMenu((o) => !o)}
                style={{ background: "none", border: 0 }}>
          <div className="admin-avatar">{initials(user?.username)}</div>
          <div style={{ textAlign: "left" }}>
            <div className="admin-profile-name">{displayName(user?.username)}</div>
            <div className="admin-profile-role">{user?.role}</div>
          </div>
          <span style={{ color: "var(--ink-faint)" }}>{menu ? "▴" : "▾"}</span>
        </button>
        {menu && (
          <>
            <div className="admin-overlay" onClick={() => setMenu(false)} />
            <div className="admin-menu">
              <button className="admin-menu-item danger"
                      onClick={() => { setMenu(false); onLogout(); }}>
                🚪 Sign out
              </button>
            </div>
          </>
        )}
      </div>
    </header>
  );
}

export default function App() {
  const [user, setUser] = useState(getUser());
  const [page, setPage] = useState("overview");
  const [search, setSearch] = useState("");
  const [badges, setBadges] = useState({ pending: 0, crisis: 0 });

  // Lightweight badge poll so the sidebar shows live counts.
  useEffect(() => {
    if (!user) return;
    let alive = true;
    async function poll() {
      try {
        const o = await api.overview();
        if (alive) setBadges({ pending: o.pending_review, crisis: o.crisis_open });
      } catch { /* ignore */ }
    }
    poll();
    const t = setInterval(poll, 15000);
    return () => { alive = false; clearInterval(t); };
  }, [user]);

  function logout() { clearSession(); setUser(null); }
  function nav(p) { setPage(p); setSearch(""); }

  if (!user) return <Login onAuth={setUser} />;

  // la-* pages render their own full dark-navy shell.
  if (LA_PAGES[page]) {
    const LaPage = LA_PAGES[page];
    return <LaPage onLogout={logout} onNav={nav} />;
  }

  const knownOld = ["overview", "cases", "crisis"];
  return (
    <div className="admin-shell">
      <Sidebar page={page} onNav={nav} badges={badges} />
      <div className="admin-main">
        <Topbar page={page} user={user} onLogout={logout}
                search={search} onSearch={setSearch} />
        <div className="admin-content">
          {page === "overview" && <Overview onNav={nav} />}
          {page === "cases" && <Cases />}
          {page === "crisis" && <Crisis search={search} />}
          {!knownOld.includes(page) && (
            <div className="admin-placeholder">
              <div className="admin-placeholder-icon">🚧</div>
              <h2>Coming soon</h2>
              <p>This section hasn’t been built yet.</p>
              <button className="admin-btn" onClick={() => nav("overview")}>Back to Overview</button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
