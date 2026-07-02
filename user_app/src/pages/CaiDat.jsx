import { useState, useEffect } from "react";
import { api } from "../api.js";
import Mascot from "../components/Mascot.jsx";

/* ── Inline line-icon set (teal stroke, matches mockup) ────────── */
const ICON_PATHS = {
  user:     <><circle cx="12" cy="8" r="4" /><path d="M4 20c0-4 4-6 8-6s8 2 8 6" /></>,
  bell:     <><path d="M6 9a6 6 0 1112 0c0 5 2 6 2 6H4s2-1 2-6z" /><path d="M10 20a2 2 0 004 0" /></>,
  shield:   <><path d="M12 3l7 3v5c0 5-3 8-7 10-4-2-7-5-7-10V6z" /><path d="M9 12l2 2 4-4" /></>,
  lock:     <><rect x="5" y="11" width="14" height="9" rx="2" /><path d="M8 11V8a4 4 0 018 0v3" /></>,
  globe:    <><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18" /></>,
  phone:    <><path d="M5 4h4l2 5-3 2c1 3 3 5 6 6l2-3 5 2v4c0 1-1 2-2 2C9 22 2 15 2 6c0-1 1-2 3-2z" /></>,
  grid:     <><rect x="4" y="4" width="7" height="7" rx="1.5" /><rect x="13" y="4" width="7" height="7" rx="1.5" /><rect x="4" y="13" width="7" height="7" rx="1.5" /><rect x="13" y="13" width="7" height="7" rx="1.5" /></>,
  doc:      <><path d="M7 3h7l4 4v14H7z" /><path d="M14 3v4h4" /></>,
  chip:     <><rect x="6" y="6" width="12" height="12" rx="2" /><path d="M9 3v3M15 3v3M9 18v3M15 18v3M3 9h3M3 15h3M18 9h3M18 15h3" /></>,
  mail:     <><rect x="3" y="5" width="18" height="14" rx="2" /><path d="M3 7l9 6 9-6" /></>,
  monitor:  <><rect x="3" y="4" width="18" height="12" rx="2" /><path d="M8 20h8M12 16v4" /></>,
  info:     <><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8h.01" /></>,
  memory:   <><rect x="5" y="5" width="14" height="14" rx="3" /><path d="M9 9h6v6H9z" /></>,
  download: <><path d="M12 3v12M7 10l5 5 5-5" /><path d="M5 21h14" /></>,
  trash:    <><path d="M4 7h16M9 7V4h6v3M6 7l1 14h10l1-14" /></>,
  eye:      <><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z" /><circle cx="12" cy="12" r="3" /></>,
  eyeOff:   <><path d="M3 3l18 18M10.6 6.1A9.8 9.8 0 0112 6c6 0 10 6 10 6a18 18 0 01-3.1 3.6M6.6 6.6A18 18 0 002 12s4 6 10 6a9.5 9.5 0 004.3-1" /><path d="M9.9 9.9a3 3 0 004.2 4.2" /></>,
  chevron:  <><path d="M9 6l6 6-6 6" /></>,
};

function Icon({ name, size = 20, className = "" }) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      {ICON_PATHS[name]}
    </svg>
  );
}

function Toggle({ on, onChange, disabled }) {
  return (
    <button type="button" className={`st-toggle ${on ? "on" : ""}`} disabled={disabled}
      onClick={() => onChange(!on)} role="switch" aria-checked={on}>
      <span className="st-toggle-knob" />
    </button>
  );
}

function CardHead({ icon, title, sub, action }) {
  return (
    <div className="st-card-head">
      <span className="st-card-icon"><Icon name={icon} /></span>
      <div className="st-card-head-text">
        <div className="st-card-title">{title}</div>
        <div className="st-card-sub">{sub}</div>
      </div>
      {action}
    </div>
  );
}

function ToggleRow({ icon, color, title, desc, on, onChange }) {
  return (
    <div className="st-row">
      <span className="st-row-icon" style={{ color }}><Icon name={icon} size={18} /></span>
      <div className="st-row-text">
        <div className="st-row-title">{title}</div>
        <div className="st-row-desc">{desc}</div>
      </div>
      <Toggle on={on} onChange={onChange} />
    </div>
  );
}

function PasswordField({ label, placeholder, value, onChange }) {
  const [show, setShow] = useState(false);
  return (
    <div className="st-pwd">
      <label className="st-field-label">{label}</label>
      <div className="st-input-wrap">
        <input className="st-input" type={show ? "text" : "password"} placeholder={placeholder}
          value={value} onChange={(e) => onChange(e.target.value)} />
        <button type="button" className="st-eye" onClick={() => setShow((s) => !s)} aria-label="Toggle visibility">
          <Icon name={show ? "eyeOff" : "eye"} size={18} />
        </button>
      </div>
    </div>
  );
}

const Soon = () => <span className="st-soon-badge">Coming soon</span>;

const NOTIF_ROWS = [
  { key: "screening",    icon: "bell",    color: "#14b8a6", title: "Screening & Reminders",      desc: "Reminders to complete periodic screenings" },
  { key: "lessons",      icon: "doc",     color: "#f59e0b", title: "Lessons & New Content",      desc: "Updates on new lessons and resources" },
  { key: "ai_support",   icon: "chip",    color: "#14b8a6", title: "AI Support Notifications",   desc: "Suggestions, mood tracking, and messages" },
  { key: "email",        icon: "mail",    color: "#f59e0b", title: "Email Notifications",        desc: "Receive notifications via email" },
  { key: "browser_push", icon: "monitor", color: "#14b8a6", title: "Browser Push Notifications", desc: "Show notifications in your browser" },
];
const PRIVACY_ROWS = [
  { key: "share_anonymous", icon: "info",   color: "#14b8a6", title: "Share anonymous data to improve AI",   desc: "Help us improve the experience and deliver more relevant content." },
  { key: "ai_remember",     icon: "memory", color: "#14b8a6", title: "Allow AI to remember your preferences", desc: "Personalize suggestions based on your usage behavior." },
];

function fmtDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-GB", { day: "2-digit", month: "2-digit", year: "numeric" });
}

export default function CaiDat({ user, onLogout }) {
  const [data, setData] = useState(null);
  const [prefs, setPrefs] = useState(null);
  const [emergency, setEmergency] = useState({ name: "", relationship: "", phone: "" });
  const [editEm, setEditEm] = useState(false);
  const [pw, setPw] = useState({ current_password: "", new_password: "", confirm: "" });
  const [pwMsg, setPwMsg] = useState(null);

  useEffect(() => {
    api.mySettings().catch(() => null).then((s) => {
      if (!s) return;
      setData(s);
      setPrefs(s.prefs);
      setEmergency({
        name: s.emergency?.name || "", relationship: s.emergency?.relationship || "",
        phone: s.emergency?.phone || "",
      });
    });
  }, []);

  function patchPrefs(section, key, value) {
    const next = { ...prefs, [section]: { ...prefs[section], [key]: value } };
    setPrefs(next);
    api.updateSettings({ prefs: { [section]: { [key]: value } } }).catch(() => {});
  }

  async function saveEmergency() {
    try {
      const s = await api.updateSettings({ emergency });
      setData(s);
      setEditEm(false);
    } catch { /* keep editing */ }
  }

  async function updatePassword() {
    setPwMsg(null);
    if (pw.new_password !== pw.confirm) { setPwMsg({ err: true, text: "Passwords don't match" }); return; }
    try {
      await api.changePassword(pw.current_password, pw.new_password);
      setPwMsg({ err: false, text: "Password updated ✓" });
      setPw({ current_password: "", new_password: "", confirm: "" });
    } catch (e) {
      setPwMsg({ err: true, text: e.message || "Could not update password" });
    }
  }

  async function downloadData() {
    try {
      const bundle = await api.exportMyData();
      const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `mindcare-data-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch { window.alert("Could not export your data — please try again."); }
  }

  async function deleteAccount() {
    const uname = user?.username || "";
    const typed = window.prompt(
      "This permanently deletes your account and ALL your data — conversations, " +
      "screenings, journal, appointments. It cannot be undone.\n\n" +
      `To confirm, type your username (${uname}):`);
    if (typed === null) return;
    if (typed.trim() !== uname) { window.alert("Username didn't match — nothing was deleted."); return; }
    try {
      await api.deleteMyAccount(uname);
      window.alert("Your account and data have been deleted. Take care of yourself. 💚");
      if (onLogout) onLogout();
    } catch (e) {
      window.alert(e.message || "Could not delete the account — please try again.");
    }
  }

  const account = data?.account || {};
  const initials = (account.full_name || user?.username || "U").slice(0, 1).toUpperCase();

  return (
    <div className="st-page">
      <header className="st-head">
        <h1 className="st-page-title">Settings</h1>
        <p className="st-page-sub">Manage your account, app preferences, and security.</p>
      </header>

      <div className="st-grid">
        {/* ── LEFT COLUMN ── */}
        <div className="st-col">
          {/* Account */}
          <section className="st-card">
            <CardHead icon="user" title="Account" sub="Manage your account information." />
            <div className="st-account">
              <div className="st-avatar"><span className="st-avatar-initials">{initials}</span></div>
              <div className="st-account-info">
                <div className="st-info-item">
                  <div className="st-field-label">Full Name</div>
                  <div className="st-info-value">{account.full_name || "—"}</div>
                </div>
                <div className="st-info-item">
                  <div className="st-field-label">Email</div>
                  <div className="st-info-value">{account.email || "—"}</div>
                </div>
                <div className="st-info-item">
                  <div className="st-field-label">Joined</div>
                  <div className="st-info-value">{fmtDate(account.joined)}</div>
                </div>
              </div>
            </div>
          </section>

          {/* Security */}
          <section className="st-card">
            <CardHead icon="shield" title="Security" sub="Change password and manage account security." />
            <div className="st-security">
              <div className="st-security-col">
                <div className="st-subhead">Change Password</div>
                <PasswordField label="Current Password" placeholder="Enter current password"
                  value={pw.current_password} onChange={(v) => setPw((s) => ({ ...s, current_password: v }))} />
                <PasswordField label="New Password" placeholder="Enter new password"
                  value={pw.new_password} onChange={(v) => setPw((s) => ({ ...s, new_password: v }))} />
                <PasswordField label="Confirm New Password" placeholder="Re-enter new password"
                  value={pw.confirm} onChange={(v) => setPw((s) => ({ ...s, confirm: v }))} />
                {pwMsg && <div className={`st-pw-msg ${pwMsg.err ? "err" : "ok"}`}>{pwMsg.text}</div>}
                <button className="st-btn-primary st-btn-full" onClick={updatePassword}>Update Password</button>
              </div>
              <div className="st-security-col">
                <div className="st-subhead-row">
                  <span className="st-subhead">Two-Factor Authentication (2FA)</span>
                  <Soon />
                </div>
                <p className="st-2fa-intro">Add an extra layer of security to your account.</p>
                <div className="st-2fa-item st-disabled">
                  <div className="st-2fa-text">
                    <div className="st-2fa-title">Authenticator App</div>
                    <div className="st-2fa-sub">Link an authenticator app</div>
                  </div>
                  <button className="st-btn-outline st-btn-sm" disabled>Manage</button>
                </div>
                <div className="st-2fa-item st-disabled">
                  <div className="st-2fa-text">
                    <div className="st-2fa-title">Backup Codes</div>
                    <div className="st-2fa-sub">One-time recovery codes</div>
                  </div>
                  <button className="st-btn-outline st-btn-sm" disabled>View Codes</button>
                </div>
              </div>
            </div>
          </section>

          {/* Language & Appearance */}
          <section className="st-card">
            <CardHead icon="globe" title="Language & Appearance" sub="Customize the display language and appearance." />
            {prefs && (
              <div className="st-selects">
                <div className="st-select-field">
                  <label className="st-field-label">Language</label>
                  <select className="st-select" value={prefs.app.language} onChange={(e) => patchPrefs("app", "language", e.target.value)}>
                    <option value="en">🌐 English</option>
                    <option value="vi">Tiếng Việt</option>
                  </select>
                </div>
                <div className="st-select-field">
                  <label className="st-field-label">Theme</label>
                  <select className="st-select" value={prefs.app.theme} onChange={(e) => patchPrefs("app", "theme", e.target.value)}>
                    <option value="light">Light</option>
                    <option value="dark">Dark</option>
                    <option value="system">System</option>
                  </select>
                </div>
                <div className="st-select-field">
                  <label className="st-field-label">Font Size</label>
                  <select className="st-select" value={prefs.app.font_size} onChange={(e) => patchPrefs("app", "font_size", e.target.value)}>
                    <option value="small">Small</option>
                    <option value="medium">Medium</option>
                    <option value="large">Large</option>
                  </select>
                </div>
              </div>
            )}
          </section>

          {/* Other */}
          <section className="st-card">
            <CardHead icon="grid" title="Other" sub="Account management and data options." />
            <div className="st-other-list">
              <div className="st-other-row st-disabled">
                <span className="st-other-icon"><Icon name="monitor" size={18} /></span>
                <div className="st-other-text">
                  <div className="st-other-title">Manage Logged-in Devices <Soon /></div>
                  <div className="st-other-desc">View and manage devices logged into your account.</div>
                </div>
              </div>
              <div className="st-other-row" style={{ cursor: "pointer" }} onClick={downloadData}
                   role="button" tabIndex={0}>
                <span className="st-other-icon"><Icon name="download" size={18} /></span>
                <div className="st-other-text">
                  <div className="st-other-title">Download Your Data</div>
                  <div className="st-other-desc">One JSON file with your conversations, screenings, journal, and intake.</div>
                </div>
              </div>
              <div className="st-other-row danger" style={{ cursor: "pointer" }} onClick={deleteAccount}
                   role="button" tabIndex={0}>
                <span className="st-other-icon"><Icon name="trash" size={18} /></span>
                <div className="st-other-text">
                  <div className="st-other-title">Delete Account</div>
                  <div className="st-other-desc">Permanently delete your account and all your data. This cannot be undone.</div>
                </div>
              </div>
            </div>
          </section>
        </div>

        {/* ── RIGHT COLUMN ── */}
        <div className="st-col">
          {/* Notifications */}
          <section className="st-card">
            <CardHead icon="bell" title="Notifications" sub="Customize how you receive notifications." />
            {prefs && (
              <div className="st-rows">
                {NOTIF_ROWS.map((n) => (
                  <ToggleRow key={n.key} {...n} on={!!prefs.notifications[n.key]}
                    onChange={(v) => patchPrefs("notifications", n.key, v)} />
                ))}
              </div>
            )}
          </section>

          {/* Privacy */}
          <section className="st-card">
            <CardHead icon="lock" title="Privacy" sub="Manage your personal data and privacy." />
            {prefs && (
              <div className="st-rows">
                {PRIVACY_ROWS.map((p) => (
                  <ToggleRow key={p.key} {...p} on={!!prefs.privacy[p.key]}
                    onChange={(v) => patchPrefs("privacy", p.key, v)} />
                ))}
              </div>
            )}
          </section>

          {/* Emergency Contact */}
          <section className="st-card">
            <CardHead icon="phone" title="Emergency Contact"
              sub="This contact information will be used when you need emergency support."
              action={!editEm && <button className="st-btn-outline st-btn-sm" onClick={() => setEditEm(true)}>Edit</button>} />
            {!editEm ? (
              <div className="st-emergency">
                <div className="st-emergency-info">
                  <div className="st-info-item">
                    <div className="st-field-label">Contact Person</div>
                    <div className="st-info-value">
                      {emergency.name || "—"}{emergency.relationship ? ` (${emergency.relationship})` : ""}
                    </div>
                  </div>
                  <div className="st-info-item">
                    <div className="st-field-label">Phone Number</div>
                    <div className="st-info-value">{emergency.phone || "—"}</div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="st-emergency-edit">
                <input className="st-input" placeholder="Contact name" value={emergency.name}
                  onChange={(e) => setEmergency((s) => ({ ...s, name: e.target.value }))} />
                <input className="st-input" placeholder="Relationship (e.g. Sister)" value={emergency.relationship}
                  onChange={(e) => setEmergency((s) => ({ ...s, relationship: e.target.value }))} />
                <input className="st-input" placeholder="Phone number" value={emergency.phone}
                  onChange={(e) => setEmergency((s) => ({ ...s, phone: e.target.value }))} />
                <div style={{ display: "flex", gap: 8 }}>
                  <button className="st-btn-primary st-btn-sm" onClick={saveEmergency}>Save</button>
                  <button className="st-btn-outline st-btn-sm" onClick={() => setEditEm(false)}>Cancel</button>
                </div>
              </div>
            )}
            <div className="st-warn-box">
              <span className="st-warn-icon"><Icon name="info" size={18} /></span>
              <span>In case you need emergency support, we will reach out to this person to provide appropriate help.</span>
            </div>
          </section>

          {/* Tips */}
          <section className="st-card st-tips">
            <div className="st-tips-mascot"><Mascot variant="wave" size={104} /></div>
            <div className="st-tips-body">
              <div className="st-tips-title">Tips from MindCare AI</div>
              <p className="st-tips-text">
                Protecting your privacy is very important. Always keep your security information up
                to date and only share data you feel comfortable with.
              </p>
            </div>
          </section>
        </div>
      </div>

      <p className="st-footer">
        <Icon name="shield" size={15} />
        MindCare AI is committed to protecting your personal data. We never share your information
        with third parties without your consent.
      </p>
    </div>
  );
}
