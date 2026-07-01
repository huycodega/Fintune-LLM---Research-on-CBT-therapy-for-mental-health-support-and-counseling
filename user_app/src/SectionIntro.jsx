// First-visit intro banner for each section — a short, illustrative "here's what
// this does" note shown ONCE per section, then the user does the real thing.
// Dismissible; tracked per account.
const INTROS = {
  sangloc: {
    icon: "📋", title: "Screening — measure your mood",
    desc: "A quick PHQ-9 / GAD-7 check-in (about 2 minutes). Answer honestly — "
      + "there are no right or wrong answers. Your results are private and set a "
      + "baseline so we can track how you're doing over time.",
    cta: "Start the screening below ↓",
  },
  chat: {
    icon: "💬", title: "AI Support — talk any time",
    desc: "Share whatever's on your mind and I'll use CBT-based tools to help. You "
      + "can also ask things like \"what lessons are there\" or \"book a counsellor\". "
      + "A real clinician reviews anything sensitive.",
    cta: "Type a message to begin ↓",
  },
  baihoc: {
    icon: "📘", title: "Lessons — practise CBT skills",
    desc: "Short, practical CBT lessons you can finish in a few minutes. Tap any "
      + "lesson to open it; your progress is saved automatically.",
    cta: "Pick a lesson below ↓",
  },
  tainguyen: {
    icon: "📗", title: "Resources — helpful materials",
    desc: "Articles, audio, and tools to support your wellbeing between chats.",
    cta: "Browse the resources below ↓",
  },
  tuvan: {
    icon: "🧑‍⚕️", title: "Counselling — meet a real psychologist",
    desc: "When you'd like human support, book a session with a counselling "
      + "expert: pick someone, choose a time, and you're set. It's your choice, "
      + "any time.",
    cta: "Choose an expert below ↓",
  },
};

export default function SectionIntro({ section, seen, onClose }) {
  const intro = INTROS[section];
  if (!intro || (seen || []).includes(section)) return null;
  return (
    <div className="sx-intro">
      <div className="sx-intro-icon">{intro.icon}</div>
      <div className="sx-intro-body">
        <div className="sx-intro-title">{intro.title}</div>
        <div className="sx-intro-desc">{intro.desc}</div>
        <div className="sx-intro-cta">{intro.cta}</div>
      </div>
      <button className="sx-intro-x" onClick={() => onClose(section)}>Got it</button>
    </div>
  );
}
