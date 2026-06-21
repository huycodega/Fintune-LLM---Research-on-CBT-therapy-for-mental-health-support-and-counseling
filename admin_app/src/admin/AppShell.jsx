import { useState } from "react";
import Sidebar from "./Sidebar.jsx";
import TopBar from "./TopBar.jsx";

/* Canonical admin page shell: dark-navy Sidebar + shared TopBar + content
   area. Every page renders inside this so the navigation chrome, header,
   spacing and mobile drawer behave identically across the whole console. */
export default function AppShell({
  active,
  onNav,
  onLogout,
  title,
  subtitle,
  searchPlaceholder = "Search…",
  searchValue,
  onSearch,
  filterPanel,
  onRefresh,
  refreshing,
  children,
}) {
  const [mobileOpen, setMobileOpen] = useState(false);
  return (
    <div className="la-shell app-shell">
      {mobileOpen && (
        <button className="app-nav-scrim" onClick={() => setMobileOpen(false)} aria-label="Close navigation" />
      )}
      <Sidebar active={active} onNav={onNav} mobileOpen={mobileOpen} onClose={() => setMobileOpen(false)} />
      <main className="la-main">
        <TopBar
          title={title}
          subtitle={subtitle}
          searchPlaceholder={searchPlaceholder}
          searchValue={searchValue}
          onSearch={onSearch}
          onLogout={onLogout}
          onNav={onNav}
          onMenu={() => setMobileOpen(true)}
          filterPanel={filterPanel}
          onRefresh={onRefresh}
          refreshing={refreshing}
        />
        <div className="la-content la-content-nopanel app-content">{children}</div>
      </main>
    </div>
  );
}
