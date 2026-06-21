import { useState } from "react";
import Icon from "./Icon.jsx";

export default function TopBar({ title, subtitle, searchPlaceholder, onLogout, notificationCount = 3, onMenu, filterPanel, avatarSrc = "/admin-avatar.svg", onRefresh, refreshing = false, searchValue, onSearch }) {
  const [menu, setMenu] = useState(false);
  const [filters, setFilters] = useState(false);
  return (
    <header className="la-topbar">
      {onMenu && <button className="la-icon-btn la-mobile-menu" onClick={onMenu} aria-label="Open navigation"><Icon name="menu" size={20} /></button>}
      <div className="la-topbar-title">
        <h1>{title}</h1>
        <span className="la-topbar-sub">{subtitle}</span>
        {onRefresh && <button className={`la-title-refresh ${refreshing ? "loading" : ""}`} onClick={onRefresh} aria-label="Refresh data"><Icon name="refresh" size={15} /></button>}
      </div>

      <div className="la-search-wrap">
        <Icon name="search" size={17} className="la-search-icon" />
        <input
          className="la-search"
          placeholder={searchPlaceholder}
          {...(onSearch ? { value: searchValue ?? "", onChange: (e) => onSearch(e.target.value) } : {})}
        />
      </div>

      <div className="la-filter-popover">
        <button className={`la-btn-ghost ${filters ? "open" : ""}`} onClick={() => filterPanel && setFilters((v) => !v)} aria-expanded={filters}>
          <Icon name="filter" size={16} /> Filters
        </button>
        {filters && filterPanel && <div className="la-filter-menu">{filterPanel}</div>}
      </div>

      <button className="la-icon-btn la-notif" aria-label="Notifications">
        <Icon name="bell" size={19} />
        <span className="la-notif-badge">{notificationCount}</span>
      </button>

      <div className="la-user-wrap">
        <button className={`la-user ${menu ? "open" : ""}`} onClick={() => setMenu((m) => !m)}>
          <span className="la-avatar">{avatarSrc ? <img src={avatarSrc} alt="Admin avatar" /> : "A"}</span>
          <span className="la-user-text"><b>Admin</b><small>Administrator</small></span>
          <Icon name="chevronDown" size={15} />
        </button>
        {menu && (
          <>
            <div className="la-overlay" onClick={() => setMenu(false)} />
            <div className="la-user-menu"><button onClick={onLogout}>Sign out</button></div>
          </>
        )}
      </div>
    </header>
  );
}
