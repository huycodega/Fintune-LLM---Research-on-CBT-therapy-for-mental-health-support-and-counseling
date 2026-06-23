import { useEffect, useState } from "react";
import { api } from "../api.js";

// Mood (self-rated 1–10) → gentle emoji + colour.
const MOODS = [
  { max: 2,  emoji: "😢", color: "#ef4444" },
  { max: 4,  emoji: "😔", color: "#f97316" },
  { max: 6,  emoji: "😐", color: "#f59e0b" },
  { max: 8,  emoji: "🙂", color: "#22c55e" },
  { max: 10, emoji: "😊", color: "#16a34a" },
];
const moodMeta = (v) => MOODS.find((m) => v <= m.max) || MOODS[MOODS.length - 1];
const dayLabel = (iso) => new Date(iso).toLocaleDateString("en-GB", { weekday: "short" });

export default function MoodWidget() {
  const [days, setDays] = useState(null);   // null = loading, [] = no data
  const [open, setOpen] = useState(true);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    let alive = true;
    api.screeningHistory(40)
      .then((rows) => {
        if (!alive) return;
        // Keep the latest mood per calendar day, then the last 7 days with data.
        const byDay = {};
        (rows || []).forEach((r) => {
          if (r.mood_score == null) return;
          const key = new Date(r.created_at).toISOString().slice(0, 10);
          if (!byDay[key] || new Date(r.created_at) > new Date(byDay[key].created_at)) byDay[key] = r;
        });
        const list = Object.keys(byDay).sort().slice(-7).map((k) => ({
          date: k, mood: Number(byDay[k].mood_score), created_at: byDay[k].created_at,
        }));
        setDays(list);
      })
      .catch(() => setDays([]));
    return () => { alive = false; };
  }, []);

  // Trigger the grow-in once data is ready.
  useEffect(() => {
    if (days === null) return;
    const t = requestAnimationFrame(() => setShown(true));
    return () => cancelAnimationFrame(t);
  }, [days]);

  if (days === null) return null;   // stay invisible until we know

  const latest = days.length ? days[days.length - 1] : null;
  const latestMeta = latest ? moodMeta(latest.mood) : null;

  if (!open) {
    return (
      <button className="mood-widget-pill in" onClick={() => setOpen(true)} aria-label="Show mood trend">
        {latestMeta ? latestMeta.emoji : "🌱"}
      </button>
    );
  }

  return (
    <div className={`mood-widget ${shown ? "in" : ""}`}>
      <div className="mood-widget-head">
        <span className="mood-widget-title">Mood this week</span>
        <button className="mood-widget-min" onClick={() => setOpen(false)} aria-label="Minimize">–</button>
      </div>

      {days.length === 0 ? (
        <div className="mood-widget-empty">
          <span className="mood-widget-empty-emoji">🌱</span>
          <p>Take a screening to start tracking your mood.</p>
        </div>
      ) : (
        <>
          <div className="mood-chart">
            {days.map((d, i) => {
              const m = moodMeta(d.mood);
              return (
                <div className="mood-col" key={d.date} title={`${dayLabel(d.created_at)}: ${d.mood}/10`}>
                  <span className="mood-bar"
                        style={{
                          height: shown ? `${Math.max(8, d.mood * 10)}%` : "0%",
                          background: `linear-gradient(180deg, ${m.color}, ${m.color}aa)`,
                          transitionDelay: `${i * 80}ms`,
                        }} />
                  <small>{dayLabel(d.created_at)}</small>
                </div>
              );
            })}
          </div>
          <div className="mood-widget-foot">
            <span className="mood-foot-emoji">{latestMeta.emoji}</span>
            <span>Latest mood <b>{latest.mood}/10</b></span>
          </div>
        </>
      )}
    </div>
  );
}
