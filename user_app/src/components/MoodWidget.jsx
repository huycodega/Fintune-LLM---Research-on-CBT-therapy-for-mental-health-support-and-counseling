import { useEffect, useState } from "react";
import { api } from "../api.js";

// Geometry of the mini line chart (viewBox units).
const W = 240, H = 104, PT = 12, PB = 20, PL = 6, PR = 6;
const innerW = W - PL - PR, innerH = H - PT - PB;

const TREND = {
  up:     { emoji: "📈", text: "Improving", color: "#16a34a" },
  down:   { emoji: "📉", text: "Needs care", color: "#ef4444" },
  stable: { emoji: "➖", text: "Steady",     color: "#64748b" },
};

export default function MoodWidget() {
  const [data, setData] = useState(null);   // null = loading
  const [open, setOpen] = useState(true);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    let alive = true;
    api.emotionalTrend(30)
      .then((d) => { if (alive) setData(d || { points: [] }); })
      .catch(() => setData({ points: [] }));
    return () => { alive = false; };
  }, []);

  useEffect(() => {
    if (data === null) return;
    const t = requestAnimationFrame(() => setShown(true));
    return () => cancelAnimationFrame(t);
  }, [data]);

  if (data === null) return null;
  const points = data.points || [];
  const trend = TREND[data.direction] || TREND.stable;

  if (!open) {
    return (
      <button className="mood-widget-pill in" onClick={() => setOpen(true)} aria-label="Show emotional trend">
        {points.length ? trend.emoji : "🌱"}
      </button>
    );
  }

  const n = points.length;
  const x = (i) => (n <= 1 ? PL + innerW / 2 : PL + (i / (n - 1)) * innerW);
  const y = (s) => PT + (1 - Math.max(0, Math.min(100, s)) / 100) * innerH;
  const line = points.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(p.score).toFixed(1)}`).join(" ");
  const area = n ? `${line} L${x(n - 1).toFixed(1)} ${(PT + innerH).toFixed(1)} L${x(0).toFixed(1)} ${(PT + innerH).toFixed(1)} Z` : "";
  const fmt = (ts) => new Date(ts).toLocaleDateString("en-GB", { day: "2-digit", month: "short" });

  return (
    <div className={`mood-widget ${shown ? "in" : ""}`}>
      <div className="mood-widget-head">
        <span className="mood-widget-title">Emotional trend</span>
        <button className="mood-widget-min" onClick={() => setOpen(false)} aria-label="Minimize">–</button>
      </div>

      {n === 0 ? (
        <div className="mood-widget-empty">
          <span className="mood-widget-empty-emoji">🌱</span>
          <p>Chat or take a screening to start your trend.</p>
        </div>
      ) : (
        <>
          <svg className="mood-svg" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Emotional trend">
            <defs>
              <linearGradient id="moodArea" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#34d399" stopOpacity="0.32" />
                <stop offset="100%" stopColor="#34d399" stopOpacity="0" />
              </linearGradient>
            </defs>
            {/* grid */}
            {[0, 25, 50, 75, 100].map((g) => (
              <line key={g} className="mood-grid" x1={PL} x2={W - PR} y1={y(g)} y2={y(g)} />
            ))}
            {area && <path className={`mood-area ${shown ? "in" : ""}`} d={area} fill="url(#moodArea)" />}
            <path className={`mood-line ${shown ? "in" : ""}`} d={line} pathLength="1" fill="none" />
            {points.map((p, i) => (
              <circle key={i} className={`mood-dot ${p.source} ${shown ? "in" : ""}`}
                      cx={x(i)} cy={y(p.score)} r="3.1"
                      style={{ transitionDelay: `${0.55 + i * 0.045}s` }}>
                <title>{`${fmt(p.ts)} · ${p.source} · ${p.score}/100`}</title>
              </circle>
            ))}
          </svg>

          <div className="mood-widget-foot">
            <span className="mood-trend-pill" style={{ color: trend.color }}>
              {trend.emoji} {trend.text}{data.change ? ` ${data.change > 0 ? "+" : ""}${data.change}` : ""}
            </span>
            <span className="mood-legend">
              <i className="mood-legend-dot chat" /> Chat
              <i className="mood-legend-dot screening" /> Screening
            </span>
          </div>
        </>
      )}
    </div>
  );
}
