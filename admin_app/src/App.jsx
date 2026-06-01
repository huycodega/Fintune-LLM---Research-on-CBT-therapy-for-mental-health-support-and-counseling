import { useState, useEffect } from "react";
import { getUser, clearSession, api } from "./api.js";
import Login from "./pages/Login.jsx";
import Clinician from "./pages/Clinician.jsx";

function TopBar({ user, onLogout }) {
  return (
    <div className="topbar">
      <div className="brand">
        CBT Clinician
        <small>Admin app · human-in-the-loop</small>
      </div>
      {user && (
        <div className="who">
          <b>{user.username}</b> ({user.role})
          <button onClick={onLogout}>Sign out</button>
        </div>
      )}
    </div>
  );
}

export default function App() {
  const [user, setUser] = useState(getUser());
  const [health, setHealth] = useState(null);

  useEffect(() => {
    api.health().then(setHealth).catch(() => {});
  }, []);

  function logout() { clearSession(); setUser(null); }

  return (
    <>
      <TopBar user={user} onLogout={logout} />
      {health && (
        <div className="shell mono"
              style={{ fontSize: 11, color: "var(--ink-soft)",
                       paddingTop: 10 }}>
          LLM: {health.llm?.mode}
          {health.mock_llm ? " (mock — no GPU)" : ""} · model:{" "}
          {health.model_repo}
          {health.calibration?.loaded
            ? ` · T=${(health.calibration.global_temperature || 1).toFixed(2)}`
            : ""}
        </div>
      )}
      {user ? <Clinician /> : <Login onAuth={setUser} />}
    </>
  );
}
