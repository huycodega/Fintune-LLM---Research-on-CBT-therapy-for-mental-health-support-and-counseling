import { RISK_LEVELS } from "./aiModeration.types.js";

export default function ModerationFilters({
  search,
  onSearch,
  riskLevel,
  onRiskLevel,
  sortBy,
  onSortBy,
  sortOrder,
  onSortOrder,
}) {
  return (
    <section className="am-filter-card">
      <label className="am-filter-field am-filter-search">
        <span>Search sessions</span>
        <input
          value={search}
          onChange={(event) => onSearch(event.target.value)}
          placeholder="Search session, user, summary..."
        />
      </label>

      <label className="am-filter-field">
        <span>Risk Level</span>
        <select id="am-risk-filter" value={riskLevel} onChange={(event) => onRiskLevel(event.target.value)}>
          {RISK_LEVELS.map((option) => (
            <option key={option.value || "all"} value={option.value}>{option.label}</option>
          ))}
        </select>
      </label>

      <label className="am-filter-field">
        <span>Sort by</span>
        <select value={sortBy} onChange={(event) => onSortBy(event.target.value)}>
          <option value="createdAt">Created At</option>
          <option value="riskLevel">Risk Level</option>
        </select>
      </label>

      <label className="am-filter-field">
        <span>Order</span>
        <select value={sortOrder} onChange={(event) => onSortOrder(event.target.value)}>
          <option value="desc">Desc</option>
          <option value="asc">Asc</option>
        </select>
      </label>
    </section>
  );
}
