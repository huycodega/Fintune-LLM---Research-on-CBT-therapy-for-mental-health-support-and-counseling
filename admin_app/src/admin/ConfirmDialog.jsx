import { createPortal } from "react-dom";

/* In-app confirmation dialog — replaces the native window.confirm(). */
export default function ConfirmDialog({
  open, title = "Are you sure?", message, confirmLabel = "Confirm",
  danger = false, busy = false, onConfirm, onCancel,
}) {
  if (!open) return null;
  return createPortal(
    <div className="la-modal-overlay" onMouseDown={(e) => { if (e.target === e.currentTarget && !busy) onCancel(); }}>
      <div className="la-modal la-confirm" role="dialog" aria-modal="true">
        <div className="la-modal-head">
          <div><h2 className="la-modal-title">{title}</h2></div>
        </div>
        <div className="la-modal-body">
          {message && <p className="la-confirm-msg">{message}</p>}
          <div className="la-modal-foot">
            <button className="la-btn-ghost" onClick={onCancel} disabled={busy}>Cancel</button>
            <button className={danger ? "la-btn-danger" : "la-btn-primary"} onClick={onConfirm} disabled={busy}>
              {busy ? "Working…" : confirmLabel}
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body
  );
}
