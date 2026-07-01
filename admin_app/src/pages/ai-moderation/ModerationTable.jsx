import { Avatar, fmtDateTime, IdChip } from "../../ui.jsx";
import RiskLevelBadge from "./RiskLevelBadge.jsx";

export default function ModerationTable({
  sessions,
  selectedId,
  onSelect,
  loading,
  error,
  pagination,
  onPage,
}) {
  return (
    <section className="am-table-card">
      <div className="am-table-head">
        <div>
          <h2>Moderation sessions</h2>
          <p>{pagination?.total ?? 0} sessions found</p>
        </div>
      </div>

      {error && <div className="am-state error">{error}</div>}
      {loading && <div className="am-state">Loading sessions...</div>}
      {!loading && !error && sessions.length === 0 && (
        <div className="am-state">No matching moderation sessions.</div>
      )}

      {!loading && !error && sessions.length > 0 && (
        <div className="am-table-scroll">
          <table className="am-table">
            <thead>
              <tr>
                <th>Session ID</th>
                <th>User</th>
                <th>Risk Level</th>
                <th>Content Summary</th>
                <th>Created At</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((session) => {
                const user = session.user || {};
                const fullName = user.fullName || session.userName || user.username || "Unknown user";
                const userMeta = user.userCode || user.email || session.userCode || session.userEmail || session.userId;
                return (
                  <tr
                    key={session.id}
                    className={selectedId === session.id ? "selected" : ""}
                    onClick={() => onSelect(session.id)}
                  >
                    <td><IdChip id={session.sessionId} /></td>
                    <td>
                      <div className="am-user-cell">
                        <Avatar name={fullName} size={34} />
                        <div>
                          <b>{fullName}</b>
                          <small>{userMeta}</small>
                        </div>
                      </div>
                    </td>
                    <td><RiskLevelBadge level={session.riskLevel} /></td>
                    <td className="am-summary-cell">{session.contentSummary}</td>
                    <td>{fmtDateTime(session.createdAt)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {pagination && pagination.totalPages > 1 && (
        <div className="am-pagination">
          <span>Page {pagination.page} / {pagination.totalPages}</span>
          <div>
            <button type="button" disabled={pagination.page <= 1} onClick={() => onPage(pagination.page - 1)}>Prev</button>
            {Array.from({ length: pagination.totalPages }, (_, i) => i + 1)
              .filter((page) => page === 1 || page === pagination.totalPages || Math.abs(page - pagination.page) <= 2)
              .map((page) => (
                <button key={page} type="button" className={page === pagination.page ? "active" : ""} onClick={() => onPage(page)}>
                  {page}
                </button>
              ))}
            <button type="button" disabled={pagination.page >= pagination.totalPages} onClick={() => onPage(pagination.page + 1)}>Next</button>
          </div>
        </div>
      )}
    </section>
  );
}
