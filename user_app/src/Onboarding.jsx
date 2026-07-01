// First-run onboarding for new users — a friendly checklist of setup steps.
// Shown once automatically (localStorage flag) and re-openable from the Guide
// menu item. Each step jumps to the relevant section.
const STEPS = [
  { icon: "📝", title: "Complete your profile",
    desc: "Share a little about yourself so support fits your situation.", nav: "hoso" },
  { icon: "🧭", title: "Take a quick screening",
    desc: "A short PHQ-9 / GAD-7 check-in sets a baseline for your mood.", nav: "sangloc" },
  { icon: "💬", title: "Start a chat",
    desc: "Talk through anything on your mind — I'm here any time.", nav: "chat" },
  { icon: "📘", title: "Explore CBT lessons",
    desc: "Bite-size lessons and exercises you can practise.", nav: "baihoc" },
  { icon: "🧑‍⚕️", title: "Book a counsellor",
    desc: "Meet a real psychologist whenever you'd like.", nav: "tuvan" },
];

export default function Onboarding({ open, onClose, onNav }) {
  if (!open) return null;
  function goto(nav) { onClose(); onNav(nav); }
  return (
    <div className="ob-overlay" onClick={onClose}>
      <div className="ob-modal" onClick={(e) => e.stopPropagation()}>
        <button className="ob-x" onClick={onClose} aria-label="Close">✕</button>
        <div className="ob-head">
          <div className="ob-emoji">💚</div>
          <h2>Welcome to MindCare AI</h2>
          <p>Here's how to get set up. Tap any step to jump straight in — you can
            reopen this anytime from the <b>Guide</b> menu.</p>
        </div>
        <div className="ob-steps">
          {STEPS.map((s, i) => (
            <button key={i} className="ob-step" onClick={() => goto(s.nav)}>
              <span className="ob-step-num">{i + 1}</span>
              <span className="ob-step-icon">{s.icon}</span>
              <span className="ob-step-body">
                <span className="ob-step-title">{s.title}</span>
                <span className="ob-step-desc">{s.desc}</span>
              </span>
              <span className="ob-step-arrow">›</span>
            </button>
          ))}
        </div>
        <button className="ob-done" onClick={onClose}>Got it — let's start 💬</button>
      </div>
    </div>
  );
}
