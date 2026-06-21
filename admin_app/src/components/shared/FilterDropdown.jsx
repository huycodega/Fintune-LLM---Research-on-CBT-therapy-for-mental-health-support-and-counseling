export default function FilterDropdown({ label, value, onChange, options, id }) {
  return (
    <label className="sm-filter-field">
      <span>{label}</span>
      <select id={id} value={value} onChange={event => onChange(event.target.value)}>
        {options.map(option => <option key={option.value || "all"} value={option.value}>{option.label}</option>)}
      </select>
    </label>
  );
}
