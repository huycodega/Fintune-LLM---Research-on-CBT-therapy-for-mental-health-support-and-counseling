import { useState, useEffect } from "react";
import { api } from "../api.js";
import Mascot from "../components/Mascot.jsx";

/* ── Inline Flaticon-style SVG icons (soft-green line set) ─────── */
function SvgIcon({ name, size = 28 }) {
  const c = {
    width: size, height: size, viewBox: "0 0 24 24", fill: "none",
    stroke: "currentColor", strokeWidth: 1.9, strokeLinecap: "round",
    strokeLinejoin: "round", "aria-hidden": "true",
  };
  switch (name) {
    case "shield":    return <svg {...c}><path d="M12 3 19 6v5c0 4.4-2.8 8.4-7 10-4.2-1.6-7-5.6-7-10V6l7-3Z" /><path d="m9.5 12 1.7 1.7 3.6-4" /></svg>;
    case "bot":       return <svg {...c}><path d="M12 8V5" /><path d="M8 5h8" /><rect x="5" y="8" width="14" height="10" rx="5" /><path d="M9 13h.01" /><path d="M15 13h.01" /><path d="M9.5 17c1.6 1 3.4 1 5 0" /></svg>;
    case "book":      return <svg {...c}><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v16H6.5A2.5 2.5 0 0 0 4 21V5.5Z" /><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20" /><path d="M8 7h8" /></svg>;
    case "folder":    return <svg {...c}><path d="M3.5 6.5h6l2 2H20.5v10h-17v-12Z" /><path d="M3.5 8.5h17" /></svg>;
    case "audio":     return <svg {...c}><path d="M9 18V5l12-2v13" /><circle cx="6" cy="18" r="3" /><circle cx="18" cy="16" r="3" /></svg>;
    case "user":      return <svg {...c}><circle cx="12" cy="8" r="3.5" /><path d="M5.5 20a6.5 6.5 0 0 1 13 0" /></svg>;
    case "clipboard": return <svg {...c}><rect x="6" y="4.5" width="12" height="16" rx="2" /><path d="M9.5 4.5V3.2h5v1.3" /><path d="M8.5 11h7M8.5 14.5h5" /></svg>;
    case "growth":    return <svg {...c}><path d="M4 5v15h16" /><path d="M7.5 14l3-3.2 2.6 1.8 4.4-5" /><path d="M17.5 7.6h2v2" /></svg>;
    case "compass":   return <svg {...c}><circle cx="12" cy="12" r="8.5" /><path d="M15.5 8.5l-2 5.2-5.2 2 2-5.2z" /></svg>;
    case "bulb":      return <svg {...c}><path d="M9.2 17.5h5.6" /><path d="M10 20.5h4" /><path d="M12 3.2a6 6 0 0 0-3.7 10.7c.7.6 1.2 1.4 1.2 2.3v.3h5v-.3c0-.9.5-1.7 1.2-2.3A6 6 0 0 0 12 3.2z" /></svg>;
    case "send":      return <svg {...c}><path d="M21 3 10.5 13.5" /><path d="M21 3l-6.6 18-3.9-7.5L3 9.6z" /></svg>;
    case "article":   return <svg {...c}><rect x="5" y="3.5" width="14" height="17" rx="2" /><path d="M8.5 8.5h7M8.5 12h7M8.5 15.5h4" /></svg>;
    case "play":      return <svg {...c}><circle cx="12" cy="12" r="8.5" /><path d="M10.2 8.7l5 3.3-5 3.3z" /></svg>;
    case "check":     return <svg {...c}><circle cx="12" cy="12" r="8.5" /><path d="M8.5 12l2.5 2.5 4.5-5" /></svg>;
    case "arrow":     return <svg {...c}><path d="M5 12h13" /><path d="M12.5 6l6 6-6 6" /></svg>;
    default:          return <svg {...c}><circle cx="12" cy="12" r="3.2" /><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.05.05a2 2 0 0 1-2.83 2.83l-.05-.05A1.7 1.7 0 0 0 15 19.4a1.7 1.7 0 0 0-1 1.56V21a2 2 0 0 1-4 0v-.04A1.7 1.7 0 0 0 9 19.4a1.7 1.7 0 0 0-1.88.34l-.05.05a2 2 0 0 1-2.83-2.83l.05-.05A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-1.56-1H3a2 2 0 0 1 0-4h.04A1.7 1.7 0 0 0 4.6 9a1.7 1.7 0 0 0-.34-1.88l-.05-.05a2 2 0 0 1 2.83-2.83l.05.05A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-1.56V3a2 2 0 0 1 4 0v.04A1.7 1.7 0 0 0 15 4.6a1.7 1.7 0 0 0 1.88-.34l.05-.05a2 2 0 0 1 2.83 2.83l-.05.05A1.7 1.7 0 0 0 19.4 9a1.7 1.7 0 0 0 1.56 1H21a2 2 0 0 1 0 4h-.04A1.7 1.7 0 0 0 19.4 15Z" /></svg>;
  }
}

const FEATURES = [
  { id: "sangloc",   icon: "shield",   title: "Screening",   desc: "Assess your stress, anxiety, and depression levels quickly and privately.", link: "Start" },
  { id: "chat",      icon: "bot",      title: "AI Support",  desc: "Chat anonymously with AI to be heard and get timely support.",             link: "Chat" },
  { id: "baihoc",    icon: "book",     title: "CBT Lessons", desc: "Learn effective CBT techniques through short, easy-to-apply lessons.",       link: "Learn Now" },
  { id: "tainguyen", icon: "folder",   title: "Resources",   desc: "Explore helpful articles, audio, and videos for mental wellness.",           link: "Explore" },
  { id: "hoso",      icon: "user",     title: "Profile",     desc: "Track your progress and manage your personal information.",                  link: "View Profile" },
  { id: "caidat",    icon: "settings", title: "Settings",    desc: "Customize your experience and manage your account.",                         link: "Settings" },
];

const HOW_STEPS = [
  { num: "1", icon: "clipboard", title: "Screening",           desc: "Assess your current mental state." },
  { num: "2", icon: "bot",       title: "AI Support",          desc: "Get guidance, a listening ear, and relevant suggestions." },
  { num: "3", icon: "book",      title: "Lessons & Resources", desc: "Build skills and explore helpful content." },
  { num: "4", icon: "growth",    title: "Track Your Journey",  desc: "Monitor your progress and maintain positive habits." },
];

const FEATURED_LESSONS = [
  { icon: "article", iconBg: "#EAF4FF", iconColor: "#4F6BED", title: "10 Ways to Reduce Anxiety Effectively", type: "Article", duration: "8 min read" },
  { icon: "audio",   iconBg: "#E9F8F2", iconColor: "#2BA37F", title: "4-7-8 Breathing Exercise",             type: "Audio",   duration: "5 min" },
  { icon: "play",    iconBg: "#FFF0E6", iconColor: "#F59E0B", title: "Meditation for Beginners",             type: "Video",   duration: "12 min" },
];

const ACTIVITY_STYLE = {
  screening: { icon: "shield", iconBg: "#E9F8F2", iconColor: "#2BA37F" },
  lesson:    { icon: "book",   iconBg: "#EEF4FF", iconColor: "#4F6BED" },
  chat:      { icon: "bot",    iconBg: "#F3EEFF", iconColor: "#8B5CF6" },
};
const LESSON_STYLE = [
  { icon: "book",    iconBg: "#EAF4FF", iconColor: "#4F6BED" },
  { icon: "audio",   iconBg: "#E9F8F2", iconColor: "#2BA37F" },
  { icon: "play",    iconBg: "#FFF0E6", iconColor: "#F59E0B" },
];
function fmtActDate(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleString("en-GB", {
    day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit",
  }).replace(",", "");
}

const RISK_MAP = {
  normal:            { bg: "#E6F8EE", color: "#1F9D55", label: "Low" },
  mild:              { bg: "#E6F8EE", color: "#1F9D55", label: "Low" },
  moderate:          { bg: "#FFF1DB", color: "#E8920C", label: "Medium" },
  moderately_severe: { bg: "#FEECEC", color: "#E0524E", label: "High" },
  severe:            { bg: "#FDE2E2", color: "#C0392B", label: "Very High" },
};

export default function Dashboard({ user, onNav }) {
  const [latest, setLatest] = useState(null);
  const [draft, setDraft] = useState("");
  const [activity, setActivity] = useState([]);
  const [lessons, setLessons] = useState([]);

  useEffect(() => {
    api.latestScreening().catch(() => null).then(setLatest);
    api.myOverview().then((o) => setActivity(o?.recent_activity || [])).catch(() => {});
    api.lessons().then((r) => setLessons(r?.lessons || [])).catch(() => {});
  }, []);

  const risk = RISK_MAP[latest?.phq9_level] || RISK_MAP.moderate;
  const dateStr = latest?.created_at
    ? new Date(latest.created_at).toLocaleString("en-GB", {
        day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit",
      }).replace(",", " ·")
    : "14/06/2024 · 09:24";

  return (
    <div className="dash home-dashboard-v3">
      <main className="dash-main">
        {/* HERO */}
        <section className="hero home-hero-v3">
          <div className="hero-text">
            <h1 className="hero-title">MindCare AI is with you on your mental wellness journey 🌱</h1>
            <p className="hero-sub">
              Listening, understanding, and providing the right solutions so every day feels a little better.
            </p>
            <div className="hero-actions">
              <button className="btn-hero-primary" type="button" onClick={() => onNav("sangloc")}>
                <SvgIcon name="shield" size={18} /> Start Screening
              </button>
              <button className="btn-hero-ghost" type="button" onClick={() => onNav("baihoc")}>
                <SvgIcon name="compass" size={18} /> Explore Features
              </button>
            </div>
          </div>
          <div className="hero-mascot home-hero-mascot-card">
            <Mascot variant="wave" size={250} />
          </div>
        </section>

        {/* MAIN FEATURES */}
        <section className="block home-section-card">
          <div className="block-head"><h2 className="block-title">Main Features</h2></div>
          <div className="features home-feature-grid">
            {FEATURES.map((f) => (
              <button key={f.id} className="feature home-feature-card" type="button" onClick={() => onNav(f.id)}>
                <div className="feature-icon"><SvgIcon name={f.icon} /></div>
                <div className="feature-title">{f.title}</div>
                <div className="feature-desc">{f.desc}</div>
                <span className="feature-link">{f.link}</span>
              </button>
            ))}
          </div>
        </section>

        {/* HOW IT WORKS */}
        <section className="block home-section-card">
          <div className="block-head"><h2 className="block-title">How MindCare AI Works</h2></div>
          <div className="steps home-steps-grid">
            {HOW_STEPS.map((step) => (
              <div key={step.num} className="step home-step-card">
                <div className="step-icon">
                  <SvgIcon name={step.icon} size={24} />
                  <span className="step-num">{step.num}</span>
                </div>
                <div className="step-body">
                  <div className="step-title">{step.num}. {step.title}</div>
                  <div className="step-desc">{step.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* CHAT + FEATURED LESSONS */}
        <div className="dash-bottom home-bottom-grid">
          <section className="block chat-preview home-chat-card">
            <div className="block-head">
              <h2 className="block-title">Chat with AI</h2>
              <button className="block-link" type="button" onClick={() => onNav("chat")}>Open AI Support →</button>
            </div>
            <div className="chat-preview-msg">
              <div className="chat-preview-avatar"><Mascot variant="chat" size={40} /></div>
              <div className="chat-preview-bubble">
                <div className="chat-preview-name">Mindy AI</div>
                I'm here to listen and support you. 💚<br />
                What would you like to share today?
              </div>
            </div>
            <div className="chat-preview-input">
              <input
                placeholder="Type your message..."
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") onNav("chat"); }}
              />
              <button className="chat-preview-send" type="button" onClick={() => onNav("chat")} aria-label="Send">
                <SvgIcon name="send" size={18} />
              </button>
            </div>
          </section>

          <section className="block home-lessons-card">
            <div className="block-head">
              <h2 className="block-title">Featured Lessons</h2>
              <button className="block-link" type="button" onClick={() => onNav("baihoc")}>View All →</button>
            </div>
            <div className="featured-list">
              {(lessons.length ? lessons.slice(0, 3) : FEATURED_LESSONS).map((l, i) => {
                const s = LESSON_STYLE[i % LESSON_STYLE.length];
                return (
                  <button key={l.id || l.title} className="featured-item" type="button" onClick={() => onNav("baihoc")}>
                    <div className="featured-icon" style={{ background: l.iconBg || s.iconBg, color: l.iconColor || s.iconColor }}>
                      <SvgIcon name={l.icon || s.icon} size={20} />
                    </div>
                    <div className="featured-body">
                      <div className="featured-title">{l.title}</div>
                      <div className="featured-meta">{l.category || l.type || "Lesson"} · {l.duration || l.level || "—"}</div>
                    </div>
                    <span className="featured-arrow">›</span>
                  </button>
                );
              })}
            </div>
          </section>
        </div>

        {/* FOOTER NOTE */}
        <p className="dash-footer">
          MindCare AI is committed to protecting your personal data and supporting your wellbeing every day.
        </p>
      </main>

      {/* RIGHT PANEL */}
      <aside className="dash-side home-side-v3">
        {/* Latest screening result */}
        <section className="side-card home-side-card latest-result-card">
          <div className="side-head">
            <h3 className="side-title">Latest Screening Result</h3>
            <span className="side-date">{dateStr}</span>
          </div>
          <div className="side-risk-label">Risk Level</div>
          <span className="risk-pill risk-pill-lg" style={{ background: risk.bg, color: risk.color }}>{risk.label}</span>
          <p className="side-text">You're experiencing some stress. Take time to care for yourself!</p>
          <button className="btn-outline-full" type="button" onClick={() => onNav("sangloc")}>View Result Details</button>
        </section>

        {/* Today's tip */}
        <section className="side-card home-side-card suggest-card">
          <div className="suggest-body">
            <h3 className="side-title"><span className="side-title-icon"><SvgIcon name="bulb" size={18} /></span> Today's Tip</h3>
            <p className="side-text">5 minutes of deep breathing helps reduce stress and improve your mood.</p>
            <button className="btn-primary-sm" type="button" onClick={() => onNav("tainguyen")}>Try Now</button>
          </div>
          <div className="suggest-illu">🧘‍♀️</div>
        </section>

        {/* Motivation */}
        <section className="encourage-card home-motivation-card">
          <div className="encourage-body">
            <div className="encourage-title">You're doing great! 💚</div>
            <p className="encourage-text">Every small step today is big progress for tomorrow.</p>
          </div>
          <Mascot variant="success" size={92} />
        </section>

        {/* Activity history */}
        <section className="side-card home-side-card">
          <div className="side-head">
            <h3 className="side-title">Activity History</h3>
            <button className="block-link" type="button" onClick={() => onNav("hoso")}>View All</button>
          </div>
          <div className="activity-list">
            {activity.length === 0 && (
              <p className="side-text" style={{ padding: "8px 0" }}>No activity yet — start a screening or chat.</p>
            )}
            {activity.map((a, i) => {
              const s = ACTIVITY_STYLE[a.type] || ACTIVITY_STYLE.screening;
              return (
                <div key={i} className="activity-row">
                  <div className="activity-icon" style={{ background: s.iconBg, color: s.iconColor }}><SvgIcon name={s.icon} size={18} /></div>
                  <div className="activity-main">
                    <div className="activity-text">{a.title}</div>
                    <div className="activity-date">{fmtActDate(a.time)}</div>
                  </div>
                  <div className="activity-status ok">
                    <SvgIcon name="check" size={14} />
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      </aside>
    </div>
  );
}
