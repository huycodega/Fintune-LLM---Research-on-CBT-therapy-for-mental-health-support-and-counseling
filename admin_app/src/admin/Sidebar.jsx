import Icon from "./Icon.jsx";

/* Canonical admin navigation — shared across all admin pages. */
export const NAV = [
  { id: "overview",  icon: "grid",    label: "Overview" },
  { id: "users",     icon: "users",   label: "User management" },
  { id: "cases",     icon: "cases",   label: "Cases to Handle" },
  { id: "crisis",    icon: "alert",   label: "Crisis control" },
  { id: "moderation",icon: "sparkle", label: "AI Moderation" },
  { id: "lessons",   icon: "book",    label: "CBT Lessons" },
  { id: "resources", icon: "folder",  label: "Resources" },
  { id: "experts",   icon: "expert",  label: "Psychologists" },
];

export default function Sidebar({ active, onNav }) {
  return (
    <aside className="la-sidebar">
      <div className="la-brand">
        <div className="la-brand-logo">🌿</div>
        <div className="la-brand-text">MindCare AI <span>Admin</span></div>
      </div>

      <nav className="la-nav">
        {NAV.map((n) => (
          <button key={n.id} className={`la-nav-item ${active === n.id ? "active" : ""}`} onClick={() => onNav?.(n.id)}>
            <Icon name={n.icon} size={19} />
            {n.label}
          </button>
        ))}
      </nav>

      <div className="la-side-foot">
        <div className="la-support-card">
          <div className="la-support-mascot">🌿</div>
          <div className="la-support-text">MindCare AI provides timely support and companionship.</div>
          <button className="la-support-btn"><span className="la-dot" /> Get Support</button>
        </div>
        <div className="la-version">Version 1.2.0</div>
      </div>
    </aside>
  );
}
