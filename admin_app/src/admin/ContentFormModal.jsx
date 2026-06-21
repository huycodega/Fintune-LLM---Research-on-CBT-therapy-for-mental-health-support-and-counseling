import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import Icon from "./Icon.jsx";

/* ------------------------------------------------------------------ *
 * ContentFormModal — a config-driven modal data-entry form.
 *
 * Replaces the old window.prompt() flow on the Resources / Lessons
 * admin pages with a proper form: every field is labelled, typed and
 * validated before it ever hits the API.
 *
 * Props:
 *   title     — heading text ("Add Resource", "Edit Lesson"…)
 *   subtitle  — small helper line under the heading
 *   fields    — [{ name, label, type, options?, placeholder?, help?,
 *                  required?, half?, rows? }]
 *               type ∈ text | textarea | select | checkbox | tags | url | number
 *   initial   — initial values keyed by field name (for edit)
 *   submitLabel
 *   onSubmit  — async (values) => void ; throw to surface an error
 *   onClose   — () => void
 * ------------------------------------------------------------------ */
export default function ContentFormModal({
  title, subtitle, fields, initial = {}, submitLabel = "Save", onSubmit, onClose,
}) {
  const seed = {};
  for (const f of fields) {
    const v = initial[f.name];
    if (f.type === "tags") seed[f.name] = Array.isArray(v) ? v.join(", ") : (v || "");
    else if (f.type === "checkbox") seed[f.name] = !!v;
    else if (f.type === "select") {
      // A select must default to a real option, never "" — otherwise the form
      // submits an empty value that fails the backend's enum pattern.
      const first = typeof f.options[0] === "string" ? f.options[0] : f.options[0]?.value;
      seed[f.name] = v ?? first ?? "";
    }
    else seed[f.name] = v ?? "";
  }
  const [values, setValues] = useState(seed);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const firstRef = useRef(null);

  useEffect(() => { firstRef.current?.focus(); }, []);
  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape" && !busy) onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [busy, onClose]);

  function set(name, val) { setValues((v) => ({ ...v, [name]: val })); }

  async function submit(e) {
    e.preventDefault();
    setErr("");
    for (const f of fields) {
      if (f.required && !String(values[f.name] ?? "").trim()) {
        setErr(`${f.label} is required.`);
        return;
      }
    }
    // Normalise: split tag strings into arrays, trim text.
    const payload = {};
    for (const f of fields) {
      const raw = values[f.name];
      if (f.type === "tags") {
        payload[f.name] = String(raw || "")
          .split(",").map((t) => t.trim()).filter(Boolean);
      } else if (f.type === "checkbox") {
        payload[f.name] = !!raw;
      } else if (f.type === "number") {
        payload[f.name] = raw === "" ? null : Number(raw);
      } else {
        payload[f.name] = typeof raw === "string" ? raw.trim() : raw;
      }
    }
    setBusy(true);
    try {
      await onSubmit(payload);
      onClose();
    } catch (e2) {
      setErr(e2?.message || "Something went wrong. Please try again.");
      setBusy(false);
    }
  }

  return createPortal(
    <div className="la-modal-overlay" onMouseDown={(e) => { if (e.target === e.currentTarget && !busy) onClose(); }}>
      <div className="la-modal" role="dialog" aria-modal="true" aria-label={title}>
        <div className="la-modal-head">
          <div>
            <h2 className="la-modal-title">{title}</h2>
            {subtitle && <p className="la-modal-sub">{subtitle}</p>}
          </div>
          <button type="button" className="la-modal-x" onClick={onClose} disabled={busy} aria-label="Close">
            <Icon name="close" size={18} />
          </button>
        </div>

        <form className="la-modal-body" onSubmit={submit}>
          <div className="la-form-grid">
            {fields.map((f, i) => (
              <Field
                key={f.name}
                f={f}
                value={values[f.name]}
                onChange={(v) => set(f.name, v)}
                inputRef={i === 0 ? firstRef : null}
              />
            ))}
          </div>

          {err && <div className="la-modal-err"><Icon name="alert" size={14} /> {err}</div>}

          <div className="la-modal-foot">
            <button type="button" className="la-btn-ghost" onClick={onClose} disabled={busy}>Cancel</button>
            <button type="submit" className="la-btn-primary" disabled={busy}>
              {busy ? "Saving…" : submitLabel}
            </button>
          </div>
        </form>
      </div>
    </div>,
    document.body
  );
}

function Field({ f, value, onChange, inputRef }) {
  const cls = `la-field${f.half ? " la-field-half" : ""}`;

  if (f.type === "checkbox") {
    return (
      <label className={`${cls} la-field-check`}>
        <input
          ref={inputRef}
          type="checkbox"
          checked={!!value}
          onChange={(e) => onChange(e.target.checked)}
        />
        <span><strong>{f.label}</strong>{f.help && <em className="la-field-help"> — {f.help}</em>}</span>
      </label>
    );
  }

  return (
    <div className={cls}>
      <label className="la-field-label">
        {f.label}{f.required && <span className="la-req">*</span>}
      </label>
      {f.type === "textarea" ? (
        <textarea
          ref={inputRef}
          className="la-input"
          rows={f.rows || 4}
          placeholder={f.placeholder || ""}
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
      ) : f.type === "select" ? (
        <select ref={inputRef} className="la-input" value={value} onChange={(e) => onChange(e.target.value)}>
          {f.options.map((o) => {
            const val = typeof o === "string" ? o : o.value;
            const lab = typeof o === "string" ? o : o.label;
            return <option key={val} value={val}>{lab}</option>;
          })}
        </select>
      ) : (
        <input
          ref={inputRef}
          className="la-input"
          type={f.type === "url" ? "url" : f.type === "number" ? "number" : "text"}
          placeholder={f.placeholder || ""}
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
      )}
      {f.help && f.type !== "checkbox" && <span className="la-field-help">{f.help}</span>}
    </div>
  );
}
