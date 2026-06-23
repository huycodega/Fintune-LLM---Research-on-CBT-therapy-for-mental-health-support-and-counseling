import { useEffect, useState } from "react";
import { Avatar, fmtDateTime } from "../../ui.jsx";
import RiskLevelBadge from "./RiskLevelBadge.jsx";
import LaPager from "../../components/shared/LaPager.jsx";

const PAGE_SIZE = 10;

const DECISION = {
  approve: { label: "Approved", cls: "ok" },
  edit: { label: "Edited & sent", cls: "edit" },
  reject: { label: "Rejected", cls: "danger" },
  need_improvement: { label: "Needs improvement", cls: "warn" },
};

export default function ModerationHistory({ items, loading, error }) {
  const [openId, setOpenId] = useState(null);
  const [page, setPage] = useState(1);
  useEffect(() => {
    const pc = Math.max(1, Math.ceil(items.length / PAGE_SIZE));
    if (page > pc) setPage(pc);
  }, [items.length, page]);
  const pageItems = items.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  return (
    <section className="am-table-card">
      <div className="am-table-head">
        <div>
          <h2>Processed history</h2>
          <p>{items.length} resolved moderation{items.length === 1 ? "" : "s"}</p>
        </div>
      </div>

      {error && <div className="am-state error">{error}</div>}
      {loading && <div className="am-state">Loading history…</div>}
      {!loading && !error && items.length === 0 && (
        <div className="am-state">No processed moderations yet.</div>
      )}

      {!loading && !error && items.length > 0 && (
        <div className="am-table-scroll">
          <table className="am-table">
            <thead>
              <tr>
                <th>Session ID</th>
                <th>User</th>
                <th>Risk</th>
                <th>Decision</th>
                <th>Reviewed by</th>
                <th>Resolved at</th>
              </tr>
            </thead>
            <tbody>
              {pageItems.map((it) => {
                const d = DECISION[it.resolution] || { label: it.resolution || "Resolved", cls: "" };
                const open = openId === it.id;
                return [
                  <tr key={it.id} className={open ? "selected" : ""}
                      onClick={() => setOpenId(open ? null : it.id)}>
                    <td><strong>{it.sessionId?.slice(0, 8)}</strong></td>
                    <td>
                      <div className="am-user-cell">
                        <Avatar name={it.user?.name || "User"} size={34} />
                        <div><b>{it.user?.name || "User"}</b><small>{it.user?.masked_email}</small></div>
                      </div>
                    </td>
                    <td><RiskLevelBadge level={it.riskLevel} /></td>
                    <td><span className={`am-decision ${d.cls}`}>{d.label}</span></td>
                    <td>{it.reviewedBy || "—"}</td>
                    <td>{fmtDateTime(it.resolvedAt)}</td>
                  </tr>,
                  open && (
                    <tr key={it.id + "-d"} className="am-history-detail-row">
                      <td colSpan={6}>
                        <div className="am-history-detail">
                          <div className="am-history-block user">
                            <span className="am-history-label">💬 User message</span>
                            <p className="am-history-text">{it.userContent || "—"}</p>
                          </div>
                          <div className="am-history-block reply">
                            <span className="am-history-label">✅ Final response sent</span>
                            <p className="am-history-text">{it.finalResponse || "(no reply was sent)"}</p>
                          </div>
                        </div>
                      </td>
                    </tr>
                  ),
                ];
              })}
            </tbody>
          </table>
        </div>
      )}
      {!loading && !error && (
        <LaPager page={page} pageSize={PAGE_SIZE} total={items.length}
                 onChange={setPage} noun="resolved" />
      )}
    </section>
  );
}
