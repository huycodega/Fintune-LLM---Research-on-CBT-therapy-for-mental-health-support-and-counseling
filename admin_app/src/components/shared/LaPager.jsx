import Icon from "../../admin/Icon.jsx";

// Build a compact page list with ellipses, e.g. 1 … 4 5 6 … 12
function pageList(page, pages) {
  if (pages <= 7) return Array.from({ length: pages }, (_, i) => i + 1);
  const out = [1];
  if (page > 3) out.push("…");
  for (let i = Math.max(2, page - 1); i <= Math.min(pages - 1, page + 1); i++) out.push(i);
  if (page < pages - 2) out.push("…");
  out.push(pages);
  return out;
}

/* Functional numbered pager shared across admin tables (matches .la-page-*). */
export default function LaPager({ page, pageSize, total, onChange, noun = "items" }) {
  const pages = Math.max(1, Math.ceil((total || 0) / pageSize));
  if (pages <= 1) return null;
  const from = (page - 1) * pageSize + 1;
  const to = Math.min(total, page * pageSize);
  return (
    <div className="la-pagination">
      <div className="la-page-info">Showing {from}–{to} of {total} {noun}</div>
      <div className="la-page-controls">
        <button type="button" className="la-page-btn" disabled={page <= 1}
                onClick={() => onChange(page - 1)} aria-label="Previous page">
          <Icon name="chevronLeft" size={15} />
        </button>
        {pageList(page, pages).map((p, i) =>
          p === "…" ? (
            <button key={`e${i}`} type="button" className="la-page-btn ellipsis" disabled>…</button>
          ) : (
            <button key={p} type="button"
                    className={`la-page-btn ${p === page ? "active" : ""}`}
                    onClick={() => onChange(p)}>{p}</button>
          ))}
        <button type="button" className="la-page-btn" disabled={page >= pages}
                onClick={() => onChange(page + 1)} aria-label="Next page">
          <Icon name="chevronRight" size={15} />
        </button>
      </div>
    </div>
  );
}
