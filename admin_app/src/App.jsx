import { useState, useEffect, useLayoutEffect } from "react";
import { getUser, clearSession } from "./api.js";
import Login from "./pages/Login.jsx";
import AppShell from "./admin/AppShell.jsx";

// Content-only pages (rendered inside the shared AppShell chrome).
import DashboardPage from "./components/dashboard/DashboardPage.jsx";
import Users from "./pages/Users.jsx";
import CaseManagementPage from "./components/cases/CaseManagementPage.jsx";
import ModerationPage from "./pages/ai-moderation/ModerationPage.jsx";
import ScreeningManagementPage from "./components/screenings/ScreeningManagementPage.jsx";
import ExpertsAdmin from "./pages/ExpertsAdmin.jsx";

// Self-shell pages (bring their own AppShell / la-shell + nav).
import LessonsAdmin from "./pages/LessonsAdmin.jsx";
import ResourcesAdmin from "./pages/ResourcesAdmin.jsx";
import Crisis from "./pages/Crisis.jsx";
import ReportsAdmin from "./pages/ReportsAdmin.jsx";
import SettingsAdmin from "./pages/SettingsAdmin.jsx";
import LogsAdmin from "./pages/LogsAdmin.jsx";

// Pages that render their own full shell — App just hands them nav + logout.
const SELF_SHELL = {
  lessons: LessonsAdmin,
  resources: ResourcesAdmin,
  crisis: Crisis,
  reports: ReportsAdmin,
  settings: SettingsAdmin,
  logs: LogsAdmin,
};

// Header text for the content-only pages wrapped in AppShell.
const PAGE_META = {
  overview:   { title: "Overview", sub: "System health & key metrics" },
  users:      { title: "User management", sub: "Accounts, status & per-user case history" },
  casemgmt:   { title: "Case Management", sub: "Assign, escalate & resolve cases" },
  moderation: { title: "AI Moderation", sub: "Review AI responses & risk levels" },
  experts:    { title: "Psychologists", sub: "Experts & consultation appointments" },
  screening:  { title: "Screening", sub: "PHQ-9 / GAD-7 results" },
};

// Clean URL ↔ admin page id.
const PAGE_PATHS = {
  overview: "/", users: "/users", casemgmt: "/cases", moderation: "/moderation",
  experts: "/psychologists", screening: "/screening", lessons: "/lessons",
  resources: "/resources", crisis: "/crisis", reports: "/reports",
  settings: "/settings", logs: "/logs",
};
const PATH_PAGES = Object.fromEntries(
  Object.entries(PAGE_PATHS).map(([id, p]) => [p, id]));

export default function App() {
  const [user, setUser] = useState(getUser());
  const [path, setPath] = useState(() => window.location.pathname);
  const [search, setSearch] = useState("");
  const [selectedUserId, setSelectedUserId] = useState(null);

  function go(p) {
    if (window.location.pathname !== p) window.history.pushState({}, "", p);
    setPath(p);
  }
  const page = PATH_PAGES[path] || "overview";

  useEffect(() => {
    const onPop = () => setPath(window.location.pathname);
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  // Soft staggered reveal of the outermost cards on page change — the same
  // feel as the user app, so the two dashboards read as one product.
  useLayoutEffect(() => {
    if (!user) return;
    const sel = ".stat-card, .panel, .la-card, .dashboard-kpi, .detail-card";
    const all = Array.from(document.querySelectorAll(sel));
    const items = all.filter((el) => !all.some((o) => o !== el && o.contains(el)));
    items.forEach((el, i) => {
      el.classList.add("u-reveal");
      el.style.setProperty("--rd", `${Math.min(i, 9) * 0.05}s`);
    });
    const raf = requestAnimationFrame(() =>
      items.forEach((el) => el.classList.add("u-reveal-in")));
    return () => {
      cancelAnimationFrame(raf);
      items.forEach((el) => {
        el.classList.remove("u-reveal", "u-reveal-in");
        el.style.removeProperty("--rd");
      });
    };
  }, [page, user]);

  function logout() { clearSession(); setUser(null); }
  function nav(p, userId = null) { setSearch(""); setSelectedUserId(userId); go(PAGE_PATHS[p] || "/"); }

  if (!user) return <Login onAuth={setUser} />;

  // Pages that own their full shell render standalone.
  if (SELF_SHELL[page]) {
    const Page = SELF_SHELL[page];
    return <Page onNav={nav} onLogout={logout} />;
  }

  const meta = PAGE_META[page] || PAGE_META.overview;
  const isUsers = page === "users";
  return (
    <AppShell
      active={page}
      onNav={nav}
      onLogout={logout}
      title={meta.title}
      subtitle={meta.sub}
      searchPlaceholder={isUsers ? "Search name or email…" : "Search…"}
      searchValue={isUsers ? search : undefined}
      onSearch={isUsers ? setSearch : undefined}
    >
      {page === "overview" && <DashboardPage onNav={nav} />}
      {page === "users" && (
        <Users search={search} selectedUserId={selectedUserId} onOpenCase={() => nav("cases")} />
      )}
      {page === "casemgmt" && <CaseManagementPage onNav={nav} />}
      {page === "moderation" && <ModerationPage />}
      {page === "experts" && <ExpertsAdmin />}
      {page === "screening" && <ScreeningManagementPage />}
    </AppShell>
  );
}
