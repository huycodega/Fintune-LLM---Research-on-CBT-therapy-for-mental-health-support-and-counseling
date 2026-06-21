import { useState, useEffect } from "react";
import { getUser, clearSession, api } from "./api.js";
import { initials, displayName } from "./ui.jsx";
import Login from "./pages/Login.jsx";
import DashboardPage from "./components/dashboard/DashboardPage.jsx";
import Users from "./pages/Users.jsx";
import CaseManagementPage from "./components/cases/CaseManagementPage.jsx";
import ModerationPage from "./pages/ai-moderation/ModerationPage.jsx";

const NAV = [
  { id: "overview", icon: "📊", label: "Tổng quan" },
  { id: "users",    icon: "👥", label: "User management" },
  { id: "moderation", icon: "🤖", label: "AI Moderation", badgeKey: "pending" },
  { id: "cases",    icon: "📋", label: "Ca cần xử lý" },
];

const PAGE_META = {
  overview: { title: "Tổng quan", sub: "Chỉ số vận hành và tín hiệu cần chú ý" },
  users:    { title: "User management", sub: "Accounts, status & per-user case history" },
  moderation: { title: "AI Moderation", sub: "Kiểm duyệt phản hồi AI và mức độ rủi ro" },
  cases:    { title: "Ca cần xử lý", sub: "Phân công và theo dõi ca rủi ro" },
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
  const showSearch = page === "users";
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
  const [selectedUserId, setSelectedUserId] = useState(null);
  const [badges, setBadges] = useState({ pending: 0 });

  // Lightweight badge poll so the sidebar shows live counts.
  useEffect(() => {
    if (!user) return;
    let alive = true;
    async function poll() {
      try {
        const o = await api.overview();
        if (alive) setBadges({ pending: o.pending_review });
      } catch { /* ignore */ }
    }
    poll();
    const t = setInterval(poll, 15000);
    return () => { alive = false; clearInterval(t); };
  }, [user]);

  function logout() { clearSession(); setUser(null); }
  function nav(p, userId = null) { setPage(p); setSearch(""); setSelectedUserId(userId); }

  if (!user) return <Login onAuth={setUser} />;

  return (
    <div className="admin-shell">
      <Sidebar page={page} onNav={nav} badges={badges} />
      <div className="admin-main">
        <Topbar page={page} user={user} onLogout={logout}
                search={search} onSearch={setSearch} />
        <div className="admin-content">
          {page === "overview" && <DashboardPage onNav={nav} />}
          {page === "users" && <Users search={search} selectedUserId={selectedUserId} onOpenCase={() => setPage("cases")} />}
          {page === "moderation" && <ModerationPage />}
          {page === "cases" && <CaseManagementPage onNav={nav} />}
        </div>
      </div>
    </div>
  );
}
