import { useState } from "react";
import { api } from "../api.js";

export default function Consent({ onDone }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [checked, setChecked] = useState(false);

  async function accept() {
    if (!checked) return;
    setBusy(true);
    setErr("");
    try {
      await api.consent();
      onDone();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="shell" style={{ paddingTop: 30, paddingBottom: 60 }}>
      <div className="eyebrow">HIPAA · Layer 1 — Privacy & Consent</div>
      <h1 className="title">Before we begin</h1>
      <p className="sub">
        This system supports your mental wellness with AI-assisted
        Cognitive Behavioral Therapy techniques. A licensed clinician
        reviews any response when your situation may benefit from
        professional judgment. Please review and accept the terms below
        to continue.
      </p>

      <div className="card">
        <h3 style={{ fontFamily: "var(--font-display)", marginBottom: 12 }}>
          What we collect and why
        </h3>
        <ul style={{ paddingLeft: 22, marginBottom: 18 }}>
          <li>
            Your intake form and chat messages, stored encrypted at rest
            (AES-256).
          </li>
          <li>
            Personally identifying information (name, contact) is{" "}
            <b>removed</b> before any data is sent to the AI model.
          </li>
          <li>
            Aggregated, de-identified data may be used to improve clinical
            quality.
          </li>
        </ul>

        <h3 style={{ fontFamily: "var(--font-display)", marginBottom: 12 }}>
          Your rights
        </h3>
        <ul style={{ paddingLeft: 22, marginBottom: 18 }}>
          <li>Withdraw consent at any time and request data deletion.</li>
          <li>Receive a copy of any session record on request.</li>
          <li>
            Be informed before any change to your data-handling practices.
          </li>
        </ul>

        <div className="banner crisis">
          <strong>This is not emergency care.</strong> If you are in
          immediate danger or experiencing a mental-health emergency, call
          your local crisis line. In the US: <b>988</b>.
        </div>

        <label
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: 10,
            marginTop: 18,
            fontFamily: "var(--font-body)",
            textTransform: "none",
            letterSpacing: 0,
            color: "var(--ink)",
            fontSize: 15,
          }}
        >
          <input
            type="checkbox"
            checked={checked}
            onChange={(e) => setChecked(e.target.checked)}
            style={{ width: "auto", marginTop: 4 }}
          />
          <span>
            I have read and agree to the privacy notice above. I
            understand my data is encrypted, PII is scrubbed before AI
            processing, and a clinician reviews high-risk situations.
          </span>
        </label>

        {err && (
          <div className="banner crisis" style={{ marginTop: 14 }}>
            {err}
          </div>
        )}

        <button
          className="btn accent"
          onClick={accept}
          disabled={!checked || busy}
          style={{ marginTop: 18 }}
        >
          {busy && <span className="spinner" />}
          Accept and continue
        </button>
      </div>
    </div>
  );
}
