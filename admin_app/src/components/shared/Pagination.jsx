export default function Pagination({ page, pageSize, total, onChange }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (pages <= 1) return null;
  return (
    <div className="pager">
      <button className="pager-btn" disabled={page <= 1} onClick={() => onChange(page - 1)}>‹</button>
      <span className="pager-summary">Page {page}/{pages} · {total} results</span>
      <button className="pager-btn" disabled={page >= pages} onClick={() => onChange(page + 1)}>›</button>
    </div>
  );
}
