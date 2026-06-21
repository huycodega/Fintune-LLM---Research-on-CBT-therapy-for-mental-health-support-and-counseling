import { useState, useEffect, useRef } from "react";
import Icon from "../admin/Icon.jsx";
import Sidebar from "../admin/Sidebar.jsx";
import TopBar from "../admin/TopBar.jsx";
import ContentFormModal from "../admin/ContentFormModal.jsx";
import { api } from "../api.js";

/* Field layout for the Lesson add/edit modal — mirrors LessonIn in
   backend/app/schemas/api.py. */
const LESSON_FIELDS = [
  { name: "title", label: "Title", type: "text", required: true, placeholder: "e.g. Identifying cognitive distortions" },
  { name: "level", label: "Level", type: "select", half: true, options: ["basic", "intermediate", "advanced"] },
  { name: "status", label: "Status", type: "select", half: true, options: ["draft", "published"] },
  { name: "category", label: "Category", type: "text", half: true, placeholder: "e.g. Cognitive restructuring" },
  { name: "duration", label: "Duration", type: "text", half: true, placeholder: "e.g. 15 min" },
  { name: "author", label: "Author", type: "text", half: true, placeholder: "e.g. Clinical team" },
  { name: "tags", label: "Tags", type: "tags", half: true, help: "Comma-separated", placeholder: "distortions, thoughts" },
  { name: "objectives", label: "Learning objectives", type: "tags", help: "Comma-separated — one objective per item", placeholder: "Spot all-or-nothing thinking, Reframe a thought" },
  { name: "description", label: "Short description", type: "textarea", rows: 2, placeholder: "One-line summary shown in the list." },
  { name: "content", label: "Lesson content", type: "textarea", rows: 6, placeholder: "Full lesson body / script." },
];

/* Thumb art is keyed 1..8; map any row to one by its position so DB-backed
   rows (UUID ids) still get a stable icon. */
function thumbFor(idx) { return THUMBS[(idx % 8) + 1]; }

/* ── Motion helpers ────────────────────────────────────────────── */
function prefersReducedMotion() {
  return typeof window !== "undefined" &&
    window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/* Counts a number up from 0 to its target, keeping any prefix/suffix
   ("48", "63%", "1,842"). Re-runs whenever the value changes (e.g. after
   the API loads or stats update). Falls back to the raw value otherwise. */
function CountUp({ value, duration = 1000 }) {
  const [display, setDisplay] = useState(value);
  const rafRef = useRef(0);
  useEffect(() => {
    const m = String(value).match(/^(\D*)([\d,]+)(.*)$/);
    const target = m ? parseInt(m[2].replace(/,/g, ""), 10) : NaN;
    if (!m || Number.isNaN(target) || prefersReducedMotion()) {
      setDisplay(value);
      return;
    }
    const [, prefix, , suffix] = m;
    const start = performance.now();
    const tick = (now) => {
      const p = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      setDisplay(prefix + Math.round(target * eased).toLocaleString("en-US") + suffix);
      if (p < 1) rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
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

/* ── Skeletons (shown while data loads) ────────────────────────── */
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
        <td key={i}><div className="la-skel la-skel-line" style={{ width: i === 5 ? 44 : "70%" }} /></td>
      ))}
    </tr>
  );
}
function DetailSkeleton() {
  return (
    <aside className="la-detail">
      <div className="la-card">
        <div className="la-skel la-skel-line" style={{ width: "40%", marginBottom: 12 }} />
        <div className="la-skel" style={{ height: 150, borderRadius: 13, marginBottom: 14 }} />
        <div className="la-skel la-skel-line" style={{ width: "75%", height: 16 }} />
        <div className="la-skel la-skel-line" style={{ width: "100%", marginTop: 12 }} />
        <div className="la-skel la-skel-line" style={{ width: "90%", marginTop: 8 }} />
        <div className="la-skel la-skel-line" style={{ width: "60%", marginTop: 8 }} />
        <div style={{ display: "flex", gap: 10, marginTop: 18 }}>
          <div className="la-skel" style={{ flex: 1, height: 38, borderRadius: 10 }} />
          <div className="la-skel" style={{ flex: 1, height: 38, borderRadius: 10 }} />
        </div>
      </div>
    </aside>
  );
}

/* ── Badges ────────────────────────────────────────────────────── */
function StatusBadge({ status }) {
  const published = status === "published";
  return (
    <span className={`la-badge ${published ? "la-badge-green" : "la-badge-amber"}`}>
      <span className="la-badge-dot" />{published ? "Published" : "Draft"}
    </span>
  );
}

const LEVEL_MAP = {
  basic:        ["Basic", "la-lvl-green"],
  intermediate: ["Intermediate", "la-lvl-amber"],
  advanced:     ["Advanced", "la-lvl-red"],
};
function LevelBadge({ level }) {
  const [label, cls] = LEVEL_MAP[level] || ["—", "la-lvl-green"];
  return <span className={`la-level ${cls}`}>{label}</span>;
}

/* ── Data ──────────────────────────────────────────────────────── */
const CAT_COLOR = {
  "Stress Management":      "indigo",
  "Positive Thinking":      "green",
  "Mindfulness":            "amber",
  "Breathing & Relaxation": "blue",
  "Habits":                 "purple",
  "Social Skills":          "pink",
  "Mental Wellness":        "teal",
};

const THUMBS = {
  1: ["🧘", "linear-gradient(135deg,#a7f3d0,#6ee7b7)"],
  2: ["🌅", "linear-gradient(135deg,#fde68a,#fca5a5)"],
  3: ["🪷", "linear-gradient(135deg,#ddd6fe,#c4b5fd)"],
  4: ["🫁", "linear-gradient(135deg,#bfdbfe,#93c5fd)"],
  5: ["🌱", "linear-gradient(135deg,#bbf7d0,#86efac)"],
  6: ["🌧️", "linear-gradient(135deg,#cbd5e1,#94a3b8)"],
  7: ["💬", "linear-gradient(135deg,#fbcfe8,#f9a8d4)"],
  8: ["🌙", "linear-gradient(135deg,#c7d2fe,#a5b4fc)"],
};

const POPULAR = [
  { rank: 1, title: "Positive Thinking Every Day", n: "1,842" },
  { rank: 2, title: "Managing Stress Effectively", n: "1,539" },
  { rank: 3, title: "Mindfulness in the Present", n: "1,203" },
];

/* ── Filter bar ────────────────────────────────────────────────── */
function FilterBar({ onAdd }) {
  return (
    <div className="la-filterbar">
      <div className="la-filter-search">
        <Icon name="search" size={16} className="la-search-icon" />
        <input placeholder="Search lessons..." />
      </div>
      <div className="la-select-group">
        <label>Category</label>
        <select className="la-select"><option>All</option></select>
      </div>
      <div className="la-select-group">
        <label>Level</label>
        <select className="la-select"><option>All</option></select>
      </div>
      <div className="la-select-group">
        <label>Status</label>
        <select className="la-select"><option>All</option></select>
      </div>
      <button className="la-btn-ghost"><Icon name="sort" size={16} /> Sort: Newest</button>
      <button className="la-btn-primary" onClick={onAdd}><Icon name="plus" size={16} /> Add Lesson</button>
    </div>
  );
}

/* ── Lesson row ────────────────────────────────────────────────── */
function fmtDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  return d.toLocaleDateString("en-GB") + " " +
    d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
}

function LessonRow({ lesson, idx, selected, onSelect, onDelete }) {
  const [emoji, bg] = thumbFor(idx);
  const [user, time] = [lesson.author || "—", fmtDate(lesson.updated_at)];
  const isDraft = lesson.status === "draft";
  return (
    <tr className={`la-rise ${selected ? "selected" : ""}`} style={{ "--i": idx }} onClick={() => onSelect(lesson.id)}>
      <td>
        <div className="la-title-cell">
          <span className="la-thumb" style={{ background: bg }}>{emoji}</span>
          <div className="la-title-text">
            <div className="la-title-main">{lesson.title}</div>
            <div className="la-title-desc">{lesson.desc}</div>
          </div>
        </div>
      </td>
      <td><span className={`la-cat la-cat-${CAT_COLOR[lesson.category] || "indigo"}`}>{lesson.category}</span></td>
      <td><LevelBadge level={lesson.level} /></td>
      <td className="la-muted">{lesson.duration}</td>
      <td><StatusBadge status={lesson.status} /></td>
      <td>
        <div className="la-updated"><span>{time}</span><small>{user}</small></div>
      </td>
      <td onClick={(e) => e.stopPropagation()}>
        <div className="la-actions">
          <button className="la-act" title={isDraft ? "Edit" : "View"} onClick={() => onSelect(lesson.id)}><Icon name={isDraft ? "pencil" : "eye"} size={17} /></button>
          <button className="la-act" title="Delete" onClick={() => onDelete(lesson)}><Icon name="close" size={17} /></button>
        </div>
      </td>
    </tr>
  );
}

/* ── Pagination ────────────────────────────────────────────────── */
function Pagination({ total = 0, pageSize = 10 }) {
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const shown = Math.min(total, pageSize);
  const pages = Array.from({ length: pageCount }, (_, i) => i + 1);
  return (
    <div className="la-pagination">
      <div className="la-page-info">
        {total === 0 ? "No lessons yet" : `Showing 1 to ${shown} of ${total} lessons`}
      </div>
      <div className="la-page-controls">
        <button className="la-page-btn" disabled><Icon name="chevronLeft" size={15} /></button>
        {pages.map((p) => (
          <button key={p} className={`la-page-btn ${p === 1 ? "active" : ""}`}>{p}</button>
        ))}
        <button className="la-page-btn" disabled={pageCount <= 1}><Icon name="chevronRight" size={15} /></button>
      </div>
      <div className="la-select-group">
        <select className="la-select"><option>10 / page</option></select>
      </div>
    </div>
  );
}

/* ── Mini line chart ───────────────────────────────────────────── */
function MiniLineChart() {
  const data = [42, 38, 47, 44, 53, 58, 63];
  const W = 280, H = 96, pad = 6;
  const max = 100;
  const pts = data.map((v, i) => {
    const x = pad + (i * (W - 2 * pad)) / (data.length - 1);
    const y = H - pad - (v / max) * (H - 2 * pad);
    return [x, y];
  });
  const line = pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(" ");
  const area = `${line} L ${W - pad} ${H} L ${pad} ${H} Z`;
  return (
    <div className="la-chart">
      <div className="la-chart-yaxis"><span>100%</span><span>50%</span><span>0%</span></div>
      <div className="la-chart-plot">
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="la-chart-svg">
          <defs>
            <linearGradient id="laFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="#6366f1" stopOpacity="0.22" />
              <stop offset="1" stopColor="#6366f1" stopOpacity="0" />
            </linearGradient>
          </defs>
          <line x1={pad} y1={H / 2} x2={W - pad} y2={H / 2} stroke="#eef0f6" strokeWidth="1" />
          <path className="la-chart-area" d={area} fill="url(#laFill)" />
          <path className="la-chart-line" d={line} pathLength="1" fill="none" stroke="#6366f1" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
          {pts.length > 0 && <circle className="la-chart-dot" cx={pts[pts.length - 1][0]} cy={pts[pts.length - 1][1]} r="3.5" fill="#6366f1" stroke="#fff" strokeWidth="2" />}
        </svg>
        <div className="la-chart-xaxis"><span>13/05</span><span>27/05</span><span>10/06</span></div>
      </div>
    </div>
  );
}

/* ── Detail panel ──────────────────────────────────────────────── */
const OBJECTIVES_FALLBACK = [
  "Understand the causes and signs of stress",
  "Apply simple relaxation techniques",
  "Build a personal stress management plan",
];

function DetailPanel({ lesson, thumb, onTogglePublish, onEdit }) {
  const objectives = (lesson.objectives && lesson.objectives.length)
    ? lesson.objectives : OBJECTIVES_FALLBACK;
  const tags = lesson.tags && lesson.tags.length ? lesson.tags : [];
  const isPub = lesson.status === "published";
  const [heroEmoji, heroBg] = thumb || ["🧘", "linear-gradient(135deg,#bbf7d0,#7dd3c0)"];
  return (
    <aside className="la-detail">
      <div className="la-card la-xfade" key={lesson.id}>
        <div className="la-card-eyebrow">Selected Lesson</div>
        <div className="la-detail-hero" style={{ background: heroBg }}>
          <span>{heroEmoji}</span>
        </div>
        <div className="la-detail-titlerow">
          <h3>{lesson.title}</h3>
          <StatusBadge status={lesson.status} />
        </div>
        <p className="la-detail-desc">
          {lesson.description || "No description provided."}
        </p>

        <div className="la-detail-section">
          <div className="la-detail-h">Learning Objectives</div>
          {objectives.map((o) => (
            <div key={o} className="la-objective"><span className="la-obj-tick"><Icon name="check" size={12} stroke={2.4} /></span>{o}</div>
          ))}
        </div>

        <div className="la-detail-section">
          <div className="la-detail-h">Category &amp; Tags</div>
          <span className="la-cat la-cat-indigo" style={{ marginBottom: 8, display: "inline-block" }}>{lesson.category}</span>
          <div className="la-tags">
            {tags.map((t) => <span key={t} className="la-tag">{t}</span>)}
          </div>
        </div>

        <div className="la-detail-actions">
          <button className="la-btn-primary la-btn-grow" onClick={() => onEdit(lesson)}><Icon name="pencil" size={15} /> Edit</button>
          <button className="la-btn-green la-btn-grow" onClick={() => onTogglePublish(lesson)}><Icon name="publish" size={15} /> {isPub ? "Unpublish" : "Publish"}</button>
        </div>
        <button className="la-btn-outline la-btn-full"><Icon name="eye" size={16} /> Preview</button>
      </div>

      <div className="la-card">
        <div className="la-card-title">Lesson Statistics</div>
        <div className="la-stat-rate">
          <div>
            <div className="la-rate-label">Completion Rate</div>
            <div className="la-rate-value"><CountUp value="63%" /></div>
          </div>
          <div className="la-rate-trend"><Icon name="arrowUp" size="13" /> 8% vs last month</div>
        </div>
        <div className="la-rate-bar"><span style={{ "--val": "63%" }} /></div>

        <MiniLineChart />

        <div className="la-detail-h" style={{ marginTop: 18 }}>Popular Lessons</div>
        {POPULAR.map((p) => (
          <div key={p.rank} className="la-popular">
            <span className="la-pop-rank">{p.rank}</span>
            <div className="la-pop-text">
              <div className="la-pop-title">{p.title}</div>
              <div className="la-pop-sub">{p.n} completions</div>
            </div>
          </div>
        ))}
        <button className="la-link">View All</button>
      </div>
    </aside>
  );
}

/* ── Page ──────────────────────────────────────────────────────── */
export default function LessonsAdmin({ onLogout, onNav }) {
  const [lessons, setLessons] = useState([]);
  const [stats, setStats] = useState({ total: 0, published: 0, draft: 0, views: 0 });
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);
  const [mock, setMock] = useState(false);
  const [err, setErr] = useState("");
  // null = closed; {} = add new; {...lesson} = editing.
  const [formItem, setFormItem] = useState(null);

  async function load() {
    setLoading(true);
    try {
      const r = await api.lessons();
      setLessons(r.lessons || []);
      setStats(r.stats || { total: 0, published: 0, draft: 0, views: 0 });
      setSelected((prev) =>
        prev && (r.lessons || []).some((l) => l.id === prev)
          ? prev : (r.lessons?.[0]?.id ?? null));
      setMock(false);
      setErr("");
    } catch (e) {
      // Backend unreachable → show an empty list with an error. Never inject
      // demo data so the page only ever reflects real DB content.
      setLessons([]);
      setStats({ total: 0, published: 0, draft: 0, views: 0 });
      setSelected(null);
      setMock(false);
      setErr("Couldn't reach the lessons API.");
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { load(); }, []);

  // Keep stats in sync after a local (demo) mutation.
  function commitLocal(list) {
    setLessons(list);
    setStats((s) => ({
      ...s,
      total: list.length,
      published: list.filter((x) => x.status === "published").length,
      draft: list.filter((x) => x.status === "draft").length,
    }));
  }

  function handleAdd() { setFormItem({}); }

  async function handleFormSubmit(payload) {
    const editingId = formItem && formItem.id;
    if (mock) {
      if (editingId) {
        commitLocal(lessons.map((l) => l.id === editingId ? { ...l, ...payload, desc: payload.description, updated_at: new Date().toISOString() } : l));
      } else {
        const item = {
          id: `m${Date.now()}`, ...payload, desc: payload.description,
          updated_at: new Date().toISOString(),
        };
        commitLocal([item, ...lessons]); setSelected(item.id);
      }
      return;
    }
    if (editingId) await api.updateLesson(editingId, payload);
    else await api.createLesson(payload);
    await load();
  }

  async function handleDelete(lesson) {
    if (!window.confirm(`Delete lesson "${lesson.title}"?`)) return;
    if (mock) { commitLocal(lessons.filter((l) => l.id !== lesson.id)); return; }
    try { await api.deleteLesson(lesson.id); await load(); }
    catch (e) { alert(e.message); }
  }

  async function handleTogglePublish(lesson) {
    const status = lesson.status === "published" ? "draft" : "published";
    if (mock) { commitLocal(lessons.map((l) => l.id === lesson.id ? { ...l, status } : l)); return; }
    try { await api.updateLesson(lesson.id, { status }); await load(); }
    catch (e) { alert(e.message); }
  }

  function handleEdit(lesson) {
    setFormItem({ ...lesson, description: lesson.description ?? lesson.desc ?? "" });
  }

  const selectedLesson = lessons.find((l) => l.id === selected) || lessons[0] || null;

  return (
    <div className="la-shell">
      <Sidebar active="lessons" onNav={onNav} />

      <div className="la-main">
        <TopBar
          title="CBT Lessons Management"
          subtitle={loading ? "Loading…" : `${stats.total} lessons`}
          searchPlaceholder="Search lessons, categories, tags..."
          onLogout={onLogout}
          onNav={onNav}
        />

        <div className={`la-content ${selectedLesson ? "" : "la-content-nopanel"}`}>
          <div className="la-content-left">
            {/* Stat cards */}
            <div className="la-stats">
              {loading ? (
                [0, 1, 2, 3].map((i) => <StatSkeleton key={i} i={i} />)
              ) : (
                <>
                  <StatCard i={0} icon="book" tone="indigo" label="Total Lessons" value={String(stats.total)} sub="all lessons" />
                  <StatCard i={1} icon="checkCircle" tone="green" label="Published" value={String(stats.published)} sub="visible to users" />
                  <StatCard i={2} icon="file" tone="orange" label="Drafts" value={String(stats.draft)} sub="not yet published" />
                  <StatCard i={3} icon="clock" tone="red" label="Total Views" value={String(stats.views)} sub="across all lessons" />
                </>
              )}
            </div>

            {/* Table card */}
            <div className="la-card la-table-card">
              <FilterBar onAdd={handleAdd} />
              {mock && <div style={{ marginBottom: 12 }}><span className="mz-mock-flag"><Icon name="alert" size={12} /> Demo data — lessons API not reachable yet</span></div>}
              {err && <div className="la-empty" style={{ color: "#ef4444", padding: 16 }}>{err}</div>}
              <div className="la-table-wrap">
                <table className="la-table">
                  <thead>
                    <tr>
                      <th>Title</th><th>Category</th><th>Level</th><th>Duration</th>
                      <th>Status</th><th>Last Updated</th><th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {loading && Array.from({ length: 6 }).map((_, i) => <RowSkeleton key={i} />)}
                    {!loading && lessons.map((l, i) => (
                      <LessonRow key={l.id} lesson={l} idx={i} selected={l.id === selected} onSelect={setSelected} onDelete={handleDelete} />
                    ))}
                    {!loading && lessons.length === 0 && (
                      <tr><td colSpan={7} style={{ textAlign: "center", padding: 24, color: "#94a3b8" }}>No lessons yet.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
              <Pagination total={stats.total || lessons.length} />
            </div>
          </div>

          {loading
            ? <DetailSkeleton />
            : selectedLesson && (
              <DetailPanel
                lesson={selectedLesson}
                thumb={thumbFor(Math.max(0, lessons.findIndex((l) => l.id === selectedLesson.id)))}
                onTogglePublish={handleTogglePublish}
                onEdit={handleEdit}
              />
            )}
        </div>
      </div>

      {formItem && (
        <ContentFormModal
          title={formItem.id ? "Edit Lesson" : "Add Lesson"}
          subtitle={formItem.id ? "Update this lesson's details." : "Create a new CBT lesson."}
          fields={LESSON_FIELDS}
          initial={formItem}
          submitLabel={formItem.id ? "Save changes" : "Create lesson"}
          onSubmit={handleFormSubmit}
          onClose={() => setFormItem(null)}
        />
      )}
    </div>
  );
}
