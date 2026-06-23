import { useState, useEffect, useRef } from "react";
import Icon from "../admin/Icon.jsx";
import Sidebar from "../admin/Sidebar.jsx";
import TopBar from "../admin/TopBar.jsx";
import { api } from "../api.js";
import { DemoNotice, updatedNow } from "../ui.jsx";
import ContentFormModal from "../admin/ContentFormModal.jsx";
import ConfirmDialog from "../admin/ConfirmDialog.jsx";
import LaPager from "../components/shared/LaPager.jsx";

const PAGE_SIZE = 10;

const RESOURCE_FIELDS = [
  { name: "title", label: "Title", type: "text", required: true, placeholder: "e.g. Grounding techniques for panic" },
  { name: "type", label: "Type", type: "select", half: true, options: ["Article", "Audio", "Video", "CBT Tool"] },
  { name: "status", label: "Status", type: "select", half: true, options: ["published", "draft", "update", "urgent"] },
  { name: "category", label: "Category", type: "text", half: true, placeholder: "e.g. Anxiety" },
  { name: "duration", label: "Duration", type: "text", half: true, placeholder: "e.g. 8 min read" },
  { name: "url", label: "URL", type: "url", placeholder: "https://… (link to the resource)" },
  { name: "owner", label: "Owner", type: "text", half: true, placeholder: "e.g. Clinical team" },
  { name: "tags", label: "Tags", type: "tags", half: true, help: "Comma-separated", placeholder: "anxiety, breathing" },
  { name: "description", label: "Short description", type: "textarea", rows: 2, placeholder: "One-line summary shown in the list." },
  { name: "content", label: "Content / notes", type: "textarea", rows: 5, placeholder: "Full body, transcript or clinician notes." },
];

/* Thumb art is keyed 1..8; map any row to one by position so DB-backed rows
   (UUID ids) still render a stable icon. */
function thumbFor(idx) { return THUMBS[(idx % 8) + 1] || THUMBS[1]; }

/* ── Motion helpers (shared behaviour with LessonsAdmin) ───────── */
function prefersReducedMotion() {
  return typeof window !== "undefined" && window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/* Counts up from 0, keeping any prefix/suffix ("326", "1,248", "87.7%"). */
function CountUp({ value, duration = 950 }) {
  const [display, setDisplay] = useState(value);
  const raf = useRef(0);
  useEffect(() => {
    const m = String(value).match(/^(\D*)([\d,.]+)(.*)$/);
    const target = m ? parseFloat(m[2].replace(/,/g, "")) : NaN;
    if (!m || Number.isNaN(target) || prefersReducedMotion()) { setDisplay(value); return; }
    const [, prefix, raw, suffix] = m;
    const decimals = raw.includes(".") ? (raw.split(".")[1] || "").length : 0;
    const start = performance.now();
    const tick = (now) => {
      const p = Math.min((now - start) / duration, 1);
      const v = target * (1 - Math.pow(1 - p, 3));
      const text = decimals
        ? v.toFixed(decimals)
        : Math.round(v).toLocaleString("en-US");
      setDisplay(prefix + text + suffix);
      if (p < 1) raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [value, duration]);
  return <>{display}</>;
}

/* ── Stat card ─────────────────────────────────────────────────── */
function StatCard({ icon, tone, label, value, sub, trend, i = 0 }) {
  return (
    <div className="la-stat la-rise" style={{ "--i": i }}>
      <div className={`la-stat-icon tone-${tone}`}><Icon name={icon} size={22} /></div>
      <div className="la-stat-body">
        <div className="la-stat-label">{label}</div>
        <div className="la-stat-value"><CountUp value={value} /></div>
        <div className={`la-stat-sub ${trend ? "up" : ""}`}>
          {trend && <Icon name="arrowUp" size={12} />}{sub}
        </div>
      </div>
    </div>
  );
}

/* ── Skeletons ─────────────────────────────────────────────────── */
function StatSkeleton({ i = 0 }) {
  return (
    <div className="la-stat la-rise" style={{ "--i": i }}>
      <div className="la-skel la-skel-icon" />
      <div className="la-stat-body" style={{ flex: 1 }}>
        <div className="la-skel la-skel-line" style={{ width: "60%" }} />
        <div className="la-skel la-skel-line" style={{ width: "40%", height: 22, margin: "8px 0" }} />
        <div className="la-skel la-skel-line" style={{ width: "70%" }} />
      </div>
    </div>
  );
}
function RowSkeleton() {
  return (
    <tr className="la-skel-row">
      <td className="la-check-cell"><div className="la-skel" style={{ width: 17, height: 17, borderRadius: 5, margin: "0 auto" }} /></td>
      <td>
        <div className="la-title-cell">
          <span className="la-skel la-skel-thumb" />
          <div style={{ flex: 1 }}>
            <div className="la-skel la-skel-line" style={{ width: "70%" }} />
            <div className="la-skel la-skel-line" style={{ width: "50%", marginTop: 6 }} />
          </div>
        </div>
      </td>
      {Array.from({ length: 6 }).map((_, i) => (
        <td key={i}><div className="la-skel la-skel-line" style={{ width: i === 5 ? 28 : "70%" }} /></td>
      ))}
    </tr>
  );
}

/* ── Filter tabs ───────────────────────────────────────────────── */
const TABS = [
  { id: "all",      label: "All" },
  { id: "articles", label: "Articles" },
  { id: "audio",    label: "Audio" },
  { id: "video",    label: "Video" },
  { id: "tools",    label: "CBT Tools" },
];

function FilterTabs({ active, onTab }) {
  const wrapRef = useRef(null);
  const [ind, setInd] = useState(null); // {left, top, width, height}

  useEffect(() => {
    function place() {
      const wrap = wrapRef.current;
      const el = wrap?.querySelector(".la-tab.active");
      if (el) setInd({ left: el.offsetLeft, top: el.offsetTop, width: el.offsetWidth, height: el.offsetHeight });
    }
    place();
    window.addEventListener("resize", place);
    return () => window.removeEventListener("resize", place);
  }, [active]);

  return (
    <div className="la-tabs" ref={wrapRef}>
      {ind && (
        <span
          className={`la-tab-indicator ${active === "urgent" ? "urgent" : ""}`}
          style={{ transform: `translate(${ind.left}px, ${ind.top}px)`, width: ind.width, height: ind.height }}
          aria-hidden="true"
        />
      )}
      {TABS.map((t) => (
        <button key={t.id} className={`la-tab ${active === t.id ? "active" : ""}`} onClick={() => onTab(t.id)}>
          {t.label}
        </button>
      ))}
      <button className={`la-tab la-tab-urgent ${active === "urgent" ? "active" : ""}`} onClick={() => onTab("urgent")}>
        <Icon name="alert" size={14} /> Urgent
      </button>
    </div>
  );
}

/* ── Type icon ─────────────────────────────────────────────────── */
const TYPE_META = {
  Audio:     { icon: "headphones", tone: "green",  label: "Audio" },
  Article:   { icon: "article",    tone: "blue",   label: "Article" },
  Video:     { icon: "play",       tone: "pink",   label: "Video" },
  "CBT Tool":{ icon: "tool",       tone: "purple", label: "CBT Tool" },
};
function TypeCell({ type }) {
  const m = TYPE_META[type] || TYPE_META.Article;
  return (
    <span className="la-type">
      <span className={`la-type-icon tone-${m.tone}`}><Icon name={m.icon} size={15} /></span>
      {m.label}
    </span>
  );
}

/* ── Status badge ──────────────────────────────────────────────── */
const STATUS_META = {
  published: ["Published", "la-badge-green"],
  urgent:    ["Urgent", "la-badge-red"],
  update:    ["Needs Update", "la-badge-amber"],
};
function StatusBadge({ status }) {
  const [label, cls] = STATUS_META[status] || STATUS_META.published;
  return <span className={`la-badge ${cls}`}><span className="la-badge-dot" />{label}</span>;
}

/* ── Owner cell ────────────────────────────────────────────────── */
function initials(name) {
  const p = name.trim().split(/\s+/);
  return ((p[0]?.[0] || "") + (p[p.length - 1]?.[0] || "")).toUpperCase();
}
const AVATAR_TONES = ["#6366f1", "#0ea5e9", "#8b5cf6", "#ef4444", "#14b8a6", "#f59e0b", "#ec4899"];
function Owner({ name, idx }) {
  return (
    <span className="la-owner">
      <span className="la-owner-avatar" style={{ background: AVATAR_TONES[idx % AVATAR_TONES.length] }}>{initials(name)}</span>
      {name}
    </span>
  );
}

/* ── Data ──────────────────────────────────────────────────────── */
const CAT_COLOR = {
  "Stress Relief":        "green",
  "Psychology Knowledge": "blue",
  "Mindfulness":          "purple",
  "Emergency Support":    "pink",
  "CBT":                  "indigo",
  "Mental Wellness":      "teal",
  "Personal Development": "amber",
};
const THUMBS = {
  1: ["🌅", "linear-gradient(135deg,#fde68a,#fca5a5)"],
  2: ["📘", "linear-gradient(135deg,#bfdbfe,#a5b4fc)"],
  3: ["🪷", "linear-gradient(135deg,#ddd6fe,#c4b5fd)"],
  4: ["📞", "linear-gradient(135deg,#fecaca,#fca5a5)"],
  5: ["📓", "linear-gradient(135deg,#c7d2fe,#a5b4fc)"],
  6: ["🌙", "linear-gradient(135deg,#c7d2fe,#93c5fd)"],
  7: ["💪", "linear-gradient(135deg,#fed7aa,#fdba74)"],
};
const RESOURCES = [
  { id: 1, type: "Audio",    title: "5 Minutes of Deep Breathing Daily", desc: "A guided deep-breathing practice to relieve stress quickly.", category: "Stress Relief", duration: "05:23", status: "published", owner: "Trần Quang Huy" },
  { id: 2, type: "Article",  title: "Understanding Anxiety and How to Manage It", desc: "An article covering the basics of anxiety and how to control it.", category: "Psychology Knowledge", duration: "", status: "published", owner: "Lê Thanh Tâm" },
  { id: 3, type: "Video",    title: "Mindfulness Meditation for Beginners", desc: "A 10-minute mindfulness meditation guide for beginners.", category: "Mindfulness", duration: "10:12", status: "published", owner: "Vũ Thùy Linh" },
  { id: 4, type: "Article",  title: "Emergency Support Hotline", desc: "24/7 contact information for emergency situations.", category: "Emergency Support", duration: "", status: "urgent", owner: "Phạm Gia Bảo", urgent: true },
  { id: 5, type: "CBT Tool", title: "Thought Journal (CBT)", desc: "A tool to record and analyze thoughts using the CBT method.", category: "CBT", duration: "", status: "published", owner: "Hoàng Nam" },
  { id: 6, type: "Article",  title: "Managing Sleep Effectively", desc: "Tips and habits to improve sleep quality every day.", category: "Mental Wellness", duration: "", status: "update", owner: "Đặng Thu Trang" },
  { id: 7, type: "Video",    title: "Building Self-Confidence", desc: "A video guide on building and maintaining self-confidence.", category: "Personal Development", duration: "08:45", status: "published", owner: "Nguyễn Hoài An" },
];
const TYPE_TO_TAB = { Audio: "audio", Article: "articles", Video: "video", "CBT Tool": "tools" };

/* ── Resource row ──────────────────────────────────────────────── */
function ResourceRow({ r, idx, selected, onSelect, onDelete }) {
  const [emoji, bg] = thumbFor(idx);
  return (
    <tr className={`la-rise ${selected ? (r.urgent ? "row-urgent-selected" : "selected") : ""}`} style={{ "--i": idx }} onClick={() => onSelect(r.id)}>
      <td onClick={(e) => e.stopPropagation()} className="la-check-cell">
        <input type="checkbox" className="la-check" />
      </td>
      <td>
        <div className="la-title-cell">
          <span className="la-thumb" style={{ background: bg }}>
            {emoji}
            {r.urgent && <span className="la-thumb-badge">URGENT</span>}
          </span>
          <div className="la-title-text">
            <div className="la-title-main">{r.title}</div>
            <div className="la-title-desc">{r.desc}</div>
          </div>
        </div>
      </td>
      <td><TypeCell type={r.type} /></td>
      <td><span className={`la-cat la-cat-${CAT_COLOR[r.category] || "indigo"}`}>{r.category}</span></td>
      <td className="la-muted">{r.duration || "N/A"}</td>
      <td><StatusBadge status={r.status} /></td>
      <td><Owner name={r.owner} idx={idx} /></td>
      <td onClick={(e) => e.stopPropagation()}>
        <div className="la-actions"><button className="la-act" title="Delete" onClick={() => onDelete(r)}><Icon name="close" size={17} /></button></div>
      </td>
    </tr>
  );
}

/* ── Detail panel ──────────────────────────────────────────────── */
const TAGS = ["urgent", "hotline", "support", "24/7"];
const INFO = [
  ["Resource ID", "RSRC-2026-0123"],
  ["Created", "12/06/2026 14:22"],
  ["Last Updated", "13/06/2026 09:18"],
];

function fmtDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  return d.toLocaleDateString("en-GB") + " " +
    d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
}

function DetailPanel({ resource, onClose, onEdit, onTogglePublish }) {
  const tags = resource.tags && resource.tags.length ? resource.tags : [];
  const isPub = resource.status === "published";
  const owner = resource.owner || "—";
  const oi = owner.trim().split(/\s+/);
  const initials = ((oi[0]?.[0] || "") + (oi[oi.length - 1]?.[0] || "")).toUpperCase();
  const usageStr = resource.usage_count != null
    ? Number(resource.usage_count).toLocaleString("en-US") : "1,248";
  return (
    <aside className="la-detail la-detail-single">
      <div className="la-card la-detail-card la-xfade" key={resource.id}>
        <button className="la-close" onClick={onClose} aria-label="Close"><Icon name="close" size={18} /></button>

        {resource.urgent && (
          <div className="la-hotline-banner">
            <span className="la-hotline-circle"><Icon name="phone" size={22} /></span>
            <div>
              <div className="la-hotline-label">24/7 SUPPORT HOTLINE</div>
              <div className="la-hotline-num">0169 234 5678</div>
            </div>
          </div>
        )}

        <div className="la-detail-titlerow">
          <h3>{resource.title}</h3>
          {resource.urgent
            ? <span className="la-badge la-badge-red"><span className="la-badge-dot" />Urgent</span>
            : <span className="la-badge la-badge-green"><span className="la-badge-dot" />{resource.status}</span>}
        </div>
        <div className="la-detail-meta">{resource.type} • {resource.category || "—"}</div>
        <p className="la-detail-desc">{resource.description || "No description provided."}</p>

        <div className="la-info">
          <div className="la-info-row"><span className="la-info-label">Resource ID</span><span className="la-info-value">{resource.resource_code || String(resource.id).slice(0, 8)}</span></div>
          <div className="la-info-row"><span className="la-info-label">Created</span><span className="la-info-value">{fmtDate(resource.created_at)}</span></div>
          <div className="la-info-row"><span className="la-info-label">Last Updated</span><span className="la-info-value">{fmtDate(resource.updated_at)}</span></div>
          <div className="la-info-row">
            <span className="la-info-label">Owner</span>
            <span className="la-info-value la-info-owner">
              <span className="la-owner-avatar" style={{ background: "#6366f1" }}>{initials}</span>{owner}
            </span>
          </div>
        </div>

        <div className="la-detail-section">
          <div className="la-detail-h">Tags</div>
          <div className="la-tags">{tags.map((t) => <span key={t} className="la-tag">{t}</span>)}</div>
        </div>

        <div className="la-detail-section">
          <div className="la-detail-h">Usage Count</div>
          <div className="la-usage">
            <span className="la-usage-icon"><Icon name="users" size={20} /></span>
            <div>
              <div className="la-usage-num"><CountUp value={usageStr} /></div>
              <div className="la-usage-trend"><Icon name="arrowUp" size={12} /> 15% vs last month</div>
            </div>
          </div>
        </div>

        <div className="la-detail-foot">
          <button className="la-btn-outline la-btn-grow" onClick={() => onEdit(resource)}><Icon name="pencil" size={15} /> Edit</button>
          {resource.url && <a className="la-icon-btn-sm" href={resource.url} target="_blank" rel="noreferrer"><Icon name="link" size={16} /></a>}
          <button className="la-btn-green la-btn-grow" onClick={() => onTogglePublish(resource)}><Icon name="publish" size={15} /> {isPub ? "Unpublish" : "Publish"}</button>
        </div>
      </div>
    </aside>
  );
}

function DetailSkeleton() {
  return (
    <aside className="la-detail la-detail-single">
      <div className="la-card">
        <div className="la-skel" style={{ height: 72, borderRadius: 13, marginBottom: 16 }} />
        <div className="la-skel la-skel-line" style={{ width: "70%", height: 16 }} />
        <div className="la-skel la-skel-line" style={{ width: "45%", marginTop: 10 }} />
        <div className="la-skel la-skel-line" style={{ width: "100%", marginTop: 14 }} />
        <div className="la-skel la-skel-line" style={{ width: "85%", marginTop: 8 }} />
        <div className="la-skel" style={{ height: 130, borderRadius: 12, marginTop: 16 }} />
        <div style={{ display: "flex", gap: 10, marginTop: 16 }}>
          <div className="la-skel" style={{ flex: 1, height: 38, borderRadius: 10 }} />
          <div className="la-skel" style={{ flex: 1, height: 38, borderRadius: 10 }} />
        </div>
      </div>
    </aside>
  );
}

/* ── Page ──────────────────────────────────────────────────────── */
export default function ResourcesAdmin({ onLogout, onNav }) {
  const [tab, setTab] = useState("all");
  const [resources, setResources] = useState([]);
  const [page, setPage] = useState(1);
  const [stats, setStats] = useState({ total: 0, urgent: 0, by_type: {} });
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);
  const [mock, setMock] = useState(false);
  const [err, setErr] = useState("");
  const [formItem, setFormItem] = useState(null);   // null | {} (add) | resource (edit)
  const [confirmDel, setConfirmDel] = useState(null);  // resource pending delete
  const [delBusy, setDelBusy] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const r = await api.resources();
      setResources(r.resources || []);
      setStats(r.stats || { total: 0, urgent: 0, by_type: {} });
      setMock(false);
      setErr("");
    } catch (e) {
      // Backend not wired yet → demo with representative data instead of an
      // empty 500 screen, and open the urgent item so the panel isn't blank.
      const demo = RESOURCES.map((r) => ({
        ...r,
        resource_code: `RSRC-2026-0${100 + r.id}`,
        description: r.desc + " Curated by the clinical team and reviewed for accuracy and tone.",
        tags: r.urgent ? ["urgent", "hotline", "support", "24/7"]
          : [r.category.toLowerCase().split(" ")[0], r.type.toLowerCase()],
        created_at: "2026-06-12T14:22:00",
        updated_at: "2026-06-13T09:18:00",
        usage_count: 1248 - (r.id - 1) * 96,
      }));
      setResources(demo);
      setStats({ total: demo.length, urgent: demo.filter((x) => x.urgent || x.status === "urgent").length, by_type: {} });
      setSelected((prev) => (prev && demo.some((r) => r.id === prev) ? prev : (demo.find((r) => r.urgent)?.id ?? demo[0].id)));
      setMock(true);
      setErr("");
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { load(); }, []);

  // Keep stats in sync after a local (demo) mutation.
  function commitLocal(list) {
    setResources(list);
    setStats((s) => ({ ...s, total: list.length, urgent: list.filter((x) => x.urgent || x.status === "urgent").length }));
  }

  function handleAdd() { setFormItem({ type: "Article", status: "published" }); }

  async function handleFormSubmit(payload) {
    const editingId = formItem && formItem.id;
    if (mock) {
      if (editingId) {
        commitLocal(resources.map((x) => x.id === editingId
          ? { ...x, ...payload, desc: payload.description, updated_at: new Date().toISOString() } : x));
      } else {
        const item = { id: `m${Date.now()}`, ...payload, desc: payload.description,
          resource_code: `RSRC-2026-${String(Date.now()).slice(-4)}`,
          created_at: new Date().toISOString(), updated_at: new Date().toISOString(), usage_count: 0 };
        commitLocal([item, ...resources]); setSelected(item.id);
      }
      return;
    }
    if (editingId) await api.updateResource(editingId, payload);
    else await api.createResource(payload);
    await load();
  }

  function handleDelete(r) { setConfirmDel(r); }
  async function doDelete() {
    const r = confirmDel;
    if (!r) return;
    setDelBusy(true);
    if (mock) {
      const next = resources.filter((x) => x.id !== r.id);
      commitLocal(next);
      if (selected === r.id) setSelected(next[0]?.id ?? null);
      setDelBusy(false); setConfirmDel(null); return;
    }
    try { await api.deleteResource(r.id); if (selected === r.id) setSelected(null); await load(); }
    catch (e) { setErr(e.message); }
    finally { setDelBusy(false); setConfirmDel(null); }
  }

  function handleEdit(r) {
    setFormItem({ ...r, description: r.description ?? r.desc ?? "" });
  }

  async function handleTogglePublish(r) {
    const status = r.status === "published" ? "draft" : "published";
    if (mock) { commitLocal(resources.map((x) => x.id === r.id ? { ...x, status } : x)); return; }
    try { await api.updateResource(r.id, { status }); await load(); }
    catch (e) { setErr(e.message); }
  }

  const published = stats.total - (resources.filter((r) => r.status === "draft").length);
  const needsUpdate = resources.filter((r) => r.status === "update").length;
  const pct = (n) => (stats.total ? ((n / stats.total) * 100).toFixed(1) : "0");

  const filtered = resources.filter((r) => {
    if (tab === "all") return true;
    if (tab === "urgent") return r.urgent || r.status === "urgent";
    return TYPE_TO_TAB[r.type] === tab;
  });
  const selectedResource = resources.find((r) => r.id === selected);
  const panelOpen = !!selectedResource;

  // Reset to page 1 when the filter tab changes; keep page valid as the list shrinks.
  useEffect(() => { setPage(1); }, [tab]);
  useEffect(() => {
    const pc = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
    if (page > pc) setPage(pc);
  }, [filtered.length, page]);

  return (
    <div className="la-shell">
      <Sidebar active="resources" onNav={onNav} />

      <div className="la-main">
        <TopBar
          title="Resource Management"
          subtitle={loading ? "Loading…" : updatedNow()}
          searchPlaceholder="Search resources, categories, owners..."
          onLogout={onLogout}
        />

        <div className={`la-content ${(panelOpen || loading) ? "" : "la-content-nopanel"}`}>
          <div className="la-content-left">
            {/* Stat cards */}
            <div className="la-stats">
              {loading ? [0, 1, 2, 3].map((i) => <StatSkeleton key={i} i={i} />) : (
                <>
                  <StatCard i={0} icon="book" tone="indigo" label="Total Resources" value={String(stats.total)} sub="all resources" />
                  <StatCard i={1} icon="alert" tone="red" label="Urgent" value={String(stats.urgent)} sub="need attention" />
                  <StatCard i={2} icon="checkCircle" tone="green" label="Published" value={String(published)} sub={`${pct(published)}% of all resources`} />
                  <StatCard i={3} icon="clock" tone="orange" label="Needs Update" value={String(needsUpdate)} sub={`${pct(needsUpdate)}% of all resources`} />
                </>
              )}
            </div>

            {/* Table card */}
            <div className="la-card la-table-card">
              <div className="la-res-toolbar">
                <FilterTabs active={tab} onTab={setTab} />
                <div className="la-filter-search la-res-search">
                  <Icon name="search" size={16} className="la-search-icon" />
                  <input placeholder="Search within list..." />
                </div>
                <div className="la-select-group">
                  <label>Category</label>
                  <select className="la-select"><option>All</option></select>
                </div>
                <button className="la-btn-primary" onClick={handleAdd}><Icon name="plus" size={16} /> Add Resource</button>
              </div>

              {mock && <div style={{ marginBottom: 12 }}><DemoNotice>Sample data shown — resources API isn't connected yet.</DemoNotice></div>}
              {err && <div style={{ color: "#ef4444", padding: 16 }}>{err}</div>}
              <div className="la-table-wrap">
                <table className="la-table">
                  <thead>
                    <tr>
                      <th className="la-check-cell"><input type="checkbox" className="la-check" /></th>
                      <th>Resource Name</th><th>Type</th><th>Category</th>
                      <th>Duration</th><th>Status</th><th>Owner</th><th>Actions</th>
                    </tr>
                  </thead>
                  <tbody key={loading ? "loading" : tab}>
                    {loading && Array.from({ length: 6 }).map((_, i) => <RowSkeleton key={i} />)}
                    {!loading && filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE).map((r, i) => (
                      <ResourceRow key={r.id} r={r} idx={i} selected={r.id === selected} onSelect={setSelected} onDelete={handleDelete} />
                    ))}
                    {!loading && filtered.length === 0 && (
                      <tr><td colSpan={8} style={{ textAlign: "center", padding: 24, color: "#94a3b8" }}>No resources.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>

              <LaPager page={page} pageSize={PAGE_SIZE} total={filtered.length}
                       onChange={setPage} noun="resources" />
            </div>
          </div>

          {loading
            ? <DetailSkeleton />
            : panelOpen && <DetailPanel resource={selectedResource} onClose={() => setSelected(null)} onEdit={handleEdit} onTogglePublish={handleTogglePublish} />}
        </div>
      </div>

      {formItem && (
        <ContentFormModal
          title={formItem.id ? "Edit Resource" : "Add Resource"}
          subtitle={formItem.id ? "Update this resource's details." : "Create a new resource."}
          fields={RESOURCE_FIELDS}
          initial={formItem}
          submitLabel={formItem.id ? "Save changes" : "Create resource"}
          onSubmit={handleFormSubmit}
          onClose={() => setFormItem(null)}
        />
      )}

      <ConfirmDialog
        open={!!confirmDel}
        title="Delete resource?"
        message={confirmDel ? `Delete "${confirmDel.title}"? This can't be undone.` : ""}
        confirmLabel="Delete"
        danger
        busy={delBusy}
        onConfirm={doDelete}
        onCancel={() => setConfirmDel(null)}
      />
    </div>
  );
}
