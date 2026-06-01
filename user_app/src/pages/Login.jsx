import { useState } from "react";
import { api, setSession } from "../api.js";

export default function Login({ onAuth }) {
  const [username, setU] = useState("user");
  const [password, setP] = useState("user123");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      const res = await api.login(username, password);
      setSession(res.token, { username: res.username, role: res.role });
      onAuth({ username: res.username, role: res.role });
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-wrap">
      <div className="card login-card">
        <div className="eyebrow">CBT — Patient</div>
        <h1 className="title" style={{ fontSize: 34 }}>
          Talk through what's on your mind
        </h1>
        <p className="sub" style={{ marginBottom: 22 }}>
          AI-assisted CBT techniques with clinician oversight on
          sensitive cases. A licensed clinician reviews any response
          when professional judgment is needed.
        </p>

        <form onSubmit={submit}>
          <label>Username</label>
          <input
            value={username}
            onChange={(e) => setU(e.target.value)}
            style={{ marginBottom: 14 }}
          />
          <label>Password</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setP(e.target.value)}
            style={{ marginBottom: 18 }}
          />
          {err && (
            <div className="banner crisis" style={{ marginTop: 0 }}>
              {err}
            </div>
          )}
          <button
            className="btn accent"
            disabled={busy}
            style={{ width: "100%" }}
          >
            {busy && <span className="spinner" />}
            Sign in
          </button>
        </form>

        <div className="divider" />
        <p className="mono" style={{ color: "var(--ink-soft)", fontSize: 11.5 }}>
          DEMO PATIENT ACCOUNT<br />
          user / user123
        </p>
        <p
          className="mono"
          style={{ color: "var(--ink-soft)", fontSize: 11, marginTop: 10 }}
        >
          Clinicians sign in at <b>http://localhost:5174</b>.
        </p>
      </div>
    </div>
  );
}
