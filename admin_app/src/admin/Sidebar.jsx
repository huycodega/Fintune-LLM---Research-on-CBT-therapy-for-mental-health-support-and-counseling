import Icon from "./Icon.jsx";

/* Canonical admin navigation — shared across all admin pages. */
export const NAV = [
  { id: "overview",  icon: "grid",    label: "Overview" },
  { id: "users",     icon: "users",   label: "Users" },
  { id: "casemgmt",  icon: "sliders", label: "Case Management" },
  { id: "crisis",    icon: "alert",   label: "Crisis Control" },
  { id: "screening", icon: "shield",  label: "Screening" },
  { id: "moderation",icon: "sparkle", label: "AI Moderation" },
  { id: "lessons",   icon: "book",    label: "CBT Lessons" },
  { id: "resources", icon: "folder",  label: "Resources" },
  { id: "experts",   icon: "expert",  label: "Psychologists" },
  { id: "reports",   icon: "bars",    label: "Reports" },
  { id: "logs",      icon: "logs",    label: "System Logs" },
  { id: "settings",  icon: "gear",    label: "Settings" },
];

export default function Sidebar({ active, onNav, mobileOpen = false, onClose }) {
  return (
    <aside className={`la-sidebar ${mobileOpen ? "mobile-open" : ""}`}>
      {onClose && <button className="la-sidebar-close" onClick={onClose} aria-label="Close navigation"><Icon name="close" size={19} /></button>}
      <div className="la-brand">
        <div className="la-brand-logo"><img src="/mascot-wave.png" alt="MindCare mascot" /></div>
        <div className="la-brand-text">MindCare AI <span>Admin</span></div>
      </div>

      <nav className="la-nav">
        {NAV.map((n) => (
          <button key={n.id} className={`la-nav-item ${active === n.id ? "active" : ""}`} onClick={() => { onNav?.(n.id); onClose?.(); }}>
            <Icon name={n.icon} size={19} />
            {n.label}
          </button>
        ))}
      </nav>

      <div className="la-side-foot">
        <div className="la-support-card">
          <div className="la-support-mascot"><img src="/mascot-wave.png" alt="" /></div>
          <div className="la-support-text">MindCare AI supports you in managing mental wellbeing.</div>
          <button className="la-support-btn"><span className="la-dot" /> Get Support</button>
        </div>
        <div className="la-version">Version 1.2.0</div>
      </div>
    </aside>
  );
}
