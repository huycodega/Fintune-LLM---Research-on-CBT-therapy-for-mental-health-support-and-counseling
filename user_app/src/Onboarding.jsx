// First-run onboarding — a spotlight TOUR on the real UI (not a popup form). It
// highlights actual sidebar / menu elements one at a time with a tooltip beside
// them. Shown once (localStorage) and re-openable from the Guide menu.
import { useState, useEffect, useLayoutEffect } from "react";

const STEPS = [
  { sel: null, emoji: "💚", title: "Welcome to MindCare AI",
    desc: "A private, CBT-based companion for your wellbeing. Let me show you around." },
  { sel: '[data-tour="sangloc"]', title: "Screening",
    desc: "Take a quick PHQ-9 / GAD-7 check-in to set a baseline for your mood." },
  { sel: '[data-tour="chat"]', title: "AI Support",
    desc: "Chat any time — talk things through, ask for lessons, or just say hi." },
  { sel: '[data-tour="baihoc"]', title: "Lessons",
    desc: "Bite-size CBT lessons and exercises you can practise." },
  { sel: '[data-tour="tuvan"]', title: "Counselling",
    desc: "Book a session with a real psychologist whenever you'd like." },
  { sel: ".topbar-user-info", title: "Your menu",
    desc: "Profile, settings, and this Guide live here — reopen the tour anytime." },
  { sel: null, emoji: "🎉", title: "You're all set!",
    desc: "That's the tour. What's on your mind today?" },
];

export default function Onboarding({ open, onClose }) {
  const [i, setI] = useState(0);
  const [rect, setRect] = useState(null);

  useEffect(() => { if (open) setI(0); }, [open]);

  useLayoutEffect(() => {
    if (!open) return;
    function measure() {
      const sel = STEPS[i].sel;
      const el = sel ? document.querySelector(sel) : null;
      const r = el && el.offsetParent !== null ? el.getBoundingClientRect() : null;
      // Off-screen (e.g. sidebar drawer on mobile) → fall back to a centred card.
      if (r && r.width > 0 && r.left >= 0 && r.top >= 0) {
        el.scrollIntoView({ block: "nearest", inline: "nearest" });
        setRect({ top: r.top, left: r.left, width: r.width, height: r.height });
      } else {
        setRect(null);
      }
    }
    measure();
    window.addEventListener("resize", measure);
    window.addEventListener("scroll", measure, true);
    return () => {
      window.removeEventListener("resize", measure);
      window.removeEventListener("scroll", measure, true);
    };
  }, [open, i]);

  if (!open) return null;
  const step = STEPS[i];
  const isFirst = i === 0;
  const isLast = i === STEPS.length - 1;
  function finish() { setI(0); onClose(); }

  const PAD = 6;
  let tip;
  if (rect) {
    const toRight = rect.left < window.innerWidth * 0.5;
    tip = toRight
      ? { top: Math.min(Math.max(12, rect.top), window.innerHeight - 230),
          left: Math.min(rect.left + rect.width + 16, window.innerWidth - 316) }
      : { top: Math.min(rect.top + rect.height + 12, window.innerHeight - 230),
          left: Math.max(12, Math.min(rect.left, window.innerWidth - 316)) };
  } else {
    tip = { top: "50%", left: "50%", transform: "translate(-50%, -50%)" };
  }

  return (
    <>
      <div className="tour-catch" onClick={finish} />
      {rect
        ? <div className="tour-spot" style={{
            top: rect.top - PAD, left: rect.left - PAD,
            width: rect.width + PAD * 2, height: rect.height + PAD * 2 }} />
        : <div className="tour-dim" />}
      <div className="tour-tip" style={tip} onClick={(e) => e.stopPropagation()}>
        {step.emoji && <div className="tour-emoji">{step.emoji}</div>}
        <h3>{step.title}</h3>
        <p>{step.desc}</p>
        <div className="tour-progress">
          {STEPS.map((_, k) => (
            <span key={k} className={`tour-dot ${k === i ? "on" : ""} ${k < i ? "done" : ""}`} />
          ))}
        </div>
        <div className="tour-nav">
          {isFirst
            ? <button className="tour-skip" onClick={finish}>Skip</button>
            : <button className="tour-skip" onClick={() => setI(i - 1)}>← Back</button>}
          <span className="tour-count">{i + 1}/{STEPS.length}</span>
          <button className="tour-next" onClick={() => (isLast ? finish() : setI(i + 1))}>
            {isLast ? "Done 🎉" : "Next →"}
          </button>
        </div>
      </div>
    </>
  );
}
