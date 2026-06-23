import { useCallback, useEffect, useState } from "react";
import { casesApi } from "../../services/casesApi.js";
import { LoadingState, ErrorState } from "../shared/States.jsx";
import Pagination from "../shared/Pagination.jsx";
import { CaseStatsCards, CaseFilters, CaseTable } from "./CaseList.jsx";
import CaseDetailPanel from "./CaseDetailPanel.jsx";
import { AssignSpecialistModal, EscalateCaseModal, CloseCaseModal, AddCaseNoteModal } from "./CaseModals.jsx";

const initial = { q: "", priority: "", status: "", specialist_id: "", source_type: "",
  from: "", to: "", page: 1, page_size: 20 };

export default function CaseManagementPage({ onNav }) {
  const [filters, setFilters] = useState(initial);
  const [search, setSearch] = useState("");
  const [pageData, setPageData] = useState(null);
  const [stats, setStats] = useState({});
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [history, setHistory] = useState([]);
  const [error, setError] = useState(null);
  const [detailError, setDetailError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [modal, setModal] = useState(null);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    const timer = setTimeout(() => setFilters(value => ({ ...value, q: search, page: 1 })), 300);
    return () => clearTimeout(timer);
  }, [search]);

  const loadList = useCallback(async () => {
    setLoading(true); setError(null);
    try { setPageData(await casesApi.list(filters)); } catch (err) { setError(err); }
    finally { setLoading(false); }
  }, [filters]);
  const loadStats = useCallback(async () => {
    try { setStats(await casesApi.stats()); } catch { setStats({}); }
  }, []);
  const loadDetail = useCallback(async (id) => {
    if (!id) return;
    setDetailLoading(true); setDetailError(null);
    try {
      const [item, timeline] = await Promise.all([casesApi.detail(id), casesApi.history(id, { limit: 100 })]);
      setDetail(item); setHistory(timeline?.items || timeline?.history || timeline || []);
    } catch (err) { setDetailError(err); }
    finally { setDetailLoading(false); }
  }, []);

  useEffect(() => { loadList(); }, [loadList]);
  useEffect(() => { loadStats(); }, [loadStats]);
  useEffect(() => { if (selectedId) loadDetail(selectedId); }, [selectedId, loadDetail]);

  async function mutate(action, payload) {
    if (!selectedId || !detail) return;
    setBusy(true); setNotice("");
    try {
      const version = detail.version;
      if (action === "view") await casesApi.update(selectedId, { status: "viewed", version });
      if (action === "assign") await casesApi.assign(selectedId, { specialist_id: payload, version });
      if (action === "escalate") await casesApi.escalate(selectedId, {
        reason: payload, idempotency_key: crypto.randomUUID(), version,
      });
      if (action === "close") await casesApi.close(selectedId, {
        resolution_code: "resolved", resolution_note: payload, version,
      });
      if (action === "reopen") await casesApi.reopen(selectedId, { reason: "Reopened by admin", version });
      if (action === "note") await casesApi.addNote(selectedId, { note_type: "internal", content: payload });
      setModal(null); setNotice("Case updated successfully.");
      await Promise.all([loadList(), loadStats(), loadDetail(selectedId)]);
    } catch (err) {
      setNotice(err.status === 409 ? "Case has been updated by another user. Please refresh."
        : err.status === 403 ? "You do not have permission." : err.message);
    } finally { setBusy(false); }
  }
  function action(name) {
    if (["assign", "escalate", "close", "note"].includes(name)) setModal(name);
    else mutate(name);
  }
  const specialists = stats.specialists || [];

  return <div className="module-page cases-page">
    <div className="module-toolbar"><div><h1>Cases to handle</h1>
      <p>Assign, track and resolve risk signals</p></div>
      <div className="module-toolbar-actions"><div className="inline-search"><span>⌕</span>
        <input value={search} onChange={event => setSearch(event.target.value)}
          placeholder="Search user, email, phone, case code…" /></div>
        <button className="btn" onClick={() => { loadList(); loadStats(); }}>↻ Refresh</button></div></div>
    <CaseStatsCards stats={stats} />
    {notice && <div className="case-notice">{notice}<button onClick={() => setNotice("")}>×</button></div>}
    <section className="panel case-list-panel">
      <div className="panel-head filter-head"><CaseFilters value={filters} specialists={specialists}
        onChange={setFilters} /></div>
      {loading ? <LoadingState label="Loading cases…" /> :
        error ? <ErrorState message={error.message} forbidden={error.status === 403} onRetry={loadList} /> :
        <><CaseTable rows={pageData?.items || []} selectedId={selectedId} onSelect={setSelectedId} />
          <Pagination page={filters.page} pageSize={filters.page_size} total={pageData?.total || 0}
            onChange={page => setFilters(value => ({ ...value, page }))} /></>}
    </section>
    <CaseDetailPanel open={!!selectedId} detail={detail} history={history} loading={detailLoading}
      error={detailError} busy={busy} onClose={() => setSelectedId(null)} onAction={action}
      onProfile={(userId) => onNav?.("users", userId)} />
    <AssignSpecialistModal open={modal === "assign"} specialists={specialists} busy={busy}
      onClose={() => setModal(null)} onConfirm={value => mutate("assign", value)} />
    <EscalateCaseModal open={modal === "escalate"} busy={busy} onClose={() => setModal(null)}
      onConfirm={value => mutate("escalate", value)} />
    <CloseCaseModal open={modal === "close"} busy={busy} onClose={() => setModal(null)}
      onConfirm={value => mutate("close", value)} />
    <AddCaseNoteModal open={modal === "note"} busy={busy} onClose={() => setModal(null)}
      onConfirm={value => mutate("note", value)} />
  </div>;
}
