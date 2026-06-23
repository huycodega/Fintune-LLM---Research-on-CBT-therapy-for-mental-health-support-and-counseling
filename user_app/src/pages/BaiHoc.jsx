import { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import Mascot from "../components/Mascot.jsx";
import { api } from "../api.js";

/* Map a DB lesson category → the card's filter bucket, art + accent so
   DB-backed lessons render with the same illustrated style as the mockup. */
const CAT_STYLE = {
  "Stress Management":      { cat: "emotion",  art: "smiley", accent: "green" },
  "Positive Thinking":      { cat: "thinking", art: "brain",  accent: "indigo" },
  "Mindfulness":            { cat: "mindful",  art: "lotus",  accent: "purple" },
  "Breathing & Relaxation": { cat: "relax",    art: "wind",   accent: "teal" },
  "Habits":                 { cat: "habit",    art: "target", accent: "pink" },
  "Social Skills":          { cat: "thinking", art: "cloud",  accent: "orange" },
  "Mental Wellness":        { cat: "mindful",  art: "lotus",  accent: "teal" },
};
const ACCENT_CYCLE = ["green", "indigo", "purple", "teal", "orange", "pink"];
const ART_CYCLE = ["smiley", "brain", "lotus", "wind", "cloud", "target"];
function styleFor(lesson, i) {
  const s = CAT_STYLE[lesson.category];
  return s || { cat: "all", art: ART_CYCLE[i % 6], accent: ACCENT_CYCLE[i % 6] };
}

/* ── Filter chips (match mockup) ───────────────────────────────── */
const FILTERS = [
  { id: "all",      icon: "▦", label: "All" },
  { id: "emotion",  icon: "🙂", label: "Emotion Management" },
  { id: "thinking", icon: "🧠", label: "Thinking" },
  { id: "mindful",  icon: "🧘", label: "Mindfulness" },
  { id: "relax",    icon: "🌬️", label: "Relaxation" },
  { id: "habit",    icon: "🎯", label: "Habit Building" },
];

/* accent → [icon background, accent color] */
const ACCENTS = {
  green:  ["#E4F6F1", "#2BA37F"],
  indigo: ["#E8ECFD", "#4F6BED"],
  purple: ["#EEE7FC", "#8B5CF6"],
  teal:   ["#DCF5F1", "#14B8A6"],
  orange: ["#FDEFD9", "#F59E0B"],
  pink:   ["#FCE3EE", "#EC4899"],
};

/* ── Topic icons (flat illustrations matching the mockup) ──────── */
function TopicArt({ type, color }) {
  switch (type) {
    case "smiley": // green smiley face
      return (
        <svg viewBox="0 0 24 24" width="30" height="30" aria-hidden="true">
          <circle cx="12" cy="12" r="9" fill={color} />
          <circle cx="9" cy="10.3" r="1.25" fill="#fff" />
          <circle cx="15" cy="10.3" r="1.25" fill="#fff" />
          <path d="M8.4 14c.9 1.2 2.1 1.9 3.6 1.9s2.7-.7 3.6-1.9" stroke="#fff" strokeWidth="1.7" fill="none" strokeLinecap="round" />
        </svg>
      );
    case "brain": // head profile with brain
      return (
        <svg viewBox="0 0 24 24" width="30" height="30" aria-hidden="true">
          <path d="M9 16.5H7.4l.7-2.3A6.4 6.4 0 1 1 14 18.4v1.1a1 1 0 0 1-1 1h-3a1 1 0 0 1-1-1z" fill={color} />
          <path d="M10.4 7.6a1.5 1.5 0 0 1 2.8-.5 1.4 1.4 0 0 1 .9 2.3 1.3 1.3 0 0 1-1 2.1h-2.5a1.3 1.3 0 0 1-1-2.1 1.5 1.5 0 0 1 .8-1.8z" fill="#fff" opacity="0.9" />
          <path d="M12 7.4v4.2" stroke={color} strokeWidth="0.9" />
        </svg>
      );
    case "lotus": // layered lotus flower
      return (
        <svg viewBox="0 0 24 24" width="30" height="30" aria-hidden="true" fill={color}>
          <path d="M4 11.2c2 .1 3.8 1 5.1 2.5 1 1.1 1.6 2.4 1.7 3.8H10c-2.5 0-4.6-.9-5.6-2.8-.4-1-.5-2.3-.4-3.5z" opacity="0.5" />
          <path d="M20 11.2c-2 .1-3.8 1-5.1 2.5-1 1.1-1.6 2.4-1.7 3.8H14c2.5 0 4.6-.9 5.6-2.8.4-1 .5-2.3.4-3.5z" opacity="0.5" />
          <path d="M7 7.2c1.9.6 3.4 1.9 4.2 3.6.6 1.3.9 2.6.7 4-1.4-.2-2.7-.9-3.6-2C7 14.9 6.5 12.8 7 7.2z" opacity="0.72" />
          <path d="M17 7.2c-1.9.6-3.4 1.9-4.2 3.6-.6 1.3-.9 2.6-.7 4 1.4-.2 2.7-.9 3.6-2 1.3-1.9 1.8-4 1.3-5.6z" opacity="0.72" />
          <path d="M12 3.2c1.9 2.1 2.9 4.3 2.9 6.6 0 1.5-.4 2.9-1.1 4.1h-3.6C9.4 12.7 9 11.3 9 9.8c0-2.3 1-4.5 3-6.6z" />
        </svg>
      );
    case "wind": // breeze lines
      return (
        <svg viewBox="0 0 24 24" width="30" height="30" aria-hidden="true" fill="none" stroke={color} strokeWidth="1.9" strokeLinecap="round">
          <path d="M3 8.5h8.5A2.5 2.5 0 1 0 9 6" />
          <path d="M3 12.5h12A2.5 2.5 0 1 1 12.5 15" />
          <path d="M3 16.5h6.5A2 2 0 1 1 7.5 18.5" />
        </svg>
      );
    case "cloud": // fluffy thought cloud with face
      return (
        <svg viewBox="0 0 24 24" width="30" height="30" aria-hidden="true">
          <path d="M7.5 18.5a4 4 0 0 1-1.1-7.85 5 5 0 0 1 9.5-1.65 3.8 3.8 0 0 1 1.1 7.5z" fill={color} />
          <circle cx="10" cy="13" r="0.95" fill="#fff" />
          <circle cx="14" cy="13" r="0.95" fill="#fff" />
          <path d="M10 15.2c.55.6 1.25.9 2 .9s1.45-.3 2-.9" stroke="#fff" strokeWidth="1.3" fill="none" strokeLinecap="round" />
        </svg>
      );
    case "target": // target with arrow
      return (
        <svg viewBox="0 0 24 24" width="30" height="30" aria-hidden="true" fill="none" stroke={color} strokeWidth="1.8">
          <circle cx="10.5" cy="13.5" r="7.5" />
          <circle cx="10.5" cy="13.5" r="4" />
          <circle cx="10.5" cy="13.5" r="1.1" fill={color} stroke="none" />
          <path d="M10.5 13.5l8-8" strokeLinecap="round" />
          <path d="M15 4.5h4.5V9" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      );
    default:
      return null;
  }
}

const WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

const TOOLS = [
  { icon: "✏️",  title: "Emotion Journal",      sub: "Record your feelings every day" },
  { icon: "📋",  title: "Practice Exercises",   sub: "CBT exercises & worksheets" },
  { icon: "✳️",  title: "Positive Reminders",   sub: "Reminders & positive affirmations" },
];

/* Soft mountain-journey illustration for the featured card */
function JourneyArt() {
  return (
    <svg className="bh-featured-art" viewBox="0 0 200 150" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <defs>
        <linearGradient id="bhSky" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#DBF3FF" />
          <stop offset="1" stopColor="#EAFBF4" />
        </linearGradient>
        <linearGradient id="bhHill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#7FD4B0" />
          <stop offset="1" stopColor="#4FB58D" />
        </linearGradient>
      </defs>
      <rect width="200" height="150" rx="14" fill="url(#bhSky)" />
      <circle cx="150" cy="34" r="16" fill="#FCD96B" />
      <path d="M0 150 L52 70 L96 112 L150 52 L200 110 L200 150 Z" fill="url(#bhHill)" />
      <path d="M52 70 L66 86 L52 92 L62 100 L52 110" stroke="#fff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" opacity="0.85" />
      <path d="M150 52 L150 34 L166 40 L150 46" fill="#EF6F6F" />
      <line x1="150" y1="52" x2="150" y2="34" stroke="#3D7A63" strokeWidth="2.5" strokeLinecap="round" />
      <path d="M86 150 C86 132 100 124 100 124 C100 124 114 132 114 150 Z" fill="#3F9E78" />
      <path d="M30 150 C30 138 40 132 40 132 C40 132 50 138 50 150 Z" fill="#46AB82" />
    </svg>
  );
}

export default function BaiHoc() {
  const [active, setActive] = useState("all");
  const [lessons, setLessons] = useState([]);
  const [loading, setLoading] = useState(true);
  const [progress, setProgress] = useState({});   // { lessonId: {progress_pct, completed_steps, status} }
  const [openLesson, setOpenLesson] = useState(null);   // full lesson being viewed
  const [overview, setOverview] = useState(null);   // streak / week from real activity

  useEffect(() => {
    let alive = true;
    api.lessons()
      .then((r) => { if (alive) setLessons(r.lessons || []); })
      .catch(() => { if (alive) setLessons([]); })
      .finally(() => { if (alive) setLoading(false); });
    api.lessonProgress()
      .then((r) => { if (alive) setProgress(r.progress || {}); })
      .catch(() => {});
    api.myOverview().then((o) => { if (alive) setOverview(o); }).catch(() => {});
    return () => { alive = false; };
  }, []);

  // Persist this user's progress for a lesson and reflect it locally.
  // explicitPct overrides the derived % (used for objective-less lessons).
  async function saveProgress(lessonId, completedSteps, total, explicitPct) {
    const pct = explicitPct != null
      ? explicitPct
      : (total > 0 ? Math.round((completedSteps.length / total) * 100) : 0);
    setProgress((p) => ({
      ...p,
      [lessonId]: { progress_pct: pct, completed_steps: completedSteps,
                    status: pct >= 100 ? "completed" : "in_progress" },
    }));
    try { await api.setLessonProgress(lessonId, { progress_pct: pct, completed_steps: completedSteps }); }
    catch { /* best-effort; local state already updated */ }
  }

  // Map DB lessons → card shape, keeping the illustrated style.
  const cards = lessons.map((l, i) => {
    const s = styleFor(l, i);
    return {
      n: i + 1, id: l.id, accent: s.accent, cat: s.cat, art: s.art,
      title: l.title, desc: l.description || "",
      time: l.duration || "—",
      progress: progress[l.id]?.progress_pct || 0,
      lesson: l,
    };
  });
  const filtered = active === "all" ? cards : cards.filter((t) => t.cat === active);

  // Suggested = a lesson in progress, else the first not-yet-started, else first.
  const suggested = cards.find((c) => c.progress > 0 && c.progress < 100)
    || cards.find((c) => c.progress === 0)
    || cards[0]
    || null;

  const streak = overview?.streak ?? 0;
  const week = overview?.week || Array(7).fill(false);

  return (
    <div className="bh-layout">
      {/* ── LEFT COLUMN ───────────────────────────────────────── */}
      <div className="bh-main">
        {/* Header */}
        <header className="bh-header">
          <div className="bh-header-text">
            <h1 className="bh-title">CBT Lessons &amp; Exercises</h1>
            <p className="bh-subtitle">
              Learn and practice CBT techniques to understand yourself better, manage your
              emotions, and build a positive life every day.
            </p>
          </div>
          <div className="bh-header-mascot">
            <Mascot variant="reading" size={150} />
          </div>
        </header>

        {/* Filter chips */}
        <div className="bh-filters">
          {FILTERS.map((f) => (
            <button
              key={f.id}
              className={`bh-chip ${active === f.id ? "active" : ""}`}
              onClick={() => setActive(f.id)}
            >
              <span className="bh-chip-icon">{f.icon}</span>
              {f.label}
            </button>
          ))}
        </div>

        {/* Featured journey card */}
        <section className="bh-featured">
          <div className="bh-featured-thumb">
            <JourneyArt />
            <span className="bh-featured-badge">⭐ Featured Lesson</span>
          </div>
          <div className="bh-featured-body">
            <h2 className="bh-featured-title">7-Day Journey – Know Yourself, Live Positively</h2>
            <p className="bh-featured-desc">
              A 7-day path that helps you better understand your emotions and thoughts,
              and build positive habits every day.
            </p>
            <div className="bh-featured-stats">
              <span className="bh-fstat">🕐 7 lessons</span>
              <span className="bh-fstat">📊 For everyone</span>
              <span className="bh-fstat">👥 12.4k learners</span>
            </div>
          </div>
          <div className="bh-featured-action">
            <button className="bh-btn-primary">Start learning →</button>
          </div>
        </section>

        {/* Topic section */}
        <h3 className="bh-section-title">Lessons by Topic</h3>

        {loading && <p className="bh-subtitle">Loading lessons…</p>}
        {!loading && cards.length === 0 && (
          <p className="bh-subtitle">No lessons available yet. Check back soon.</p>
        )}

        <div className="bh-grid">
          {filtered.map((t) => {
            const [soft, color] = ACCENTS[t.accent];
            return (
              <article key={t.n} className="bh-card" style={{ "--accent": color, "--accent-soft": soft }}
                       onClick={() => setOpenLesson(t.lesson)} role="button" tabIndex={0}
                       onKeyDown={(e) => { if (e.key === "Enter") setOpenLesson(t.lesson); }}>
                <div className="bh-card-icon"><TopicArt type={t.art} color={color} /></div>
                <div className="bh-card-name">{t.n}. {t.title}</div>
                <p className="bh-card-desc">{t.desc}</p>
                <div className="bh-card-meta">
                  <span>🕐 {t.time}</span>
                  <span className="bh-card-pct">{t.progress}%</span>
                </div>
                <div className="bh-progress">
                  <div className="bh-progress-fill" style={{ width: `${t.progress}%` }} />
                </div>
                <button className="bh-card-btn" onClick={(e) => { e.stopPropagation(); setOpenLesson(t.lesson); }}>
                  {t.progress >= 100 ? "Review" : t.progress > 0 ? "Continue" : "Start"} <span>→</span>
                </button>
              </article>
            );
          })}
        </div>

        {/* View all */}
        <button className="bh-viewall">View all lessons ⌄</button>

        {/* Footer disclaimer */}
        <p className="bh-disclaimer">
          🛡️ MindCare AI is not a substitute for medical diagnosis. If you need urgent help,
          please contact your nearest healthcare facility.
        </p>
      </div>

      {/* ── RIGHT COLUMN ──────────────────────────────────────── */}
      <aside className="bh-side">
        {/* Suggestion card */}
        <div className="bh-suggest">
          <div className="bh-suggest-head">
            <div className="bh-suggest-title">Suggested for you</div>
            <Mascot variant="reading" size={84} />
          </div>
          <div className="bh-suggest-label">{suggested && suggested.progress > 0 ? "Continue" : "Next lesson"}</div>
          <div className="bh-suggest-lesson">{suggested ? suggested.title : "Explore a lesson"}</div>
          <p className="bh-suggest-desc">
            {suggested?.desc || "Pick a CBT lesson to start building positive habits today."}
          </p>
          <div className="bh-suggest-meta">
            <span>🕐 {suggested?.time || "—"}</span>
            {suggested && <span>📊 {suggested.progress}%</span>}
          </div>
          <button className="bh-btn-primary bh-btn-full"
            disabled={!suggested}
            onClick={() => suggested && setOpenLesson(suggested.lesson)}>
            {suggested && suggested.progress > 0 ? "Continue →" : "Start now →"}
          </button>
        </div>

        {/* Streak card */}
        <div className="bh-panel">
          <div className="bh-panel-title">Your learning streak</div>
          <div className="bh-streak-count">🔥 <strong>{streak} {streak === 1 ? "day" : "days"} in a row</strong></div>
          <div className="bh-streak-days">
            {WEEKDAY_LABELS.map((label, i) => (
              <div key={i} className="bh-streak-day">
                <div className={`bh-streak-dot ${week[i] ? "done" : ""}`}>{week[i] ? "✓" : ""}</div>
                <span className="bh-streak-lbl">{label}</span>
              </div>
            ))}
          </div>
          <p className="bh-streak-note">
            {streak > 0 ? "Keep your streak going to build positive habits!"
                        : "Complete a lesson or check-in today to start a streak!"}
          </p>
        </div>

        {/* Tools card */}
        <div className="bh-panel">
          <div className="bh-panel-title">Learning support tools</div>
          {TOOLS.map((tool, i) => (
            <button key={i} className="bh-tool">
              <div className="bh-tool-icon">{tool.icon}</div>
              <div className="bh-tool-text">
                <div className="bh-tool-title">{tool.title}</div>
                <div className="bh-tool-sub">{tool.sub}</div>
              </div>
              <span className="bh-tool-arrow">›</span>
            </button>
          ))}
        </div>
      </aside>

      {openLesson && (
        <LessonDetail
          lesson={openLesson}
          prog={progress[openLesson.id]}
          onClose={() => setOpenLesson(null)}
          onSave={saveProgress}
        />
      )}
    </div>
  );
}

/* ── Lesson detail modal: content + per-user objective checklist ───────── */
function LessonDetail({ lesson, prog, onClose, onSave }) {
  const objectives = lesson.objectives || [];
  const [done, setDone] = useState(
    new Set((prog?.completed_steps || []).filter((i) => i < objectives.length))
  );

  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const pct = objectives.length
    ? Math.round((done.size / objectives.length) * 100)
    : (prog?.progress_pct || 0);

  function toggle(i) {
    const next = new Set(done);
    next.has(i) ? next.delete(i) : next.add(i);
    setDone(next);
    onSave(lesson.id, [...next], objectives.length);
  }
  function markAll() {
    const all = new Set(objectives.map((_, i) => i));
    setDone(all);
    onSave(lesson.id, [...all], objectives.length);
  }

  return createPortal(
    <div className="lx-overlay" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="lx-modal" role="dialog" aria-modal="true" aria-label={lesson.title}>
        <button className="lx-close" onClick={onClose} aria-label="Close">✕</button>
        <div className="lx-head">
          <h2 className="lx-title">{lesson.title}</h2>
          <div className="lx-meta">
            {lesson.duration && <span>🕐 {lesson.duration}</span>}
            {lesson.level && <span className="lx-level">{lesson.level}</span>}
            {lesson.category && <span>{lesson.category}</span>}
          </div>
        </div>

        <div className="lx-progress-row">
          <div className="lx-progress"><div className="lx-progress-fill" style={{ width: `${pct}%` }} /></div>
          <span className="lx-progress-pct">{pct}%{pct >= 100 ? " · Completed ✓" : ""}</span>
        </div>

        <div className="lx-body">
          {lesson.description && <p className="lx-desc">{lesson.description}</p>}

          {objectives.length > 0 && (
            <div className="lx-objectives">
              <div className="lx-obj-head">
                <span>Learning objectives — tick as you complete</span>
                <button className="lx-markall" onClick={markAll}>Mark all done</button>
              </div>
              {objectives.map((o, i) => (
                <label key={i} className={`lx-obj ${done.has(i) ? "checked" : ""}`}>
                  <input type="checkbox" checked={done.has(i)} onChange={() => toggle(i)} />
                  <span>{o}</span>
                </label>
              ))}
            </div>
          )}

          {lesson.content && (
            <div className="lx-content">
              {lesson.content.split("\n").map((line, i) =>
                line.trim() ? <p key={i}>{line}</p> : <br key={i} />)}
            </div>
          )}

          {objectives.length === 0 && (
            <button
              className="bh-btn-primary bh-btn-full"
              onClick={() => onSave(lesson.id, [], 0, pct >= 100 ? 0 : 100)}
              style={{ marginTop: 16 }}
            >
              {pct >= 100 ? "Completed ✓ — tap to undo" : "Mark as complete"}
            </button>
          )}
        </div>
      </div>
    </div>,
    document.body
  );
}
