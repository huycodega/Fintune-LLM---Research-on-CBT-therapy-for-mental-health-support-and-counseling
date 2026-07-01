// First-run onboarding — a step-by-step wizard for new users. Shown once
// automatically (localStorage flag) and re-openable from the Guide menu. Each
// feature step has a "Take me there" jump; Next/Back walk through them.
import { useState, useEffect } from "react";

const STEPS = [
  { emoji: "💚", title: "Welcome to MindCare AI",
    desc: "A private, CBT-based companion for your wellbeing. Let's take a few seconds to get you set up.",
    nav: null },
  { emoji: "📝", title: "Complete your profile",
    desc: "Share a little about yourself so the support fits your situation. You can update it anytime.",
    nav: "hoso" },
  { emoji: "🧭", title: "Take a quick screening",
    desc: "A short PHQ-9 / GAD-7 check-in sets a baseline for your mood so we can track how you're doing.",
    nav: "sangloc" },
  { emoji: "💬", title: "Start a chat",
    desc: "Talk through anything on your mind — I'm here any time. Try 'what lessons are there' or just say hi.",
    nav: "chat" },
  { emoji: "📘", title: "Explore CBT lessons",
    desc: "Bite-size lessons and exercises you can practise between chats.",
    nav: "baihoc" },
  { emoji: "🧑‍⚕️", title: "Book a counsellor",
    desc: "Whenever you'd like, you can book a session with a real psychologist.",
    nav: "tuvan" },
  { emoji: "🎉", title: "You're all set!",
    desc: "You can reopen this guide anytime from the Guide menu. What's on your mind today?",
    nav: "chat" },
];

export default function Onboarding({ open, onClose, onNav }) {
  const [i, setI] = useState(0);
  useEffect(() => { if (open) setI(0); }, [open]);   // always start at step 1
  if (!open) return null;

  const step = STEPS[i];
  const isFirst = i === 0;
  const isLast = i === STEPS.length - 1;
  function finish() { setI(0); onClose(); }
  function goto(nav) { finish(); if (nav) onNav(nav); }
  function next() { if (isLast) goto(step.nav); else setI(i + 1); }

  return (
    <div className="ob-overlay" onClick={finish}>
      <div className="ob-modal ob-wizard" onClick={(e) => e.stopPropagation()}>
        <button className="ob-x" onClick={finish} aria-label="Close">✕</button>

        <div className="ob-progress">
          {STEPS.map((_, k) => (
            <span key={k} className={`ob-dot ${k === i ? "on" : ""} ${k < i ? "done" : ""}`} />
          ))}
        </div>

        <div className="ob-step-view" key={i}>
          <div className="ob-emoji">{step.emoji}</div>
          <h2>{step.title}</h2>
          <p>{step.desc}</p>
          {step.nav && !isFirst && !isLast && (
            <button className="ob-goto" onClick={() => goto(step.nav)}>Take me there →</button>
          )}
        </div>

        <div className="ob-nav">
          {isFirst
            ? <button className="ob-back ob-skip" onClick={finish}>Skip</button>
            : <button className="ob-back" onClick={() => setI(i - 1)}>← Back</button>}
          <span className="ob-count">{i + 1} / {STEPS.length}</span>
          <button className="ob-next" onClick={next}>{isLast ? "Start 💬" : "Next →"}</button>
        </div>
      </div>
    </div>
  );
}
