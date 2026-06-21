import { Avatar, fmtDateTime } from "../../ui.jsx";
import Pagination from "../shared/Pagination.jsx";
import { LoadingState, EmptyState, ErrorState } from "../shared/States.jsx";
import { RiskBadge, ScreeningStatusBadge } from "./ScreeningBadges.jsx";

export default function ScreeningTable({ pageData, selectedId, onSelect, loading, error, onRetry, onPage, onSort }) {
  const rows = pageData?.items || [];
  return (
    <section className="sm-table-card">
      {loading ? <LoadingState label="Loading screenings..." /> :
        error ? <ErrorState message={error.message} forbidden={error.status === 403} onRetry={onRetry} /> :
        !rows.length ? <EmptyState title="No screenings found" description="Try changing the filters or date range." /> :
        <div className="sm-table-scroll"><table className="sm-table">
          <thead><tr><th><input type="checkbox" aria-label="Select all" /></th>
            <th><button onClick={() => onSort("screening_id")}>Screening ID</button></th>
            <th>User</th><th><button onClick={() => onSort("screening_date")}>Screening Date</button></th>
            <th>Assessment Type</th><th><button onClick={() => onSort("score")}>Score</button></th>
            <th>Risk Level</th><th>Status</th><th>Actions</th></tr></thead>
          <tbody>{rows.map(item => <tr key={item.id} className={selectedId === item.id ? "selected" : ""}
            tabIndex={0} onClick={() => onSelect(item.id)} onKeyDown={event => {
              if (event.key === "Enter" || event.key === " ") onSelect(item.id);
            }}>
            <td onClick={event => event.stopPropagation()}><input type="checkbox" aria-label={"Select " + item.id} /></td>
            <td><strong>{item.screening_id}</strong></td>
            <td><div className="sm-user-cell"><Avatar name={item.user.full_name} size={34} />
              <span><b>{item.user.full_name}</b><small>{item.user_id}</small></span></div></td>
            <td>{fmtDateTime(item.screening_date)}</td><td>{item.assessment_type}</td>
            <td><strong>{item.score}</strong></td><td><RiskBadge value={item.risk_level} /></td>
            <td><ScreeningStatusBadge value={item.status} /></td>
            <td><button type="button" className="icon-button" onClick={event => {
              event.stopPropagation(); onSelect(item.id);
            }} aria-label={"View " + item.id}>→</button></td>
          </tr>)}</tbody>
        </table></div>}
      <Pagination page={pageData?.page || 1} pageSize={pageData?.page_size || 10}
        total={pageData?.total || 0} onChange={onPage} />
    </section>
  );
}
