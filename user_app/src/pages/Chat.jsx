import { useState, useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { api } from "../api.js";
import Mascot from "../components/Mascot.jsx";

/* ── Inline icon set ───────────────────────────────────────────── */
const ICON_PATHS = {
  sparkle:  <path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z" />,
  play:     <path d="M8 5.5l10 6.5-10 6.5z" fill="currentColor" stroke="none" />,
  arrow:    <><path d="M5 12h13" /><path d="M12 6l6 6-6 6" /></>,
  chevron:  <path d="M9 6l6 6-6 6" />,
  phone:    <path d="M5 4h4l2 5-3 2c1 3 3 5 6 6l2-3 5 2v4c0 1-1 2-2 2C9 22 2 15 2 6c0-1 1-2 3-2z" />,
  chat:     <path d="M21 12a8 8 0 0 1-11.5 7.2L4 21l1.8-5.5A8 8 0 1 1 21 12z" />,
  shield:   <path d="M12 3l7 3v5c0 5-3 8-7 10-4-2-7-5-7-10V6z" />,
  paperclip:<path d="M20 11l-8.5 8.5a5 5 0 0 1-7-7L12 4a3.4 3.4 0 0 1 4.9 4.8l-8 8a1.8 1.8 0 0 1-2.6-2.5l7.4-7.4" />,
  send:     <><path d="M5 12h13" /><path d="M12 6l6 6-6 6" /></>,
  wind:     <><path d="M3 8.5h8.5A2.5 2.5 0 1 0 9 6" /><path d="M3 12.5h12A2.5 2.5 0 1 1 12.5 15" /><path d="M3 16.5h6.5A2 2 0 1 1 7.5 18.5" /></>,
  refresh:  <><path d="M4.5 11a7.5 7.5 0 0 1 12.8-4.3L20 9" /><path d="M20 4v5h-5" /><path d="M19.5 13a7.5 7.5 0 0 1-12.8 4.3L4 15" /><path d="M4 20v-5h5" /></>,
  heart:    <path d="M12 20s-7-4.4-9.3-8.8C1.2 8 2.8 4.7 6.2 4.7c2 0 3.2 1.2 3.8 2.2.6-1 1.8-2.2 3.8-2.2 3.4 0 5 3.3 3.5 6.5C19 15.6 12 20 12 20z" />,
  edit:     <><path d="M4 20h4L18 10l-4-4L4 16z" /><path d="M13.5 6.5l4 4" /></>,
  check:    <path d="M5 12l4 4 10-10" />,
  swap:     <><path d="M7 7h11l-3-3" /><path d="M17 17H6l3 3" /></>,
  journal:  <><rect x="5" y="3" width="14" height="18" rx="2" /><path d="M9 3v18M12 8h4M12 12h4" /></>,
  moon:     <path d="M21 13A8 8 0 1 1 11 3a6 6 0 0 0 10 10z" />,
  headphones: <><path d="M4 14v-2a8 8 0 0 1 16 0v2" /><rect x="3" y="13.5" width="4.5" height="6.5" rx="1.6" /><rect x="16.5" y="13.5" width="4.5" height="6.5" rx="1.6" /></>,
  trash:    <><path d="M4 7h16" /><path d="M9 7V5h6v2" /><path d="M6 7l1 13h10l1-13" /><path d="M10 11v6M14 11v6" /></>,
};

function Icon({ name, size = 18, className = "", stroke = 1.7 }) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round">
      {ICON_PATHS[name]}
    </svg>
  );
}

/* Double-check read receipt */
function ReadCheck() {
  return (
    <svg className="ai-read" width="16" height="16" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 12.5l4 4 8.5-9" />
      <path d="M9.5 16.5l1 1 8.5-9" />
    </svg>
  );
}

/* ── Topic chips ───────────────────────────────────────────────── */
const TOPICS = [
  { label: "Anxiety",  emoji: "😟", text: "I've been feeling anxious lately and I'm not sure why." },
  { label: "Stress",   emoji: "😣", text: "I've been under a lot of stress recently." },
  { label: "Insomnia", emoji: "🌙", text: "I'm having trouble sleeping at night." },
  { label: "Sad",      emoji: "😢", text: "I've been feeling sad and low on energy." },
  { label: "Lonely",   emoji: "🫥", text: "I've been feeling lonely these days." },
];

const QUICK_REPLIES = [
  { icon: "edit",  text: "How can I worry less?" },
  { icon: "check", text: "I'm having trouble focusing 😟" },
  { icon: "swap",  text: "I often compare myself to others" },
];

// "What next?" suggestions shown under the latest AI reply so a conversation
// never ends abruptly — each chip sends a natural follow-up message.
const NEXT_STEPS = [
  { icon: "wind",    label: "3-min breathing",   text: "Can you guide me through a short 3-minute breathing exercise?" },
  { icon: "sparkle", label: "Try a CBT exercise", text: "Can you suggest one short CBT exercise I can try right now?" },
  { icon: "journal", label: "Note how I feel",    nav: "nhatky" },
];

/* ── Seed conversation (matches mockup) ────────────────────────── */
// Greeting shown at the top of a brand-new conversation (no history yet).
const WELCOME = [
  { role: "ai", time: "",
    text: "Hi there! 👋\nI'm MindCare AI, here to listen and be with you. What would you like to share today?" },
];

function nowTime() {
  return new Date().toTimeString().slice(0, 5);
}

function fmtTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return isNaN(d) ? "" : d.toTimeString().slice(0, 5);
}

// Convert backend conversation messages → the bubble shape this page renders.
function mapServerMessages(messages) {
  return (messages || []).map((m) => {
    if (m.role === "user")
      return { role: "user", time: fmtTime(m.created_at), read: true, text: m.content };
    if (m.role === "assistant")
      return { role: "ai", time: fmtTime(m.created_at), text: m.content };
    // system notice (crisis / pending_review / rejected)
    return { role: "ai", time: fmtTime(m.created_at), text: m.content,
             crisis: m.status === "crisis" };
  });
}

/* Render text with paragraph + line breaks preserved */
// Render inline **bold** (markdown) → <strong>. Only used for AI messages so a
// user typing literal ** isn't reinterpreted.
function renderInline(line) {
  return line.split(/(\*\*[^*]+\*\*)/g).map((part, k) => {
    const m = /^\*\*([^*]+)\*\*$/.exec(part);
    return m ? <strong key={k}>{m[1]}</strong> : <span key={k}>{part}</span>;
  });
}

function MsgText({ text, md }) {
  return text.split("\n\n").map((para, i) => (
    <p key={i} className="ai-p">
      {para.split("\n").map((line, j) => (
        <span key={j}>{j > 0 && <br />}{md ? renderInline(line) : line}</span>
      ))}
    </p>
  ));
}

/* Split the "From your library" footer out of the reply. Each footer line is
   parsed on its own ("- Lesson: Title (dur)" / "- Resource: Title [type]") and
   matched to a real library item by EXACT title, so the chips shown are exactly
   the ones attached (in order) — even after a clinician adds/removes some.
   A line with no matching published item still renders (just not clickable). */
const REC_LINE_RE = /^\s*-\s*(lesson|resource)\s*:\s*(.+?)\s*(?:\(([^)]*)\)|\[([^\]]*)\])?\s*$/i;

function parseRecs(text, library) {
  const marker = "From your library";
  const idx = (text || "").indexOf(marker);
  if (idx === -1) return { body: text, recs: [] };
  const body = text.slice(0, idx).trim();
  const footer = text.slice(idx);
  const lib = library || [];
  const recs = [];
  for (const line of footer.split("\n")) {
    const m = line.match(REC_LINE_RE);
    if (!m) continue;
    const kind = m[1].toLowerCase();
    const title = m[2].trim();
    const meta = (m[3] || m[4] || "").trim();
    const found = lib.find((it) => it.kind === kind && it.title &&
      it.title.trim().toLowerCase() === title.toLowerCase());
    recs.push(found || {
      kind, id: `txt:${kind}:${title}`, title, full: null,
      duration: kind === "lesson" ? meta : undefined,
      type: kind === "resource" ? meta : undefined,
    });
  }
  return { body: body || text, recs };
}

/* ── In-chat psychologist booking helpers ─────────────────────────── */
function isoDate(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
function fmtApptDate(iso) {
  if (!iso) return "";
  return new Date(iso + "T00:00:00").toLocaleDateString("en-GB",
    { weekday: "short", day: "numeric", month: "short" });
}
/* Match the user's recent context to a psychologist's specialty so the agent
   can recommend the most relevant expert (the user can still pick anyone). */
// Recommendation is driven by the user's emotional CONTENT, not by the crisis
// flag itself (suicidal risk is handled by the hotline + deterministic gate,
// and does NOT imply a "trauma" specialist). So no crisis→specialty mapping.
// specialty[] uses short stems so it tolerates typos / variants in the
// admin-entered specialty text (e.g. "anxi" matches "Anxiety", "Anxitey",
// "anxious"; "depress" matches "Depression").
const BOOK_THEMES = [
  { label: "anxiety & panic", weight: 1,
    triggers: ["anxious", "anxiety", "anxiet", "panic", "worry", "worried", "nervous", "on edge", "overwhelm", "racing thoughts", "chest tightens", "can't breathe", "cant breathe", "freeze up"],
    specialty: ["anxi", "panic", "stress"] },
  { label: "depression & low mood", weight: 1,
    triggers: ["sad", "depress", "hopeless", "empty", "worthless", "numb", "low mood", "no energy", "pointless", "cry", "down"],
    specialty: ["depress", "mood"] },
  { label: "trauma", weight: 2,
    triggers: ["trauma", "abuse", "assault", "ptsd", "flashback", "nightmare"],
    specialty: ["trauma", "ptsd"] },
  { label: "grief & loss", weight: 2,
    triggers: ["grief", "loss", "passed away", "died", "bereave", "mourning"],
    specialty: ["grief", "loss", "bereave"] },
  { label: "relationships", weight: 1,
    triggers: ["relationship", "partner", "breakup", "broke up", "divorce", "family", "lonely", "alone"],
    specialty: ["relationship", "family", "couple"] },
  { label: "sleep", weight: 1,
    triggers: ["sleep", "insomnia", "can't sleep", "cant sleep", "awake at night"],
    specialty: ["sleep", "insomnia"] },
];

function recommendExpert(experts, contextText) {
  const ctx = (contextText || "").toLowerCase();
  const active = BOOK_THEMES.filter((t) => t.triggers.some((w) => ctx.includes(w)));
  if (!active.length) return null;
  let best = null;
  for (const e of experts || []) {
    const hay = `${e.specialty || ""} ${e.bio || ""} ${e.experience || ""}`.toLowerCase();
    let score = 0, label = null;
    for (const t of active) {
      if (t.specialty.some((w) => hay.includes(w))) { score += t.weight; if (!label) label = t.label; }
    }
    if (score > 0 && (!best || score > best.score)) best = { expert: e, score, reason: `specializes in ${label}` };
  }
  return best;
}

/* Group an expert's free times by day across the whole booking window, so the
   user can scroll through every available day (not just the first few). */
function freeSlotsByDay(avail) {
  if (!avail || !avail.window) return [];
  const taken = new Set((avail.booked || []).map((b) => `${b.date} ${b.slot}`));
  const slots = avail.expert?.slots || [];
  const out = [];
  const start = new Date(avail.window.from + "T00:00:00");
  const end = new Date(avail.window.to + "T00:00:00");
  for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
    const ds = isoDate(d);
    const free = slots.filter((sl) => !taken.has(`${ds} ${sl}`));
    if (free.length) out.push({ date: ds, slots: free });
  }
  return out;
}

/* ── Chat bubble ───────────────────────────────────────────────── */
function ChatBubble({ msg, library, onOpenRec, onTalkExpert, onManageAppt,
                     onLessonCard, onExpertCard, onRunAction }) {
  const isAI = msg.role === "ai";
  const { body, recs } = isAI
    ? parseRecs(msg.text, library)
    : { body: msg.text, recs: [] };
  // Interactive data cards from the info-gate (lessons / psychologists /
  // appointments). When present, show only the intro line of the text — the list
  // itself is rendered as tappable cards below (the full text stays in history).
  const cards = isAI && Array.isArray(msg.cards) ? msg.cards : [];
  const displayBody = cards.length ? (body.split("\n")[0] || body) : body;
  return (
    <div className={`ai-row ${isAI ? "ai" : "user"}`}>
      {isAI && (
        <div className="ai-avatar"><Mascot variant="chat" size={30} className="mascot-idle" /></div>
      )}
      <div className="ai-msg">
        <div className={`ai-bubble ${isAI ? "ai-bubble-ai" : "ai-bubble-user"} ${msg.error ? "ai-bubble-error" : ""}`}>
          <MsgText text={displayBody} md={isAI} />
          {cards.map((c, ci) => (
            <div className="ai-recs" key={"card" + ci}>
              {c.kind === "lessons" && (c.items || []).map((it) => (
                <button key={it.id} className="ai-rec-chip"
                        onClick={() => onLessonCard && onLessonCard(it)}>
                  <span className="ai-rec-emoji">📘</span>
                  <span className="ai-rec-title">{it.title}</span>
                  {it.duration && <span className="ai-rec-meta">{it.duration}</span>}
                  <span className="ai-rec-arrow">›</span>
                </button>
              ))}
              {c.kind === "resources" && (c.items || []).map((it) => (
                <button key={it.id} className="ai-rec-chip"
                        onClick={() => onLessonCard && onLessonCard(it)}>
                  <span className="ai-rec-emoji">📗</span>
                  <span className="ai-rec-title">{it.title}</span>
                  {it.type && <span className="ai-rec-meta">{it.type}</span>}
                  <span className="ai-rec-arrow">›</span>
                </button>
              ))}
              {c.kind === "psychologists" && (c.items || []).map((it) => (
                <button key={it.id} className="ai-book-expert"
                        onClick={() => onExpertCard && onExpertCard(it)}>
                  <span className="ai-book-avatar">{(it.name || "?").slice(0, 1).toUpperCase()}</span>
                  <span className="ai-book-exp-info">
                    <span className="ai-book-exp-name">{it.name}</span>
                    <span className="ai-book-exp-spec">{it.specialty || "Counselling"}{it.experience ? ` · ${it.experience}` : ""}</span>
                  </span>
                  <span className="ai-rec-arrow">›</span>
                </button>
              ))}
              {c.kind === "appointments" && (c.items || []).map((it, k) => (
                <div key={k} className="ai-rec-chip ai-rec-chip-static">
                  <span className="ai-rec-emoji">📅</span>
                  <span className="ai-rec-title">{it.date} {it.slot} · {it.name}</span>
                  <span className="ai-rec-meta">{it.status}</span>
                </div>
              ))}
            </div>
          ))}
          {isAI && Array.isArray(msg.actions) && msg.actions.length > 0 && (
            <div className="ai-recs">
              {msg.actions.map((a, k) => (
                <ConfirmAction key={k} action={a} onRun={onRunAction} />
              ))}
            </div>
          )}
          {recs.length > 0 && (
            <div className="ai-recs">
              <div className="ai-recs-label">📚 From your library</div>
              {recs.map((r) => (
                r.full ? (
                  <button key={r.kind + r.id} className="ai-rec-chip" onClick={() => onOpenRec(r)}>
                    <span className="ai-rec-emoji">{r.kind === "lesson" ? "📘" : "📗"}</span>
                    <span className="ai-rec-title">{r.title}</span>
                    {(r.duration || r.type) && <span className="ai-rec-meta">{r.duration || r.type}</span>}
                    <span className="ai-rec-arrow">›</span>
                  </button>
                ) : (
                  <div key={r.kind + r.id} className="ai-rec-chip ai-rec-chip-static">
                    <span className="ai-rec-emoji">{r.kind === "lesson" ? "📘" : "📗"}</span>
                    <span className="ai-rec-title">{r.title}</span>
                    {(r.duration || r.type) && <span className="ai-rec-meta">{r.duration || r.type}</span>}
                  </div>
                )
              ))}
            </div>
          )}
          {/* In-chat psychologist booking is an L0 CRISIS affordance only.
              For L1 (pending_review) we just say a clinician is reviewing —
              the psychologist offer, if any, comes from the clinician's reply. */}
          {msg.crisis && onTalkExpert && (
            <button className="ai-expert-cta" onClick={onTalkExpert}>
              🧑‍⚕️ Talk to a psychologist →
            </button>
          )}
          {(msg.resources || msg.crisis) && (
            <div className="ai-bubble-hotline">
              <Icon name="phone" size={16} />
              {msg.resources ? (
                <span className="hotline-list">
                  {Object.values(msg.resources).map((res, i) => {
                    const isLink = String(res.phone).startsWith("http");
                    return (
                      <span key={i} className="hotline-item">
                        <strong>{res.name}</strong>{" "}
                        {isLink ? (
                          <a href={res.url} target="_blank" rel="noreferrer">{res.url}</a>
                        ) : (
                          <>— call <strong>{res.phone}</strong></>
                        )}
                        {res.available ? ` · ${res.available}` : ""}
                      </span>
                    );
                  })}
                </span>
              ) : (
                <span>If you're in crisis, call <strong>988</strong> — available 24/7.</span>
              )}
            </div>
          )}
          {msg.appt && (
            <div className="ai-appt-card">
              <div className="ai-appt-title">✅ Appointment booked — please check it's correct</div>
              <div className="ai-appt-row">🧑‍⚕️ <strong>{msg.appt.name}</strong>{msg.appt.specialty ? ` · ${msg.appt.specialty}` : ""}</div>
              <div className="ai-appt-row">📅 {fmtApptDate(msg.appt.date)} &nbsp; 🕐 {msg.appt.slot}</div>
              {msg.appt.phone && <div className="ai-appt-row">📞 {msg.appt.phone}</div>}
              <div className="ai-appt-status">Status: <strong>pending</strong> the expert's confirmation</div>
              {onManageAppt && (
                <button className="ai-appt-manage" onClick={onManageAppt}>
                  View / change in Counselling →
                </button>
              )}
            </div>
          )}
        </div>
        <div className="ai-meta">
          <span>{msg.time}</span>
          {!isAI && msg.read && <ReadCheck />}
        </div>
      </div>
    </div>
  );
}

function TypingBubble({ label }) {
  return (
    <div className="ai-row ai">
      <div className="ai-avatar"><Mascot variant="chat" size={30} className="mascot-idle" /></div>
      <div className="ai-bubble ai-bubble-ai ai-thinking">
        <span className="ai-thinking-label">{label || "MindCare is thinking"}</span>
        <span className="ai-typing"><span /><span /><span /></span>
      </div>
    </div>
  );
}

/* A confirm-card for a write action proposed by the assistant (log mood, cancel
   appointment, mark lesson done, open screening). Two taps for writes — the chip
   arms, then Confirm runs it — so nothing is written by accident. */
function ConfirmAction({ action, onRun }) {
  const [armed, setArmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  if (done)
    return (
      <div className="ai-rec-chip ai-rec-chip-static">
        <span className="ai-rec-emoji">✓</span>
        <span className="ai-rec-title">{action.label}</span>
      </div>
    );
  if (action.kind === "navigate" || action.kind === "reschedule_appt")
    return (
      <button className="ai-expert-cta" onClick={() => onRun(action)}>
        {action.label} →
      </button>
    );
  const emoji = action.kind === "cancel_appt" ? "🗑️"
    : action.kind === "mark_lesson" ? "✅" : "📝";
  if (!armed)
    return (
      <button className="ai-rec-chip" onClick={() => setArmed(true)}>
        <span className="ai-rec-emoji">{emoji}</span>
        <span className="ai-rec-title">{action.label}</span>
        <span className="ai-rec-arrow">›</span>
      </button>
    );
  return (
    <div className="ai-action-confirm">
      <span className="ai-action-q">{action.label}?</span>
      <button className="ai-expert-cta" disabled={busy}
        onClick={async () => {
          setBusy(true);
          const ok = await onRun(action);
          if (ok) setDone(true); else { setBusy(false); setArmed(false); }
        }}>{busy ? "…" : "Confirm"}</button>
      <button className="ai-book-cancel" disabled={busy}
        onClick={() => setArmed(false)}>Cancel</button>
    </div>
  );
}

/* In-chat psychologist booking: pick an expert → pick a free time → booked.
   Rendered as an assistant card at the foot of the feed (transient). */
function ExpertCard({ e, recommended, onPick }) {
  return (
    <button className={`ai-book-expert${recommended ? " ai-book-expert-reco" : ""}`} onClick={() => onPick(e)}>
      <span className="ai-book-avatar">{e.name.slice(0, 1).toUpperCase()}</span>
      <span className="ai-book-exp-info">
        <span className="ai-book-exp-name">{e.name}</span>
        <span className="ai-book-exp-spec">{e.specialty || "Counselling"}{e.experience ? ` · ${e.experience}` : ""}</span>
      </span>
      <span className="ai-rec-arrow">›</span>
    </button>
  );
}

function ExpertBookingCard({ state, onPickExpert, onPickSlot, onBack, onCancel }) {
  const { step, loading, experts = [], expert, avail, booking, error, recommended } = state;
  const days = step === "slots" ? freeSlotsByDay(avail) : [];
  const others = recommended
    ? experts.filter((e) => e.id !== recommended.expert.id)
    : experts;
  return (
    <div className="ai-row ai">
      <div className="ai-avatar"><Mascot variant="chat" size={30} className="mascot-idle" /></div>
      <div className="ai-msg">
        <div className="ai-bubble ai-bubble-ai ai-book">
          {step === "experts" && (
            <>
              <div className="ai-book-title">Let's connect you with a psychologist. Who would you like to talk to?</div>
              {loading ? <div className="ai-book-loading">Loading psychologists…</div> : (
                experts.length === 0 ? (
                  <div className="ai-book-empty">No psychologists are available right now — please use the hotline above.</div>
                ) : (
                  <>
                    {recommended && (
                      <div className="ai-book-reco">
                        <div className="ai-book-reco-label">✨ Recommended for you — {recommended.reason}</div>
                        <ExpertCard e={recommended.expert} recommended onPick={onPickExpert} />
                      </div>
                    )}
                    {others.length > 0 && (
                      <div className="ai-book-experts">
                        {recommended && <div className="ai-book-others-label">Or choose another psychologist</div>}
                        {others.map((e) => (
                          <ExpertCard key={e.id} e={e} onPick={onPickExpert} />
                        ))}
                      </div>
                    )}
                  </>
                )
              )}
              <button className="ai-book-cancel" onClick={onCancel}>Not now</button>
            </>
          )}

          {step === "slots" && (
            <>
              <div className="ai-book-title">Pick a time with <strong>{expert?.name}</strong> (next 3 weeks):</div>
              {loading ? <div className="ai-book-loading">Loading available times…</div> : (
                days.length === 0 ? (
                  <div className="ai-book-empty">No free slots in the next 3 weeks — try another psychologist.</div>
                ) : (
                  <div className="ai-book-days">
                    {days.map((g) => (
                      <div key={g.date} className="ai-book-day">
                        <div className="ai-book-day-label">{fmtApptDate(g.date)}</div>
                        <div className="ai-book-slots">
                          {g.slots.map((sl) => (
                            <button key={sl} className="ai-book-slot" disabled={booking}
                                    onClick={() => onPickSlot(g.date, sl)}>
                              {sl}
                            </button>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )
              )}
              {error && <div className="ai-book-error">{error}</div>}
              <div className="ai-book-foot">
                <button className="ai-book-cancel" onClick={onBack} disabled={booking}>← Back</button>
                {booking && <span className="ai-book-loading">Booking…</span>}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

/* Empty / fresh-chat state: an animated mascot greeting shown before the
   first user message, instead of a bare welcome bubble. */
function EmptyState({ greeting }) {
  return (
    <div className="ai-empty" data-reveal>
      <div className="ai-empty-mascot">
        <span className="ai-empty-halo" aria-hidden="true" />
        <Mascot variant="wave" size={104} className="mascot-idle" />
      </div>
      <p className="ai-empty-text">{greeting}</p>
      <span className="ai-empty-hint">Share anything that's on your mind — I'm listening.</span>
    </div>
  );
}

/* ── Breathing progress ring ───────────────────────────────────── */
function BreathingRing({ progress = 0.68 }) {
  const r = 26;
  const c = 2 * Math.PI * r;
  return (
    <svg className="ai-ring" width="64" height="64" viewBox="0 0 64 64">
      <circle cx="32" cy="32" r={r} fill="none" stroke="#E2F1EC" strokeWidth="7" />
      <circle cx="32" cy="32" r={r} fill="none" stroke="#14b8a6" strokeWidth="7"
        strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c * (1 - progress)}
        transform="rotate(-90 32 32)" />
      <circle cx="32" cy="32" r="9" fill="#E7F6F1" />
    </svg>
  );
}

/* ── Conversation history ──────────────────────────────────────── */
function fmtDay(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d)) return "";
  const today = new Date();
  const sameDay = d.toDateString() === today.toDateString();
  return sameDay ? d.toTimeString().slice(0, 5) : d.toLocaleDateString("en-GB");
}

function HistoryCard({ conversations, activeId, onOpen, onNew }) {
  return (
    <div className="ai-card">
      <div className="ai-card-title" style={{ justifyContent: "space-between", display: "flex", alignItems: "center" }}>
        <span><Icon name="chat" size={17} /> Conversations</span>
        <button className="ai-btn-primary ai-btn-sm" onClick={onNew}>+ New</button>
      </div>
      {conversations.length === 0 ? (
        <p className="ai-card-text">No past conversations yet. Start chatting and your history will appear here.</p>
      ) : (
        <div className="ai-history-list">
          {conversations.map((c) => (
            <button
              key={c.id}
              className={`ai-history-item ${c.id === activeId ? "active" : ""}`}
              onClick={() => onOpen(c.id)}
              title={c.title}
            >
              <span className="ai-history-title">{c.title || "Conversation"}</span>
              <span className="ai-history-time">{fmtDay(c.updated_at)}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── Left conversation rail (ChatGPT-style nav) ─────────────────── */
function ConversationNav({ conversations, activeId, onOpen, onNew, onDelete }) {
  return (
    <aside className="ai-conv">
      <button className="ai-conv-new" onClick={onNew}>
        <span className="ai-conv-plus">+</span> New chat
      </button>
      <div className="ai-conv-label">Conversations</div>
      {conversations.length === 0 ? (
        <p className="ai-conv-empty">No conversations yet — start chatting and they'll show up here.</p>
      ) : (
        <div className="ai-conv-list">
          {conversations.map((c) => (
            <div key={c.id} className={`ai-conv-item ${c.id === activeId ? "active" : ""}`}>
              <button className="ai-conv-main" onClick={() => onOpen(c.id)} title={c.title}>
                <Icon name="chat" size={15} className="ai-conv-ico" />
                <span className="ai-conv-title">{c.title || "Conversation"}</span>
                <span className="ai-conv-time">{fmtDay(c.updated_at)}</span>
              </button>
              <button
                className="ai-conv-del"
                onClick={(e) => { e.stopPropagation(); onDelete(c); }}
                title="Delete conversation"
                aria-label="Delete conversation"
              >
                <Icon name="trash" size={14} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Brand — fills the empty space at the bottom of the rail */}
      <div className="ai-conv-brand">
        <Mascot variant="wave" size={76} />
        <span className="ai-conv-brand-name">AI Support</span>
        <span className="ai-conv-brand-sub">MindCare AI</span>
      </div>
    </aside>
  );
}

/* ── Right panel ───────────────────────────────────────────────── */
function RightPanel({ onUseTip, conversations, activeId, onOpen, onNew }) {
  return (
    <aside className="ai-side">
      {/* Conversation history */}
      <HistoryCard conversations={conversations} activeId={activeId} onOpen={onOpen} onNew={onNew} />

      {/* Quick suggestions */}
      <div className="ai-card">
        <div className="ai-card-title"><Icon name="sparkle" size={17} /> Quick Suggestions</div>
        <button className="ai-sug" onClick={() => onUseTip("Can you guide me through a 5-minute anxiety relief exercise?")}>
          <div className="ai-sug-text">
            <div className="ai-sug-t">5-Minute Anxiety Relief</div>
            <div className="ai-sug-s">Relax quickly and regain balance</div>
          </div>
          <span className="ai-sug-btn ai-sug-play"><Icon name="play" size={13} /></span>
        </button>
        <button className="ai-sug" onClick={() => onUseTip("How do I write an emotion journal?")}>
          <div className="ai-sug-text">
            <div className="ai-sug-t">Write an Emotion Journal</div>
            <div className="ai-sug-s">Understand yourself better every day</div>
          </div>
          <span className="ai-sug-btn"><Icon name="chevron" size={16} /></span>
        </button>
      </div>

      {/* Breathing exercise */}
      <div className="ai-card">
        <div className="ai-breath-top">
          <div>
            <div className="ai-card-title ai-card-title-teal"><Icon name="wind" size={17} /> 4-7-8 Breathing Exercise</div>
            <p className="ai-breath-text">Deep breathing helps your body and mind relax effectively.</p>
          </div>
          <BreathingRing />
        </div>
        <button className="ai-btn-primary ai-btn-full" onClick={() => onUseTip("Can you guide me through the 4-7-8 breathing exercise?")}>
          Start
        </button>
        <div className="ai-breath-steps">4s inhale • 7s hold • 8s exhale</div>
      </div>

      {/* You're not alone */}
      <div className="ai-card">
        <div className="ai-card-title"><Icon name="chat" size={17} /> You're Not Alone</div>
        <p className="ai-card-text">If you're struggling or having negative thoughts, please seek help right away.</p>
        <div className="ai-hotline">
          <span className="ai-hotline-icon"><Icon name="phone" size={18} /></span>
          <div>
            <div className="ai-hotline-label">24/7 Suicide &amp; Crisis Lifeline</div>
            <a className="ai-hotline-num" href="tel:988">988</a>
          </div>
        </div>
      </div>

      {/* Always here */}
      <div className="ai-card ai-always">
        <div className="ai-always-mascot"><Mascot variant="wave" size={88} /></div>
        <div className="ai-always-body">
          <div className="ai-card-title">MindCare AI is always here 💚</div>
          <p className="ai-card-text">Whether it's a good day or not, you can always share with me anytime.</p>
          <button className="ai-btn-primary ai-btn-sm" onClick={() => onUseTip("I just wanted to check in and share how I'm doing today.")}>
            Send Encouragement 💚
          </button>
        </div>
      </div>
    </aside>
  );
}

/* ── Page ──────────────────────────────────────────────────────── */
export default function Chat({ onNav }) {
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [messages, setMessages] = useState(WELCOME);
  const [activeId, setActiveId] = useState(null);
  const [conversations, setConversations] = useState([]);
  // Mobile: the conversation rail is a slide-in drawer (≡ opens it). Desktop:
  // the rail is always inline and this state is ignored.
  const [railOpen, setRailOpen] = useState(false);
  const closeRailOnMobile = () => { if (window.innerWidth <= 1080) setRailOpen(false); };
  const [library, setLibrary] = useState([]);     // lessons+resources for clickable recs
  const [recDetail, setRecDetail] = useState(null);
  const [expertBooking, setExpertBooking] = useState(null); // in-chat booking flow
  const [rescheduleId, setRescheduleId] = useState(null);   // appt being rescheduled
  const [listenOnly, setListenOnly] = useState(false);      // "just listen" toggle
  const bottomRef = useRef(null);
  const inputRef = useRef(null);
  const pollRef = useRef(null);
  const pendingRef = useRef(null);  // { sid, idx } while a clinician review is outstanding
  const sendingRef = useRef(false); // synchronous double-submit guard (state is too slow)
  // Tracks the listen-only value we last pushed to the backend via the toggle,
  // so we only send it when the user actually flips the switch — a normal turn
  // sends nothing and never clobbers a "just listen" the user TYPED.
  const syncedListenRef = useRef(false);

  const listenKey = (id) => "mc_listen_" + (id || "new");
  // Restore the toggle when switching threads.
  useEffect(() => {
    const on = localStorage.getItem(listenKey(activeId)) === "1";
    setListenOnly(on);
    syncedListenRef.current = on;
  }, [activeId]);
  const toggleListen = () => {
    setListenOnly((v) => {
      const nv = !v;
      localStorage.setItem(listenKey(activeId), nv ? "1" : "0");
      return nv;
    });
  };

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, expertBooking]);

  // Load the library once so "From your library" recommendations can be matched
  // to real lessons/resources and opened on tap.
  useEffect(() => {
    let alive = true;
    Promise.all([api.lessons().catch(() => ({})), api.resources().catch(() => ({}))])
      .then(([L, R]) => {
        if (!alive) return;
        setLibrary([
          ...(L.lessons || []).map((l) => ({ kind: "lesson", id: l.id, title: l.title, duration: l.duration, full: l })),
          ...(R.resources || []).map((r) => ({ kind: "resource", id: r.id, title: r.title, type: r.type, full: r })),
        ]);
      });
    return () => { alive = false; };
  }, []);

  useEffect(() => () => clearInterval(pollRef.current), []);

  // Wake the Modal GPU containers the moment the Chat page opens, so the
  // cold start happens while the user is still typing — not after they send.
  useEffect(() => { api.warmup().catch(() => {}); }, []);

  async function loadConversations() {
    try {
      const r = await api.listConversations();
      setConversations(r.conversations || []);
    } catch { /* ignore — history is best-effort */ }
  }
  useEffect(() => { loadConversations(); }, []);

  async function openConversation(cid) {
    if (cid === activeId) return;
    try {
      const r = await api.getConversation(cid);
      const mapped = mapServerMessages(r.messages);
      setMessages(mapped.length ? mapped : WELCOME);
      setActiveId(cid);
    } catch { /* ignore */ }
  }


  function newChat() {
    clearInterval(pollRef.current);
    pollRef.current = null;
    pendingRef.current = null;
    setMessages(WELCOME);
    setActiveId(null);
    setExpertBooking(null);
    setRescheduleId(null);
    inputRef.current?.focus();
  }

  async function deleteConv(c) {
    if (!window.confirm(`Delete "${c.title || "this conversation"}"? This can't be undone.`)) return;
    // Optimistic: drop it from the list immediately, then persist.
    setConversations((prev) => prev.filter((x) => x.id !== c.id));
    try { await api.deleteConversation(c.id); } catch { /* best-effort */ }
    if (c.id === activeId) newChat();
    loadConversations();
  }

  // ── In-chat psychologist booking (opened from the crisis "Talk to a
  //    psychologist" CTA) — pick expert → pick time → auto-book → confirm. ──
  async function startExpertBooking() {
    setExpertBooking({ step: "experts", loading: true, experts: [] });
    try {
      const r = await api.experts();
      const experts = r.experts || [];
      if (!experts.length && onNav) { setExpertBooking(null); onNav("tuvan"); return; }
      // Recommend the expert whose specialty best fits the user's recent words.
      const ctx = messages.filter((m) => m.role === "user").slice(-5).map((m) => m.text).join(" ");
      const recommended = recommendExpert(experts, ctx);
      setExpertBooking({ step: "experts", loading: false, experts, recommended });
    } catch {
      setExpertBooking(null);
      if (onNav) onNav("tuvan");   // fall back to the full Counselling page
    }
  }
  function pushAi(text, error) {
    setMessages((prev) => [...prev, { role: "ai", time: nowTime(), text, error: !!error }]);
  }

  // Run a confirmed write action via the existing REST endpoints. Returns true
  // on success so the confirm-card can mark itself done.
  async function runAction(action) {
    try {
      if (action.kind === "navigate") { if (onNav) onNav(action.section); return true; }
      if (action.kind === "log_mood") {
        await api.submitScreening({ mood_score: action.value });
        pushAi(`Done — I've logged today's mood as ${action.value}/10. 💚`);
        return true;
      }
      if (action.kind === "cancel_appt") {
        await api.cancelAppointment(action.appointment_id);
        pushAi("Your appointment has been cancelled.");
        return true;
      }
      if (action.kind === "mark_lesson") {
        await api.setLessonProgress(action.lesson_id, { progress_pct: 100 });
        pushAi("Nice work — I've marked that lesson as completed. 🎉");
        return true;
      }
      if (action.kind === "reschedule_appt") {
        // Opens the slot picker for this expert; the actual change happens in
        // bookSlot once the user picks a new time.
        setRescheduleId(action.appointment_id);
        pickExpert({ id: action.psychologist_id, name: action.name });
        return true;
      }
    } catch {
      pushAi("Sorry, that didn't go through — please try again in a moment.", true);
      return false;
    }
    return false;
  }

  // Tap a lesson card from an info-gate reply → open its detail (the lesson is
  // in the library, loaded from the same published set); otherwise jump to the
  // Lessons page.
  function openLessonCard(item) {
    const lib = library.find((x) => x.id === item.id);
    if (lib) setRecDetail(lib);
    else if (onNav) onNav(item.type ? "tainguyen" : "baihoc");
  }
  async function pickExpert(e) {
    setExpertBooking((b) => ({ ...b, step: "slots", loading: true, expert: e, error: "" }));
    try {
      const av = await api.expertAvailability(e.id);
      setExpertBooking((b) => ({ ...b, step: "slots", loading: false, expert: e, avail: av }));
    } catch (err) {
      setExpertBooking((b) => ({ ...b, step: "slots", loading: false, error: err.message }));
    }
  }
  async function bookSlot(date, slot) {
    const exp = expertBooking?.expert;
    if (!exp) return;
    setExpertBooking((b) => ({ ...b, booking: true, error: "" }));
    try {
      if (rescheduleId) {
        await api.changeAppointment(rescheduleId, { date, slot });
        setRescheduleId(null);
        setExpertBooking(null);
        setMessages((prev) => [...prev, {
          role: "ai", time: nowTime(),
          text: "I've rescheduled your appointment — please check the new details below.",
          appt: { name: exp.name, date, slot },
        }]);
      } else {
        await api.bookAppointment({ psychologist_id: exp.id, date, slot });
        setExpertBooking(null);
        setMessages((prev) => [...prev, {
          role: "ai", time: nowTime(),
          text: "I've booked this consultation for you — please check the details below are correct.",
          appt: { name: exp.name, specialty: exp.specialty, phone: exp.phone, date, slot },
        }]);
      }
    } catch (err) {
      setExpertBooking((b) => ({ ...b, booking: false, error: err.message }));
    }
  }

  // Apply a fetched session: when the clinician has answered/rejected, swap the
  // placeholder bubble for the final reply and stop polling. Returns true once
  // settled. Only touches the one bubble at `idx`, so it never clobbers input.
  function applySession(s, idx) {
    if (s.status !== "answered" && s.status !== "rejected") return false;
    clearInterval(pollRef.current);
    pollRef.current = null;
    pendingRef.current = null;
    setMessages((prev) => {
      const next = [...prev];
      next[idx] = {
        role: "ai",
        time: nowTime(),
        text: s.status === "answered"
          ? s.final_reply
          : "A clinician determined a different approach is needed. Please reach out directly for support.",
      };
      return next;
    });
    return true;
  }

  function startPolling(sid, idx) {
    clearInterval(pollRef.current);
    pendingRef.current = { sid, idx };
    pollRef.current = setInterval(async () => {
      try { applySession(await api.mySession(sid), idx); } catch {}
    }, 3000);
  }

  // Background tabs throttle setInterval to ~once a minute (or pause it), so a
  // clinician reply approved while the user is on another tab/window wouldn't
  // appear until reload. Re-check the outstanding session the instant the tab
  // regains focus — covers the "approve in admin, switch back" flow.
  useEffect(() => {
    const recheck = async () => {
      const p = pendingRef.current;
      if (!p || document.visibilityState !== "visible") return;
      try { applySession(await api.mySession(p.sid), p.idx); } catch {}
    };
    document.addEventListener("visibilitychange", recheck);
    window.addEventListener("focus", recheck);
    return () => {
      document.removeEventListener("visibilitychange", recheck);
      window.removeEventListener("focus", recheck);
    };
  }, []);

  async function sendText(raw) {
    const text = (raw ?? input).trim();
    // Guard with a ref, not `busy` (state) — two rapid Enter/clicks fire within
    // the same render and both read the stale busy=false, sending twice. The ref
    // updates synchronously so the second call bails out immediately.
    if (!text || sendingRef.current) return;
    sendingRef.current = true;

    const aiIdx = messages.length + 1;
    setMessages((prev) => [...prev, { role: "user", time: nowTime(), read: true, text }, { role: "ai", typing: true }]);
    setInput("");
    setBusy(true);

    // The agent can take a few minutes on a cold start — longer than the
    // hosting gateway keeps a single request open. The backend still finishes
    // and SAVES the reply, so as a safety net we poll for the freshly-created
    // session and show its reply the moment it lands (no manual reload, no
    // "couldn't reach server"). Whichever resolves first — the direct /chat
    // response or the poll — wins; the other is ignored.
    let settled = false;
    let slowTimers = [];
    const show = (obj, after) => {
      if (settled) return;
      settled = true;
      clearTimeout(pollStartTimer);
      slowTimers.forEach(clearTimeout);
      clearInterval(pollRef.current);
      setMessages((prev) => { const n = [...prev]; n[aiIdx] = obj; return n; });
      loadConversations();
      if (after) after();
    };

    // Cold-start replies take a while. Keep the animated "thinking" bubble but
    // update its LABEL so it doesn't look frozen (the poll still replaces it with
    // the real answer when it lands — no separate "still working" message).
    const setPhase = (label) => {
      if (settled) return;
      setMessages((prev) => {
        const n = [...prev];
        if (n[aiIdx]?.typing) n[aiIdx] = { role: "ai", typing: true, label };
        return n;
      });
    };
    slowTimers = [
      setTimeout(() => setPhase("MindCare is reasoning"), 16000),
      setTimeout(() => setPhase("Still reasoning — the first reply can take a moment"), 50000),
    ];

    const fromSession = async (sess) => {
      if (sess.status === "auto_sent" || sess.status === "answered") {
        let txt = "I'm here with you.";
        try { const full = await api.mySession(sess.id); txt = full.final_reply || txt; } catch {}
        show({ role: "ai", time: nowTime(), text: txt });
      } else if (sess.status === "pending_review") {
        show({ role: "ai", time: nowTime(), text: "Thank you for sharing. A clinician is reviewing the response and will respond shortly." },
          () => startPolling(sess.id, aiIdx));
      } else if (sess.status === "crisis") {
        let txt = "I'm really glad you reached out. Your safety matters most right now.";
        try { const full = await api.mySession(sess.id); txt = full.final_reply || txt; } catch {}
        show({ role: "ai", time: nowTime(), text: txt, crisis: true });
      }
    };

    // Snapshot existing session ids NOW (t=0, before the backend commits the new
    // one) — not lazily at poll time. Otherwise, if the backend finishes and
    // commits the session before the snapshot, the new session is already in the
    // set and the recovery poll never spots it → the bubble stays "thinking"
    // until a manual reload (exactly the dropped/hung-response case on a long
    // cold-start L2 turn).
    const knownIdsP = api.mySessions()
      .then((s0) => new Set((s0.sessions || []).map((x) => x.id)))
      .catch(() => new Set());
    const startReplyPoll = async () => {
      if (settled || pollRef.current) return;
      const knownIds = await knownIdsP;
      if (settled) return;
      const t0 = Date.now();
      const pollOnce = async () => {
        if (settled) { clearInterval(pollRef.current); return; }
        if (Date.now() - t0 > 30 * 60 * 1000) {
          show({ role: "ai", time: nowTime(), error: true, text: "This is taking longer than usual — please reload in a moment to see the reply." });
          return;
        }
        try {
          const r = await api.mySessions();
          const fresh = (r.sessions || []).find((x) => !knownIds.has(x.id));
          if (fresh) await fromSession(fresh);
        } catch { /* keep polling */ }
      };
      pollOnce();                                  // check right away, not after 3s
      pollRef.current = setInterval(pollOnce, 3000);
    };
    // Start the recovery poll early so a slow/dropped reply still lands live.
    const pollStartTimer = setTimeout(startReplyPoll, 4000);

    try {
      const opts = activeId ? { conversation_id: activeId } : {};
      // While listen-only is ON, assert it on EVERY message so the backend can
      // never lose it (Redis restart / redeploy / another device). When OFF,
      // only send the clear ONCE — on the turn the user flips it off — so a
      // "just listen" the user TYPED isn't wiped by an ordinary turn.
      if (listenOnly) {
        opts.listen_only = true;
      } else if (syncedListenRef.current) {
        opts.listen_only = false;
      }
      syncedListenRef.current = listenOnly;
      const r = await api.chat(text, opts);
      if (settled) return;
      if (r.conversation_id && r.conversation_id !== activeId) setActiveId(r.conversation_id);
      // crisis_resources is sent for both L0 (crisis) and L1 (pending_review)
      // so the user always has a real-person lifeline to reach for.
      const resources = r.crisis_resources || null;
      if (r.outcome === "answered") {
        show({ role: "ai", time: nowTime(), text: r.final?.response || "I'm here with you.", cards: r.cards, actions: r.actions });
      } else if (r.outcome === "crisis") {
        show({ role: "ai", time: nowTime(), text: r.message || "I'm really glad you reached out. Your safety matters most right now.", crisis: true, resources });
      } else if (r.outcome === "pending_review") {
        show({ role: "ai", time: nowTime(), text: r.message || "Thank you for sharing. A clinician is reviewing your message and will respond shortly.", resources },
          () => r.session_id && startPolling(r.session_id, aiIdx));
      } else {
        show({ role: "ai", time: nowTime(), text: r.message || "I'm here with you." });
      }
    } catch {
      // Gateway cut / request aborted — let the poll recover the saved reply.
      if (!settled) startReplyPoll();
    } finally {
      slowTimers.forEach(clearTimeout);
      sendingRef.current = false;
      setBusy(false);
    }
  }

  function handleKey(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendText();
    }
  }

  return (
    <div className={`ai-page ${railOpen ? "rail-open" : ""}`}>
      <div className="ai-rail-scrim" onClick={() => setRailOpen(false)} />
      <div className="ai-grid">
        {/* ── LEFT: conversation rail (inline on desktop, drawer on mobile) ── */}
        <ConversationNav
          conversations={conversations}
          activeId={activeId}
          onOpen={(id) => { openConversation(id); closeRailOnMobile(); }}
          onNew={() => { newChat(); closeRailOnMobile(); }}
          onDelete={deleteConv}
        />

        {/* ── CENTER: chat ── */}
        <div className="ai-main">
          {/* Mobile-only: open the conversation history drawer */}
          <button className="ai-conv-open" onClick={() => setRailOpen(true)}
                  aria-label="Open conversations">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 strokeWidth="2" strokeLinecap="round" aria-hidden="true">
              <path d="M4 7h16M4 12h16M4 17h16" />
            </svg>
            <span>Conversations</span>
          </button>
          {/* Feed */}
          <div className="ai-feed">
            {!messages.some((m) => m.role === "user") && messages.length <= 1 ? (
              <EmptyState greeting={messages[0]?.text || WELCOME[0].text} />
            ) : (
              messages.map((m, i) => (m.typing ? <TypingBubble key={i} label={m.label} /> : (
                <ChatBubble key={i} msg={m} library={library}
                  onOpenRec={(r) => setRecDetail(r)}
                  onTalkExpert={startExpertBooking}
                  onManageAppt={onNav ? () => onNav("tuvan") : null}
                  onLessonCard={openLessonCard}
                  onExpertCard={pickExpert}
                  onRunAction={runAction} />
              )))
            )}
            {expertBooking && (
              <ExpertBookingCard
                state={expertBooking}
                onPickExpert={pickExpert}
                onPickSlot={bookSlot}
                onBack={startExpertBooking}
                onCancel={() => setExpertBooking(null)}
              />
            )}
            {(() => {
              const last = messages[messages.length - 1];
              const show = last && last.role === "ai" && !last.typing && !last.crisis
                && !expertBooking && !rescheduleId && messages.some((m) => m.role === "user");
              if (!show) return null;
              return (
                <div className="ai-nextsteps">
                  <span className="ai-nextsteps-label">What next?</span>
                  {NEXT_STEPS.filter((s) => s.nav || !listenOnly).map((s) => (
                    <button key={s.label} className="ai-nextstep"
                      onClick={() => (s.nav ? (onNav && onNav(s.nav)) : sendText(s.text))}>
                      <Icon name={s.icon} size={14} />{s.label}
                    </button>
                  ))}
                  <button className="ai-nextstep" onClick={() => inputRef.current?.focus()}>
                    <Icon name="chat" size={14} />Keep talking
                  </button>
                </div>
              );
            })()}
            <div ref={bottomRef} />
          </div>

          {/* Quick replies */}
          <div className="ai-quickreplies">
            {QUICK_REPLIES.map((q) => (
              <button key={q.text} className="ai-qr" onClick={() => sendText(q.text)}>
                <Icon name={q.icon} size={15} className="ai-qr-icon" />{q.text}
              </button>
            ))}
            <button className="ai-qr-refresh" aria-label="Refresh suggestions"><Icon name="refresh" size={16} /></button>
          </div>

          {/* "Just listen" mode banner (tap anywhere to turn off) */}
          {listenOnly && (
            <button type="button" className="ai-listen-note" onClick={toggleListen}>
              <Icon name="headphones" size={14} />
              <span>Listen-only mode — I'll just be here and listen, no advice or exercises. <b>Tap to turn it off</b> so I can suggest tips and exercises again. (If things feel harder or unsafe, I'll still step in.)</span>
            </button>
          )}

          {/* Input */}
          <div className="ai-inputbar">
            <button className="ai-attach" aria-label="Attach file"><Icon name="paperclip" size={19} /></button>
            <button
              type="button"
              className={"ai-listen-btn" + (listenOnly ? " on" : "")}
              onClick={toggleListen}
              aria-pressed={listenOnly}
              aria-label={listenOnly ? "Turn off listen-only mode" : "Turn on listen-only mode"}
              data-tip={listenOnly
                ? "Turn off to get advice & lessons"
                : "Turn on listen-only mode"}
            >
              <Icon name="headphones" size={19} />
            </button>
            <input
              ref={inputRef}
              className="ai-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKey}
              placeholder="Message MindCare AI..."
              disabled={busy}
            />
            <button className="ai-send" onClick={() => sendText()} disabled={busy || !input.trim()} aria-label="Send">
              <Icon name="send" size={18} stroke={2} />
            </button>
          </div>

          {/* Disclaimer */}
          <div className="ai-disclaimer">
            <Icon name="shield" size={14} />
            This conversation is private and for support only; it is not a substitute for professional advice.
          </div>
        </div>

      </div>

      {recDetail && <RecDetail rec={recDetail} onClose={() => setRecDetail(null)} />}
    </div>
  );
}

/* ── Read-only detail for a recommended lesson/resource (reuses lx-* CSS) ── */
function RecDetail({ rec, onClose }) {
  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const d = rec.full || {};
  const isLesson = rec.kind === "lesson";
  const objectives = d.objectives || [];

  return createPortal(
    <div className="lx-overlay" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="lx-modal" role="dialog" aria-modal="true" aria-label={d.title}>
        <button className="lx-close" onClick={onClose} aria-label="Close">✕</button>
        <div className="lx-head">
          <h2 className="lx-title">{d.title}</h2>
          <div className="lx-meta">
            {d.duration && <span>🕐 {d.duration}</span>}
            {isLesson
              ? (d.level && <span className="lx-level">{d.level}</span>)
              : (d.type && <span>{d.type}</span>)}
            {d.category && <span>{d.category}</span>}
          </div>
        </div>
        <div className="lx-body">
          {d.description && <p className="lx-desc">{d.description}</p>}
          {isLesson && objectives.length > 0 && (
            <div className="lx-objectives">
              <div className="lx-obj-head"><span>Learning objectives</span></div>
              {objectives.map((o, i) => (
                <div key={i} className="lx-obj"><span>• {o}</span></div>
              ))}
            </div>
          )}
          {d.content && (
            <div className="lx-content">
              {d.content.split("\n").map((line, i) =>
                line.trim() ? <p key={i}>{line}</p> : <br key={i} />)}
            </div>
          )}
          {!isLesson && d.url && (
            <a className="lx-link" href={d.url} target="_blank" rel="noopener noreferrer">
              {d.type === "Audio" ? "▶ Listen" : d.type === "Video" ? "▶ Watch" : "Open ↗"}
            </a>
          )}
        </div>
      </div>
    </div>,
    document.body
  );
}
