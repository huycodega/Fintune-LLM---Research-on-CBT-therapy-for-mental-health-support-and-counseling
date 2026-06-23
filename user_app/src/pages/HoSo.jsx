import { useState, useEffect } from "react";
import { api } from "../api.js";
import Mascot from "../components/Mascot.jsx";

const CONSENT_LABELS = {
  store_data: "I agree to MindCare AI storing my data to personalize my experience.",
  emails: "I agree to receive emails about lessons and wellness programs.",
  data_use: "I understand how my data is used for support purposes.",
};

const ACTIVITY_ICON = { screening: "✓", lesson: "📖", chat: "💬", resource: "↓" };
const ACTIVITY_TONE = { screening: "green", lesson: "orange", chat: "purple", resource: "blue" };

function fmtDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "2-digit", year: "numeric" });
}
function fmtDateTime(iso) {
  if (!iso) return "";
  return new Date(iso)
    .toLocaleString("en-GB", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" })
    .replace(",", " ·");
}

function FieldItem({ icon, label, value }) {
  return (
    <div className="profile-field-item">
      <div className="profile-field-icon">{icon}</div>
      <div>
        <div className="profile-field-label">{label}</div>
        <div className="profile-field-value">{value || "—"}</div>
      </div>
    </div>
  );
}

function ProgressCard({ icon, value, label, meta, accent = "green" }) {
  return (
    <div className={`progress-snapshot-card ${accent}`}>
      <div className="progress-snapshot-icon">{icon}</div>
      <div className="progress-snapshot-copy">
        <div className="progress-snapshot-value">{value}</div>
        <div className="progress-snapshot-label">{label}</div>
        <div className="progress-snapshot-meta">{meta}</div>
      </div>
    </div>
  );
}

export default function HoSo({ user }) {
  const [profile, setProfile] = useState(null);
  const [overview, setOverview] = useState(null);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState(null);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.myProfile().catch(() => null).then(setProfile);
    api.myOverview().catch(() => null).then(setOverview);
  }, []);

  function startEdit() {
    setErr("");
    setForm({
      full_name: profile?.full_name || "",
      phone: profile?.phone || "",
      date_of_birth: profile?.date_of_birth || "",
      gender: profile?.gender || "",
      wellness_goal: profile?.wellness_goal || "",
      emergency: {
        name: profile?.emergency?.name || "",
        relationship: profile?.emergency?.relationship || "",
        phone: profile?.emergency?.phone || "",
      },
    });
    setEditing(true);
  }

  async function save() {
    setSaving(true);
    setErr("");
    try {
      const updated = await api.updateProfile(form);
      setProfile(updated);
      setEditing(false);
    } catch (e) {
      setErr(e.message || "Could not save");
    } finally {
      setSaving(false);
    }
  }

  const userName = (profile?.full_name || user?.username || "there").split("@")[0];
  const initials = userName.slice(0, 2).toUpperCase();
  const consent = profile?.consent || {};
  const activities = overview?.recent_activity || [];

  const f = (k) => form[k];
  const setF = (k, v) => setForm((s) => ({ ...s, [k]: v }));
  const setEm = (k, v) => setForm((s) => ({ ...s, emergency: { ...s.emergency, [k]: v } }));

  return (
    <div className="profile-page-v2">
      <header className="profile-page-header">
        <div>
          <h1>Your Profile</h1>
          <p>Manage your personal information and track your mental wellness journey.</p>
        </div>
      </header>

      <div className="profile-dashboard-grid">
        <main className="profile-main-column">
          <section className="profile-card profile-identity-card">
            <div className="profile-avatar-wrap large">
              <div className="profile-avatar">{initials}</div>
            </div>

            <div className="profile-identity-content">
              <div className="profile-identity-topline">
                <div>
                  <h2>Hello, {userName}! 👋</h2>
                  <p>MindCare AI is here to support your mental wellness every day.</p>
                </div>
                {!editing
                  ? <button className="btn btn-ghost" type="button" onClick={startEdit}>✎ Edit Profile</button>
                  : (
                    <div style={{ display: "flex", gap: 8 }}>
                      <button className="btn btn-primary btn-sm" type="button" disabled={saving} onClick={save}>
                        {saving ? "Saving…" : "Save"}
                      </button>
                      <button className="btn btn-ghost btn-sm" type="button" disabled={saving} onClick={() => setEditing(false)}>Cancel</button>
                    </div>
                  )}
              </div>

              {err && <div className="banner crisis" style={{ marginTop: 10 }}>{err}</div>}

              {!editing ? (
                <div className="profile-info-panel">
                  <FieldItem icon="👤" label="Full Name" value={profile?.full_name} />
                  <FieldItem icon="☎" label="Phone Number" value={profile?.phone} />
                  <FieldItem icon="✉" label="Email" value={profile?.email} />
                  <FieldItem icon="📅" label="Date of Birth" value={fmtDate(profile?.date_of_birth)} />
                  <FieldItem icon="⚥" label="Gender" value={profile?.gender} />
                  <FieldItem icon="◌" label="Age Group" value={profile?.age} />
                </div>
              ) : (
                <div className="profile-edit-grid">
                  <label className="profile-edit-field"><span>Full Name</span>
                    <input className="input" value={f("full_name")} onChange={(e) => setF("full_name", e.target.value)} /></label>
                  <label className="profile-edit-field"><span>Phone Number</span>
                    <input className="input" value={f("phone")} onChange={(e) => setF("phone", e.target.value)} placeholder="0901 234 567" /></label>
                  <label className="profile-edit-field"><span>Date of Birth</span>
                    <input className="input" type="date" value={f("date_of_birth")} onChange={(e) => setF("date_of_birth", e.target.value)} /></label>
                  <label className="profile-edit-field"><span>Gender</span>
                    <select className="input" value={f("gender")} onChange={(e) => setF("gender", e.target.value)}>
                      <option value="">Prefer not to say</option>
                      <option>Male</option><option>Female</option><option>Other</option>
                    </select></label>
                </div>
              )}
            </div>
          </section>

          <section className="profile-card profile-detail-section">
            <div className="profile-section-heading">
              <div>
                <span className="profile-section-kicker">Safety network</span>
                <h3>Emergency Contact</h3>
              </div>
            </div>
            {!editing ? (
              <div className="emergency-contact-grid">
                <FieldItem icon="👥" label="Contact Name" value={profile?.emergency?.name} />
                <FieldItem icon="♡" label="Relationship" value={profile?.emergency?.relationship} />
                <FieldItem icon="☎" label="Phone Number" value={profile?.emergency?.phone} />
              </div>
            ) : (
              <div className="profile-edit-grid">
                <label className="profile-edit-field"><span>Contact Name</span>
                  <input className="input" value={form.emergency.name} onChange={(e) => setEm("name", e.target.value)} /></label>
                <label className="profile-edit-field"><span>Relationship</span>
                  <input className="input" value={form.emergency.relationship} onChange={(e) => setEm("relationship", e.target.value)} /></label>
                <label className="profile-edit-field"><span>Phone Number</span>
                  <input className="input" value={form.emergency.phone} onChange={(e) => setEm("phone", e.target.value)} /></label>
              </div>
            )}
          </section>

          <section className="profile-card profile-detail-section">
            <div className="profile-section-heading">
              <div>
                <span className="profile-section-kicker">Personal focus</span>
                <h3>Mental Wellness Goal</h3>
              </div>
            </div>
            {!editing ? (
              <p className="wellness-goal-text">
                {profile?.wellness_goal || "No goal set yet — click Edit Profile to add one."}
              </p>
            ) : (
              <textarea className="input" rows={3} value={f("wellness_goal")}
                onChange={(e) => setF("wellness_goal", e.target.value)}
                placeholder="e.g. Reduce stress, improve sleep quality, and maintain emotional balance." />
            )}
          </section>

          <section className="profile-card profile-consent-card">
            <div className="profile-section-heading">
              <div>
                <span className="profile-section-kicker">Data choices</span>
                <h3>Privacy &amp; Consent</h3>
              </div>
            </div>
            <div className="consent-content-grid">
              <div className="consent-checklist">
                {Object.entries(CONSENT_LABELS).map(([key, label]) => (
                  <div className="consent-check-item" key={key} style={{ opacity: consent[key] ? 1 : 0.45 }}>
                    <span>{consent[key] ? "✓" : "○"}</span>
                    <p>{label}</p>
                  </div>
                ))}
                <div className="profile-policy-links">
                  <a href="#privacy">Privacy Policy</a>
                  <a href="#terms">Terms of Service</a>
                </div>
              </div>
              <div className="consent-status-panel">
                <div className="consent-status-row">
                  <span>Consent Status</span>
                  <strong>{Object.values(consent).some(Boolean) ? "Agreed" : "Not set"}</strong>
                </div>
                <div className="consent-status-row">
                  <span>Last Updated Date</span>
                  <strong>{fmtDate(profile?.consent_updated_at)}</strong>
                </div>
              </div>
            </div>
          </section>

          <section className="profile-card progress-snapshot-section">
            <div className="profile-section-heading compact">
              <div>
                <h3>Progress Snapshot</h3>
                <p>A quick view of your mental wellness journey.</p>
              </div>
            </div>
            <div className="progress-snapshot-grid">
              <ProgressCard icon="✓" value={overview?.screenings_completed ?? 0} label="Screenings Completed"
                meta={overview?.last_screening_at ? `Last completed: ${fmtDate(overview.last_screening_at)}` : "No screenings yet"} />
              <ProgressCard icon="🔥" value={overview?.streak ?? 0} label="Learning Streak" meta="Days in a row" accent="orange" />
              <ProgressCard icon="💬" value={overview?.ai_sessions ?? 0} label="AI Support Sessions" meta="Support is always available" accent="blue" />
              <ProgressCard icon="📁" value={overview?.resources_saved ?? 0} label="Resources Saved" meta="Helpful tools saved" accent="mint" />
            </div>
          </section>
        </main>

        <aside className="profile-sidebar-column">
          <section className="profile-card profile-motivation-card">
            <Mascot variant="success" size={180} />
            <h3>You're doing great! 💚</h3>
            <p>Keep taking small steps toward better mental wellness.</p>
          </section>

          <section className="profile-card recent-activity-card">
            <div className="profile-section-heading compact">
              <h3>Recent Activity</h3>
            </div>
            <div className="recent-activity-list">
              {activities.length === 0 && (
                <p className="profile-field-value" style={{ color: "var(--ink-soft)" }}>No activity yet.</p>
              )}
              {activities.map((item, i) => (
                <div className="recent-activity-item" key={i}>
                  <div className={`recent-activity-icon ${ACTIVITY_TONE[item.type] || "green"}`}>
                    {ACTIVITY_ICON[item.type] || "•"}
                  </div>
                  <div className="recent-activity-line" />
                  <div className="recent-activity-copy">
                    <div className="recent-activity-title">{item.title}</div>
                    <div className="recent-activity-detail">{item.detail}</div>
                    <div className="recent-activity-time">{fmtDateTime(item.time)}</div>
                  </div>
                </div>
              ))}
            </div>
          </section>
        </aside>
      </div>
    </div>
  );
}
