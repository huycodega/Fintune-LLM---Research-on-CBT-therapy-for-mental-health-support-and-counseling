import { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import { api } from "../api.js";

const WD = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

function iso(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
function fmtDate(isoStr) {
  if (!isoStr) return "";
  return new Date(isoStr + "T00:00:00").toLocaleDateString("en-GB",
    { weekday: "short", day: "numeric", month: "short" });
}
function buildDays(fromISO, toISO) {
  const out = [];
  const s = new Date(fromISO + "T00:00:00");
  const e = new Date(toISO + "T00:00:00");
  for (let d = new Date(s); d <= e; d.setDate(d.getDate() + 1)) out.push(new Date(d));
  return out;
}

export default function TuVan() {
  const [experts, setExperts] = useState([]);
  const [appts, setAppts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [booking, setBooking] = useState(null);   // { expert, avail, editingId }
  const [selDate, setSelDate] = useState("");
  const [msg, setMsg] = useState(null);           // { type, text }
  const [confirmA, setConfirmA] = useState(null); // appointment pending cancel

  async function loadAll() {
    setLoading(true);
    try {
      const [e, a] = await Promise.all([api.experts(), api.myAppointments()]);
      setExperts(e.experts || []);
      setAppts(a.appointments || []);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }
  useEffect(() => { loadAll(); }, []);

  // Light refresh after booking/cancelling — update only the appointments,
  // without re-fetching the expert list or flashing the loading state.
  async function refreshAppts() {
    try { const a = await api.myAppointments(); setAppts(a.appointments || []); }
    catch { /* ignore */ }
  }

  async function openBooking(expertId, editingId = null) {
    setMsg(null);
    try {
      const av = await api.expertAvailability(expertId);
      setBooking({ expert: av.expert, avail: av, editingId });
      setSelDate("");
    } catch (e) { setMsg({ type: "err", text: e.message }); }
  }

  function freeSlots(date) {
    if (!booking) return [];
    const taken = (booking.avail.booked || []).filter((b) => b.date === date).map((b) => b.slot);
    return (booking.expert.slots || []).filter((s) => !taken.includes(s));
  }

  async function pickSlot(date, slot) {
    try {
      if (booking.editingId) {
        await api.changeAppointment(booking.editingId, { date, slot });
        setMsg({ type: "ok", text: "Appointment updated ✓" });
      } else {
        await api.bookAppointment({ psychologist_id: booking.expert.id, date, slot });
        setMsg({ type: "ok", text: "Booked ✓ — pending the expert's confirmation." });
      }
      setBooking(null); setSelDate("");
      await refreshAppts();
    } catch (e) { setMsg({ type: "err", text: e.message }); }
  }

  async function doCancel(a) {
    setConfirmA(null);
    try { await api.cancelAppointment(a.id); setMsg({ type: "ok", text: "Appointment cancelled." }); await refreshAppts(); }
    catch (e) { setMsg({ type: "err", text: e.message }); }
  }

  return (
    <div className="tv-page">
      <header className="tv-header">
        <h1>Talk to a psychologist</h1>
        <p>Book a 1:1 consultation with a licensed expert. You can reschedule or cancel while it's still pending.</p>
      </header>

      {msg && <div className={`tv-banner ${msg.type}`}>{msg.text}</div>}

      {/* My appointments */}
      {appts.length > 0 && (
        <section className="tv-section">
          <h2 className="tv-h2">Your appointments</h2>
          <div className="tv-appts">
            {appts.map((a) => (
              <div key={a.id} className="tv-appt">
                <div className="tv-appt-main">
                  <div className="tv-appt-name">{a.psychologist?.name || "Psychologist"}
                    {a.psychologist?.specialty ? <span className="tv-appt-spec"> · {a.psychologist.specialty}</span> : null}</div>
                  <div className="tv-appt-when">📅 {fmtDate(a.date)} &nbsp; 🕐 {a.slot}</div>
                  {a.psychologist?.phone && <div className="tv-appt-phone">📞 {a.psychologist.phone}</div>}
                </div>
                <div className="tv-appt-side">
                  <span className={`tv-pill ${a.status}`}>{a.status}</span>
                  {a.status === "pending" && (
                    <div className="tv-appt-actions">
                      <button className="tv-btn-ghost" onClick={() => openBooking(a.psychologist_id, a.id)}>Change</button>
                      <button className="tv-btn-ghost danger" onClick={() => setConfirmA(a)}>Cancel</button>
                    </div>
                  )}
                  {a.status === "accepted" && <span className="tv-locked">Confirmed — contact the expert to change</span>}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Experts */}
      <section className="tv-section">
        <h2 className="tv-h2">Choose a psychologist</h2>
        {loading ? <p className="tv-muted">Loading…</p> : (
          experts.length === 0 ? <p className="tv-muted">No psychologists are available right now. Please check back soon or use the hotline.</p> : (
            <div className="tv-experts">
              {experts.map((e) => (
                <div key={e.id} className="tv-expert">
                  <div className="tv-expert-top">
                    <div className="tv-avatar">{e.name.slice(0, 1).toUpperCase()}</div>
                    <div>
                      <div className="tv-expert-name">{e.name}</div>
                      <div className="tv-expert-spec">{e.specialty || "Counselling"}</div>
                    </div>
                  </div>
                  {e.experience && <p className="tv-expert-exp">{e.experience}</p>}
                  {e.phone && <div className="tv-expert-phone">📞 {e.phone}</div>}
                  <button className="tv-btn-primary" onClick={() => openBooking(e.id)}>Book a consultation</button>
                </div>
              ))}
            </div>
          )
        )}
      </section>

      {/* Booking modal */}
      {booking && (
        <BookingModal
          booking={booking}
          selDate={selDate}
          onSelDate={setSelDate}
          freeSlots={freeSlots}
          onPick={pickSlot}
          onClose={() => { setBooking(null); setSelDate(""); }}
        />
      )}

      {/* Cancel confirmation (in-app, not the browser dialog) */}
      {confirmA && createPortal(
        <div className="lx-overlay lx-overlay-center" onMouseDown={(e) => { if (e.target === e.currentTarget) setConfirmA(null); }}>
          <div className="lx-modal tv-confirm" role="dialog" aria-modal="true">
            <h2 className="lx-title">Cancel this appointment?</h2>
            <p className="lx-desc">
              {confirmA.psychologist?.name} · {fmtDate(confirmA.date)} at {confirmA.slot}.
              This can't be undone, but you can book again anytime.
            </p>
            <div className="tv-confirm-actions">
              <button className="tv-btn-ghost" onClick={() => setConfirmA(null)}>Keep it</button>
              <button className="tv-btn-danger" onClick={() => doCancel(confirmA)}>Yes, cancel</button>
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}

function BookingModal({ booking, selDate, onSelDate, freeSlots, onPick, onClose }) {
  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const days = buildDays(booking.avail.window.from, booking.avail.window.to);
  const pad = days.length ? days[0].getDay() : 0;
  const slots = selDate ? freeSlots(selDate) : [];

  return createPortal(
    <div className="lx-overlay" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="lx-modal tv-modal" role="dialog" aria-modal="true">
        <button className="lx-close" onClick={onClose} aria-label="Close">✕</button>
        <h2 className="lx-title">{booking.editingId ? "Reschedule with " : "Book with "}{booking.expert.name}</h2>
        <div className="lx-meta">
          {booking.expert.specialty && <span>{booking.expert.specialty}</span>}
          <span>Pick a free day (next 3 weeks) — red = full</span>
        </div>

        <div className="tv-cal">
          <div className="tv-cal-grid tv-cal-head">
            {WD.map((w) => <div key={w} className="tv-cal-wd">{w}</div>)}
          </div>
          <div className="tv-cal-grid">
            {Array.from({ length: pad }).map((_, i) => <div key={"p" + i} />)}
            {days.map((d) => {
              const ds = iso(d);
              const free = freeSlots(ds).length;
              const full = free === 0;
              return (
                <button
                  key={ds}
                  className={`tv-day ${full ? "full" : ""} ${selDate === ds ? "sel" : ""}`}
                  disabled={full}
                  onClick={() => onSelDate(ds)}
                  title={full ? "Fully booked" : `${free} slot(s) free`}
                >
                  <span className="tv-day-num">{d.getDate()}</span>
                  {!full && <span className="tv-day-dot" />}
                </button>
              );
            })}
          </div>
          <div className="tv-cal-legend">
            <span><i className="tv-lg free" /> Available</span>
            <span><i className="tv-lg full" /> Full</span>
          </div>
        </div>

        {selDate && (
          <div className="tv-slots-wrap">
            <div className="tv-slots-label">Times on {fmtDate(selDate)}</div>
            {slots.length === 0 ? (
              <p className="tv-muted">No free slots that day — pick another.</p>
            ) : (
              <div className="tv-slots">
                {slots.map((s) => (
                  <button key={s} className="tv-slot" onClick={() => onPick(selDate, s)}>{s}</button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>,
    document.body
  );
}
