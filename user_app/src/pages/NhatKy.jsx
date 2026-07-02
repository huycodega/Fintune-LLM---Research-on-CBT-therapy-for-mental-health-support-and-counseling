import { useState, useEffect } from "react";
import { api } from "../api.js";

/* Journal — a private space. Entries are encrypted and PRIVATE BY DEFAULT;
   the user can share individual entries with their clinician (opt-in). */

const MOODS = [
  { v: 2, e: "😞" }, { v: 4, e: "😕" }, { v: 6, e: "😐" },
  { v: 8, e: "🙂" }, { v: 10, e: "😊" },
];

function fmtDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return isNaN(d) ? "" : d.toLocaleString("en-GB", {
    day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
  });
}

export default function NhatKy() {
  const [entries, setEntries] = useState(null);
  const [text, setText] = useState("");
  const [mood, setMood] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = () =>
    api.listJournal().then((r) => setEntries(r.entries || [])).catch(() => setEntries([]));
  useEffect(() => { load(); }, []);

  async function save() {
    const t = text.trim();
    if (!t || busy) return;
    setBusy(true);
    try {
      await api.createJournal({ content: t, mood: mood || undefined });
      setText(""); setMood(null);
      await load();
    } catch { /* keep the draft so nothing is lost */ }
    setBusy(false);
  }

  async function toggleShare(e) {
    try {
      await api.shareJournal(e.id, !e.shared_with_clinician);
      await load();
    } catch { /* ignore */ }
  }

  async function remove(e) {
    if (!window.confirm("Delete this entry? This really deletes it — it can't be recovered.")) return;
    try { await api.deleteJournal(e.id); await load(); } catch { /* ignore */ }
  }

  return (
    <div className="journal-page">
      <header className="journal-head">
        <h1 className="journal-page-title">Journal</h1>
        <p className="journal-page-sub">
          A space that's yours. Writing down what you feel — even a few lines —
          helps untangle it.
        </p>
        <div className="journal-privacy">
          🔒 <b>Private by default.</b> Entries are encrypted and only you can
          read them. You can choose to share an individual entry with your
          clinician using its "Share" switch.
        </div>
      </header>

      {/* Composer */}
      <section className="journal-composer">
        <textarea
          rows={4}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="How are you feeling right now? What happened today?"
        />
        <div className="journal-composer-row">
          <div className="journal-moods">
            <span className="journal-moods-label">Mood:</span>
            {MOODS.map((m) => (
              <button key={m.v}
                className={"journal-mood" + (mood === m.v ? " on" : "")}
                onClick={() => setMood(mood === m.v ? null : m.v)}
                aria-label={`Mood ${m.v}/10`}>{m.e}</button>
            ))}
          </div>
          <button className="journal-save" onClick={save} disabled={busy || !text.trim()}>
            {busy ? "Saving…" : "Save entry"}
          </button>
        </div>
      </section>

      {/* Entries */}
      {entries === null ? (
        <p className="journal-empty">Loading…</p>
      ) : entries.length === 0 ? (
        <p className="journal-empty">
          No entries yet. Your first note can be a single sentence — that's enough.
        </p>
      ) : (
        <div className="journal-entries">
          {entries.map((e) => (
            <article className="journal-entry" key={e.id}>
              <div className="journal-entry-top">
                <span className="journal-entry-date">
                  {fmtDate(e.created_at)}
                  {e.mood ? <span className="journal-entry-mood"> · {MOODS.find((m) => m.v === e.mood)?.e || ""} {e.mood}/10</span> : null}
                </span>
                <div className="journal-entry-actions">
                  <label className="journal-share" title="Let your clinician read this entry">
                    <input type="checkbox" checked={e.shared_with_clinician}
                      onChange={() => toggleShare(e)} />
                    <span>{e.shared_with_clinician ? "Shared with clinician" : "Share"}</span>
                  </label>
                  <button className="journal-del" onClick={() => remove(e)} aria-label="Delete entry">✕</button>
                </div>
              </div>
              <p className="journal-entry-text">{e.content}</p>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
