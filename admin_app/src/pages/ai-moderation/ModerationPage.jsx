import { useCallback, useEffect, useMemo, useState } from "react";
import { Avatar, displayName } from "../../ui.jsx";
import { getUser } from "../../api.js";
import { aiModerationApi } from "./aiModeration.service.js";
import ModerationDetailPanel from "./ModerationDetailPanel.jsx";
import ModerationFilters from "./ModerationFilters.jsx";
import ModerationStats from "./ModerationStats.jsx";
import ModerationTable from "./ModerationTable.jsx";
import ModerationHistory from "./ModerationHistory.jsx";

function nowText() {
  return new Date().toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function ModerationPage() {
  const admin = getUser();
  const [stats, setStats] = useState(null);
  const [statsLoading, setStatsLoading] = useState(false);
  const [sessions, setSessions] = useState([]);
  const [pagination, setPagination] = useState({ page: 1, limit: 10, total: 0, totalPages: 1 });
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [riskLevel, setRiskLevel] = useState("");
  const [sortBy, setSortBy] = useState("createdAt");
  const [sortOrder, setSortOrder] = useState("desc");
  const [selectedId, setSelectedId] = useState(null);
  const [selectedRows, setSelectedRows] = useState([]);
  const [detail, setDetail] = useState(null);
  const [listLoading, setListLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [actionBusy, setActionBusy] = useState(false);
  const [listError, setListError] = useState("");
  const [detailError, setDetailError] = useState("");
  const [lastUpdated, setLastUpdated] = useState(nowText());
  const [view, setView] = useState("queue");          // queue | history
  const [history, setHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState("");

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search.trim()), 300);
    return () => clearTimeout(timer);
  }, [search]);

  useEffect(() => setPage(1), [debouncedSearch, riskLevel, sortBy, sortOrder]);

  const query = useMemo(() => ({
    search: debouncedSearch,
    riskLevel,
    page,
    limit: 10,
    sortBy,
    sortOrder,
  }), [debouncedSearch, riskLevel, page, sortBy, sortOrder]);

  const loadStats = useCallback(async () => {
    setStatsLoading(true);
    try {
      setStats(await aiModerationApi.stats());
    } finally {
      setStatsLoading(false);
    }
  }, []);

  const loadList = useCallback(async () => {
    setListLoading(true);
    setListError("");
    try {
      const data = await aiModerationApi.sessions(query);
      setSessions(data.items || []);
      setPagination(data.pagination || { page, limit: 10, total: 0, totalPages: 1 });
      setSelectedRows((rows) => rows.filter((id) => (data.items || []).some((item) => item.id === id)));
      setSelectedId((current) => {
        if (current && (data.items || []).some((item) => item.id === current)) return current;
        return data.items?.[0]?.id || null;
      });
      setLastUpdated(nowText());
    } catch (error) {
      setSessions([]);
      setListError(error.message || "Could not load moderation sessions");
    } finally {
      setListLoading(false);
    }
  }, [query, page]);

  const loadDetail = useCallback(async (id = selectedId) => {
    if (!id) {
      setDetail(null);
      return;
    }
    setDetailLoading(true);
    setDetailError("");
    try {
      setDetail(await aiModerationApi.detail(id));
    } catch (error) {
      setDetail(null);
      setDetailError(error.message || "Could not load session detail");
    } finally {
      setDetailLoading(false);
    }
  }, [selectedId]);

  useEffect(() => {
    loadStats().catch(() => setStats(null));
  }, [loadStats]);

  useEffect(() => {
    loadList();
  }, [loadList]);

  useEffect(() => {
    loadDetail(selectedId);
  }, [selectedId, loadDetail]);

  const loadHistory = useCallback(async () => {
    setHistoryLoading(true);
    setHistoryError("");
    try {
      setHistory(await aiModerationApi.history());
    } catch (error) {
      setHistory([]);
      setHistoryError(error.message || "Could not load history");
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  useEffect(() => {
    if (view === "history") loadHistory();
  }, [view, loadHistory]);

  function toggleRow(id, checked) {
    setSelectedRows((rows) => checked ? [...new Set([...rows, id])] : rows.filter((rowId) => rowId !== id));
  }

  function toggleAll(checked) {
    setSelectedRows(checked ? sessions.map((session) => session.id) : []);
  }

  async function refreshAfterAction() {
    await Promise.all([loadStats(), loadList()]);
    await loadDetail(selectedId);
  }

  async function runAction(action) {
    if (!selectedId) return;
    setActionBusy(true);
    try {
      await action();
      await refreshAfterAction();
    } catch (error) {
      alert(error.message || "Action failed");
    } finally {
      setActionBusy(false);
    }
  }

  return (
    <div className="am-page">
      <header className="am-header">
        <div>
          <h1>AI Moderation</h1>
          <p>Updated {lastUpdated}</p>
        </div>
        <div className="am-header-tools">
          <div className="am-header-search">
            <span aria-hidden="true">Search</span>
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search sessions..."
            />
          </div>
          <button type="button" className="am-filter-button" onClick={() => document.getElementById("am-risk-filter")?.focus()}>
            Filters
          </button>
          <div className="am-admin-chip">
            <Avatar name={admin?.username || "Admin"} size={36} className="am-avatar" />
            <span>
              <strong>{displayName(admin?.username || "Admin")}</strong>
              <small>{admin?.role || "ADMIN"}</small>
            </span>
          </div>
        </div>
      </header>

      <div className="am-tabs">
        <button type="button" className={`am-tab ${view === "queue" ? "active" : ""}`} onClick={() => setView("queue")}>
          Pending queue
        </button>
        <button type="button" className={`am-tab ${view === "history" ? "active" : ""}`} onClick={() => setView("history")}>
          Processed history
        </button>
      </div>

      <ModerationStats stats={stats} loading={statsLoading} />

      {view === "queue" ? (
        <>
          <ModerationFilters
            search={search}
            onSearch={setSearch}
            riskLevel={riskLevel}
            onRiskLevel={setRiskLevel}
            sortBy={sortBy}
            onSortBy={setSortBy}
            sortOrder={sortOrder}
            onSortOrder={setSortOrder}
          />

          <div className="am-workspace">
            <ModerationTable
              sessions={sessions}
              selectedId={selectedId}
              onSelect={setSelectedId}
              selectedRows={selectedRows}
              onToggleRow={toggleRow}
              onToggleAll={toggleAll}
              loading={listLoading}
              error={listError}
              pagination={pagination}
              onPage={setPage}
            />
            <ModerationDetailPanel
              detail={detail}
              loading={detailLoading}
              error={detailError}
              busy={actionBusy}
              onApprove={(draftIdx) => runAction(() => aiModerationApi.approve(selectedId, draftIdx))}
              onReject={(reason) => runAction(() => aiModerationApi.reject(selectedId, reason))}
              onEditResponse={(editedResponse, note) => runAction(() => aiModerationApi.editResponse(selectedId, editedResponse, note))}
              onNeedImprovement={(reason) => runAction(() => aiModerationApi.needImprovement(selectedId, reason))}
            />
          </div>
        </>
      ) : (
        <ModerationHistory items={history} loading={historyLoading} error={historyError} />
      )}
    </div>
  );
}
