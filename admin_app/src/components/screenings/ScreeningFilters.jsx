import DateRangePicker from "../shared/DateRangePicker.jsx";
import SearchInput from "../shared/SearchInput.jsx";
import FilterDropdown from "../shared/FilterDropdown.jsx";

export function ExportButton({ onClick, busy }) {
  return <button type="button" className="sm-ghost-btn" onClick={onClick} disabled={busy}>⇩ Export</button>;
}

export default function ScreeningFilters({ value, onChange, onExport, onAddNote, canAddNote, exporting }) {
  const set = key => next => onChange({ ...value, [key]: next, page: 1 });
  return (
    <section className="sm-filter-card">
      <label className="sm-filter-field"><span>Date Range</span>
        <DateRangePicker value={value} onChange={range => onChange({ ...value, ...range, page: 1 })} />
      </label>
      <FilterDropdown label="Risk Level" value={value.risk_level} onChange={set("risk_level")}
        options={[{ value: "", label: "All Levels" }, ...["L0","L1","L2","L3"].map(item => ({ value: item, label: item }))]} />
      <FilterDropdown label="Status" value={value.status} onChange={set("status")}
        options={[{ value: "", label: "All Statuses" }, { value: "completed", label: "Completed" },
          { value: "pending", label: "Pending" }, { value: "in_progress", label: "In Progress" },
          { value: "expired", label: "Expired" }, { value: "cancelled", label: "Cancelled" }]} />
      <div className="sm-filter-field sm-filter-search"><span>Search</span>
        <SearchInput value={value.search_input} onChange={set("search_input")} placeholder="Screening ID or user..." />
      </div>
      <div className="sm-filter-actions">
        <ExportButton onClick={onExport} busy={exporting} />
        <button type="button" className="sm-primary-btn" onClick={onAddNote} disabled={!canAddNote}>＋ Add Note</button>
      </div>
    </section>
  );
}
