import { useEffect, useRef, useState } from "react";
import Icon from "../admin/Icon.jsx";
import Sidebar from "../admin/Sidebar.jsx";
import TopBar from "../admin/TopBar.jsx";
import { api } from "../api.js";
import { DemoNotice, updatedNow } from "../ui.jsx";

const ROLES = [
  { role: "Administrator", permission: "Full Access", users: 3, tone: "green" },
  { role: "Manager", permission: "General Management", users: 8, tone: "blue" },
  { role: "Specialist", permission: "Professional", users: 24, tone: "purple" },
  { role: "Partner", permission: "Report View Only", users: 7, tone: "amber" },
];

const INTEGRATIONS = [
  { name: "Email (SMTP)", icon: "mail", tone: "blue", connected: true },
  { name: "SMS Gateway", icon: "message", tone: "green", connected: true },
  { name: "Google Analytics 4", icon: "bars", tone: "orange", connected: true },
  { name: "SSO (SAML/OAuth)", icon: "key", tone: "indigo", connected: false },
];

const INITIAL = {
  general: {
    systemName: "MindCare AI", timeZone: "(UTC+07:00) Bangkok, Hanoi, Jakarta",
    language: "Vietnamese", dateFormat: "DD/MM/YYYY", timeFormat: "24-hour",
    registration: true, emailVerification: true,
  },
  privacy: { twoFactor: true, timeout: "30 minutes", passwordPolicy: true, hideSensitive: true },
  notifications: { email: true, inApp: true, emergencies: true, dailySummary: false, recipients: "admin@mindcare.ai, manager@mindcare.ai" },
  hotline: { primary: "1900 1234", backup: "1900 5678", workflow: "Call hotline → Notify specialist → Send email", email: "crisis@mindcare.ai" },
  backup: { automatic: true, retention: "30 days" },
};

const INITIAL_THRESHOLDS = [
  { level: "Low", range: "0–24", color: "#22C55E", action: "Record Only", tone: "low" },
  { level: "Moderate", range: "25–49", color: "#F59E0B", action: "Send Support Resources", tone: "moderate" },
  { level: "High", range: "50–74", color: "#EF4444", action: "Notify Specialist", tone: "high" },
  { level: "Crisis", range: "75–100", color: "#DC2626", action: "Trigger Emergency Workflow", tone: "crisis" },
];

const INITIAL_RULES = [
  { name: "Self-harm / Suicide", icon: "alert", tone: "red", action: "Block Content & Trigger Emergency" },
  { name: "Violence / Threats", icon: "shield", tone: "amber", action: "Block Content & Forward to Specialist" },
  { name: "Adult Content", icon: "users", tone: "purple", action: "Block Content" },
  { name: "Personal Information", icon: "lock", tone: "blue", action: "Hide & Warn User" },
];

function CardHeader({ icon, title, subtitle }) {
  return <div className="st-card-head"><span className="st-card-icon"><Icon name={icon} size={17} /></span><div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div></div>;
}

function Field({ label, children, helper }) {
  return <label className="st-field"><span>{label}</span>{children}{helper && <small>{helper}</small>}</label>;
}

function TextInput({ value, onChange, type = "text", required = false }) {
  return <input className="st-input" type={type} value={value} required={required} onChange={(event) => onChange(event.target.value)} />;
}

function Select({ value, onChange, children }) {
  return <select className="st-select" value={value} onChange={(event) => onChange(event.target.value)}>{children || <option>{value}</option>}</select>;
}

function Toggle({ checked, onChange, label, description }) {
  return <label className="st-toggle-row"><span><b>{label}</b>{description && <small>{description}</small>}</span><input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} /><i aria-hidden="true"><span /></i></label>;
}

function SaveButton({ saved }) {
  return <button className={`st-save ${saved ? "saved" : ""}`} type="submit">{saved ? <><Icon name="check" size={15} />Saved</> : "Save Changes"}</button>;
}

function GeneralCard({ data, setValue, onSave, saved }) {
  return <form id="settings-general" className="st-card st-rise" style={{ "--i": 0 }} onSubmit={(event) => onSave("general", event)}>
    <CardHeader icon="sliders" title="General Settings" />
    <div className="st-form-grid">
      <Field label="System Name"><TextInput value={data.systemName} required onChange={(value) => setValue("systemName", value)} /></Field>
      <Field label="Time Zone"><Select value={data.timeZone} onChange={(value) => setValue("timeZone", value)}><option>(UTC+07:00) Bangkok, Hanoi, Jakarta</option><option>(UTC+00:00) Coordinated Universal Time</option></Select></Field>
      <Field label="Default Language"><Select value={data.language} onChange={(value) => setValue("language", value)}><option>Vietnamese</option><option>English</option></Select></Field>
      <Field label="Date Format"><Select value={data.dateFormat} onChange={(value) => setValue("dateFormat", value)}><option>DD/MM/YYYY</option><option>MM/DD/YYYY</option><option>YYYY-MM-DD</option></Select></Field>
      <Field label="Time Format"><Select value={data.timeFormat} onChange={(value) => setValue("timeFormat", value)}><option>24-hour</option><option>12-hour</option></Select></Field>
    </div>
    <div className="st-toggle-list"><Toggle checked={data.registration} onChange={(value) => setValue("registration", value)} label="Allow New User Registration" description="Allow users to register new accounts." /><Toggle checked={data.emailVerification} onChange={(value) => setValue("emailVerification", value)} label="Require Email Verification" description="Users must verify email before signing in." /></div>
    <div className="st-card-foot"><SaveButton saved={saved} /></div>
  </form>;
}

function RolesCard({ roles, openMenu, setOpenMenu }) {
  return <section id="settings-roles" className="st-card st-rise" style={{ "--i": 1 }}>
    <CardHeader icon="users" title="Roles & Permissions" subtitle="Manage roles and permissions in the system." />
    <div className="st-table-wrap"><table className="st-table"><thead><tr><th>Role</th><th>Users</th><th>Actions</th></tr></thead><tbody>{roles.map((row, index) => <tr key={row.role} style={{ "--i": index }}><td><b>{row.role}</b><span className={`st-permission ${row.tone}`}>{row.permission}</span></td><td>{row.users}</td><td className="st-action-cell"><button onClick={() => setOpenMenu(openMenu === row.role ? null : row.role)} aria-label={`Actions for ${row.role}`}><Icon name="dots" size={17} /></button>{openMenu === row.role && <div className="st-action-menu"><button>Edit role</button><button>View users</button></div>}</td></tr>)}</tbody></table></div>
    <button className="st-outline">Manage Roles</button>
  </section>;
}

function PrivacyCard({ data, setValue, onSave, saved }) {
  return <form id="settings-privacy" className="st-card st-rise" style={{ "--i": 2 }} onSubmit={(event) => onSave("privacy", event)}>
    <CardHeader icon="lock" title="Privacy & Security" />
    <div className="st-toggle-list"><Toggle checked={data.twoFactor} onChange={(value) => setValue("twoFactor", value)} label="Two-Factor Authentication (2FA)" description="Require 2FA for administrator accounts." />
      <div className="st-inline-setting"><span><b>Login Session Timeout</b><small>Automatically sign out after inactivity.</small></span><Select value={data.timeout} onChange={(value) => setValue("timeout", value)}><option>15 minutes</option><option>30 minutes</option><option>1 hour</option></Select></div>
      <Toggle checked={data.passwordPolicy} onChange={(value) => setValue("passwordPolicy", value)} label="Password Policy" description="Require strong passwords with at least 8 characters, letters, numbers, and special characters." />
      <Toggle checked={data.hideSensitive} onChange={(value) => setValue("hideSensitive", value)} label="Hide Sensitive Personal Information" description="Hide email and phone numbers from unauthorized viewers." /></div>
    <div className="st-card-foot"><SaveButton saved={saved} /></div>
  </form>;
}

function ThresholdCard({ rows, setRows }) {
  function update(index, key, value) { setRows((current) => current.map((row, rowIndex) => rowIndex === index ? { ...row, [key]: value } : row)); }
  return <section id="settings-ai" className="st-card st-rise" style={{ "--i": 3 }}><CardHeader icon="alert" title="AI Alert Thresholds" subtitle="Set risk score thresholds so the system can classify risk levels and trigger actions." />
    <div className="st-table-wrap"><table className="st-table st-risk-table"><thead><tr><th>Risk Level</th><th>Score Range (0–100)</th><th>Display Color</th><th>Default Action</th></tr></thead><tbody>{rows.map((row, index) => <tr key={row.level} style={{ "--i": index }}><td><span className={`st-risk-dot ${row.tone}`} />{row.level}</td><td><input value={row.range} onChange={(event) => update(index, "range", event.target.value)} /></td><td><label className="st-color"><input type="color" value={row.color} onChange={(event) => update(index, "color", event.target.value.toUpperCase())} /><span>{row.color}</span></label></td><td><Select value={row.action} onChange={(value) => update(index, "action", value)}><option>{row.action}</option><option>Record Only</option><option>Send Support Resources</option><option>Notify Specialist</option><option>Trigger Emergency Workflow</option></Select></td></tr>)}</tbody></table></div>
  </section>;
}

function ModerationCard({ rows, setRows }) {
  return <section id="settings-moderation" className="st-card st-rise" style={{ "--i": 4 }}><CardHeader icon="shieldCheck" title="Moderation Rules" subtitle="Configure AI rules to detect harmful content and risky behavior." />
    <div className="st-rule-list">{rows.map((row, index) => <div className="st-rule" key={row.name}><span className={`st-rule-icon ${row.tone}`}><Icon name={row.icon} size={15} /></span><b>{row.name}</b><Select value={row.action} onChange={(value) => setRows((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, action: value } : item))}><option>{row.action}</option><option>Block Content</option><option>Hide & Warn User</option><option>Block Content & Trigger Emergency</option><option>Block Content & Forward to Specialist</option></Select></div>)}</div>
  </section>;
}

function NotificationsCard({ data, setValue, onSave, saved }) {
  return <form id="settings-notifications" className="st-card st-rise" style={{ "--i": 5 }} onSubmit={(event) => onSave("notifications", event)}><CardHeader icon="bell" title="Notifications" subtitle="Configure system notifications and delivery channels." />
    <div className="st-toggle-list compact"><Toggle checked={data.email} onChange={(value) => setValue("email", value)} label="System Email Notifications" /><Toggle checked={data.inApp} onChange={(value) => setValue("inApp", value)} label="In-App Notifications" /><Toggle checked={data.emergencies} onChange={(value) => setValue("emergencies", value)} label="Notify Specialists for Emergency Cases" /><Toggle checked={data.dailySummary} onChange={(value) => setValue("dailySummary", value)} label="Daily Summary Report" /></div>
    <Field label="Report Recipient Emails" helper="Separate multiple emails with commas."><TextInput value={data.recipients} required onChange={(value) => setValue("recipients", value)} /></Field><div className="st-card-foot"><SaveButton saved={saved} /></div>
  </form>;
}

function HotlineCard({ data, setValue, onSave, saved }) {
  return <form id="settings-hotline" className="st-card st-rise" style={{ "--i": 6 }} onSubmit={(event) => onSave("hotline", event)}><CardHeader icon="phone" title="Emergency Hotline" subtitle="Configure hotline numbers and emergency support workflow." />
    <div className="st-form-grid"><Field label="Primary Hotline Number"><TextInput value={data.primary} required onChange={(value) => setValue("primary", value)} /></Field><Field label="Backup Hotline Number"><TextInput value={data.backup} onChange={(value) => setValue("backup", value)} /></Field><Field label="Escalation Workflow"><Select value={data.workflow} onChange={(value) => setValue("workflow", value)}><option>Call hotline → Notify specialist → Send email</option><option>Notify specialist → Call hotline</option></Select></Field><Field label="Emergency Alert Email"><TextInput type="email" value={data.email} required onChange={(value) => setValue("email", value)} /></Field></div><div className="st-card-foot"><SaveButton saved={saved} /></div>
  </form>;
}

function IntegrationsCard({ integrations, configured, configure }) {
  return <section id="settings-integrations" className="st-card st-rise" style={{ "--i": 7 }}><CardHeader icon="plug" title="System Integrations" subtitle="Connect external services and third-party systems." /><div className="st-integration-list">{integrations.map((item, index) => <div className="st-integration" style={{ "--i": index }} key={item.name}><span className={`st-integration-icon ${item.tone}`}><Icon name={item.icon} size={17} /></span><b>{item.name}</b><span className={`st-connection ${item.connected ? "connected" : "disconnected"}`}>{item.connected ? "Connected" : "Not Connected"}</span><button onClick={() => configure(item.name)}>{configured === item.name ? "Configured" : "Configure"}</button></div>)}</div></section>;
}

function BackupCard({ data, setValue, status, runAction }) {
  return <section id="settings-backup" className="st-card st-rise" style={{ "--i": 8 }}><CardHeader icon="backup" title="Backup & Restore" subtitle="Manage system backup and recovery data." /><div className="st-toggle-list"><Toggle checked={data.automatic} onChange={(value) => setValue("automatic", value)} label="Automatic Backup" description="Automatically back up data daily at 02:00." /><div className="st-inline-setting"><span><b>Backup Retention</b></span><Select value={data.retention} onChange={(value) => setValue("retention", value)}><option>7 days</option><option>30 days</option><option>90 days</option></Select></div></div><div className="st-backup-actions"><button className="st-outline" onClick={() => runAction("backup")}><Icon name={status === "backup" ? "check" : "backup"} size={15} />{status === "backup" ? "Backup Complete" : "Back Up Now"}</button><button className="st-danger" onClick={() => runAction("restore")}><Icon name="restore" size={15} />{status === "restore" ? "Restore Ready" : "Restore Data"}</button></div></section>;
}

function SettingsSkeleton() {
  return <div className="st-skeleton-grid">{Array.from({ length: 9 }, (_, index) => <div className="st-skeleton" style={{ "--i": index }} key={index}><i /><i /><i /><i /></div>)}</div>;
}

// Stat row — matches the la-stats row used on every other admin page.
function SettingsStats({ roles, integrations, rulesCount }) {
  const connected = integrations.filter((item) => item.connected).length;
  const members = roles.reduce((sum, row) => sum + (row.users || 0), 0);
  const cards = [
    ["shieldCheck", "indigo", "Admin Roles", String(roles.length), "configured"],
    ["users", "green", "Role Members", String(members), "across all roles"],
    ["plug", "orange", "Integrations", `${connected}/${integrations.length}`, "connected"],
    ["shield", "red", "Moderation Rules", String(rulesCount), "enforced"],
  ];
  return <section className="la-stats st-stats">{cards.map(([icon, tone, label, value, sub], index) => (
    <div className="la-stat la-rise" style={{ "--i": index }} key={label}>
      <div className={`la-stat-icon tone-${tone}`}><Icon name={icon} size={22} /></div>
      <div className="la-stat-body">
        <div className="la-stat-label">{label}</div>
        <div className="la-stat-value">{value}</div>
        <div className="la-stat-sub">{sub}</div>
      </div>
    </div>
  ))}</section>;
}

export default function SettingsAdmin({ onLogout, onNav }) {
  const [values, setValues] = useState(INITIAL);
  const [thresholds, setThresholds] = useState(INITIAL_THRESHOLDS);
  const [rules, setRules] = useState(INITIAL_RULES);
  const [roles, setRoles] = useState(ROLES);
  const [integrations, setIntegrations] = useState(INTEGRATIONS);
  const [saved, setSaved] = useState("");
  const [openRole, setOpenRole] = useState(null);
  const [configured, setConfigured] = useState("");
  const [backupStatus, setBackupStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [demo, setDemo] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [updatedLabel, setUpdatedLabel] = useState(updatedNow);
  const ready = useRef(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const data = await api.settings();
        if (!alive) return;
        setValues({
          general: data.general || INITIAL.general,
          privacy: data.privacy || INITIAL.privacy,
          notifications: data.notifications || INITIAL.notifications,
          hotline: data.hotline || INITIAL.hotline,
          backup: data.backup || INITIAL.backup,
        });
        if (Array.isArray(data.thresholds) && data.thresholds.length) setThresholds(data.thresholds);
        if (Array.isArray(data.rules) && data.rules.length) setRules(data.rules);
        if (Array.isArray(data.roles) && data.roles.length) setRoles(data.roles);
        if (Array.isArray(data.integrations) && data.integrations.length) setIntegrations(data.integrations);
        if (data.meta?.updated_at) setUpdatedLabel(updatedNow());
        setDemo(false);
      } catch (error) {
        console.error("Settings API unavailable:", error);
        if (alive) setDemo(true);
      } finally {
        if (alive) { setLoading(false); ready.current = true; }
      }
    })();
    return () => { alive = false; };
  }, []);

  function setSection(section, key, value) { setValues((current) => ({ ...current, [section]: { ...current[section], [key]: value } })); }

  async function persist(section, value) {
    if (demo) return false;
    try { await api.updateSettings(section, value); return true; }
    catch (error) { console.error(`Failed to save ${section}:`, error); return false; }
  }

  async function save(section, event) {
    event.preventDefault();
    const ok = await persist(section, values[section]);
    if (!ok && !demo) return;            // surface failures by not flashing "Saved"
    setSaved(section);
    setTimeout(() => setSaved((current) => current === section ? "" : current), 1500);
  }

  // Cards without an explicit Save button (AI thresholds, moderation rules,
  // backup toggles) auto-persist on change, debounced so per-keystroke edits
  // don't spam the API. Skipped until the initial load has populated state.
  useEffect(() => { if (!ready.current) return; const t = setTimeout(() => persist("thresholds", thresholds), 700); return () => clearTimeout(t); }, [thresholds]);
  useEffect(() => { if (!ready.current) return; const t = setTimeout(() => persist("rules", rules), 700); return () => clearTimeout(t); }, [rules]);
  useEffect(() => { if (!ready.current) return; const t = setTimeout(() => persist("backup", values.backup), 700); return () => clearTimeout(t); }, [values.backup]);

  function configure(name) { setConfigured(name); setTimeout(() => setConfigured((current) => current === name ? "" : current), 1400); }

  async function runBackup(action) {
    setBackupStatus(action);
    try { await (action === "restore" ? api.settingsRestore() : api.settingsBackup()); }
    catch (error) { console.error(`Backup action '${action}' failed:`, error); }
    setTimeout(() => setBackupStatus((current) => current === action ? "" : current), 1600);
  }

  function jump(id) { document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" }); }
  const filterPanel = <><label>Settings group<select><option>All settings</option><option>Security</option><option>AI & Moderation</option><option>Integrations</option></select></label><button onClick={() => jump("settings-general")}>Show Settings</button></>;

  return <div className="la-shell st-shell">{mobileOpen && <button className="st-nav-scrim" onClick={() => setMobileOpen(false)} aria-label="Close navigation" />}<Sidebar active="settings" onNav={onNav} mobileOpen={mobileOpen} onClose={() => setMobileOpen(false)} /><main className="la-main st-main"><TopBar title="System Settings" subtitle={updatedLabel} searchPlaceholder="Search users, email, phone..." onLogout={onLogout} onMenu={() => setMobileOpen(true)} filterPanel={filterPanel} />
    <div className="la-content la-content-nopanel st-content">{loading ? <SettingsSkeleton /> : <div className="la-content-left">{demo && <div style={{ marginBottom: 12 }}><DemoNotice>Sample settings shown — changes won't be saved until the settings API is connected.</DemoNotice></div>}<SettingsStats roles={roles} integrations={integrations} rulesCount={rules.length} /><div className="st-grid"><div className="st-column"><GeneralCard data={values.general} setValue={(key, value) => setSection("general", key, value)} onSave={save} saved={saved === "general"} /><ThresholdCard rows={thresholds} setRows={setThresholds} /><ModerationCard rows={rules} setRows={setRules} /></div><div className="st-column"><RolesCard roles={roles} openMenu={openRole} setOpenMenu={setOpenRole} /><NotificationsCard data={values.notifications} setValue={(key, value) => setSection("notifications", key, value)} onSave={save} saved={saved === "notifications"} /><IntegrationsCard integrations={integrations} configured={configured} configure={configure} /></div><div className="st-column"><PrivacyCard data={values.privacy} setValue={(key, value) => setSection("privacy", key, value)} onSave={save} saved={saved === "privacy"} /><HotlineCard data={values.hotline} setValue={(key, value) => setSection("hotline", key, value)} onSave={save} saved={saved === "hotline"} /><BackupCard data={values.backup} setValue={(key, value) => setSection("backup", key, value)} status={backupStatus} runAction={runBackup} /></div></div></div>}</div>
  </main></div>;
}
