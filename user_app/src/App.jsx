import { useState, useEffect, useLayoutEffect } from "react";
import { getUser, clearSession, api } from "./api.js";
import Mascot from "./components/Mascot.jsx";
import Landing from "./pages/Landing.jsx";
import Login from "./pages/Login.jsx";
import Consent from "./pages/Consent.jsx";
import Intake from "./pages/Intake.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Chat from "./pages/Chat.jsx";
import SangLoc from "./pages/SangLoc.jsx";
import HoSo from "./pages/HoSo.jsx";
import BaiHoc from "./pages/BaiHoc.jsx";
import TaiNguyen from "./pages/TaiNguyen.jsx";
import TuVan from "./pages/TuVan.jsx";
import CaiDat from "./pages/CaiDat.jsx";
import MoodWidget from "./components/MoodWidget.jsx";
import NotifBell from "./components/NotifBell.jsx";

const NAV_ITEMS = [
  { id: "dashboard", icon: "home", label: "Home" },
  { id: "sangloc", icon: "shield", label: "Screening" },
  { id: "chat", icon: "bot", label: "AI Support" },
  { id: "baihoc", icon: "book", label: "Lessons" },
  { id: "tainguyen", icon: "folder", label: "Resources" },
  { id: "tuvan", icon: "expert", label: "Counselling" },
  { id: "hoso", icon: "user", label: "Profile" },
  { id: "caidat", icon: "settings", label: "Settings" },
];

const TOPBAR_TABS = [
  { id: "dashboard", icon: "home", label: "Home" },
  { id: "baihoc", icon: "book", label: "Lessons" },
  { id: "tainguyen", icon: "folder", label: "Resources" },
  { id: "chat", icon: "bot", label: "AI Support" },
];

function NavSvgIcon({ name }) {
  const common = {
    width: 22,
    height: 22,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 2,
    strokeLinecap: "round",
    strokeLinejoin: "round",
    "aria-hidden": "true",
  };

  if (name === "home") {
    return (
      <svg {...common} className="nav-svg-icon filled-home">
        <path d="M3 11.5 12 4l9 7.5" />
        <path d="M5.5 10.5V20h13v-9.5" />
        <path d="M9.5 20v-6h5v6" />
      </svg>
    );
  }
  if (name === "shield") {
    return (
      <svg {...common} className="nav-svg-icon">
        <path d="M12 3 19 6v5c0 4.4-2.8 8.4-7 10-4.2-1.6-7-5.6-7-10V6l7-3Z" />
        <path d="m9.5 12 1.7 1.7 3.6-4" />
      </svg>
    );
  }
  if (name === "bot") {
    return (
      <svg {...common} className="nav-svg-icon">
        <path d="M12 8V5" />
        <path d="M8 5h8" />
        <rect x="5" y="8" width="14" height="10" rx="5" />
        <path d="M9 13h.01" />
        <path d="M15 13h.01" />
        <path d="M9.5 17c1.6 1 3.4 1 5 0" />
      </svg>
    );
  }
  if (name === "book") {
    return (
      <svg {...common} className="nav-svg-icon">
        <path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v16H6.5A2.5 2.5 0 0 0 4 21V5.5Z" />
        <path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20" />
        <path d="M8 7h8" />
      </svg>
    );
  }
  if (name === "folder") {
    return (
      <svg {...common} className="nav-svg-icon">
        <path d="M3.5 6.5h6l2 2H20.5v10h-17v-12Z" />
        <path d="M3.5 8.5h17" />
      </svg>
    );
  }
  if (name === "expert") {
    return (
      <svg {...common} className="nav-svg-icon">
        <circle cx="9" cy="8" r="3.2" />
        <path d="M3.5 19a5.5 5.5 0 0 1 11 0" />
        <path d="M16 4.5c1.6-1.4 4-0.3 4 1.7 0 1.6-2 3-4 4.3-2-1.3-4-2.7-4-4.3 0-2 2.4-3.1 4-1.7Z" />
      </svg>
    );
  }
  if (name === "user") {
    return (
      <svg {...common} className="nav-svg-icon">
        <circle cx="12" cy="8" r="3.5" />
        <path d="M5.5 20a6.5 6.5 0 0 1 13 0" />
      </svg>
    );
  }
  return (
  <svg {...common} className="nav-svg-icon">
    <circle cx="12" cy="12" r="3.2" />
    <path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.05.05a2 2 0 0 1-2.83 2.83l-.05-.05A1.7 1.7 0 0 0 15 19.4a1.7 1.7 0 0 0-1 1.56V21a2 2 0 0 1-4 0v-.04A1.7 1.7 0 0 0 9 19.4a1.7 1.7 0 0 0-1.88.34l-.05.05a2 2 0 0 1-2.83-2.83l.05-.05A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-1.56-1H3a2 2 0 0 1 0-4h.04A1.7 1.7 0 0 0 4.6 9a1.7 1.7 0 0 0-.34-1.88l-.05-.05a2 2 0 0 1 2.83-2.83l.05.05A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-1.56V3a2 2 0 0 1 4 0v.04A1.7 1.7 0 0 0 15 4.6a1.7 1.7 0 0 0 1.88-.34l.05-.05a2 2 0 0 1 2.83 2.83l-.05.05A1.7 1.7 0 0 0 19.4 9a1.7 1.7 0 0 0 1.56 1H21a2 2 0 0 1 0 4h-.04A1.7 1.7 0 0 0 19.4 15Z" />
  </svg>
);
}
function Topbar({ activePage, onNav, user, onLogout, onMenu }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const initials = user?.username ? user.username.slice(0, 1).toUpperCase() : "U";
  const displayName = user?.username
    ? user.username.split("@")[0]
    : "You";

  return (
    <header className="app-topbar">
      {/* Hamburger — only shows on mobile (CSS) to open the nav drawer */}
      <button type="button" className="topbar-hamburger" onClick={onMenu} aria-label="Open menu">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
          <path d="M4 7h16M4 12h16M4 17h16" />
        </svg>
      </button>
      {/* Logo (aligned to sidebar width) — click to go Home */}
      <button
        type="button"
        className="topbar-logo-section"
        onClick={() => onNav("dashboard")}
        aria-label="Go to Home"
      >
        <div className="topbar-logo-icon"><Mascot variant="wave" size={30} /></div>
        <span className="topbar-brand">MindCare AI</span>
      </button>

      {/* Center tabs â€” only on Home/Dashboard */}
      {activePage === "dashboard" && (
        <nav className="topbar-tabs">
          {TOPBAR_TABS.map((tab) => (
            <button
              key={tab.id}
              className={`topbar-tab ${activePage === tab.id ? "active" : ""}`}
              onClick={() => onNav(tab.id)}
            >
              <span className="topbar-tab-icon"><NavSvgIcon name={tab.icon} /></span>
              {tab.label}
            </button>
          ))}
        </nav>
      )}

      {/* Right: notification + user */}
      <div className="topbar-right">
        <NotifBell onNav={onNav} />
        <div className="topbar-user-wrap">
          <button className="topbar-user-info" onClick={() => setMenuOpen((o) => !o)}>
            <div className="topbar-avatar">{initials}</div>
            <span className="topbar-username">{displayName}</span>
            <span className="topbar-caret">{menuOpen ? "▴" : "▾"}</span>
          </button>
          {menuOpen && (
            <>
              <div className="topbar-overlay" onClick={() => setMenuOpen(false)} />
              <div className="topbar-user-menu">
                <button className="user-menu-item" onClick={() => { setMenuOpen(false); onNav("hoso"); }}>
                  👤 Profile
                </button>
                <button className="user-menu-item" onClick={() => { setMenuOpen(false); onNav("caidat"); }}>
                  ⚙️ Settings
                </button>
                <div className="user-menu-divider" />
                <button className="user-menu-item user-menu-signout" onClick={() => { setMenuOpen(false); onLogout(); }}>
                  🚪 Sign out
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  );
}

function Sidebar({ activePage, onNav, open, onClose }) {
  return (
    <>
      {open && <div className="sidebar-backdrop" onClick={onClose} />}
      <nav className={`sidebar ${open ? "sidebar-open" : ""}`}>
      <div className="sidebar-nav">
        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            className={`nav-item ${activePage === item.id ? "active" : ""}`}
            onClick={() => onNav(item.id)}
          >
            <span className="nav-icon"><NavSvgIcon name={item.icon} /></span>
            {item.label}
          </button>
        ))}
      </div>

      {/* Bottom companion card */}
      <div className="sidebar-companion-card">
        <div className="sidebar-companion-title">You are not alone</div>
        <div className="sidebar-companion-text">
          MindCare AI is always here to listen and accompany you.
        </div>
        <div className="sidebar-companion-mascot">
          <svg className="sidebar-plant" width="70" height="70" viewBox="0 0 64 64" fill="none" aria-hidden="true">
            <path d="M20 60h24l-2-12H22z" fill="#E4F0EC" stroke="#7FB8A6" strokeWidth="2" strokeLinejoin="round" />
            <path d="M32 48V30" stroke="#3F9E78" strokeWidth="2.4" strokeLinecap="round" />
            <path d="M32 34c-8 0-13-5-13-13 8 0 13 5 13 13z" fill="#9FE0C4" stroke="#3F9E78" strokeWidth="2" strokeLinejoin="round" />
            <path d="M32 30c8 0 13-5 13-13-8 0-13 5-13 13z" fill="#BDEBD6" stroke="#3F9E78" strokeWidth="2" strokeLinejoin="round" />
            <path d="M32 40c-5-1-8-4-9-9 5 1 8 4 9 9z" fill="#9FE0C4" stroke="#3F9E78" strokeWidth="2" strokeLinejoin="round" />
          </svg>
        </div>
      </div>
      </nav>
    </>
  );
}

export default function App() {
  const [user, setUser] = useState(getUser());
  const [stage, setStage] = useState("loading");
  const [activePage, setActivePage] = useState("dashboard");
  const [showLogin, setShowLogin] = useState(false);
  const [navOpen, setNavOpen] = useState(false);
  // Navigate + always close the mobile drawer.
  const navTo = (id) => { setActivePage(id); setNavOpen(false); };

  useEffect(() => {
    if (!user) { setStage("landing"); return; }
    api.me()
      .then((m) => {
        if (m.consent_required) setStage("consent");
        else if (m.intake_required) setStage("intake");
        else setStage("app");
      })
      .catch(() => setStage("app"));
  }, [user]);

  // Soft staggered reveal of the outermost cards whenever the page changes.
  // Runs before paint (useLayoutEffect) so cards start hidden — no flicker.
  useLayoutEffect(() => {
    if (stage !== "app") return;
    const root = document.querySelector(".main-content");
    if (!root) return;
    const sel = [
      ".card", ".st-card", ".profile-card", ".ai-card", ".bh-panel",
      ".home-section-card", ".home-side-card", ".side-card", ".suggest-card",
      ".home-hero", ".profile-hero", ".block",
    ].join(",");
    const all = Array.from(root.querySelectorAll(sel));
    // keep only the outermost matches so nested cards don't double-animate
    const items = all.filter((el) => !all.some((o) => o !== el && o.contains(el)));
    items.forEach((el, i) => {
      el.classList.add("u-reveal");
      el.style.setProperty("--rd", `${Math.min(i, 9) * 0.05}s`);
    });
    const raf = requestAnimationFrame(() =>
      items.forEach((el) => el.classList.add("u-reveal-in"))
    );
    return () => {
      cancelAnimationFrame(raf);
      items.forEach((el) => {
        el.classList.remove("u-reveal", "u-reveal-in");
        el.style.removeProperty("--rd");
      });
    };
  }, [activePage, stage]);

  function handleAuth(u) { setUser(u); setShowLogin(false); }

  function logout() {
    clearSession();
    setUser(null);
    setStage("landing");
    setShowLogin(false);
    setActivePage("dashboard");
  }

  if (stage === "landing" && !showLogin) return <Landing onSignIn={() => setShowLogin(true)} />;
  if (!user || showLogin) return <Login onAuth={handleAuth} onBack={() => setShowLogin(false)} />;
  if (stage === "loading") return null;
  if (stage === "consent") return <Consent onDone={() => setStage("intake")} />;
  if (stage === "intake")  return <Intake  onDone={() => setStage("app")} />;

  const pages = {
    dashboard: <Dashboard user={user} onNav={navTo} />,
    sangloc:   <SangLoc />,
    chat:      <Chat onNav={navTo} />,
    baihoc:    <BaiHoc />,
    hoso:      <HoSo user={user} />,
    tainguyen: <TaiNguyen />,
    tuvan:     <TuVan />,
    caidat:    <CaiDat user={user} onLogout={logout} />,
  };

  const isChatPage = activePage === "chat";

  return (
    <div className="app-shell">
      <Topbar activePage={activePage} onNav={navTo} user={user} onLogout={logout}
              onMenu={() => setNavOpen((o) => !o)} />

      <div className="app-body">
        <Sidebar activePage={activePage} onNav={navTo}
                 open={navOpen} onClose={() => setNavOpen(false)} />

        <div className={`main-content ${isChatPage ? "chat-mode" : ""}`}>
          {isChatPage ? (
            pages.chat
          ) : (
            <div className="page-content" key={activePage}>
              {pages[activePage]}
            </div>
          )}
        </div>
      </div>

      {/* Floating per-account mood trend — gentle, on every page. */}
      <MoodWidget />
    </div>
  );
}



