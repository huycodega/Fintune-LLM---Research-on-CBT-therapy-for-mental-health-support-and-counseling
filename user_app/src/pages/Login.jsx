import { useState } from "react";
import { api, setSession } from "../api.js";
import Register from "./Register.jsx";
import AuthLayout from "../components/AuthLayout.jsx";
import GoogleSignInButton from "../components/GoogleSignInButton.jsx";

// Small inline icons used inside the form fields / buttons.
const UserIcon = () => (
  <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor"
    strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <circle cx="12" cy="8" r="3.4" />
    <path d="M5.5 19a6.5 6.5 0 0 1 13 0" />
  </svg>
);
const LockIcon = () => (
  <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor"
    strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <rect x="5" y="10.5" width="14" height="9" rx="2" />
    <path d="M8 10.5V8a4 4 0 0 1 8 0v2.5" />
  </svg>
);
const EyeIcon = ({ off }) => (
  <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor"
    strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z" />
    <circle cx="12" cy="12" r="3" />
    {off && <path d="M4 4l16 16" />}
  </svg>
);
const GoogleIcon = () => (
  <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
    <path fill="#4285F4" d="M21.6 12.2c0-.7-.06-1.4-.18-2H12v3.8h5.4a4.6 4.6 0 0 1-2 3v2.5h3.24c1.9-1.75 3-4.34 3-7.3Z" />
    <path fill="#34A853" d="M12 22c2.7 0 4.96-.9 6.62-2.43l-3.24-2.5c-.9.6-2.05.96-3.38.96-2.6 0-4.8-1.76-5.58-4.12H3.08v2.58A10 10 0 0 0 12 22Z" />
    <path fill="#FBBC05" d="M6.42 13.9a6 6 0 0 1 0-3.8V7.52H3.08a10 10 0 0 0 0 8.96l3.34-2.58Z" />
    <path fill="#EA4335" d="M12 5.98c1.47 0 2.79.5 3.83 1.5l2.87-2.87C16.95 2.99 14.7 2 12 2A10 10 0 0 0 3.08 7.52l3.34 2.58C7.2 7.74 9.4 5.98 12 5.98Z" />
  </svg>
);

export default function Login({ onAuth, onBack }) {
  const [mode, setMode] = useState("login"); // login | register
  const [username, setU] = useState("");
  const [password, setP] = useState("");
  const [showPw, setShowPw] = useState(false);
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
          <div className="auth-input-wrap">
            <span className="auth-input-icon"><UserIcon /></span>
            <input value={username} onChange={(e) => setU(e.target.value)}
              placeholder="you@gmail.com" autoFocus />
          </div>
        </div>
        <div className="field">
          <label>Password</label>
          <div className="auth-input-wrap">
            <span className="auth-input-icon"><LockIcon /></span>
            <input type={showPw ? "text" : "password"} value={password}
              onChange={(e) => setP(e.target.value)} placeholder="••••••••" />
            <button type="button" className="auth-input-eye"
              onClick={() => setShowPw((v) => !v)}
              aria-label={showPw ? "Hide password" : "Show password"}>
              <EyeIcon off={showPw} />
            </button>
          </div>
        </div>
        <a href="#" className="auth-forgot" onClick={(e) => e.preventDefault()}>
          Forgot password?
        </a>
        {err && <div className="banner crisis">{err}</div>}
        <button className="btn accent full" disabled={busy} style={{ marginTop: 4 }}>
          {busy ? <span className="spinner" /> : null}
          Sign in
          <span className="landing-btn-arrow">→</span>
        </button>
      </form>

      <div className="auth-or"><span>or</span></div>
      <div className="gsi-row">
        <GoogleSignInButton onCredential={handleGoogle} text="continue_with" />
      </div>

      <button type="button" className="auth-google-btn"
        onClick={() => setMode("register")}>
        New here? <strong>Create an account with Gmail</strong>
      </button>

      <div className="auth-demo">
        <span className="auth-demo-flask">🧪</span>
        Demo: <strong>user</strong> / <strong>user123</strong>
      </div>
    </AuthLayout>
  );
}
