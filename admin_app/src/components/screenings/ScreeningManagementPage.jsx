import { useCallback, useEffect, useMemo, useState } from "react";
import { Avatar, displayName } from "../../ui.jsx";
import { getUser } from "../../api.js";
import { screeningsApi } from "../../services/screeningsApi.ts";
import ScreeningSummaryCards from "./ScreeningSummaryCards.jsx";
import ScreeningFilters from "./ScreeningFilters.jsx";
import ScreeningTable from "./ScreeningTable.jsx";
import ScreeningDetailDrawer from "./ScreeningDetailDrawer.jsx";
import ScreeningAnalytics from "./ScreeningAnalytics.jsx";
import AddNoteModal from "./AddNoteModal.jsx";

function nowText() {
  return new Date().toLocaleString("en-GB", {
    day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

const INITIAL_FILTERS = {
  from: "", to: "", risk_level: "", status: "",
  search_input: "", page: 1, page_size: 10,
  sort_by: "screening_date", sort_order: "desc",
};

export default function ScreeningManagementPage() {
  const admin = getUser();

  // ── data state ──
  const [filters, setFilters] = useState(INITIAL_FILTERS);
  const [globalSearch, setGlobalSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [pageData, setPageData] = useState(null);
  const [summary, setSummary] = useState({});
  const [analytics, setAnalytics] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);

  // ── UI state ──
  const [loading, setLoading] = useState(true);
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState(null);
  const [exporting, setExporting] = useState(false);
  const [noteModal, setNoteModal] = useState(false);
  const [noteBusy, setNoteBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [lastUpdated, setLastUpdated] = useState(nowText());

  // ── debounce filter search (300ms) ──
  useEffect(() => {
    const timer = setTimeout(() => {
      setFilters(prev => ({ ...prev, search_input: globalSearch.trim(), page: 1 }));
    }, 300);
    return () => clearTimeout(timer);
  }, [globalSearch]);

  // ── debounce inline search ──
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(filters.search_input), 300);
    return () => clearTimeout(timer);
  }, [filters.search_input]);

  // ── query object ──
  const query = useMemo(() => ({
    ...filters,
    search: debouncedSearch || filters.search_input,
  }), [filters, debouncedSearch]);

  // ── loaders ──
  const loadList = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const data = await screeningsApi.list(query);
      setPageData(data);
      setLastUpdated(nowText());
    } catch (err) { setError(err); }
    finally { setLoading(false); }
  }, [query]);

  const loadSummary = useCallback(async () => {
    setSummaryLoading(true);
    try { setSummary(await screeningsApi.summary()); }
    catch { setSummary({}); }
    finally { setSummaryLoading(false); }
  }, []);

  const loadAnalytics = useCallback(async () => {
    try { setAnalytics(await screeningsApi.analytics()); }
    catch { setAnalytics(null); }
  }, []);

  const loadDetail = useCallback(async (id) => {
    if (!id) { setDetail(null); return; }
    setDetailLoading(true);
    try { setDetail(await screeningsApi.detail(id)); }
    catch { setDetail(null); }
    finally { setDetailLoading(false); }
  }, []);

  // ── effects ──
  useEffect(() => { loadList(); }, [loadList]);
  useEffect(() => { loadSummary(); loadAnalytics(); }, [loadSummary, loadAnalytics]);
  useEffect(() => { if (selectedId) loadDetail(selectedId); }, [selectedId, loadDetail]);

  // ── sort handler ──
  function handleSort(field) {
    setFilters(prev => ({
      ...prev,
      sort_by: field,
      sort_order: prev.sort_by === field && prev.sort_order === "asc" ? "desc" : "asc",
      page: 1,
    }));
  }

  // ── export CSV ──
  async function handleExport() {
    setExporting(true);
    try {
      const rows = await screeningsApi.exportCsv(query);
      const headers = ["Screening ID", "User", "Date", "Assessment Type", "Score", "Risk Level", "Status"];
      const csvRows = [
        headers.join(","),
        ...rows.map(r => [
          r.screening_id, r.user.full_name,
          new Date(r.screening_date).toLocaleDateString("en-GB"),
          r.assessment_type, r.score, r.risk_level, r.status,
        ].join(",")),
      ];
      const blob = new Blob([csvRows.join("\n")], { type: "text/csv" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `screenings_${new Date().toISOString().slice(0, 10)}.csv`;
      link.click();
      URL.revokeObjectURL(url);
      setNotice("Export completed successfully.");
    } catch { setNotice("Export failed. Please try again."); }
    finally { setExporting(false); }
  }

  // ── add note ──
  async function handleAddNote(content) {
    if (!selectedId) return;
    setNoteBusy(true);
    try {
      await screeningsApi.addNote(selectedId, content);
      setNoteModal(false);
      setNotice("Note saved successfully.");
      await loadDetail(selectedId);
    } catch { setNotice("Failed to save note."); }
    finally { setNoteBusy(false); }
  }

  return (
    <div className="sm-page">
      {/* ── Header ── */}
      <header className="sm-header">
        <div>
          <h1>Screening Management</h1>
          <p>Last updated: {lastUpdated}</p>
        </div>
        <div className="sm-header-tools">
          <div className="sm-header-search">
            <span aria-hidden="true">🔍</span>
            <input
              value={globalSearch}
              onChange={e => setGlobalSearch(e.target.value)}
              placeholder="Search screenings..."
            />
          </div>
          <button
            type="button"
            className="sm-ghost-btn"
            onClick={() => document.getElementById("sm-risk-filter")?.focus()}
          >
            ☰ Filter
          </button>
          <button type="button" className="sm-ghost-btn" title="Notifications" style={{ position: "relative" }}>
            🔔
            <span style={{
              position: "absolute", top: -4, right: -4, minWidth: 18, height: 18,
              borderRadius: 9, background: "#dc2626", color: "#fff", fontSize: 10,
              fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "center",
              border: "2px solid #fff",
            }}>3</span>
          </button>
          <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
            <Avatar name={admin?.username || "Admin"} size={38} className="am-avatar" />
            <div style={{ textAlign: "left", lineHeight: 1.25 }}>
              <b style={{ display: "block", fontSize: 13.5, fontWeight: 700 }}>
                {displayName(admin?.username || "Admin")}
              </b>
              <small style={{ fontSize: 11.5, color: "#667085" }}>
                {admin?.role || "Administrator"}
              </small>
            </div>
          </div>
        </div>
      </header>

      {/* ── KPI Cards ── */}
      <ScreeningSummaryCards summary={summary} loading={summaryLoading} />

      {/* ── Notice ── */}
      {notice && (
        <div className="sm-notice">
          {notice}
          <button onClick={() => setNotice("")}>×</button>
        </div>
      )}

      {/* ── Filters ── */}
      <ScreeningFilters
        value={filters}
        onChange={setFilters}
        onExport={handleExport}
        exporting={exporting}
        onAddNote={() => setNoteModal(true)}
        canAddNote={!!selectedId}
      />

      {/* ── Table ── */}
      <ScreeningTable
        pageData={pageData}
        selectedId={selectedId}
        onSelect={setSelectedId}
        loading={loading}
        error={error}
        onRetry={loadList}
        onPage={page => setFilters(prev => ({ ...prev, page }))}
        onSort={handleSort}
        sortBy={filters.sort_by}
        sortOrder={filters.sort_order}
      />

      {/* ── Detail Drawer (renders its own scrim, portaled to body) ── */}
      <ScreeningDetailDrawer
        open={!!selectedId}
        detail={detail}
        loading={detailLoading}
        onClose={() => setSelectedId(null)}
        onAddNote={() => setNoteModal(true)}
      />

      {/* ── Analytics ── */}
      <ScreeningAnalytics data={analytics} />

      {/* ── Add Note Modal ── */}
      <AddNoteModal
        open={noteModal}
        busy={noteBusy}
        onClose={() => setNoteModal(false)}
        onSubmit={handleAddNote}
      />
    </div>
  );
}
