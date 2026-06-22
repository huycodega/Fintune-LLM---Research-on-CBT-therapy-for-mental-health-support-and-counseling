import { useState, useEffect } from "react";
import { api } from "../api.js";
import ContentFormModal from "../admin/ContentFormModal.jsx";
import ConfirmDialog from "../admin/ConfirmDialog.jsx";

const DEFAULT_SLOTS = ["09:00", "10:00", "11:00", "14:00", "15:00", "16:00"];

const EXPERT_FIELDS = [
  { name: "name", label: "Name", type: "text", required: true, placeholder: "Dr. Mai Lan" },
  { name: "specialty", label: "Specialty", type: "text", half: true, placeholder: "Anxiety, Trauma…" },
  { name: "phone", label: "Phone", type: "text", half: true, placeholder: "09xx xxx xxx" },
  { name: "experience", label: "Experience", type: "textarea", rows: 2, placeholder: "8 years · CBT for anxiety & trauma" },
  { name: "bio", label: "Bio", type: "textarea", rows: 3, placeholder: "Short professional bio shown to users." },
  { name: "slots", label: "Daily time slots", type: "tags", help: "Comma-separated, e.g. 09:00, 10:00, 14:00", placeholder: "09:00, 10:00, 14:00" },
  { name: "active", label: "Active (bookable by users)", type: "checkbox", help: "Uncheck to hide from booking" },
];

const ST_TONE = { pending: "amber", accepted: "green", cancelled: "gray", declined: "red" };

export default function ExpertsAdmin() {
  const [experts, setExperts] = useState([]);
  const [appts, setAppts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [formItem, setFormItem] = useState(null);   // null|{}|expert
  const [confirmDel, setConfirmDel] = useState(null);  // expert pending delete
  const [delBusy, setDelBusy] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const [e, a] = await Promise.all([api.experts(), api.appointments()]);
      setExperts(e.experts || []);
      setAppts(a.appointments || []);
      setErr("");
    } catch (ex) { setErr(ex.message); }
    finally { setLoading(false); }
  }
  useEffect(() => { load(); }, []);

  // Light refreshes after an action — update only what changed, with no
  // loading flash and no needless re-fetch of the other list.
  async function refreshExperts() {
    try { const e = await api.experts(); setExperts(e.experts || []); } catch { /* ignore */ }
  }
  async function refreshAppts() {
    try { const a = await api.appointments(); setAppts(a.appointments || []); } catch { /* ignore */ }
  }

  function handleAdd() { setFormItem({ active: true, slots: DEFAULT_SLOTS }); }
  function handleEdit(e) { setFormItem(e); }

  async function handleSubmit(payload) {
    if (formItem.id) await api.updateExpert(formItem.id, payload);
    else await api.createExpert(payload);
    await refreshExperts();
  }
  function handleDelete(e) { setConfirmDel(e); }
  async function doDelete() {
    if (!confirmDel) return;
    setDelBusy(true);
    // Deleting an expert also removes their appointments, so refresh both.
    try { await api.deleteExpert(confirmDel.id); await Promise.all([refreshExperts(), refreshAppts()]); }
    catch (ex) { setErr(ex.message); }
    finally { setDelBusy(false); setConfirmDel(null); }
  }
  async function setStatus(a, status) {
    try { await api.setAppointmentStatus(a.id, status); await refreshAppts(); }
    catch (ex) { setErr(ex.message); }
  }

  return (
    <div className="ex-wrap">
      {/* Psychologists */}
      <div className="ex-section-head">
        <h2>Psychologists</h2>
        <button className="la-btn-primary" onClick={handleAdd}>＋ Add psychologist</button>
      </div>
      {err && <div className="ex-err">{err}</div>}
      {loading ? <p className="ex-muted">Loading…</p> : (
        <div className="ex-grid">
          {experts.length === 0 && <p className="ex-muted">No psychologists yet. Add one to let users book consultations.</p>}
          {experts.map((e) => (
            <div key={e.id} className="ex-card">
              <div className="ex-card-top">
                <div className="ex-avatar">{e.name.slice(0, 1).toUpperCase()}</div>
                <div className="ex-card-id">
                  <div className="ex-name">{e.name}{!e.active && <span className="ex-inactive"> · inactive</span>}</div>
                  <div className="ex-spec">{e.specialty || "—"}</div>
                </div>
              </div>
              {e.experience && <div className="ex-exp">{e.experience}</div>}
              <div className="ex-meta">📞 {e.phone || "—"}</div>
              <div className="ex-slots">
                {(e.slots || []).map((s) => <span key={s} className="ex-slot">{s}</span>)}
              </div>
              <div className="ex-card-actions">
                <button className="admin-btn sm" onClick={() => handleEdit(e)}>✏️ Edit</button>
                <button className="admin-btn sm danger" onClick={() => handleDelete(e)}>🗑 Delete</button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Appointments */}
      <div className="ex-section-head" style={{ marginTop: 28 }}>
        <h2>Appointments</h2>
      </div>
      <div className="ex-table-wrap">
        <table className="ex-table">
          <thead>
            <tr><th>User</th><th>Psychologist</th><th>Date</th><th>Time</th><th>Status</th><th>Actions</th></tr>
          </thead>
          <tbody>
            {appts.length === 0 && <tr><td colSpan={6} className="ex-muted" style={{ textAlign: "center", padding: 18 }}>No appointments yet.</td></tr>}
            {appts.map((a) => (
              <tr key={a.id}>
                <td>{a.user?.name || "—"}</td>
                <td>{a.psychologist?.name || "—"}</td>
                <td>{a.date}</td>
                <td>{a.slot}</td>
                <td><span className={`ex-pill ${ST_TONE[a.status] || "gray"}`}>{a.status}</span></td>
                <td className="ex-row-actions">
                  {a.status === "pending" && (
                    <button className="admin-btn sm" onClick={() => setStatus(a, "accepted")}>Accept</button>
                  )}
                  {(a.status === "pending" || a.status === "accepted") && (
                    <button className="admin-btn sm danger" onClick={() => setStatus(a, "cancelled")}>Cancel</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {formItem && (
        <ContentFormModal
          title={formItem.id ? "Edit psychologist" : "Add psychologist"}
          subtitle={formItem.id ? "Update this expert's profile." : "Add a counselling expert users can book."}
          fields={EXPERT_FIELDS}
          initial={formItem}
          submitLabel={formItem.id ? "Save changes" : "Create"}
          onSubmit={handleSubmit}
          onClose={() => setFormItem(null)}
        />
      )}

      <ConfirmDialog
        open={!!confirmDel}
        title="Delete psychologist?"
        message={confirmDel ? `Delete "${confirmDel.name}"? Their appointments will be removed too.` : ""}
        confirmLabel="Delete"
        danger
        busy={delBusy}
        onConfirm={doDelete}
        onCancel={() => setConfirmDel(null)}
      />
    </div>
  );
}
