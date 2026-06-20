import { useState, useEffect, useRef } from "react";
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
function MsgText({ text }) {
  return text.split("\n\n").map((para, i) => (
    <p key={i} className="ai-p">
      {para.split("\n").map((line, j) => (
        <span key={j}>{j > 0 && <br />}{line}</span>
      ))}
    </p>
  ));
}

/* ── Chat bubble ───────────────────────────────────────────────── */
function ChatBubble({ msg }) {
  const isAI = msg.role === "ai";
  return (
    <div className={`ai-row ${isAI ? "ai" : "user"}`}>
      {isAI && (
        <div className="ai-avatar"><Mascot variant="chat" size={30} className="mascot-idle" /></div>
      )}
      <div className="ai-msg">
        <div className={`ai-bubble ${isAI ? "ai-bubble-ai" : "ai-bubble-user"} ${msg.error ? "ai-bubble-error" : ""}`}>
          <MsgText text={msg.text} />
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
        </div>
        <div className="ai-meta">
          <span>{msg.time}</span>
          {!isAI && msg.read && <ReadCheck />}
        </div>
      </div>
    </div>
  );
}

function TypingBubble() {
  return (
    <div className="ai-row ai">
      <div className="ai-avatar"><Mascot variant="chat" size={30} className="mascot-idle" /></div>
      <div className="ai-bubble ai-bubble-ai ai-thinking">
        <span className="ai-thinking-label">MindCare is thinking</span>
        <span className="ai-typing"><span /><span /><span /></span>
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
export default function Chat() {
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [messages, setMessages] = useState(WELCOME);
  const [activeId, setActiveId] = useState(null);
  const [conversations, setConversations] = useState([]);
  const bottomRef = useRef(null);
  const inputRef = useRef(null);
  const pollRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => () => clearInterval(pollRef.current), []);

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
    setMessages(WELCOME);
    setActiveId(null);
    inputRef.current?.focus();
  }

  function startPolling(sid, idx) {
    clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const s = await api.mySession(sid);
        if (s.status === "answered" || s.status === "rejected") {
          clearInterval(pollRef.current);
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
        }
      } catch {}
    }, 4000);
  }

  async function sendText(raw) {
    const text = (raw ?? input).trim();
    if (!text || busy) return;

    const aiIdx = messages.length + 1;
    setMessages((prev) => [...prev, { role: "user", time: nowTime(), read: true, text }, { role: "ai", typing: true }]);
    setInput("");
    setBusy(true);

    try {
      const r = await api.chat(text, activeId ? { conversation_id: activeId } : {});
      const wasNew = r.conversation_id && r.conversation_id !== activeId;
      if (wasNew) setActiveId(r.conversation_id);

      let replyText;
      let crisis = false;
      // crisis_resources is sent for both L0 (crisis) and L1 (pending_review)
      // so the user always has a real-person lifeline to reach for.
      let resources = r.crisis_resources || null;
      if (r.outcome === "answered") {
        replyText = r.final?.response || "I'm here with you.";
        resources = null;
      } else if (r.outcome === "crisis") {
        replyText = r.message || "I'm really glad you reached out. Your safety matters most right now.";
        crisis = true;
      } else if (r.outcome === "pending_review") {
        replyText = r.message || "Thank you for sharing. A clinician is reviewing your message and will respond shortly.";
      } else {
        replyText = r.message || "I'm here with you.";
        resources = null;
      }

      setMessages((prev) => {
        const next = [...prev];
        next[aiIdx] = { role: "ai", time: nowTime(), text: replyText, crisis, resources };
        return next;
      });

      if (r.outcome === "pending_review" && r.session_id) startPolling(r.session_id, aiIdx);
      // Refresh the sidebar so a newly-created thread appears (and titles update).
      loadConversations();
    } catch {
      setMessages((prev) => {
        const next = [...prev];
        next[aiIdx] = { role: "ai", time: nowTime(), error: true, text: "Sorry, I couldn't reach the server. Please try again in a moment." };
        return next;
      });
    } finally {
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
    <div className="ai-page">
      <div className="ai-grid">
        {/* ── CENTER: chat ── */}
        <div className="ai-main">
          {/* Header */}
          <header className="ai-header">
            <div className="ai-header-text">
              <h1 className="ai-title">AI Support</h1>
              <p className="ai-subtitle">
                Chat with MindCare AI to share, work through your emotions, and find the right
                solutions for you.
              </p>
            </div>
            <div className="ai-header-mascot"><Mascot variant="wave" size={138} /></div>
          </header>

          {/* Topic chips */}
          <div className="ai-topicbar">
            <span className="ai-topic-label">You can start with common topics</span>
            {TOPICS.map((t) => (
              <button key={t.label} className="ai-chip" onClick={() => sendText(t.text)}>
                <span className="ai-chip-emoji">{t.emoji}</span>{t.label}
              </button>
            ))}
            <button className="ai-chip-more" aria-label="More topics"><Icon name="chevron" size={16} /></button>
          </div>

          {/* Feed */}
          <div className="ai-feed">
            {!messages.some((m) => m.role === "user") && messages.length <= 1 ? (
              <EmptyState greeting={messages[0]?.text || WELCOME[0].text} />
            ) : (
              messages.map((m, i) => (m.typing ? <TypingBubble key={i} /> : <ChatBubble key={i} msg={m} />))
            )}
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

          {/* Input */}
          <div className="ai-inputbar">
            <button className="ai-attach" aria-label="Attach file"><Icon name="paperclip" size={19} /></button>
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

        {/* ── RIGHT: panel ── */}
        <RightPanel
          onUseTip={(t) => sendText(t)}
          conversations={conversations}
          activeId={activeId}
          onOpen={openConversation}
          onNew={newChat}
        />
      </div>
    </div>
  );
}
