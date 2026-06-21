export function LoadingState({ label = "Đang tải dữ liệu…" }) {
  return <div className="state-view"><span className="state-spinner" />{label}</div>;
}
export function EmptyState({ title = "Chưa có dữ liệu", description }) {
  return <div className="state-view"><b>{title}</b>{description && <span>{description}</span>}</div>;
}
export function ErrorState({ message, onRetry, forbidden = false }) {
  return (
    <div className="state-view state-error">
      <b>{forbidden ? "You do not have permission." : "Không thể tải dữ liệu"}</b>
      {!forbidden && <span>{message}</span>}
      {onRetry && <button className="btn sm" onClick={onRetry}>Thử lại</button>}
    </div>
  );
}
