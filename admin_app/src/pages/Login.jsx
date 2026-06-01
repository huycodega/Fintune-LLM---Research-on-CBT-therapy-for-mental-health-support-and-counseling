import { useState } from "react";
import { api, setSession } from "../api.js";

export default function Login({ onAuth }) {
  const [username, setU] = useState("clinician");
  const [password, setP] = useState("clinic123");
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
        <div className="eyebrow">CBT — Chuyên gia</div>
        <h1 className="title" style={{ fontSize: 32 }}>
          Clinician Dashboard
        </h1>
        <p className="sub" style={{ marginBottom: 22 }}>
          Hệ thống hỗ trợ quyết định lâm sàng. Xem hàng đợi các phiên cần
          duyệt, đọc nháp do AI tạo, và phê duyệt / chỉnh sửa / từ chối
          trước khi phản hồi tới người dùng.
        </p>

        <form onSubmit={submit}>
          <label>Tên đăng nhập</label>
          <input
            value={username}
            onChange={(e) => setU(e.target.value)}
            style={{ marginBottom: 14 }}
          />
          <label>Mật khẩu</label>
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
            Đăng nhập
          </button>
        </form>

        <div className="divider" />
        <p className="mono" style={{ color: "var(--ink-soft)", fontSize: 11.5 }}>
          DEMO CLINICIAN ACCOUNT<br />
          clinician / clinic123
        </p>
        <p
          className="mono"
          style={{ color: "var(--ink-soft)", fontSize: 11, marginTop: 10 }}
        >
          App này CHỈ chấp nhận tài khoản chuyên gia. Người dùng thường
          đăng nhập tại <b>http://localhost:5173</b>.
        </p>
      </div>
    </div>
  );
}
