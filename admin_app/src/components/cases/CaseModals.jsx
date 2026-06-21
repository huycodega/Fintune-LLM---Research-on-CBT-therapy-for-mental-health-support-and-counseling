import { useEffect, useState } from "react";

function Modal({ title, children, submitLabel, danger, open, busy, onClose, onSubmit }) {
  if (!open) return null;
  return <div className="modal-layer" role="dialog" aria-modal="true">
    <button className="modal-backdrop" onClick={onClose} aria-label="Đóng" />
    <form className="case-modal" onSubmit={onSubmit}><div className="case-modal-head">
      <h2>{title}</h2><button type="button" className="icon-button" onClick={onClose}>×</button></div>
      <div className="case-modal-body">{children}</div>
      <div className="case-modal-actions"><button type="button" className="btn" onClick={onClose}>Hủy</button>
        <button className={`btn ${danger ? "red" : "primary"}`} disabled={busy}>{submitLabel}</button></div>
    </form>
  </div>;
}

function TextActionModal({ open, mode, busy, onClose, onConfirm }) {
  const [text, setText] = useState("");
  useEffect(() => { if (open) setText(""); }, [open]);
  const config = {
    escalate: ["Chuyển cấp ca", "Lý do chuyển cấp", "Chuyển cấp", true],
    close: ["Đóng ca", "Resolution code / lý do đóng", "Đóng ca", true],
    note: ["Thêm ghi chú", "Nội dung ghi chú", "Lưu ghi chú", false],
  }[mode];
  return <Modal open={open} title={config[0]} submitLabel={config[2]} danger={config[3]}
    busy={busy} onClose={onClose} onSubmit={(event) => { event.preventDefault(); onConfirm(text); }}>
    <label className="field-label">{config[1]}</label>
    <textarea className="textarea" rows={5} required value={text} onChange={event => setText(event.target.value)} />
    {mode === "note" && <p className="form-help">Ghi chú được gửi qua API để mã hóa phía backend.</p>}
  </Modal>;
}

export function AssignSpecialistModal({ open, specialists = [], busy, onClose, onConfirm }) {
  const [id, setId] = useState("");
  useEffect(() => { if (open) setId(""); }, [open]);
  return <Modal open={open} title="Phân công chuyên viên" submitLabel="Phân công" busy={busy}
    onClose={onClose} onSubmit={event => { event.preventDefault(); onConfirm(id); }}>
    <label className="field-label">Chuyên viên phụ trách</label>
    <select className="select block" required value={id} onChange={event => setId(event.target.value)}>
      <option value="">Chọn chuyên viên</option>{specialists.map(item =>
        <option key={item.id} value={item.id}>{item.display_name}</option>)}
    </select>
  </Modal>;
}
export const EscalateCaseModal = (props) => <TextActionModal {...props} mode="escalate" />;
export const CloseCaseModal = (props) => <TextActionModal {...props} mode="close" />;
export const AddCaseNoteModal = (props) => <TextActionModal {...props} mode="note" />;
