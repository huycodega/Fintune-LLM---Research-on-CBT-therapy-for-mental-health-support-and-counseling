import { useState, useEffect, useCallback } from "react";
import { api, getUser } from "../api.js";
import {
  Avatar, RiskPill, StatusPill, StatCard, Empty,
  displayName, fmtDate, timeAgo, fmtDateTime,
} from "../ui.jsx";
import ConfirmDialog from "../admin/ConfirmDialog.jsx";

const STATUS_TABS = [
  { id: "", label: "All" },
  { id: "active", label: "Active" },
  { id: "suspended", label: "Suspended" },
];

export default function Users({ search, selectedUserId }) {
  const me = getUser();
  const isAdmin = me?.role === "admin";

  const [data, setData] = useState(null);
  const [status, setStatus] = useState("");
  const [risk, setRisk] = useState("");
  const [page, setPage] = useState(1);
  const [selId, setSelId] = useState(selectedUserId || null);
  const [detail, setDetail] = useState(null);
  const [busy, setBusy] = useState(false);
  const [errMsg, setErrMsg] = useState("");

  const load = useCallback(() => {
    api.users({ q: search, status, risk, page, page_size: 12 })
      .then((d) => {
        setData(d);
        // keep selection valid / auto-select first
        if (!d.users.find((u) => u.id === selId)) {
          setSelId(d.users[0]?.id || null);
        }
      })
      .catch(() => setData({ users: [], total: 0 }));
  }, [search, status, risk, page, selId]);

  useEffect(() => { if (selectedUserId) setSelId(selectedUserId); }, [selectedUserId]);
  useEffect(() => { setPage(1); }, [search, status, risk]);
  useEffect(() => { load(); }, [search, status, risk, page]); // eslint-disable-line

  useEffect(() => {
    if (!selId) { setDetail(null); return; }
    setDetail(null);
    api.userDetail(selId).then(setDetail).catch(() => setDetail(null));
  }, [selId]);

  const [confirmStatus, setConfirmStatus] = useState(null);   // pending status change

  function requestStatus(next) {
    if (!detail) return;
    setConfirmStatus(next);
  }
  async function changeStatus(next) {
    if (!detail) return;
    setBusy(true);
    try {
      await api.setUserStatus(detail.id, next);
      setDetail({ ...detail, status: next });
      load();
    } catch (e) { setErrMsg("Error: " + e.message); }
    finally { setBusy(false); setConfirmStatus(null); }
  }

  async function changeRole(role) {
    if (!detail || role === detail.role) return;
    setBusy(true);
    try {
      await api.setUserRole(detail.id, role);
      setDetail({ ...detail, role });
      load();
    } catch (e) { setErrMsg("Error: " + e.message); }
    finally { setBusy(false); }
  }

  const users = data?.users || [];
  const total = data?.total || 0;
  const pageCount = Math.max(1, Math.ceil(total / 12));

  // top-line counts (from current page-set is approximate; use total for primary)
  const highRisk = users.filter((u) => u.risk === "high").length;
  const suspended = users.filter((u) => u.status === "suspended").length;

  return (
    <>
      <div className="stat-row">
        <StatCard icon="👥" color="purple" value={total} label="Users (filtered)" />
        <StatCard icon="🚨" color="red" value={highRisk} label="High-risk on page" />
        <StatCard icon="⛔" color="amber" value={suspended} label="Suspended on page" />
        <StatCard icon="✅" color="green" value={users.filter(u => u.status === "active").length}
                  label="Active on page" />
      </div>

      <div className="split">
        {/* ---- table ---- */}
        <div className="panel">
          <div className="panel-head">
            <div className="filter-tabs">
              {STATUS_TABS.map((t) => (
                <button key={t.id}
                        className={`filter-tab ${status === t.id ? "active" : ""}`}
                        onClick={() => setStatus(t.id)}>{t.label}</button>
              ))}
            </div>
            <div className="panel-tools">
              <select className="select" value={risk} onChange={(e) => setRisk(e.target.value)}>
                <option value="">All risk</option>
                <option value="high">High</option>
                <option value="elevated">Elevated</option>
                <option value="moderate">Moderate</option>
                <option value="low">Low</option>
              </select>
            </div>
          </div>

          {users.length === 0 ? (
            <Empty icon="🔍" text="No users match these filters." />
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>User</th><th>Status</th><th>Risk</th>
                  <th>Sessions</th><th>Crisis</th><th>Last active</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} className={u.id === selId ? "selected" : ""}
                      onClick={() => setSelId(u.id)}>
                    <td>
                      <div className="cell-user">
                        <Avatar name={u.username} />
                        <div>
                          <div className="cell-name">{displayName(u.username)}</div>
                          <div className="cell-sub">{u.email || "—"}</div>
                        </div>
                      </div>
                    </td>
                    <td><StatusPill status={u.status} /></td>
                    <td><RiskPill risk={u.risk} /></td>
                    <td>{u.sessions}</td>
                    <td>{u.crisis_count > 0
                      ? <span className="pill red"><span className="dot" />{u.crisis_count}</span>
                      : <span style={{ color: "var(--ink-faint)" }}>0</span>}</td>
                    <td style={{ color: "var(--ink-soft)" }}>{timeAgo(u.last_active)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {pageCount > 1 && (
            <div className="pager">
              <button className="pager-btn" disabled={page <= 1}
                      onClick={() => setPage(page - 1)}>‹</button>
              {Array.from({ length: pageCount }, (_, i) => i + 1)
                .filter((p) => Math.abs(p - page) < 3 || p === 1 || p === pageCount)
                .map((p, i, arr) => (
                  <span key={p} style={{ display: "flex", gap: 6 }}>
                    {i > 0 && arr[i - 1] !== p - 1 && <span style={{ color: "var(--ink-faint)" }}>…</span>}
                    <button className={`pager-btn ${p === page ? "active" : ""}`}
                            onClick={() => setPage(p)}>{p}</button>
                  </span>
                ))}
              <button className="pager-btn" disabled={page >= pageCount}
                      onClick={() => setPage(page + 1)}>›</button>
            </div>
          )}
        </div>

        {/* ---- detail ---- */}
        <UserDetail detail={detail} isAdmin={isAdmin} busy={busy}
                    onStatus={requestStatus} onRole={changeRole} />
      </div>

      <ConfirmDialog
        open={!!confirmStatus}
        title={confirmStatus === "suspended" ? "Suspend account?" : "Re-activate account?"}
        message={detail ? `Are you sure you want to ${confirmStatus === "suspended" ? "suspend" : "re-activate"} ${displayName(detail.username)}?` : ""}
        confirmLabel={confirmStatus === "suspended" ? "Suspend" : "Re-activate"}
        danger={confirmStatus === "suspended"}
        busy={busy}
        onConfirm={() => changeStatus(confirmStatus)}
        onCancel={() => setConfirmStatus(null)}
      />
      {errMsg && (
        <div className="la-toast-err" onClick={() => setErrMsg("")}>{errMsg}</div>
      )}
    </>
  );
}

function UserDetail({ detail, isAdmin, busy, onStatus, onRole }) {
  // SOAP medical records for the selected user (hooks must run before any return).
  const [records, setRecords] = useState([]);
  const [openRec, setOpenRec] = useState(null);
  useEffect(() => {
    setRecords([]); setOpenRec(null);
    if (detail?.id) {
      api.userSoapRecords(detail.id).then((r) => setRecords(r.records || [])).catch(() => {});
    }
  }, [detail?.id]);

  function downloadSoap(r) {
    const s = r.soap || {};
    const text = "SOAP NOTE\n" + "=".repeat(48)
      + `\n\nS — SUBJECTIVE\n${s.subjective}`
      + `\n\nO — OBJECTIVE\n${s.objective}`
      + `\n\nA — ASSESSMENT\n${s.assessment}`
      + `\n\nP — PLAN\n${s.plan}\n`;
    const url = URL.createObjectURL(new Blob([text], { type: "text/plain" }));
    const a = document.createElement("a");
    a.href = url; a.download = `soap-${r.session_id}.txt`; a.click();
    URL.revokeObjectURL(url);
  }

  if (!detail) {
    return (
      <div className="panel detail">
        <Empty icon="👈" text="Select a user to see their case history." />
      </div>
    );
  }
  const d = detail;
  const recentCrisis = (d.sessions || []).filter((s) => ["L0", "L1"].includes(s.triage_level));

  return (
    <div className="panel detail">
      <div className="detail-head">
        <Avatar name={d.username} size={64} className="detail-avatar" />
        <div className="detail-name">{displayName(d.username)}</div>
        <div className="detail-email">{d.email || "no email"}</div>
        <div style={{ marginTop: 10, display: "flex", gap: 6, justifyContent: "center" }}>
          <StatusPill status={d.status} />
          <RiskPill risk={d.risk} />
        </div>
      </div>

      <div className="detail-body">
        <div className="detail-row"><span className="k">Role</span><span className="v">{d.role}</span></div>
        <div className="detail-row"><span className="k">Joined</span><span className="v">{fmtDate(d.created_at)}</span></div>
        <div className="detail-row"><span className="k">Last login</span><span className="v">{d.last_login ? fmtDate(d.last_login) : "—"}</span></div>
        <div className="detail-row"><span className="k">Email verified</span>
          <span className="v">{d.email_verified ? "✅ Yes" : "⚠️ No"}</span></div>
        <div className="detail-row"><span className="k">Sessions</span><span className="v">{d.sessions.length}</span></div>
        <div className="detail-row"><span className="k">Crisis events</span>
          <span className="v">{recentCrisis.length}</span></div>

        {d.memory?.summary && (
          <>
            <div className="detail-section-title">AI memory gist</div>
            <div className="timeline-text">{d.memory.summary}</div>
          </>
        )}

        {/* latest screening */}
        {d.screenings?.[0] && (
          <>
            <div className="detail-section-title">Latest screening</div>
            <div className="detail-row"><span className="k">PHQ-9</span>
              <span className="v">{d.screenings[0].phq9_score ?? "—"} ({d.screenings[0].phq9_level || "—"})</span></div>
            <div className="detail-row"><span className="k">GAD-7</span>
              <span className="v">{d.screenings[0].gad7_score ?? "—"} ({d.screenings[0].gad7_level || "—"})</span></div>
            <div className="detail-row"><span className="k">Mood</span>
              <span className="v">{d.screenings[0].mood_score ?? "—"}/10</span></div>
          </>
        )}

        {/* case history */}
        <div className="detail-section-title">Recent cases</div>
        {d.sessions.length === 0 ? (
          <div className="timeline-text">No sessions yet.</div>
        ) : d.sessions.slice(0, 6).map((s) => (
          <div className="timeline-item" key={s.id}>
            <div className="timeline-top">
              <span className={`pill ${s.triage_level || "gray"}`}>{s.triage_level || "—"}</span>
              {s.status === "pending_review" && <span className="pill amber">pending</span>}
              <span className="timeline-date">{fmtDateTime(s.created_at)}</span>
            </div>
            <div className="timeline-text">{s.preview || "—"}</div>
          </div>
        ))}

        {/* medical records (SOAP) — one per reviewed turn */}
        <div className="detail-section-title">
          Medical records (SOAP)
          {records.length > 0 && (
            <span className="pill green" style={{ marginLeft: 8 }}>
              {records.filter((r) => r.approved).length} approved
            </span>
          )}
        </div>
        {records.length === 0 ? (
          <div className="timeline-text">No SOAP records yet.</div>
        ) : records.map((r) => (
          <div className="timeline-item" key={r.id}>
            <div className="timeline-top" style={{ cursor: "pointer" }}
                 onClick={() => setOpenRec(openRec === r.id ? null : r.id)}>
              <span className={`pill ${r.risk_level || "gray"}`}>{r.risk_level || "—"}</span>
              {r.approved
                ? <span className="pill green">✓ approved</span>
                : <span className="pill amber">draft</span>}
              <span className="timeline-date">{fmtDateTime(r.created_at)}</span>
            </div>
            <div className="timeline-text">{r.message_preview || "—"}</div>
            {openRec === r.id && (
              <div className="timeline-text" style={{ whiteSpace: "pre-wrap", marginTop: 6 }}>
                <b>S:</b> {r.soap.subjective}{"\n"}
                <b>O:</b> {r.soap.objective}{"\n"}
                <b>A:</b> {r.soap.assessment}{"\n"}
                <b>P:</b> {r.soap.plan}
                <div style={{ marginTop: 6 }}>
                  <button className="pager-btn" onClick={(e) => { e.stopPropagation(); downloadSoap(r); }}>
                    Download .txt
                  </button>
                </div>
              </div>
            )}
          </div>
        ))}

        {/* admin actions */}
        {isAdmin && d.role !== "admin" && (
          <div className="detail-actions">
            {d.status === "active" ? (
              <button className="btn red block" disabled={busy}
                      onClick={() => onStatus("suspended")}>⛔ Suspend account</button>
            ) : (
              <button className="btn green block" disabled={busy}
                      onClick={() => onStatus("active")}>✅ Re-activate account</button>
            )}
            <select className="select" value={d.role} disabled={busy}
                    onChange={(e) => onRole(e.target.value)}>
              <option value="user">Role: user</option>
              <option value="clinician">Role: clinician</option>
              <option value="admin">Role: admin</option>
            </select>
          </div>
        )}
        {!isAdmin && (
          <div className="banner info" style={{ marginTop: 14 }}>
            Sign in as an admin to suspend accounts or change roles.
          </div>
        )}
      </div>
    </div>
  );
}
