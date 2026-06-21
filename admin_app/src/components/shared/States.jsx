export function LoadingState({ label = "Loading data…" }) {
  return <div className="state-view"><span className="state-spinner" />{label}</div>;
}
export function EmptyState({ title = "No data", description }) {
  return <div className="state-view"><b>{title}</b>{description && <span>{description}</span>}</div>;
}
export function ErrorState({ message, onRetry, forbidden = false }) {
  return (
    <div className="state-view state-error">
      <b>{forbidden ? "You do not have permission." : "Couldn't load data"}</b>
      {!forbidden && <span>{message}</span>}
      {onRetry && <button className="btn sm" onClick={onRetry}>Retry</button>}
    </div>
  );
}
