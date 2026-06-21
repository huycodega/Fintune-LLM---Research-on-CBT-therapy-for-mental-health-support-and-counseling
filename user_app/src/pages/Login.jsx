import { useState } from "react";
import { api, setSession } from "../api.js";
import Register from "./Register.jsx";
import AuthLayout from "../components/AuthLayout.jsx";
import GoogleSignInButton from "../components/GoogleSignInButton.jsx";

export default function Login({ onAuth, onBack }) {
  const [mode, setMode] = useState("login"); // login | register
  const [username, setU] = useState("");
  const [password, setP] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  if (mode === "register") {
    return (
      <Register onAuth={onAuth} onBackToLogin={() => setMode("login")} />
    );
  }

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

  async function handleGoogle(credential) {
    setErr("");
    setBusy(true);
    try {
      const res = await api.googleAuth(credential);
      setSession(res.token, { username: res.username, role: res.role });
      onAuth({ username: res.username, role: res.role });
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout>
      {onBack && (
        <button className="auth2-back" onClick={onBack}>
          ← Back to home
        </button>
      )}
      <div className="auth2-card-logo">🌿</div>
      <div className="login-title">Welcome back</div>
      <p className="login-sub">
        A safe space to talk. CBT-guided support with a clinician
        reviewing anything sensitive — AI never responds alone on critical cases.
      </p>

      <form onSubmit={submit}>
        <div className="field">
          <label>Gmail or username</label>
          <input value={username} onChange={(e) => setU(e.target.value)}
            placeholder="you@gmail.com" autoFocus />
        </div>
        <div className="field">
          <label>Password</label>
          <input type="password" value={password} onChange={(e) => setP(e.target.value)} />
        </div>
        {err && <div className="banner crisis">{err}</div>}
        <button className="btn accent full" disabled={busy} style={{ marginTop: 4 }}>
          {busy ? <span className="spinner" /> : null}
          Sign in
        </button>
      </form>

      <div className="auth-or"><span>or</span></div>
      <div className="gsi-row">
        <GoogleSignInButton onCredential={handleGoogle} text="continue_with" />
      </div>

      <div className="divider" />
      <div className="demo-hint">
        New here?{" "}
        <a href="#" onClick={(e) => { e.preventDefault(); setMode("register"); }}>
          Create an account with Gmail
        </a>
      </div>
      <div className="demo-hint" style={{ marginTop: 6, opacity: 0.7 }}>
        Demo: <strong>user</strong> / <strong>user123</strong>
      </div>
    </AuthLayout>
  );
}
