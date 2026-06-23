import { createPortal } from "react-dom";
import { RiskBadge, ScreeningStatusBadge } from "./ScreeningBadges.jsx";
import { fmtDateTime } from "../../ui.jsx";

const BARS = [
  ["Depression (PHQ-9)", "depression", 27],
  ["Anxiety (GAD-7)", "anxiety", 21],
  ["Mood (self-rated)", "mood", 10],
];

export default function ScreeningDetailDrawer({ open, detail, loading, onClose, onAddNote }) {
  if (!open) return null;
  const u = detail?.user || {};
  return createPortal(
    <>
      <button className="sm-drawer-scrim" onClick={onClose} aria-label="Close detail" />
      <aside className="sm-drawer">
        <div className="sm-drawer-head">
          <div>
            <div className="eyebrow">SCREENING DETAIL</div>
            <h2>{detail?.assessment_type || "Screening"}</h2>
          </div>
          <button className="sm-ghost-btn" onClick={onClose}>×</button>
        </div>

        {loading ? (
          <div className="sm-drawer-scroll"><p className="sm-page-info">Loading details…</p></div>
        ) : !detail ? (
          <div className="sm-drawer-scroll"><p className="sm-page-info">Screening not found.</p></div>
        ) : (
          <div className="sm-drawer-scroll">
            <section className="sm-drawer-section sm-user-info">
              <div className="sm-user-info-avatar">{(u.full_name || "U").slice(0, 1).toUpperCase()}</div>
              <div>
                <div className="sm-user-info-name">{u.full_name || "User"}</div>
                <div className="sm-user-info-sub">
                  {[u.email, u.age ? `${u.age} yrs` : null, u.gender].filter(Boolean).join(" · ") || "—"}
                </div>
              </div>
            </section>

            <section className="sm-drawer-section">
              <div className="sm-info-grid">
                <span>Date</span><strong>{fmtDateTime(detail.screening_date)}</strong>
                <span>Type</span><strong>{detail.assessment_type}</strong>
                <span>Score</span><strong>{detail.score}</strong>
                <span>Risk</span><strong><RiskBadge value={detail.risk_level} /></strong>
                <span>Status</span><strong><ScreeningStatusBadge value={detail.status} /></strong>
              </div>
            </section>

            {detail.ai_assessment && (
              <section className="sm-drawer-section sm-ai-summary">
                <h3>AI assessment</h3>
                <p><b>{detail.ai_assessment.risk_summary}</b></p>
                <div className="sm-emotion-tags">
                  {(detail.ai_assessment.emotions || []).map((e) => (
                    <span key={e} className="sm-emotion-tag">{e}</span>
                  ))}
                </div>
                <p>{detail.ai_assessment.recommendation}</p>
              </section>
            )}

            {detail.breakdown && (
              <section className="sm-drawer-section sm-breakdown">
                <h3>Score breakdown</h3>
                {BARS.map(([label, key, max]) => {
                  const val = Number(detail.breakdown[key] || 0);
                  return (
                    <div key={key} className="sm-breakdown-item">
                      <span>{label}</span>
                      <div className="sm-breakdown-bar"><i style={{ width: `${Math.min(100, (val / max) * 100)}%` }} /></div>
                      <b>{val}</b>
                    </div>
                  );
                })}
              </section>
            )}

            {(detail.answers || []).length > 0 && (
              <section className="sm-drawer-section">
                <h3>Answers / notes</h3>
                {detail.answers.map((a, i) => (
                  <div key={i} className="sm-answer-item"><span>{a.question}</span><b>{a.answer}</b></div>
                ))}
              </section>
            )}

            {(detail.notes || []).length > 0 && (
              <section className="sm-drawer-section">
                <h3>Clinician notes</h3>
                {detail.notes.map((n, i) => (
                  <div key={i} className="sm-note-item">
                    <div className="sm-note-meta">
                      <b>{n.author || "clinician"}</b>
                      <span>{fmtDateTime(n.created_at)}</span>
                    </div>
                    <p>{n.content}</p>
                  </div>
                ))}
              </section>
            )}

            <div className="sm-drawer-actions">
              <button type="button" className="sm-primary-btn" onClick={onAddNote}>＋ Add note</button>
            </div>
          </div>
        )}
      </aside>
    </>,
    document.body
  );
}
