// Shared UI helpers for the admin console.
import Icon from "./admin/Icon.jsx";

const AVATAR_COLORS = [
  "linear-gradient(135deg,#6366F1,#8B5CF6)",
  "linear-gradient(135deg,#16B981,#0EA5A5)",
  "linear-gradient(135deg,#F59E0B,#EF7C0B)",
  "linear-gradient(135deg,#EF4444,#EC4899)",
  "linear-gradient(135deg,#3B82F6,#06B6D4)",
  "linear-gradient(135deg,#8B5CF6,#D946EF)",
];

export function avatarColor(seed = "") {
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) >>> 0;
  return AVATAR_COLORS[h % AVATAR_COLORS.length];
}

export function initials(name = "") {
  const base = (name || "").split("@")[0];
  return (base.slice(0, 1) || "U").toUpperCase();
}

export function displayName(name = "") {
  return (name || "").split("@")[0] || "user";
}

export function fmtDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

export function fmtDateTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString("en-GB", {
    day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
  });
}

// "Updated 20/06/2026 · 14:32" for the moment the page was opened. Used in
// the topbar subtitle so dashboards read as live rather than frozen in time.
export function updatedNow() {
  const d = new Date();
  return `Updated ${d.toLocaleDateString("en-GB")} · ${d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}`;
}

// One consistent, low-key notice shown when a page is rendering sample data
// because its live API isn't wired yet. Replaces the old amber "warning"
// banners so it informs without looking like an error.
export function DemoNotice({ children }) {
  return (
    <div className="demo-notice" role="status">
      <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor"
        strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <circle cx="12" cy="12" r="9" />
        <path d="M12 11v5M12 7.5h.01" />
      </svg>
      <span>{children}</span>
    </div>
  );
}

export function timeAgo(iso) {
  if (!iso) return "never";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 2592000) return `${Math.floor(diff / 86400)}d ago`;
  return fmtDate(iso);
}

const RISK_LABEL = { high: "High risk", elevated: "Elevated", moderate: "Moderate", low: "Low" };
const RISK_CLASS = { high: "red", elevated: "amber", moderate: "blue", low: "green" };

export function RiskPill({ risk }) {
  return (
    <span className={`pill ${RISK_CLASS[risk] || "gray"}`}>
      <span className="dot" />{RISK_LABEL[risk] || risk}
    </span>
  );
}

export function StatusPill({ status }) {
  const cls = status === "suspended" ? "red" : "green";
  const label = status === "suspended" ? "Suspended" : "Active";
  return <span className={`pill ${cls}`}><span className="dot" />{label}</span>;
}

export function Avatar({ name, size = 34, className = "cell-avatar" }) {
  return (
    <div className={className}
         style={{ background: avatarColor(name), width: size, height: size }}>
      {initials(name)}
    </div>
  );
}

export function StatCard({ icon, color, value, label }) {
  return (
    <div className="stat-card">
      <div className={`stat-icon ${color}`}><Icon name={icon} size={22} /></div>
      <div>
        <div className="stat-value">{value}</div>
        <div className="stat-label">{label}</div>
      </div>
    </div>
  );
}

export function Empty({ icon = "🌿", text }) {
  return <div className="empty"><div className="empty-mascot">{icon}</div>{text}</div>;
}
