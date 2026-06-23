import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";

const KIND = {
  lesson:   { icon: "📘", tone: "lesson" },
  resource: { icon: "📗", tone: "resource" },
  reminder: { icon: "🔔", tone: "reminder" },
};
const ACK_KEY = "mc_user_notif_ack";

function loadSet() { try { return new Set(JSON.parse(localStorage.getItem(ACK_KEY) || "[]")); } catch { return new Set(); } }
function saveSet(s) { try { localStorage.setItem(ACK_KEY, JSON.stringify([...s])); } catch { /* ignore */ } }
function relTime(iso) {
  if (!iso) return "";
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

export default function NotifBell({ onNav }) {
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const ackRef = useRef(loadSet());

  useEffect(() => {
    let alive = true;
    async function poll() {
      try {
        const r = await api.myNotifications();
        if (alive) setItems(r.items || []);
      } catch { /* ignore */ }
    }
    poll();
    const t = setInterval(poll, 30000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  const unread = items.filter((x) => !ackRef.current.has(x.id)).length;

  function toggle() {
    const next = !open;
    setOpen(next);
    if (next && items.length) {
      items.forEach((x) => ackRef.current.add(x.id));
      saveSet(ackRef.current);
    }
  }
  function go(link) { setOpen(false); onNav && onNav(link); }

  return (
    <div className="unotif-wrap">
      <button className={`topbar-notif ${unread ? "has-unread" : ""}`} title="Notifications" onClick={toggle}>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M6 9.5a6 6 0 1 1 12 0c0 4.5 1.8 5.5 1.8 5.5H4.2S6 14 6 9.5z" />
          <path d="M10 19a2 2 0 0 0 4 0" />
        </svg>
        {unread > 0 && <span className="topbar-notif-badge">{unread > 9 ? "9+" : unread}</span>}
      </button>
      {open && (
        <>
          <div className="unotif-overlay" onClick={() => setOpen(false)} />
          <div className="unotif-menu" role="dialog" aria-label="Notifications">
            <div className="unotif-head"><span>Notifications</span><span className="unotif-count">{items.length}</span></div>
            {items.length === 0 ? (
              <div className="unotif-empty">🌿 You're all caught up.</div>
            ) : (
              <div className="unotif-list">
                {items.map((x) => {
                  const k = KIND[x.kind] || { icon: "🔔", tone: "reminder" };
                  return (
                    <button key={x.id} className="unotif-item" onClick={() => go(x.link)}>
                      <span className={`unotif-icon ${k.tone}`}>{k.icon}</span>
                      <span className="unotif-body">
                        <b>{x.title}</b>
                        <span className="unotif-text">{x.text}</span>
                        <span className="unotif-time">{relTime(x.created_at)}</span>
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
  );
}
