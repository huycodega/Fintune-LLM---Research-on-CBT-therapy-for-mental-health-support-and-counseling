import { useState } from "react";
import { api } from "../api.js";

/* Structured intake — every field is optional. New users can skip the whole
   thing and start chatting; the AI builds context from conversation instead,
   and they can fill this in later from Profile. */

const EMPTY = {
  name: "", age: "", gender: "", occupation: "",
  presenting: "", reason: "", past_history: "",
  functioning_study: "", functioning_relationships: "", functioning_daily: "",
  social_support: "",
};

const BROOKE = {
  name: "Brooke Davis", age: "41", gender: "female",
  occupation: "Veterinary Assistant",
  presenting: "I feel anxious and avoid going back to the animal shelter because I believe the animals there will hate me for not remembering me. This leads to feelings of guilt and self-blame. These feelings started a few months ago after a visit where some animals did not greet me as warmly as before.",
  reason: "This issue has started affecting my daily life and my passion for working with animals.",
  past_history: "I have not experienced similar problems before. No prior counseling and no significant physical illnesses.",
  functioning_study: "My job performance has not been affected yet, but my passion for working with animals has dwindled.",
  functioning_relationships: "My relationships with other shelter volunteers have been strained as I have distanced myself.",
  functioning_daily: "My anxiety about going to the shelter has disrupted my sleep patterns and overall well-being.",
  social_support: "A few close friends are supportive, but they do not fully understand the extent of my anxiety.",
};

function Field({ label, hint, value, onChange, rows = 3, type }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <label style={{ display: "block", marginBottom: 4 }}>
        {label} <span style={{ color: "var(--ink-soft,#94a3b8)", fontWeight: 400, fontSize: 12.5 }}>· optional</span>
      </label>
      {rows === 1 ? (
        <input type={type || "text"} value={value} placeholder={hint}
          onChange={(e) => onChange(e.target.value)} style={{ width: "100%" }} />
      ) : (
        <textarea rows={rows} value={value} placeholder={hint}
          onChange={(e) => onChange(e.target.value)} style={{ width: "100%" }} />
      )}
    </div>
  );
}

export default function Intake({ onDone }) {
  const [f, setF] = useState(EMPTY);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const set = (k) => (v) => setF((s) => ({ ...s, [k]: v }));

  async function submit(fields) {
    setBusy(true);
    setErr("");
    try {
      const body = {};
      for (const [k, v] of Object.entries(fields)) {
        const t = String(v || "").trim();
        if (!t) continue;
        body[k] = k === "age" ? parseInt(t, 10) || undefined : t;
      }
      await api.submitIntakeStructured(body);
      onDone();
    } catch (e) {
      setErr(e.message || "Could not save — please try again.");
      setBusy(false);
    }
  }

  return (
    <div className="shell" style={{ paddingTop: 30, paddingBottom: 60 }}>
      <div className="eyebrow">Getting to know you · everything is optional</div>
      <h1 className="title">Tell us about yourself</h1>
      <p className="sub">
        Share as much or as little as you like — every field is optional, and
        you can <b>skip this entirely</b> and start chatting right away. The
        more you share, the more personal the support; anything you skip, the
        AI will gently learn through conversation instead.
      </p>

      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <b>1 · About you</b>
          <button className="btn ghost sm" type="button" onClick={() => setF(BROOKE)}>
            Load sample (Brooke Davis)
          </button>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "0 12px" }}>
          <Field label="Name" hint="What should we call you?" rows={1} value={f.name} onChange={set("name")} />
          <Field label="Age" hint="e.g. 21" rows={1} type="number" value={f.age} onChange={set("age")} />
          <Field label="Gender" hint="However you identify" rows={1} value={f.gender} onChange={set("gender")} />
          <Field label="Occupation" hint="e.g. student" rows={1} value={f.occupation} onChange={set("occupation")} />
        </div>

        <b style={{ display: "block", margin: "10px 0 12px" }}>2 · What's been on your mind?</b>
        <Field label="Presenting concern" value={f.presenting} onChange={set("presenting")}
          hint="What's been troubling you, and in which situations does it show up?" />

        <b style={{ display: "block", margin: "10px 0 12px" }}>3 · Why now?</b>
        <Field label="Reason for reaching out" rows={2} value={f.reason} onChange={set("reason")}
          hint="What made you decide to seek support now?" />

        <b style={{ display: "block", margin: "10px 0 12px" }}>4 · Past history</b>
        <Field label="Anything similar before?" rows={2} value={f.past_history} onChange={set("past_history")}
          hint="Prior counseling, similar issues, or relevant medical history" />

        <b style={{ display: "block", margin: "10px 0 12px" }}>5 · How it's affecting you</b>
        <Field label="Study / work" rows={2} value={f.functioning_study} onChange={set("functioning_study")}
          hint="Any impact on school or your job?" />
        <Field label="Relationships" rows={2} value={f.functioning_relationships} onChange={set("functioning_relationships")}
          hint="Any impact on friends, family, colleagues?" />
        <Field label="Daily life" rows={2} value={f.functioning_daily} onChange={set("functioning_daily")}
          hint="Sleep, energy, appetite, daily routine…" />

        <b style={{ display: "block", margin: "10px 0 12px" }}>6 · Support around you</b>
        <Field label="Social support" rows={2} value={f.social_support} onChange={set("social_support")}
          hint="Who knows what you're going through? How supportive are they?" />

        {err && <div className="banner crisis" style={{ marginTop: 4 }}>{err}</div>}

        <div style={{ display: "flex", gap: 10, marginTop: 14, alignItems: "center" }}>
          <button className="btn accent" onClick={() => submit(f)} disabled={busy}>
            {busy ? <span className="spinner" /> : null}
            <span>Save &amp; continue →</span>
          </button>
          <button className="btn ghost" onClick={() => submit(EMPTY)} disabled={busy}>
            Skip for now →
          </button>
          <span style={{ fontSize: 12.5, color: "var(--ink-soft,#94a3b8)" }}>
            You can add or edit this anytime later.
          </span>
        </div>
      </div>
    </div>
  );
}
