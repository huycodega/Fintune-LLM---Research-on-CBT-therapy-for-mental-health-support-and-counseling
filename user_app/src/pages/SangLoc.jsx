import { useState, useEffect, useRef } from "react";
import { api } from "../api.js";
import MascotCard from "../components/MascotCard.jsx";
import PageHero from "../components/PageHero.jsx";

const PHQ9_QUESTIONS = [
  "Little interest or pleasure in doing things?",
  "Feeling down, depressed, or hopeless?",
  "Trouble falling or staying asleep, or sleeping too much?",
  "Feeling tired or having little energy?",
  "Poor appetite or overeating?",
  "Feeling bad about yourself — or that you are a failure or have let yourself or your family down?",
  "Trouble concentrating on things, such as reading or watching TV?",
  "Moving or speaking so slowly that other people could have noticed? Or the opposite — being so fidgety or restless that you have been moving around a lot more than usual?",
  "Thoughts that you would be better off dead, or of hurting yourself in some way?",
];

const OPTIONS = [
  { label: "Not at all",            value: 0, sub: "0 days" },
  { label: "Several days",          value: 1, sub: "1–6 days" },
  { label: "More than half the days", value: 2, sub: "7–11 days" },
  { label: "Nearly every day",      value: 3, sub: "12–14 days" },
];

const GAD7_QUESTIONS = [
  "Feeling nervous, anxious, or on edge?",
  "Not being able to stop or control worrying?",
  "Worrying too much about different things?",
  "Trouble relaxing?",
  "Being so restless that it is hard to sit still?",
  "Becoming easily annoyed or irritable?",
  "Feeling afraid, as if something awful might happen?",
];

const STEP_LABELS = ["PHQ-9", "GAD-7", "Mood", "Summary"];

function getLevel(score, max) {
  const pct = score / max;
  if (pct < 0.2) return { label: "Normal",            color: "var(--success)", badge: "badge-green" };
  if (pct < 0.4) return { label: "Mild",              color: "var(--warn)",    badge: "badge-yellow" };
  if (pct < 0.6) return { label: "Moderate",          color: "var(--warn)",    badge: "badge-yellow" };
  if (pct < 0.8) return { label: "Moderately Severe", color: "var(--danger)",  badge: "badge-red" };
  return           { label: "Severe",                  color: "var(--danger)",  badge: "badge-red" };
}

export default function SangLoc() {
  const [step, setStep] = useState(0);
  const [phq9, setPhq9] = useState(Array(9).fill(null));
  const [gad7, setGad7] = useState(Array(7).fill(null));
  const [mood, setMood] = useState(5);
  const [done, setDone] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [rec, setRec] = useState(null);   // today's personalised recommendation
  const [recStarted, setRecStarted] = useState(false);
  const stepsRef = useRef(null);

  // Jump into the recommended instrument. PHQ-9 is already step 0, so without
  // this the click looked like a no-op — we dismiss the card and scroll the
  // questionnaire into view so it's clear the check-in has begun.
  function startRecommended() {
    setStep(rec?.instrument === "gad7" ? 1 : 0);
    setRecStarted(true);
    setTimeout(() => stepsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
  }

  // Memory/context-aware suggestion of which check-in to focus on today.
  useEffect(() => {
    let alive = true;
    api.screeningToday().then((r) => { if (alive) setRec(r); }).catch(() => {});
    return () => { alive = false; };
  }, []);

  const phq9Score = phq9.reduce((a, v) => a + (v ?? 0), 0);
  const gad7Score = gad7.reduce((a, v) => a + (v ?? 0), 0);
  const phq9Level = getLevel(phq9Score, 27);
  const gad7Level = getLevel(gad7Score, 21);

  const canNextPhq9 = phq9.every((v) => v !== null);
  const canNextGad7 = gad7.every((v) => v !== null);

  function renderQuestionBlock(questions, answers, setAnswers) {
    return (
      <div>
        <div className="question-sub">Over the past 2 weeks, how often have you been bothered by any of the following?</div>
        {questions.map((q, i) => (
          <div key={i} className="question-card card" style={{ marginBottom: 12 }}>
            <div className="question-text">
              <span style={{ color: "var(--ink-soft)", marginRight: 8, fontSize: 13 }}>Q{i + 1}.</span>
              {q}
            </div>
            <div className="option-list" style={{ marginTop: 10 }}>
              {OPTIONS.map((opt) => (
                <label
                  key={opt.value}
                  className={`option-radio ${answers[i] === opt.value ? "selected" : ""}`}
                  onClick={() => {
                    const next = [...answers];
                    next[i] = opt.value;
                    setAnswers(next);
                  }}
                >
                  <div className="radio-circle">
                    {answers[i] === opt.value && <div className="radio-dot" />}
                  </div>
                  <div>
                    <div className="option-label">{opt.label}</div>
                    <div className="option-sublabel">{opt.sub}</div>
                  </div>
                </label>
              ))}
            </div>
          </div>
        ))}
      </div>
    );
  }

  const ScorePanel = () => (
    <div>
      {step >= 1 && (
        <div className="card card-sm" style={{ marginBottom: 12 }}>
          <div className="score-display">
            <div style={{ fontSize: 12, fontWeight: 600, color: "var(--ink-soft)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>
              PHQ-9 — Depression
            </div>
            <div className="score-number">{phq9Score}</div>
            <div className="score-unit">/ 27 pts</div>
            <div className="progress-bar" style={{ margin: "12px 0 8px" }}>
              <div className="progress-fill" style={{ width: `${(phq9Score / 27) * 100}%`, background: phq9Level.color }} />
            </div>
            <div className={`badge ${phq9Level.badge}`} style={{ display: "inline-flex" }}>{phq9Level.label}</div>
          </div>
        </div>
      )}
      {step >= 2 && (
        <div className="card card-sm" style={{ marginBottom: 12 }}>
          <div className="score-display">
            <div style={{ fontSize: 12, fontWeight: 600, color: "var(--ink-soft)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>
              GAD-7 — Anxiety
            </div>
            <div className="score-number">{gad7Score}</div>
            <div className="score-unit">/ 21 pts</div>
            <div className="progress-bar" style={{ margin: "12px 0 8px" }}>
              <div className="progress-fill" style={{ width: `${(gad7Score / 21) * 100}%`, background: gad7Level.color }} />
            </div>
            <div className={`badge ${gad7Level.badge}`} style={{ display: "inline-flex" }}>{gad7Level.label}</div>
          </div>
        </div>
      )}
      {step >= 3 && (
        <div className="card card-sm">
          <div style={{ fontSize: 12, fontWeight: 600, color: "var(--ink-soft)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>
            Overall Mood
          </div>
          <div style={{ textAlign: "center", fontSize: 32, marginBottom: 4 }}>
            {mood <= 2 ? "😢" : mood <= 4 ? "😔" : mood <= 6 ? "😐" : mood <= 8 ? "🙂" : "😊"}
          </div>
          <div style={{ textAlign: "center", fontSize: 13, color: "var(--ink-soft)" }}>{mood}/10</div>
        </div>
      )}
    </div>
  );

  if (done) {
    return (
      <div style={{ maxWidth: 700, margin: "0 auto" }}>
        <div className="card" style={{ textAlign: "center", padding: 40 }}>
          <div style={{ fontSize: 56, marginBottom: 16 }}>✅</div>
          <h2 style={{ fontSize: 22, fontWeight: 700, marginBottom: 8 }}>Thank you for completing the screening!</h2>
          <p style={{ color: "var(--ink-soft)", marginBottom: 24 }}>
            Your results have been saved. Share them with AI Support to receive personalized suggestions.
          </p>
          {submitError && (
            <div className="banner warn" style={{ marginBottom: 16, textAlign: "left" }}>
              ⚠️ Could not save to server: {submitError}. Results are still shown below.
            </div>
          )}
          <div style={{ display: "flex", gap: 16, justifyContent: "center", flexWrap: "wrap", marginBottom: 24 }}>
            <div className="card card-sm" style={{ minWidth: 140, textAlign: "center" }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: "var(--ink-soft)", textTransform: "uppercase", marginBottom: 6 }}>PHQ-9</div>
              <div style={{ fontSize: 28, fontWeight: 700, color: phq9Level.color }}>{phq9Score}</div>
              <div className={`badge ${phq9Level.badge}`} style={{ marginTop: 6 }}>{phq9Level.label}</div>
            </div>
            <div className="card card-sm" style={{ minWidth: 140, textAlign: "center" }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: "var(--ink-soft)", textTransform: "uppercase", marginBottom: 6 }}>GAD-7</div>
              <div style={{ fontSize: 28, fontWeight: 700, color: gad7Level.color }}>{gad7Score}</div>
              <div className={`badge ${gad7Level.badge}`} style={{ marginTop: 6 }}>{gad7Level.label}</div>
            </div>
            <div className="card card-sm" style={{ minWidth: 140, textAlign: "center" }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: "var(--ink-soft)", textTransform: "uppercase", marginBottom: 6 }}>Mood</div>
              <div style={{ fontSize: 28 }}>{mood <= 4 ? "😔" : mood <= 6 ? "😐" : "🙂"}</div>
              <div style={{ fontSize: 13, color: "var(--ink-soft)", marginTop: 4 }}>{mood}/10</div>
            </div>
          </div>
          {(phq9Score >= 10 || gad7Score >= 10) && (
            <div className="banner warn" style={{ marginBottom: 16, textAlign: "left" }}>
              ⚠️ Your scores suggest you may be experiencing some difficulties. Consider chatting with AI Support or speaking with a professional.
            </div>
          )}
          <div style={{ display: "flex", gap: 10, justifyContent: "center" }}>
            <button
              className="btn btn-primary btn-lg"
              onClick={() => {
                setDone(false);
                setStep(0);
                setPhq9(Array(9).fill(null));
                setGad7(Array(7).fill(null));
                setMood(5);
                setSubmitError(null);
              }}
            >
              Retake
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <>
      <PageHero
        title="Mental Health Screening"
        subtitle="A few quick, confidential questions help us understand how you're doing and tailor the right support for you."
        mascot="screening"
      />
      <div className="screening-layout">
      {/* Left: questions */}
      <div>
        {rec && !recStarted && (
          <div className="screening-rec card" style={{ marginBottom: 20 }}>
            <div className="screening-rec-label">✨ Recommended for you today</div>
            <div className="screening-rec-title">{rec.title}</div>
            <p className="screening-rec-intro">{rec.intro}</p>
            <p className="screening-rec-reason">{rec.reason}</p>
            <div className="screening-rec-actions">
              <button className="btn btn-primary" onClick={startRecommended}>
                Start {rec.instrument === "gad7" ? "GAD-7" : "PHQ-9"} →
              </button>
              {rec.done_today && <span className="screening-rec-done">✓ You already checked in today</span>}
            </div>
          </div>
        )}
        <div className="screening-steps" ref={stepsRef} style={{ marginBottom: 24, scrollMarginTop: 16 }}>
          {STEP_LABELS.map((label, i) => (
            <div key={i} className={`step-item ${i === step ? "active" : i < step ? "done" : ""}`}>
              <div className="step-circle">
                {i < step ? "✓" : i + 1}
              </div>
              <div className="step-label">{label}</div>
            </div>
          ))}
        </div>

        {step === 0 && (
          <div>
            <div className="card" style={{ marginBottom: 20 }}>
              <div className="eyebrow">PHQ-9 Questionnaire</div>
              <div className="question-text" style={{ fontSize: 18, marginBottom: 4 }}>Depression Assessment</div>
              <div className="question-sub">Please answer all 9 questions as honestly as possible.</div>
            </div>
            {renderQuestionBlock(PHQ9_QUESTIONS, phq9, setPhq9)}
          </div>
        )}

        {step === 1 && (
          <div>
            <div className="card" style={{ marginBottom: 20 }}>
              <div className="eyebrow">GAD-7 Questionnaire</div>
              <div className="question-text" style={{ fontSize: 18, marginBottom: 4 }}>Anxiety Assessment</div>
              <div className="question-sub">Please answer all 7 questions below.</div>
            </div>
            {renderQuestionBlock(GAD7_QUESTIONS, gad7, setGad7)}
          </div>
        )}

        {step === 2 && (
          <div className="card">
            <div className="eyebrow">Overall Mood</div>
            <div className="question-text" style={{ fontSize: 18, marginBottom: 8 }}>
              How would you rate your overall mood today?
            </div>
            <div className="question-sub">Drag the slider to rate from 1 (very bad) to 10 (very good).</div>
            <div className="mood-slider-wrap" style={{ padding: "20px 0" }}>
              <div style={{ textAlign: "center", fontSize: 48, marginBottom: 12 }}>
                {mood <= 2 ? "😢" : mood <= 4 ? "😔" : mood <= 6 ? "😐" : mood <= 8 ? "🙂" : "😊"}
              </div>
              <input
                type="range"
                min={1} max={10}
                value={mood}
                onChange={(e) => setMood(Number(e.target.value))}
                className="mood-slider"
              />
              <div className="mood-labels">
                <span>😢 Very bad</span>
                <span style={{ fontWeight: 600, color: "var(--ink)", fontSize: 14 }}>{mood}/10</span>
                <span>😊 Very good</span>
              </div>
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="card">
            <div className="eyebrow">Summary</div>
            <div className="question-text" style={{ fontSize: 18, marginBottom: 16 }}>
              Review your screening results
            </div>
            <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
              <div style={{ flex: 1, minWidth: 120, textAlign: "center", padding: "16px", background: "var(--bg)", borderRadius: 12 }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: "var(--ink-soft)", textTransform: "uppercase", marginBottom: 6 }}>PHQ-9</div>
                <div style={{ fontSize: 32, fontWeight: 700, color: phq9Level.color }}>{phq9Score}<span style={{ fontSize: 14, color: "var(--ink-soft)", fontWeight: 400 }}>/27</span></div>
                <div className={`badge ${phq9Level.badge}`} style={{ marginTop: 8 }}>{phq9Level.label}</div>
              </div>
              <div style={{ flex: 1, minWidth: 120, textAlign: "center", padding: "16px", background: "var(--bg)", borderRadius: 12 }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: "var(--ink-soft)", textTransform: "uppercase", marginBottom: 6 }}>GAD-7</div>
                <div style={{ fontSize: 32, fontWeight: 700, color: gad7Level.color }}>{gad7Score}<span style={{ fontSize: 14, color: "var(--ink-soft)", fontWeight: 400 }}>/21</span></div>
                <div className={`badge ${gad7Level.badge}`} style={{ marginTop: 8 }}>{gad7Level.label}</div>
              </div>
              <div style={{ flex: 1, minWidth: 120, textAlign: "center", padding: "16px", background: "var(--bg)", borderRadius: 12 }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: "var(--ink-soft)", textTransform: "uppercase", marginBottom: 6 }}>Mood</div>
                <div style={{ fontSize: 32 }}>{mood <= 4 ? "😔" : mood <= 6 ? "😐" : "🙂"}</div>
                <div style={{ fontSize: 13, color: "var(--ink-soft)", marginTop: 4 }}>{mood}/10</div>
              </div>
            </div>
            {(phq9Score >= 10 || gad7Score >= 10) && (
              <div className="banner warn" style={{ marginTop: 16 }}>
                ⚠️ Your scores suggest you may benefit from additional support. Please chat with AI Support or consult a counselor.
              </div>
            )}
            {phq9Score < 10 && gad7Score < 10 && (
              <div className="banner ok" style={{ marginTop: 16 }}>
                ✅ Your results are within a normal range. Keep up your mental wellness habits!
              </div>
            )}
          </div>
        )}

        <div className="screening-nav">
          {step > 0 ? (
            <button className="btn btn-ghost" onClick={() => setStep(step - 1)}>← Back</button>
          ) : <div />}
          {step < 3 ? (
            <button
              className="btn btn-primary"
              disabled={
                (step === 0 && !canNextPhq9) ||
                (step === 1 && !canNextGad7)
              }
              onClick={() => setStep(step + 1)}
            >
              Continue →
            </button>
          ) : (
            <button
              className="btn btn-primary"
              disabled={submitting}
              onClick={async () => {
                setSubmitting(true);
                setSubmitError(null);
                try {
                  await api.submitScreening({
                    phq9_answers: phq9,
                    gad7_answers: gad7,
                    mood_score: mood,
                  });
                } catch (e) {
                  setSubmitError(e.message);
                } finally {
                  setSubmitting(false);
                  setDone(true);
                }
              }}
            >
              {submitting ? "Saving..." : "✅ Complete"}
            </button>
          )}
        </div>
      </div>

      {/* Right: score panel */}
      <div>
        <div className="card card-sm" style={{ position: "sticky", top: 0 }}>
          <div className="section-title" style={{ marginBottom: 12 }}>📊 Current Results</div>
          <ScorePanel />
          {step < 1 && (
            <div style={{ textAlign: "center", color: "var(--ink-soft)", fontSize: 12, padding: "20px 0" }}>
              Complete each step to see your results
            </div>
          )}
        </div>

        <MascotCard
          variant="screening"
          title="You're very brave! 💚"
          text="Taking the time to assess your mental health is the first important step on your journey of self-care."
          size={72}
        />

        <div className="card card-sm" style={{ marginTop: 14 }}>
          <div className="section-title" style={{ marginBottom: 10 }}>ℹ️ PHQ-9 Score Guide</div>
          {[
            { range: "0–4",   label: "Normal",            color: "var(--success)" },
            { range: "5–9",   label: "Mild",              color: "var(--warn)" },
            { range: "10–14", label: "Moderate",          color: "var(--warn)" },
            { range: "15–19", label: "Moderately Severe", color: "var(--danger)" },
            { range: "20–27", label: "Severe",            color: "var(--danger)" },
          ].map((r) => (
            <div key={r.range} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: "1px solid var(--line)", fontSize: 12 }}>
              <span style={{ color: "var(--ink-soft)" }}>{r.range} pts</span>
              <span style={{ fontWeight: 600, color: r.color }}>{r.label}</span>
            </div>
          ))}
        </div>
      </div>
      </div>
    </>
  );
}
