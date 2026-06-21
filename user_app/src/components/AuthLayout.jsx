import Mascot from "./Mascot.jsx";

// Thin line icons for the brand feature list (green stroke in a soft circle).
const BRAND_ICONS = {
  shield: (
    <path d="M12 3.4 18 5.6v4.9c0 4-2.6 6.8-6 7.9-3.4-1.1-6-3.9-6-7.9V5.6L12 3.4ZM9.2 11.4l1.9 1.9 3.7-3.7" />
  ),
  clipboard: (
    <>
      <rect x="6" y="5" width="12" height="15" rx="1.6" />
      <path d="M9.2 5V4a1 1 0 0 1 1-1h3.6a1 1 0 0 1 1 1v1M9 10.5l1.4 1.4 2.4-2.4M9 15h6" />
    </>
  ),
  clock: (
    <>
      <circle cx="12" cy="12" r="8.4" />
      <path d="M12 7.4V12l3 1.8" />
    </>
  ),
};

const BRAND_FEATURES = [
  { icon: "shield",    title: "Private & encrypted",            sub: "Your privacy is our priority." },
  { icon: "clipboard", title: "Clinically informed (PHQ-9 & GAD-7)", sub: "Grounded in proven, evidence-based tools." },
  { icon: "clock",     title: "Available 24/7",                 sub: "Support when you need it most." },
];

// Shared two-pane auth shell: a decorated brand panel (landing aesthetic)
// on the left and the form card on the right. `children` is the form card body.
export default function AuthLayout({ children }) {
  return (
    <div className="auth2">
      {/* ── Brand / hero panel ── */}
      <aside className="auth2-brand">
        <div className="auth2-brand-bg" aria-hidden="true">
          <span className="landing-orb landing-orb-1" />
          <span className="landing-orb landing-orb-2" />
          <span className="auth2-brand-grid" />
        </div>

        <div className="auth2-brand-top">
          <div className="auth2-brand-logo">
            <span className="auth2-brand-logo-icon">🌿</span>
            <span>MindCare AI</span>
          </div>
        </div>

        <div className="auth2-brand-inner">
          <div className="auth2-brand-badge">
            <span className="auth2-brand-badge-spark">✦</span>
            AI-Powered Mental Health Support
          </div>
          <h2 className="auth2-brand-head">
            Your mental health journey,{" "}
            <span className="auth2-brand-accent">supported by AI</span>
          </h2>
          <p className="auth2-brand-sub">
            Evidence-based CBT techniques with compassionate AI — a safe,
            confidential space, with clinicians reviewing anything sensitive.
          </p>
          <ul className="auth2-brand-list">
            {BRAND_FEATURES.map((f) => (
              <li key={f.title} className="auth2-brand-feat">
                <span className="auth2-brand-feat-icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24" width="20" height="20" fill="none"
                    stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
                    {BRAND_ICONS[f.icon]}
                  </svg>
                </span>
                <span className="auth2-brand-feat-text">
                  <span className="auth2-brand-feat-title">{f.title}</span>
                  <span className="auth2-brand-feat-sub">{f.sub}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>

        <div className="auth2-brand-mascot">
          <Mascot size={130} />
          <div className="auth2-brand-quote">
            <span className="auth2-brand-quote-mark">“</span>
            I finally feel heard.
            <span className="auth2-brand-quote-emoji">💚</span>
          </div>
        </div>
      </aside>

      {/* ── Form panel ── */}
      <main className="auth2-panel">
        <div className="auth2-panel-deco" aria-hidden="true">
          <span className="landing-deco-blob landing-deco-blob-teal" style={{ top: "-120px", right: "-120px" }} />
          <span className="landing-deco-dots" style={{ bottom: "40px", left: "30px" }} />
        </div>
        <div className="login-card auth2-card">{children}</div>
      </main>
    </div>
  );
}
