import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

function Modal({ title, children, submitLabel, danger, open, busy, onClose, onSubmit }) {
  if (!open) return null;
  // Portal to body so the modal sits above the case detail drawer (which is
  // itself portaled to body at z-index 80) instead of behind it.
  return createPortal(
    <div className="modal-layer" role="dialog" aria-modal="true">
      <button className="modal-backdrop" onClick={onClose} aria-label="Close" />
      <form className="case-modal" onSubmit={onSubmit}><div className="case-modal-head">
        <h2>{title}</h2><button type="button" className="icon-button" onClick={onClose}>×</button></div>
        <div className="case-modal-body">{children}</div>
        <div className="case-modal-actions"><button type="button" className="btn" onClick={onClose}>Cancel</button>
          <button className={`btn ${danger ? "red" : "primary"}`} disabled={busy}>{submitLabel}</button></div>
      </form>
    </div>,
    document.body
  );
}

function TextActionModal({ open, mode, busy, onClose, onConfirm }) {
  const [text, setText] = useState("");
  useEffect(() => { if (open) setText(""); }, [open]);
  const config = {
    escalate: ["Escalate case", "Escalation reason", "Escalate", true],
    close: ["Close case", "Resolution code / closing reason", "Close case", true],
    note: ["Add note", "Note content", "Save note", false],
  }[mode];
  return <Modal open={open} title={config[0]} submitLabel={config[2]} danger={config[3]}
    busy={busy} onClose={onClose} onSubmit={(event) => { event.preventDefault(); onConfirm(text); }}>
    <label className="field-label">{config[1]}</label>
    <textarea className="textarea" rows={5} required value={text} onChange={event => setText(event.target.value)} />
    {mode === "note" && <p className="form-help">Notes are sent via the API for backend-side encryption.</p>}
  </Modal>;
}

export function AssignSpecialistModal({ open, specialists = [], busy, onClose, onConfirm }) {
  const [id, setId] = useState("");
  useEffect(() => { if (open) setId(""); }, [open]);
  return <Modal open={open} title="Assign specialist" submitLabel="Assign" busy={busy}
    onClose={onClose} onSubmit={event => { event.preventDefault(); onConfirm(id); }}>
    <label className="field-label">Assigned specialist</label>
    <select className="select block" required value={id} onChange={event => setId(event.target.value)}>
      <option value="">Select a specialist</option>{specialists.map(item =>
        <option key={item.id} value={item.id}>{item.display_name}</option>)}
    </select>
  </Modal>;
}
export const EscalateCaseModal = (props) => <TextActionModal {...props} mode="escalate" />;
export const CloseCaseModal = (props) => <TextActionModal {...props} mode="close" />;
export const AddCaseNoteModal = (props) => <TextActionModal {...props} mode="note" />;
