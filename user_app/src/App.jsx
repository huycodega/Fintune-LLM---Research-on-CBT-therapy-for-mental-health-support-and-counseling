import { useState, useEffect } from "react";
import { getUser, clearSession, api } from "./api.js";
import Login from "./pages/Login.jsx";
import Consent from "./pages/Consent.jsx";
import Intake from "./pages/Intake.jsx";
import Chat from "./pages/Chat.jsx";

function TopBar({ user, onLogout }) {
  return (
    <div className="topbar">
      <div className="brand">
        CBT Assistant
        <small>Patient app · with clinician oversight</small>
      </div>
      {user && (
        <div className="who">
          <b>{user.username}</b>
          <button onClick={onLogout}>Sign out</button>
        </div>
      )}
    </div>
  );
}

export default function App() {
  const [user, setUser] = useState(getUser());
  const [stage, setStage] = useState("loading");  // loading | consent | intake | chat
  const [health, setHealth] = useState(null);

  useEffect(() => {
    api.health().then(setHealth).catch(() => {});
  }, []);

  // After login (or on page refresh), ask the backend what the user needs next.
  useEffect(() => {
    if (!user) {
      setStage("loading");
      return;
    }
    api
      .me()
      .then((m) => {
        if (m.consent_required) setStage("consent");
        else if (m.intake_required) setStage("intake");
        else setStage("chat");
      })
      .catch(() => setStage("chat"));
  }, [user]);

  function handleAuth(u) {
    setUser(u);
  }

  function logout() {
    clearSession();
    setUser(null);
  }

  let body;
  if (!user) body = <Login onAuth={handleAuth} />;
  else if (stage === "loading") body = null;
  else if (stage === "consent")
    body = <Consent onDone={() => setStage("intake")} />;
  else if (stage === "intake")
    body = <Intake onDone={() => setStage("chat")} />;
  else body = <Chat />;

  return (
    <>
      <TopBar user={user} onLogout={logout} />
      {health && (
        <div
          className="shell mono"
          style={{ fontSize: 11, color: "var(--ink-soft)", paddingTop: 10 }}
        >
          LLM: {health.llm?.mode}
          {health.mock_llm ? " (mock — no GPU)" : ""} · model:{" "}
          {health.model_repo}
          {health.calibration?.loaded
            ? ` · T=${(health.calibration.global_temperature || 1).toFixed(2)}`
            : ""}
        </div>
      )}
      {body}
    </>
  );
}
