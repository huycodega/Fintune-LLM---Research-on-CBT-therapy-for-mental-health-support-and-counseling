export default function SearchInput({ value, onChange, placeholder = "Search...", ariaLabel = "Search" }) {
  return (
    <label className="sm-search-input">
      <span aria-hidden="true">⌕</span>
      <input aria-label={ariaLabel} value={value} onChange={event => onChange(event.target.value)}
        placeholder={placeholder} />
    </label>
  );
}
