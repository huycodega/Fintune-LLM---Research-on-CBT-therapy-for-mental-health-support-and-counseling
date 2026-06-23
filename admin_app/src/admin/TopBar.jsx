import { useState, useEffect, useRef } from "react";
import Icon from "./Icon.jsx";
import { api } from "../api.js";

/* Danger level → label + colour tone for the notification pill. */
const LEVEL = {
  L0: { tone: "crisis", label: "Crisis" },
  L1: { tone: "high", label: "High" },
  L2: { tone: "mod", label: "Moderate" },
  L3: { tone: "low", label: "Low" },
};
const KIND = {
  review:      { icon: "🛡️", label: "Review" },
  appointment: { icon: "📅", label: "Booking" },
};
const ACK_KEY = "mc_admin_notif_ack";    // ids the admin has opened/read
const SEEN_KEY = "mc_admin_notif_seen";  // ids the bell has already rung for

function loadSet(key) {
  try { return new Set(JSON.parse(localStorage.getItem(key) || "[]")); }
  catch { return new Set(); }
}
function saveSet(key, set) {
  try { localStorage.setItem(key, JSON.stringify([...set])); } catch { /* ignore */ }
}
function relTime(iso) {
  if (!iso) return "";
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

export default function TopBar({ title, subtitle, searchPlaceholder, onLogout, onMenu, filterPanel, avatarSrc = "/admin-avatar.svg", onRefresh, refreshing = false, searchValue, onSearch, onNav }) {
  const [menu, setMenu] = useState(false);
  const [filters, setFilters] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [items, setItems] = useState([]);
  const [shake, setShake] = useState(false);
  const ackRef = useRef(loadSet(ACK_KEY));
  const seenRef = useRef(loadSet(SEEN_KEY));
  const shakeTimer = useRef(null);

  // Poll the unified admin feed — pending clinician reviews + new appointment
  // bookings, newest first. A brand-new item rings the bell once.
  useEffect(() => {
    let alive = true;
    async function poll() {
      try {
        const r = await api.notifications();
        if (!alive) return;
        const q = r.items || [];
        setItems(q);
        const fresh = q.filter((x) => !seenRef.current.has(x.id));
        if (fresh.length) {
          fresh.forEach((x) => seenRef.current.add(x.id));
          saveSet(SEEN_KEY, seenRef.current);
          if (fresh.some((x) => !ackRef.current.has(x.id))) {
            setShake(true);
            clearTimeout(shakeTimer.current);
            shakeTimer.current = setTimeout(() => setShake(false), 1500);
          }
        }
      } catch { /* ignore */ }
    }
    poll();
    const t = setInterval(poll, 12000);
    return () => { alive = false; clearInterval(t); clearTimeout(shakeTimer.current); };
  }, []);

  const unreadCount = items.filter((x) => !ackRef.current.has(x.id)).length;

  function openNotif() {
    const next = !notifOpen;
    setNotifOpen(next);
    setMenu(false);
    if (next && items.length) {
      items.forEach((x) => ackRef.current.add(x.id));
      saveSet(ACK_KEY, ackRef.current);
      setShake(false);
    }
  }
  function go(link) {
    setNotifOpen(false);
    onNav && onNav(link || "moderation");
  }

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

      <div className="la-notif-wrap">
        <button className={`la-icon-btn la-notif ${shake ? "ring" : ""}`} onClick={openNotif}
                aria-label={`Notifications${unreadCount ? ` (${unreadCount} new)` : ""}`}>
          <Icon name="bell" size={19} />
          {unreadCount > 0 && <span className="la-notif-badge">{unreadCount > 9 ? "9+" : unreadCount}</span>}
        </button>
        {notifOpen && (
          <>
            <div className="la-overlay" onClick={() => setNotifOpen(false)} />
            <div className="la-notif-menu" role="dialog" aria-label="Notifications">
              <div className="la-notif-head">
                <span>Notifications</span>
                <span className="la-notif-count">{items.length}</span>
              </div>
              {items.length === 0 ? (
                <div className="la-notif-empty">🎉 Nothing new right now.</div>
              ) : (
                <div className="la-notif-list">
                  {items.slice(0, 10).map((x) => {
                    const lv = x.level ? (LEVEL[x.level] || { tone: "mod", label: x.level }) : null;
                    const k = KIND[x.kind] || { icon: "🔔", label: x.kind };
                    return (
                      <button key={x.id} className="la-notif-item" onClick={() => go(x.link)}>
                        <span className={`la-notif-dot ${lv ? lv.tone : x.kind}`} />
                        <span className="la-notif-body">
                          <span className="la-notif-row1">
                            <b className="la-notif-user">{k.icon} {x.title}</b>
                            {lv
                              ? <span className={`la-notif-pill ${lv.tone}`}>{x.level} · {lv.label}</span>
                              : <span className="la-notif-pill appt">{k.label}</span>}
                          </span>
                          <span className="la-notif-text">{x.text}</span>
                          <span className="la-notif-time">{relTime(x.created_at)}</span>
                        </span>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          </>
        )}
      </div>

      <div className="la-user-wrap">
        <button className={`la-user ${menu ? "open" : ""}`} onClick={() => { setMenu((m) => !m); setNotifOpen(false); }}>
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
