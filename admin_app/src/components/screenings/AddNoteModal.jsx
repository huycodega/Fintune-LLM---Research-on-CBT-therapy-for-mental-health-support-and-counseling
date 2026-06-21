import { useEffect, useState } from "react";
export default function AddNoteModal({ open, busy, onClose, onSubmit }) {
  const [content, setContent] = useState("");
  useEffect(() => { if (open) setContent(""); }, [open]);
  if (!open) return null;
  return <div className="modal-layer" role="dialog" aria-modal="true">
    <button className="modal-backdrop" onClick={onClose} aria-label="Close" />
    <form className="case-modal" onSubmit={event => { event.preventDefault(); onSubmit(content); }}>
      <div className="case-modal-head"><h2>Add Screening Note</h2>
        <button type="button" className="icon-button" onClick={onClose}>×</button></div>
      <div className="case-modal-body"><label className="field-label">Internal note</label>
        <textarea className="textarea" rows={5} required value={content}
          onChange={event => setContent(event.target.value)} /></div>
      <div className="case-modal-actions"><button type="button" className="btn" onClick={onClose}>Cancel</button>
        <button className="btn primary" disabled={busy}>{busy ? "Saving..." : "Save Note"}</button></div>
    </form>
  </div>;
}
