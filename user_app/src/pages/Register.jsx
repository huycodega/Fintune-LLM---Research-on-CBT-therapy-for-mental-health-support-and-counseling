import { useState } from "react";
import { api, setSession } from "../api.js";
import AuthLayout from "../components/AuthLayout.jsx";
import GoogleSignInButton from "../components/GoogleSignInButton.jsx";

// Two-step Gmail registration: (1) email + password → OTP emailed,
// (2) enter OTP → verified + auto-logged-in.
export default function Register({ onAuth, onBackToLogin }) {
  const [step, setStep] = useState("form"); // form | otp
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [otp, setOtp] = useState("");
  const [devOtp, setDevOtp] = useState("");
  const [delivery, setDelivery] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function submitForm(e) {
    e.preventDefault();
    setErr("");
    if (!email.toLowerCase().endsWith("@gmail.com")) {
      setErr("Please use a @gmail.com address.");
      return;
    }
    setBusy(true);
    try {
      const r = await api.register(email.trim().toLowerCase(), password);
      setDelivery(r.delivery);
      if (r.dev_otp) setDevOtp(r.dev_otp); // DEV mode convenience
      setStep("otp");
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function submitOtp(e) {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      const res = await api.verifyOtp(email.trim().toLowerCase(), otp.trim());
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

  async function resend() {
    setErr("");
    setBusy(true);
    try {
      const r = await api.resendOtp(email.trim().toLowerCase());
      if (r.dev_otp) setDevOtp(r.dev_otp);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout>
      <button className="auth2-back" onClick={onBackToLogin}>
        ← Back to sign in
      </button>
      <div className="auth2-card-logo">🌿</div>
      <div className="login-title">
        {step === "form" ? "Create your account" : "Verify your email"}
      </div>
      <p className="login-sub">
        {step === "form"
          ? "Sign up with your Gmail. A safe, confidential space for student wellbeing — with a clinician reviewing anything sensitive."
          : `We sent a ${devOtp ? "code" : "verification code"} to ${email}.`}
      </p>

      {step === "form" ? (
          <form onSubmit={submitForm}>
            <div className="field">
              <label>Gmail address</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@gmail.com"
                autoFocus
              />
            </div>
            <div className="field">
              <label>Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="At least 6 characters"
              />
            </div>
            {err && <div className="banner crisis">{err}</div>}
            <button className="btn accent full" disabled={busy} style={{ marginTop: 4 }}>
              {busy ? <span className="spinner" /> : null}
              Send verification code
            </button>
          </form>
        ) : (
          <form onSubmit={submitOtp}>
            {devOtp && (
              <div className="banner" style={{ background: "#eef6ff", color: "#1d4ed8" }}>
                Dev mode — your code is <strong>{devOtp}</strong>
              </div>
            )}
            <div className="field">
              <label>Verification code</label>
              <input
                value={otp}
                onChange={(e) => setOtp(e.target.value)}
                placeholder="6-digit code"
                inputMode="numeric"
                autoFocus
              />
            </div>
            {err && <div className="banner crisis">{err}</div>}
            <button className="btn accent full" disabled={busy} style={{ marginTop: 4 }}>
              {busy ? <span className="spinner" /> : null}
              Verify & continue
            </button>
            <button
              type="button"
              className="btn ghost full"
              disabled={busy}
              onClick={resend}
              style={{ marginTop: 8 }}
            >
              Resend code
            </button>
          </form>
        )}

      {step === "form" && (
        <>
          <div className="auth-or"><span>or</span></div>
          <div className="gsi-row">
            <GoogleSignInButton onCredential={handleGoogle} text="signup_with" />
          </div>
        </>
      )}

      <div className="divider" />
      <div className="demo-hint">
        Already have an account?{" "}
        <a href="#" onClick={(e) => { e.preventDefault(); onBackToLogin(); }}>
          Sign in
        </a>
      </div>
    </AuthLayout>
  );
}
