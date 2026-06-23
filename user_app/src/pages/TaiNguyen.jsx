import { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import Mascot from "../components/Mascot.jsx";
import { api } from "../api.js";

const FILTER_TABS = ["All", "Articles", "Audio", "Video", "Emergency", "CBT Tools"];

/* Map a DB resource type → the card's display props (tab bucket, label, icon,
   CTA, thumb) so DB-backed resources render with the mockup styling. */
const TYPE_UI = {
  "Audio":    { category: "Audio",     typeLabel: "Audio",    icon: "♪", action: "Listen Now", thumbClass: "breathing" },
  "Article":  { category: "Articles",  typeLabel: "Article",  icon: "📄", action: "Read Now",   thumbClass: "grounding" },
  "Video":    { category: "Video",     typeLabel: "Video",    icon: "▶", action: "Watch Now",  thumbClass: "sleep" },
  "CBT Tool": { category: "CBT Tools", typeLabel: "CBT Tool", icon: "✎", action: "Use Now",    thumbClass: "journal" },
};

function toCard(r) {
  const ui = TYPE_UI[r.type] || TYPE_UI["Article"];
  const emergency = !!r.urgent;
  return {
    id: r.id,
    category: emergency ? "Emergency" : ui.category,
    typeLabel: emergency ? "Emergency" : ui.typeLabel,
    icon: emergency ? "!" : ui.icon,
    title: r.title,
    desc: r.description || "",
    duration: r.duration || (emergency ? "24/7" : ui.typeLabel),
    tags: r.tags && r.tags.length ? r.tags : [],
    action: emergency ? "Get Help Now" : ui.action,
    url: r.url || "",
    content: r.content || "",
    rawType: r.type || "Article",
    thumbClass: emergency ? "hotline" : ui.thumbClass,
    useImageIcon: false,
    emergency,
  };
}


function BookmarkIcon({ filled = true }) {
  return (
    <svg className="bookmark-svg" viewBox="0 0 16 22" aria-hidden="true" focusable="false">
      <path
        d="M3 2.75C3 1.78 3.78 1 4.75 1h6.5C12.22 1 13 1.78 13 2.75V20l-5-3.15L3 20V2.75Z"
        fill={filled ? "currentColor" : "none"}
        stroke="currentColor"
        strokeWidth="2"
        strokeLinejoin="round"
      />
    </svg>
  );
}
function ResourceCard({ resource, saved, onToggleSave, onOpen }) {
  return (
    <article className={`resource-v2-card ${resource.emergency ? "emergency" : ""}`}
             onClick={() => onOpen(resource)} role="button" tabIndex={0}
             onKeyDown={(e) => { if (e.key === "Enter") onOpen(resource); }}>
      <div className={`resource-v2-thumb ${resource.thumbClass} ${resource.useImageIcon ? "image-icon" : ""}`}>
        {!resource.useImageIcon && (
          <span className={`resource-v2-icon-badge ${resource.category.toLowerCase().replace(/\s+/g, "-")}`}>
            {resource.icon}
          </span>
        )}
      </div>
      <div className="resource-v2-body">
        <div className="resource-v2-card-head">
          <span className="resource-v2-type">{resource.typeLabel}</span>
          <button
            className={`resource-save-btn ${saved ? "saved" : ""}`}
            type="button"
            onClick={(e) => { e.stopPropagation(); onToggleSave(resource.id); }}
            aria-label={saved ? "Remove saved resource" : "Save resource"}
          >
            <BookmarkIcon filled={saved} />
          </button>
        </div>
        <h3>{resource.title}</h3>
        <p>{resource.desc}</p>
        <div className="resource-v2-tags">
          {resource.tags.map((tag) => (
            <span key={tag}>{tag}</span>
          ))}
          <span>{resource.duration}</span>
        </div>
      </div>
      <button className={`resource-v2-action ${resource.emergency ? "danger" : ""}`} type="button"
              onClick={(e) => { e.stopPropagation(); onOpen(resource); }}>
        {resource.action}
      </button>
    </article>
  );
}

/* ── Resource detail modal (reuses lx-* styles) ───────────────────────── */
function ResourceDetail({ resource, onClose }) {
  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const linkLabel = resource.rawType === "Audio" ? "▶ Listen"
    : resource.rawType === "Video" ? "▶ Watch" : "Open resource ↗";

  return createPortal(
    <div className="lx-overlay" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="lx-modal" role="dialog" aria-modal="true" aria-label={resource.title}>
        <button className="lx-close" onClick={onClose} aria-label="Close">✕</button>
        <div className="lx-head">
          <h2 className="lx-title">{resource.title}</h2>
          <div className="lx-meta">
            <span>{resource.typeLabel}</span>
            {resource.duration && <span>🕐 {resource.duration}</span>}
          </div>
        </div>
        <div className="lx-body">
          {resource.desc && <p className="lx-desc">{resource.desc}</p>}
          {resource.content && (
            <div className="lx-content">
              {resource.content.split("\n").map((line, i) =>
                line.trim() ? <p key={i}>{line}</p> : <br key={i} />)}
            </div>
          )}
          {resource.url && (
            <a className="lx-link" href={resource.url} target="_blank" rel="noopener noreferrer">
              {linkLabel}
            </a>
          )}
          {!resource.content && !resource.url && (
            <p className="lx-desc">No additional content for this resource yet.</p>
          )}
        </div>
      </div>
    </div>,
    document.body
  );
}

function SavedResourceItem({ title, resource }) {
  return (
    <div className="saved-resource-item">
      <div className={`saved-resource-icon ${resource?.thumbClass || "journal"}`}>{resource?.icon || "\uD83D\uDCC4"}</div>
      <div>
        <div className="saved-resource-title">{title}</div>
        <div className="saved-resource-meta">{resource?.typeLabel || "Resource"} {"\u00B7"} {resource?.duration || "Saved"}</div>
      </div>
      <span className="saved-resource-bookmark"><BookmarkIcon /></span>
    </div>
  );
}

export default function TaiNguyen() {
  const [activeTab, setActiveTab] = useState("All");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState("Newest");
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [savedItems, setSavedItems] = useState(new Set());
  const [openRes, setOpenRes] = useState(null);

  useEffect(() => {
    let alive = true;
    api.resources()
      .then((r) => { if (alive) setItems((r.resources || []).map(toCard)); })
      .catch(() => { if (alive) setItems([]); })
      .finally(() => { if (alive) setLoading(false); });
    api.savedResources()
      .then((r) => { if (alive) setSavedItems(new Set((r.resources || []).map((x) => x.id))); })
      .catch(() => {});
    return () => { alive = false; };
  }, []);

  const filtered = items.filter((resource) => {
    const text = `${resource.title} ${resource.desc} ${resource.typeLabel} ${resource.tags.join(" ")}`.toLowerCase();
    const matchSearch = !search || text.includes(search.toLowerCase());
    const matchTab = activeTab === "All" || resource.category === activeTab;
    return matchSearch && matchTab;
  });

  const savedResources = items.filter((resource) => savedItems.has(resource.id));

  function toggleSave(id) {
    const isSaved = savedItems.has(id);
    setSavedItems((prev) => {
      const next = new Set(prev);
      if (isSaved) next.delete(id); else next.add(id);
      return next;
    });
    const call = isSaved ? api.unsaveResource(id) : api.saveResource(id);
    call.catch(() => {
      // revert on failure
      setSavedItems((prev) => {
        const next = new Set(prev);
        if (isSaved) next.add(id); else next.delete(id);
        return next;
      });
    });
  }

  return (
    <div className="resources-page-v2">
      <div className="resources-v2-grid">
        <main className="resources-v2-main">
          <header className="resources-v2-header">
            <div>
              <h1>Resources</h1>
              <p>Explore articles, exercises, and tools designed to support your mental wellness every day.</p>
            </div>
          </header>

          <div className="resources-v2-toolbar">
            <label className="resources-v2-search">
              <span>{"\u2315"}</span>
              <input
                type="text"
                placeholder="Search resources..."
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
            </label>
            <select className="resources-v2-sort" value={sort} onChange={(event) => setSort(event.target.value)} aria-label="Sort resources">
              <option>Newest</option>
              <option>Most popular</option>
              <option>Shortest</option>
            </select>
          </div>

          <div className="resources-v2-tabs" role="tablist" aria-label="Resource categories">
            {FILTER_TABS.map((tab) => (
              <button
                key={tab}
                className={activeTab === tab ? "active" : ""}
                type="button"
                onClick={() => setActiveTab(tab)}
              >
                {tab}
              </button>
            ))}
          </div>

          {filtered.length === 0 ? (
            <div className="resources-empty-state">
              <div>{"\u2315"}</div>
              <h3>No resources found</h3>
              <p>Try another keyword or choose a different category.</p>
            </div>
          ) : (
            <section className="resources-v2-card-grid" aria-label="Resource list">
              {filtered.map((resource) => (
                <ResourceCard
                  key={resource.id}
                  resource={resource}
                  saved={savedItems.has(resource.id)}
                  onToggleSave={toggleSave}
                  onOpen={setOpenRes}
                />
              ))}
            </section>
          )}

          <footer className="resources-v2-note">
            <span>{"\u25C7"}</span>
            All resources are reviewed by professionals and based on evidence-informed practices.
          </footer>
        </main>

        <aside className="resources-v2-sidebar">
          <section className="resources-v2-emergency-card">
            <div className="resources-emergency-copy">
              <div className="resources-alert-icon">!</div>
              <div>
                <h2>Need support now?</h2>
                <p>If you are in crisis or thinking about harming yourself, please seek help immediately.</p>
                <button type="button">Get Emergency Support</button>
              </div>
            </div>
            <Mascot variant="concerned" size={118} />
          </section>

          <section className="resources-v2-side-card">
            <div className="resources-v2-side-head">
              <h2>Saved Resources</h2>
              <button type="button">View all</button>
            </div>
            <div className="saved-resource-list">
              {(savedResources.length ? savedResources : items).slice(0, 3).map((resource, index) => (
                <SavedResourceItem key={resource.id || index} title={resource.title} resource={resource} />
              ))}
              {!loading && items.length === 0 && (
                <p className="saved-resource-meta" style={{ padding: "8px 0" }}>No resources yet.</p>
              )}
            </div>
            <button className="view-saved-btn" type="button">View all saved resources</button>
          </section>

          <section className="resources-v2-motivation-card">
            <div>
              <h2>You deserve care {"\u2665"}</h2>
              <p>Taking a few minutes for your mental health each day can make a real difference.</p>
              <button type="button">Explore Recommended Exercises</button>
            </div>
            <Mascot variant="resources" size={112} />
          </section>
        </aside>
      </div>

      {openRes && <ResourceDetail resource={openRes} onClose={() => setOpenRes(null)} />}
    </div>
  );
}

