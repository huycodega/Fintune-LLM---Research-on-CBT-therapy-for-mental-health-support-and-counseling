export default function DateRangePicker({ value, onChange }) {
  return (
    <div className="date-range">
      <input className="input" type="date" value={value.from || ""}
             onChange={(event) => onChange({ ...value, from: event.target.value })} />
      <span>—</span>
      <input className="input" type="date" value={value.to || ""}
             onChange={(event) => onChange({ ...value, to: event.target.value })} />
    </div>
  );
}
