import { useState } from "react";
import { getUser, clearSession } from "./api.js";
import { Empty } from "./ui.jsx";
import AppShell from "./admin/AppShell.jsx";
import Login from "./pages/Login.jsx";
import Overview from "./pages/Overview.jsx";
import Cases from "./pages/Cases.jsx";
import Crisis from "./pages/Crisis.jsx";
import UsersAdmin from "./pages/UsersAdmin.jsx";
import ModerationAdmin from "./pages/ModerationAdmin.jsx";
import LessonsAdmin from "./pages/LessonsAdmin.jsx";
import ResourcesAdmin from "./pages/ResourcesAdmin.jsx";
import ReportsAdmin from "./pages/ReportsAdmin.jsx";
import LogsAdmin from "./pages/LogsAdmin.jsx";
import SettingsAdmin from "./pages/SettingsAdmin.jsx";

/* Every page renders its own canonical AppShell (dark-navy Sidebar + shared
   TopBar), so the whole console shares one layout, header and navigation. */
const PAGES = {
  overview:   Overview,
  users:      UsersAdmin,
  cases:      Cases,
  crisis:     Crisis,
  moderation: ModerationAdmin,
  lessons:    LessonsAdmin,
  resources:  ResourcesAdmin,
  reports:    ReportsAdmin,
  logs:       LogsAdmin,
  settings:   SettingsAdmin,
};

function ComingSoon({ page, onNav, onLogout }) {
  return (
    <AppShell active={page} onNav={onNav} onLogout={onLogout}
              title="Coming soon" subtitle="This section hasn't been built yet">
      <Empty icon="🚧" text="This section hasn't been built yet." />
    </AppShell>
  );
}

export default function App() {
  const [user, setUser] = useState(getUser());
  const [page, setPage] = useState("overview");

  function logout() { clearSession(); setUser(null); }
  function nav(p) { setPage(p); }

  if (!user) return <Login onAuth={setUser} />;

  const Page = PAGES[page];
  if (!Page) return <ComingSoon page={page} onNav={nav} onLogout={logout} />;
  return <Page onLogout={logout} onNav={nav} />;
}
