import { useEffect, useRef, useState } from "react";
import Mascot from "../components/Mascot.jsx";
import FeatureIcon from "../components/FeatureIcon.jsx";

/* Counts a number up from 0 once it scrolls into view. Keeps any
   prefix/suffix (e.g. "10,000+", "95%") and falls back to the raw
   string for non-numeric values like "24/7" or "Free". */
function CountUpValue({ value }) {
  const ref = useRef(null);
  const [display, setDisplay] = useState(value);

  useEffect(() => {
    const m = String(value).match(/^([^\d]*)([\d,]+)(.*)$/);
    if (!m || !ref.current || !("IntersectionObserver" in window)) return;
    const [, prefix, numStr, suffix] = m;
    const target = parseInt(numStr.replace(/,/g, ""), 10);
    if (Number.isNaN(target)) return;
    setDisplay(prefix + "0" + suffix);

    let raf;
    const io = new IntersectionObserver(
      (entries) => {
        if (!entries[0].isIntersecting) return;
        io.disconnect();
        const dur = 1400;
        const start = performance.now();
        const tick = (now) => {
          const p = Math.min((now - start) / dur, 1);
          const eased = 1 - Math.pow(1 - p, 3);
          const n = Math.round(target * eased).toLocaleString("en-US");
          setDisplay(prefix + n + suffix);
          if (p < 1) raf = requestAnimationFrame(tick);
        };
        raf = requestAnimationFrame(tick);
      },
      { threshold: 0.6 }
    );
    io.observe(ref.current);
    return () => {
      io.disconnect();
      if (raf) cancelAnimationFrame(raf);
    };
  }, [value]);

  return <span ref={ref}>{display}</span>;
}

/* Thin line icons used in the stats bar (rendered white over the
   green gradient). Stroke uses currentColor so the CSS controls color. */
const STAT_ICONS = {
  smile: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M8.5 14a4.5 4.5 0 0 0 7 0" />
      <path d="M9 9.5h.01M15 9.5h.01" />
    </>
  ),
  thumb: (
    <>
      <path d="M7 10.5V20H4.5a.5.5 0 0 1-.5-.5v-8.5a.5.5 0 0 1 .5-.5H7Z" />
      <path d="M7 10.5 10 4a2 2 0 0 1 2 2v3h5.2a1.8 1.8 0 0 1 1.78 2.08l-1 6A1.8 1.8 0 0 1 17.2 20H7" />
    </>
  ),
  clock: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7.5V12l3 1.8" />
    </>
  ),
  gift: (
    <>
      <rect x="4" y="9.5" width="16" height="10.5" rx="1.2" />
      <path d="M3.5 9.5h17M12 9.5V20" />
      <path d="M12 9.5C12 6.8 10.4 5 8.6 5.3 7 5.6 6.7 8 9 9.5M12 9.5c0-2.7 1.6-4.5 3.4-4.2 1.6.3 1.9 2.7-.4 4.2" />
    </>
  ),
};

function StatIcon({ name }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width="30"
      height="30"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {STAT_ICONS[name] || STAT_ICONS.smile}
    </svg>
  );
}

const HERO_PILLS = [
  { icon: "chat", label: "AI-Powered Support" },
  { icon: "chart", label: "Personalized Insights" },
  { icon: "shield", label: "Privacy First" },
];

const FEATURES = [
  {
    icon: "shield",
    accent: "#10B981",
    bg: "linear-gradient(135deg, #E8F7F0 0%, #D6F2E6 100%)",
    title: "Mental Health Screening",
    desc: "Understand your mental well-being through AI-powered assessments and personalized insights.",
  },
  {
    icon: "chat",
    accent: "#3B82F6",
    bg: "linear-gradient(135deg, #E8F1FD 0%, #D8E8FC 100%)",
    title: "AI-Powered Support",
    desc: "Chat with our AI companion available 24/7 to listen, support, and guide you.",
  },
  {
    icon: "book",
    accent: "#8B5CF6",
    bg: "linear-gradient(135deg, #F1ECFC 0%, #E7DEFB 100%)",
    title: "CBT Lessons & Exercises",
    desc: "Build healthy habits with evidence-based CBT techniques and guided exercises.",
  },
  {
    icon: "lotus",
    accent: "#3B82F6",
    bg: "linear-gradient(135deg, #E8F1FD 0%, #D8E8FC 100%)",
    title: "Breathing & Mindfulness",
    desc: "Relax your mind with guided breathing exercises and mindfulness sessions.",
  },
  {
    icon: "chart",
    accent: "#EC4899",
    bg: "linear-gradient(135deg, #FCEAF2 0%, #FBDCEA 100%)",
    title: "Progress Tracking",
    desc: "Monitor your mood, habits, and growth with beautiful progress charts.",
  },
  {
    icon: "folder",
    accent: "#10B981",
    bg: "linear-gradient(135deg, #E8F7F0 0%, #D6F2E6 100%)",
    title: "Curated Resources",
    desc: "Explore expert articles, self-help tools, and videos for your mental wellness journey.",
  },
];

const STEPS = [
  { num: "1", icon: "shield", title: "Take a Screening", desc: "Answer a few simple questions to understand your current mental well-being." },
  { num: "2", icon: "chat",   title: "Chat with AI", desc: "Share your thoughts with our AI companion available 24/7." },
  { num: "3", icon: "book",   title: "Learn & Practice", desc: "Access personalized lessons and exercises to build healthy habits." },
  { num: "4", icon: "trend",  title: "Track Your Journey", desc: "Monitor your progress and celebrate every small win." },
];

const STATS = [
  { value: "10,000+", label: "Happy users",     icon: "smile" },
  { value: "95%",     label: "Positive feedback", icon: "thumb" },
  { value: "24/7",    label: "AI availability",  icon: "clock" },
  { value: "Free",    label: "To get started",   icon: "gift" },
];

const ABOUT_POINTS = [
  "Backed by proven psychological methods",
  "Designed with privacy and safety in mind",
  "Continuous learning to improve support",
  "You're not alone — we're here for you",
];

export default function Landing({ onSignIn }) {
  // Reveal-on-scroll: fade/slide elements in as they enter the viewport.
  useEffect(() => {
    const els = document.querySelectorAll("[data-reveal]");
    if (!("IntersectionObserver" in window) || !els.length) {
      els.forEach((el) => el.classList.add("reveal-in"));
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add("reveal-in");
            io.unobserve(e.target);
          }
        });
      },
      { threshold: 0.15, rootMargin: "0px 0px -8% 0px" }
    );
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);

  // Navbar gains a shadow / solid background once the page is scrolled.
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Subtle 3D tilt that follows the cursor across a feature card.
  const handleTilt = (e) => {
    const card = e.currentTarget;
    const r = card.getBoundingClientRect();
    const px = (e.clientX - r.left) / r.width - 0.5;
    const py = (e.clientY - r.top) / r.height - 0.5;
    card.style.setProperty("--rx", `${(-py * 7).toFixed(2)}deg`);
    card.style.setProperty("--ry", `${(px * 7).toFixed(2)}deg`);
    card.style.setProperty("--mx", `${((px + 0.5) * 100).toFixed(1)}%`);
    card.style.setProperty("--my", `${((py + 0.5) * 100).toFixed(1)}%`);
  };
  const resetTilt = (e) => {
    e.currentTarget.style.setProperty("--rx", "0deg");
    e.currentTarget.style.setProperty("--ry", "0deg");
  };

  return (
    <div className="landing-wrap">

      {/* ── NAVBAR ── */}
      <nav className={`landing-nav${scrolled ? " scrolled" : ""}`}>
        <div className="landing-nav-inner">
          <div className="landing-logo">
            <div className="landing-logo-icon">🌿</div>
            <span className="landing-logo-text">MindCare AI</span>
          </div>
          <div className="landing-nav-links">
            <a href="#features" className="landing-nav-link">Features</a>
            <a href="#how" className="landing-nav-link">How it works</a>
            <a href="#pricing" className="landing-nav-link">Pricing</a>
            <a href="#about" className="landing-nav-link">About</a>
          </div>
          <button className="landing-signin-btn" onClick={onSignIn}>
            Sign in
          </button>
        </div>
      </nav>

      {/* ── HERO ── */}
      <section className="landing-hero">
        <div className="landing-hero-bg" aria-hidden="true">
          <span className="landing-orb landing-orb-1" />
          <span className="landing-orb landing-orb-2" />
          <span className="landing-orb landing-orb-3" />
          <span className="landing-hero-grid" />
        </div>
        <div className="landing-hero-inner">
          <div className="landing-hero-left landing-hero-enter">
            <h1 className="landing-hero-title" style={{ "--d": "0.1s" }}>
              Your Mental Health<br />
              Journey,{" "}
              <span className="landing-hero-accent">Supported&nbsp;by&nbsp;AI</span>
            </h1>
            <p className="landing-hero-sub" style={{ "--d": "0.2s" }}>
              MindCare AI combines advanced AI technology with{" "}
              <strong>compassionate care</strong> to help you manage stress, anxiety,
              and emotions — anytime, anywhere.
            </p>
            <div className="landing-hero-pills" style={{ "--d": "0.3s" }}>
              {HERO_PILLS.map((p) => (
                <span key={p.label} className="landing-hero-pill">
                  <FeatureIcon name={p.icon} size={18} color="var(--primary-dark)" />
                  {p.label}
                </span>
              ))}
            </div>
            <div className="landing-hero-actions" style={{ "--d": "0.4s" }}>
              <button className="landing-btn-primary" onClick={onSignIn}>
                Get Started — It's Free
                <span className="landing-btn-arrow">→</span>
              </button>
              <a href="#features" className="landing-btn-outline">
                Learn More
              </a>
            </div>
            <div className="landing-hero-rating" style={{ "--d": "0.5s" }}>
              <span className="landing-rating-stars">★★★★<span className="landing-rating-half">★</span></span>
              <span className="landing-rating-text">Trusted by <b>10,000+</b> users worldwide</span>
            </div>
          </div>
          <div className="landing-hero-right landing-hero-enter-right">
            <div className="landing-hero-mascot-wrap">
              <div className="landing-hero-ring" />
              <div className="landing-hero-blob" />
              <div className="landing-hero-glow" />
              <Mascot size={280} />
              <div className="landing-hero-bubble landing-hero-bubble-1">
                <span className="landing-bubble-avatar">AI</span>
                How are you feeling today?
              </div>
              <div className="landing-hero-bubble landing-hero-bubble-2">
                <span className="landing-bubble-emoji">💚</span>
                I'm here for you.
              </div>
              <div className="landing-hero-bubble landing-hero-bubble-3">
                Let's take a deep breath together. 🌱
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── STATS ── */}
      <section className="landing-stats">
        <div className="landing-stats-inner">
          {STATS.map((s, i) => (
            <div key={s.label} className="landing-stat">
              {i > 0 && <span className="landing-stat-divider" aria-hidden="true" />}
              <div className="landing-stat-icon"><StatIcon name={s.icon} /></div>
              <div className="landing-stat-value"><CountUpValue value={s.value} /></div>
              <div className="landing-stat-label">{s.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ── FEATURES ── */}
      <section className="landing-section" id="features">
        <div className="landing-deco" aria-hidden="true">
          <span className="landing-deco-blob landing-deco-blob-teal" style={{ top: "-130px", left: "-120px" }} />
          <span className="landing-deco-blob landing-deco-blob-blue" style={{ bottom: "-140px", right: "-110px" }} />
          <span className="landing-deco-dots" style={{ top: "40px", right: "30px" }} />
          <span className="landing-deco-dots" style={{ bottom: "40px", left: "30px" }} />
        </div>
        <div className="landing-section-inner">
          <div className="landing-section-eyebrow">Powerful Features</div>
          <h2 className="landing-section-title">Everything you need for your well-being</h2>
          <p className="landing-section-sub">
            From mental screenings to daily mindfulness — all in one place.
          </p>
          <div className="landing-features-grid">
            {FEATURES.map((f, i) => (
              <div
                key={f.title}
                className="landing-feature-card"
                data-reveal
                onMouseMove={handleTilt}
                onMouseLeave={resetTilt}
                style={{ "--card-accent": f.accent, transitionDelay: `${i * 0.08}s` }}
              >
                <div className="landing-feature-tilt">
                  <span className="landing-feature-shine" aria-hidden="true" />
                  <div className="landing-feature-icon" style={{ background: f.bg }}>
                    <FeatureIcon name={f.icon} color={f.accent} />
                  </div>
                  <div className="landing-feature-title">{f.title}</div>
                  <div className="landing-feature-desc">{f.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── HOW IT WORKS ── */}
      <section className="landing-section landing-section-alt" id="how">
        <div className="landing-deco" aria-hidden="true">
          <span className="landing-deco-dots" style={{ top: "50px", left: "40px" }} />
          <span className="landing-deco-dots" style={{ bottom: "50px", right: "40px" }} />
        </div>
        <div className="landing-section-inner">
          <div className="landing-section-eyebrow">How it works</div>
          <h2 className="landing-section-title">Simple steps to a better you</h2>
          <p className="landing-section-sub">
            Get started in minutes. No appointment needed, no waiting room.
          </p>
          <div className="landing-steps">
            <div className="landing-steps-track" aria-hidden="true" />
            {STEPS.map((s, i) => (
              <div key={s.num} className="landing-step" data-reveal style={{ transitionDelay: `${i * 0.1}s` }}>
                <div className="landing-step-icon-circle">
                  <FeatureIcon name={s.icon} size={32} color="var(--primary-dark)" />
                  <span className="landing-step-num">{s.num}</span>
                </div>
                <div className="landing-step-title">{s.title}</div>
                <div className="landing-step-desc">{s.desc}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── ABOUT / TRUST ── */}
      <section className="landing-section" id="about">
        <div className="landing-deco" aria-hidden="true">
          <span className="landing-deco-blob landing-deco-blob-purple" style={{ top: "-120px", right: "-100px" }} />
          <span className="landing-deco-blob landing-deco-blob-teal" style={{ bottom: "-150px", left: "-120px" }} />
          <span className="landing-deco-dots" style={{ top: "60px", left: "40px" }} />
        </div>
        <div className="landing-section-inner landing-about">
          <div className="landing-about-left">
            <div className="landing-section-eyebrow" style={{ textAlign: "left" }}>About MindCare AI</div>
            <h2 className="landing-section-title" style={{ textAlign: "left" }}>
              Mental health support that truly understands you
            </h2>
            <p className="landing-about-text">
              MindCare AI is built with empathy and science-backed techniques to provide
              personalized support when you need it most.
            </p>
            <ul className="landing-about-list">
              {ABOUT_POINTS.map((point) => (
                <li key={point}><span className="landing-about-check">✓</span> {point}</li>
              ))}
            </ul>
            <button className="landing-btn-primary" style={{ marginTop: 28 }} onClick={onSignIn}>
              Start your journey
              <span className="landing-btn-arrow">→</span>
            </button>
          </div>
          <div className="landing-about-right">
            <div className="landing-about-mascot">
              <div className="landing-about-glow" />
              <Mascot size={200} />
              <div className="landing-about-card">
                <div className="landing-about-quote-mark">“</div>
                <div className="landing-about-card-text">
                  MindCare AI helps me feel heard and supported every day.
                  <span className="landing-about-card-author">— A happy user</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── CTA BANNER ── */}
      <section className="landing-cta">
        <div className="landing-cta-bg" aria-hidden="true">
          <span className="landing-cta-orb landing-cta-orb-1" />
          <span className="landing-cta-orb landing-cta-orb-2" />
        </div>
        <div className="landing-cta-inner">
          <h2 className="landing-cta-title">Ready to take care of your mind?</h2>
          <p className="landing-cta-sub">
            Join thousands of people using MindCare AI to feel better every day.
          </p>
          <button className="landing-cta-btn" onClick={onSignIn}>
            Get Started for Free
            <span className="landing-btn-arrow">→</span>
          </button>
          <div className="landing-cta-note">
            No credit card required · 100% free to start
          </div>
        </div>
      </section>

      {/* ── FOOTER ── */}
      <footer className="landing-footer">
        <div className="landing-footer-inner">
          <div className="landing-logo" style={{ marginBottom: 8 }}>
            <div className="landing-logo-icon">🌿</div>
            <span className="landing-logo-text">MindCare AI</span>
          </div>
          <p className="landing-footer-text">
            AI-powered mental health support, available 24/7.
          </p>
          <nav className="landing-footer-links">
            <a href="#features" className="landing-footer-link">Features</a>
            <a href="#how" className="landing-footer-link">How it works</a>
            <a href="#pricing" className="landing-footer-link">Pricing</a>
            <a href="#about" className="landing-footer-link">About</a>
            <a href="#privacy" className="landing-footer-link">Privacy</a>
            <a href="#terms" className="landing-footer-link">Terms</a>
          </nav>
          <div className="landing-footer-divider" aria-hidden="true" />
          <p className="landing-footer-text landing-footer-fine">
            © 2026 MindCare AI. All rights reserved. · Not a substitute for professional
            medical advice. If you're in crisis, call{" "}
            <strong className="landing-footer-hotline">988</strong> — Suicide &amp; Crisis Lifeline (24/7)
          </p>
        </div>
      </footer>

    </div>
  );
}
