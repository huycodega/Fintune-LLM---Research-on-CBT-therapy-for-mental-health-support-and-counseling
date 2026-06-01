import { useState } from "react";
import { api } from "../api.js";

const BROOKE_SAMPLE = `Name: Brooke Davis Age: 41 Gender: female Occupation: Veterinary Assistant Education: Certified Veterinary Technician Marital Status: Single Family Details: Lives alone with multiple pets

2. Presenting Problem
I feel anxious and avoid going back to the animal shelter because I believe the animals there will hate me for not remembering me. This leads to feelings of guilt and self-blame. These feelings started a few months ago after a visit to the shelter where some animals did not greet me as warmly as before.

3. Reason for Seeking Counseling
I decided to seek counseling because this issue has started affecting my daily life and my passion for working with animals.

4. Past History (including medical history)
I have not experienced similar problems before. I have not received treatment or counseling for psychological problems in the past. I do not have any significant physical illnesses.

5. Academic/occupational functioning level:
My job performance as a veterinary assistant has not been affected yet, but my passion for working with animals has dwindled. Interpersonal relationships: My relationships with other animal shelter volunteers have been strained as I have distanced myself because of this issue. Daily life: My anxiety about going to the shelter has disrupted my sleep patterns and overall well-being.

6. Social Support System
I have a few close friends who are supportive, but they do not fully understand the extent of my anxiety related to the animal shelter.`;

const SECTIONS_TEMPLATE = `Name: 
Age: 
Gender: 
Occupation: 
Education: 
Marital Status: 
Family Details: 

2. Presenting Problem
[Describe what's been on your mind and the situations where it shows up]

3. Reason for Seeking Counseling
[What made you decide to reach out now?]

4. Past History (including medical history)
[Have you experienced similar issues before? Any prior counseling or relevant medical history?]

5. Academic/occupational functioning level:
[How is your work or school affected?]
Interpersonal relationships:
[How is this affecting relationships with others?]
Daily life:
[How does this affect sleep, energy, daily routine?]

6. Social Support System
[Who in your life knows about this? How supportive are they?]`;

export default function Intake({ onDone }) {
  const [text, setText] = useState(SECTIONS_TEMPLATE);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [result, setResult] = useState(null);

  async function submit() {
    if (text.trim().length < 40) {
      setErr("Please complete more of the form before submitting.");
      return;
    }
    setBusy(true);
    setErr("");
    try {
      const r = await api.submitIntake(text);
      setResult(r);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="shell" style={{ paddingTop: 30, paddingBottom: 60 }}>
      <div className="eyebrow">Intake form · required before first session</div>
      <h1 className="title">Tell us about yourself</h1>
      <p className="sub">
        This 6-section intake helps us understand your situation. Your
        clinician will see this. The AI uses it (with personal details
        removed) to choose techniques that fit you. Submit once — you
        can edit later.
      </p>

      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between",
                       alignItems: "center", marginBottom: 10 }}>
          <label style={{ marginBottom: 0 }}>Your intake (free text)</label>
          <button
            className="btn ghost sm"
            type="button"
            onClick={() => setText(BROOKE_SAMPLE)}
          >
            Load sample (Brooke Davis)
          </button>
        </div>
        <textarea
          rows={22}
          value={text}
          onChange={(e) => setText(e.target.value)}
          style={{ fontFamily: "var(--font-mono)", fontSize: 13.5 }}
        />
        {err && (
          <div className="banner crisis" style={{ marginTop: 12 }}>
            {err}
          </div>
        )}
        {result && (
          <div className="banner ok" style={{ marginTop: 12 }}>
            <b>Intake received.</b> Parse confidence:{" "}
            {Math.round((result.parse_confidence || 0) * 100)}% ·
            sections recognized: {result.sections_recognized || 0}/6.
            <br />
            <button
              className="btn accent"
              onClick={onDone}
              style={{ marginTop: 12 }}
            >
              Continue to chat →
            </button>
          </div>
        )}
        {!result && (
          <button
            className="btn accent"
            onClick={submit}
            disabled={busy}
            style={{ marginTop: 14 }}
          >
            {busy && <span className="spinner" />}
            Submit intake
          </button>
        )}
      </div>
    </div>
  );
}
