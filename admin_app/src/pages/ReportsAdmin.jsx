import { useCallback, useEffect, useRef, useState } from "react";
import Icon from "../admin/Icon.jsx";
import Sidebar from "../admin/Sidebar.jsx";
import TopBar from "../admin/TopBar.jsx";
import { api } from "../api.js";
import { DemoNotice, updatedNow } from "../ui.jsx";

const RISK_COLORS = {
  low: "#10b981",
  medium: "#fbbf24",
  high: "#ef4444",
  emergency: "#991b1b",
};
const STATUS_META = [
  ["New", "new", "#6366f1"],
  ["In Progress", "in_progress", "#3b82f6"],
  ["Pending", "pending", "#f59e0b"],
  ["Completed", "completed", "#22c55e"],
  ["Closed", "closed", "#94a3b8"],
];

const DEMO_REPORT = {
  updated_at: "2026-06-14T09:24:00Z",
  range: { start_date: "2026-06-07", end_date: "2026-06-14", days: 8 },
  kpis: {
    total_screenings: { value: 24582, change_pct: 18.6 },
    high_risk_rate: { value_percent: 6.54, change_points: 1.21 },
    average_processing_time: { value_seconds: 1122, change_pct: -12.4 },
    ai_approval_rate: { value_percent: 91.35, change_points: 3.18 },
  },
  daily_screenings: [1650, 2010, 2390, 3120, 2470, 1540, 2080, 3180].map((screenings, index) => ({
    date: `2026-06-${String(index + 7).padStart(2, "0")}`,
    label: `${String(index + 7).padStart(2, "0")}/06`,
    screenings,
    seven_day_average: [1720, 1840, 1980, 2689, 2380, 2110, 2260, 2670][index],
  })),
  risk_distribution: [
    { key: "low", label: "Low", count: 12458, percentage: 50.7 },
    { key: "medium", label: "Medium", count: 8223, percentage: 33.5 },
    { key: "high", label: "High", count: 2980, percentage: 12.1 },
    { key: "emergency", label: "Emergency", count: 921, percentage: 2.7 },
  ],
  popular_topics: [
    ["Stress", 6152, 25], ["Anxiety", 5231, 21.3], ["Depression", 4128, 16.8],
    ["Relationships", 3024, 12.3], ["Academic Pressure", 2658, 10.8], ["Other", 1389, 5.6],
  ].map(([topic, count, percentage]) => ({ topic, count, percentage })),
  case_status: [
    [30, 23, 22, 20, 5], [31, 22, 23, 19, 5], [29, 25, 22, 20, 4],
    [32, 22, 21, 20, 5], [30, 25, 20, 20, 5], [31, 24, 21, 19, 5],
    [29, 26, 21, 19, 5], [30, 25, 20, 20, 5],
  ].map((values, index) => ({
    label: `${String(index + 7).padStart(2, "0")}/06`,
    ...Object.fromEntries(STATUS_META.map((meta, statusIndex) => [meta[1], values[statusIndex]])),
  })),
  monthly_summary: [
    ["06/2026", 24582, 6.54, 1122, 91.35, 921, 18.6, "up"],
    ["05/2026", 20748, 5.33, 1279, 88.17, 742, 12.4, "up"],
    ["04/2026", 18466, 4.27, 1391, 86.02, 611, 2.8, "down"],
    ["03/2026", 18996, 4.58, 1327, 87.45, 654, 6.5, "up"],
    ["02/2026", 17826, 4.11, 1471, 85.21, 562, 9.3, "up"],
    ["01/2026", 16317, 3.78, 1544, 84.1, 491, 7.1, "up"],
  ].map(([month, screenings, high_risk_rate, avg_processing_seconds, ai_approval_rate, emergency_cases, trend_pct, trend_direction]) => ({
    month, screenings, high_risk_rate, avg_processing_seconds, ai_approval_rate,
    emergency_cases, trend_pct, trend_direction,
  })),
  insights: [
    { icon: "arrowUp", tone: "green", title: "Screenings Increased", text: "Total screenings increased by 18.6% compared with the previous period. Demand for support is rising." },
    { icon: "alert", tone: "orange", title: "High Risk Rate Increased", text: "High-risk rate increased by 1.21%. Pay close attention to users showing high-risk signals." },
    { icon: "clock", tone: "blue", title: "Processing Time Improved", text: "Average processing time decreased by 12.4%, thanks to AI-assisted workflow optimization." },
    { icon: "users", tone: "purple", title: "AI Performance Improved", text: "AI approval rate reached 91.35%, up 3.18%. The model is learning effectively from reviewed cases." },
  ],
};

function reducedMotion() {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
}

function CountUp({ value, duration = 900 }) {
  const [text, setText] = useState(reducedMotion() ? value : "0");
  const raf = useRef(0);
  useEffect(() => {
    const raw = String(value);
    const match = raw.match(/([\d,.]+)/);
    if (!match || reducedMotion()) { setText(value); return undefined; }
    const target = Number(match[1].replace(/,/g, ""));
    const decimals = match[1].includes(".") ? match[1].split(".")[1].length : 0;
    const start = performance.now();
    const tick = (now) => {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const number = decimals
        ? (target * eased).toFixed(decimals)
        : Math.round(target * eased).toLocaleString("en-US");
      setText(raw.replace(match[1], number));
      if (progress < 1) raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [value, duration]);
  return text;
}

function formatDuration(seconds = 0) {
  const value = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(value / 60);
  return `${minutes}m ${String(value % 60).padStart(2, "0")}s`;
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString("en-US");
}

function compactNumber(value) {
  if (value >= 1000) return `${Number((value / 1000).toFixed(value >= 10000 ? 0 : 1))}K`;
  return String(Math.round(value));
}

function displayDate(iso) {
  const [year, month, day] = String(iso).split("-");
  return year && month && day ? `${day}/${month}/${year}` : iso;
}

function updatedLabel(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Updated just now";
  return `Updated ${date.toLocaleDateString("en-GB")} · ${date.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}`;
}

function CardTitle({ children, info = false }) {
  return <div className="rp-card-title"><span>{children}</span>{info && <Icon name="info" size={14} />}</div>;
}

function StatCard({ icon, tone, title, value, trend, direction = "up", positive = true, index }) {
  return (
    <article className="rp-stat rp-reveal" style={{ "--i": index }}>
      <span className={`rp-stat-icon ${tone}`}><Icon name={icon} size={23} /></span>
      <div>
        <div className="rp-stat-label">{title}</div>
        <div className="rp-stat-value"><CountUp value={value} /></div>
        <div className={`rp-stat-trend ${positive ? "good" : "bad"}`}>
          <Icon name={direction === "down" ? "arrowDown" : "arrowUp"} size={12} />
          {trend} vs previous period
        </div>
      </div>
    </article>
  );
}

function chartPoints(values, maximum) {
  const denominator = Math.max(values.length - 1, 1);
  return values.map((value, index) =>
    `${32 + (index * 544) / denominator},${170 - (value / maximum) * 148}`).join(" ");
}

function LineChart({ rows }) {
  const screenings = rows.map((row) => row.screenings);
  const averages = rows.map((row) => row.seven_day_average);
  const rawMaximum = Math.max(1, ...screenings, ...averages);
  const maximum = rawMaximum > 100 ? Math.ceil(rawMaximum / 1000) * 1000 : Math.ceil(rawMaximum);
  const yLabels = [maximum, maximum * 0.75, maximum * 0.5, maximum * 0.25, 0];
  const peak = rows.reduce((best, row) => row.screenings > best.screenings ? row : best, rows[0] || { screenings: 0, seven_day_average: 0, date: "" });
  const labelStep = Math.max(1, Math.ceil(rows.length / 8));
  return (
    <article className="rp-card rp-chart-card rp-reveal" style={{ "--i": 5 }}>
      <div className="rp-card-head">
        <CardTitle info>Daily Screenings</CardTitle>
        <div className="rp-legend"><span><i className="indigo" />Screenings</span><span><i className="dash" />7-day Average</span></div>
      </div>
      <div className="rp-line-layout">
        <div className="rp-y-labels">{yLabels.map((value, index) => <span key={index}>{compactNumber(value)}</span>)}</div>
        <div className="rp-line-plot">
          <svg viewBox="0 0 600 190" role="img" aria-label="Daily screenings line chart">
            <defs>
              <linearGradient id="rpAreaFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#6366f1" stopOpacity="0.2" />
                <stop offset="100%" stopColor="#6366f1" stopOpacity="0" />
              </linearGradient>
            </defs>
            {[20, 57, 94, 131, 168].map((y) => <line key={y} x1="32" y1={y} x2="576" y2={y} className="rp-gridline" />)}
            <polygon points={`${chartPoints(screenings, maximum)} 576,170 32,170`} className="rp-area" fill="url(#rpAreaFill)" />
            <polyline points={chartPoints(averages, maximum)} className="rp-average-line" pathLength="1" />
            <polyline points={chartPoints(screenings, maximum)} className="rp-main-line" pathLength="1" />
            {screenings.map((value, index) => (
              <circle key={index} cx={32 + (index * 544) / Math.max(screenings.length - 1, 1)}
                cy={170 - (value / maximum) * 148} r="4" className="rp-line-dot" />
            ))}
          </svg>
          <div className="rp-x-labels">{rows.map((row, index) => <span key={row.date || index}>{index % labelStep === 0 || index === rows.length - 1 ? row.label : ""}</span>)}</div>
        </div>
      </div>
    </article>
  );
}

function DonutChart({ rows, total }) {
  let offset = 0;
  return (
    <article className="rp-card rp-donut-card rp-reveal" style={{ "--i": 6 }}>
      <CardTitle>Risk Level Distribution</CardTitle>
      <div className="rp-donut-layout">
        <div className="rp-donut">
          <svg viewBox="0 0 120 120" role="img" aria-label="Risk distribution donut chart">
            <circle cx="60" cy="60" r="45" className="rp-donut-bg" />
            {rows.map((row, index) => {
              const start = offset;
              offset += row.percentage;
              return <circle key={row.key} cx="60" cy="60" r="45" pathLength="100"
                stroke={RISK_COLORS[row.key]} strokeDasharray={`${row.percentage} ${100 - row.percentage}`}
                strokeDashoffset={-start} className="rp-donut-seg" style={{ "--i": index }} />;
            })}
          </svg>
          <div className="rp-donut-center"><span>Total</span><b><CountUp value={formatNumber(total)} /></b></div>
        </div>
        <div className="rp-risk-list">
          {rows.map((row) => <div className="rp-risk-row" key={row.key}>
            <i style={{ background: RISK_COLORS[row.key] }} /><span>{row.label}</span>
            <b>{formatNumber(row.count)}</b><small>({row.percentage.toFixed(1)}%)</small>
          </div>)}
        </div>
      </div>
    </article>
  );
}

function TopicsChart({ rows }) {
  const maximum = Math.max(1, ...rows.map((row) => row.count));
  return (
    <article className="rp-card rp-topic-card rp-reveal" style={{ "--i": 7 }}>
      <CardTitle>Popular Topics</CardTitle>
      <div className="rp-topic-chart">
        {rows.map((row, index) => <div className="rp-topic-row" key={row.topic}>
          <span>{row.topic}</span><div className="rp-topic-track"><i style={{ "--w": `${(row.count / maximum) * 100}%`, "--i": index }} /></div>
          <b>{formatNumber(row.count)} <small>({row.percentage.toFixed(1)}%)</small></b>
        </div>)}
        <div className="rp-topic-axis">{[0, .25, .5, .75, 1].map((step) => <span key={step}>{compactNumber(maximum * step)}</span>)}</div>
      </div>
    </article>
  );
}

function StatusChart({ rows }) {
  const labelStep = Math.max(1, Math.ceil(rows.length / 8));
  return (
    <article className="rp-card rp-status-card rp-reveal" style={{ "--i": 8 }}>
      <CardTitle>Case Processing by Status</CardTitle>
      <div className="rp-legend rp-status-legend">{STATUS_META.map(([label,, color]) => <span key={label}><i style={{ background: color }} />{label}</span>)}</div>
      <div className="rp-status-layout">
        <div className="rp-status-y">{["100%", "75%", "50%", "25%", "0%"].map((value) => <span key={value}>{value}</span>)}</div>
        <div className="rp-status-plot">{rows.map((row, index) => <div className="rp-stack-col" key={row.date || index}>
          <div className="rp-stack">{STATUS_META.map(([, key, color]) => <i key={key} style={{ height: `${row[key]}%`, background: color, "--i": index }} />)}</div>
          <span>{index % labelStep === 0 || index === rows.length - 1 ? row.label : ""}</span>
        </div>)}</div>
      </div>
    </article>
  );
}

function Sparkline({ values, down }) {
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const spread = maximum - minimum || 1;
  const points = values.map((value, index) => `${2 + (index * 56) / Math.max(values.length - 1, 1)},${20 - ((value - minimum) / spread) * 16}`).join(" ");
  return <svg className={`rp-spark ${down ? "down" : ""}`} viewBox="0 0 60 25" aria-hidden="true"><polyline points={points} pathLength="1" /></svg>;
}

function MonthlyTable({ rows }) {
  const [page, setPage] = useState(1);
  const sparkValues = rows.slice().reverse().map((row) => row.screenings);
  return (
    <article className={`rp-card rp-table-card rp-reveal ${page === 2 ? "rp-page-two" : ""}`} style={{ "--i": 9 }}>
      <CardTitle>Monthly Summary</CardTitle>
      <div className="rp-table-wrap"><table className="rp-table">
        <thead><tr>{["Month", "Screenings", "High Risk Rate", "Avg. Processing Time", "AI Approval Rate", "Emergency Cases", "Trend"].map((header) => <th key={header}>{header}</th>)}</tr></thead>
        <tbody>{rows.map((row, index) => <tr key={row.month} style={{ "--i": index }}>
          <td><b>{row.month}</b></td><td>{formatNumber(row.screenings)}</td><td>{row.high_risk_rate.toFixed(2)}%</td>
          <td>{formatDuration(row.avg_processing_seconds)}</td><td>{row.ai_approval_rate.toFixed(2)}%</td><td>{formatNumber(row.emergency_cases)}</td>
          <td><div className={`rp-trend-cell ${row.trend_direction}`}><Sparkline values={sparkValues} down={row.trend_direction === "down"} /><span>{row.trend_direction === "down" ? "↓" : "↑"} {row.trend_pct.toFixed(1)}%</span></div></td>
        </tr>)}</tbody>
      </table></div>
      <div className="rp-pagination"><div>
        <button aria-label="Previous page" onClick={() => setPage(1)}><Icon name="chevronLeft" size={14} /></button>
        <button className={page === 1 ? "active" : ""} onClick={() => setPage(1)}>1</button>
        <button className={page === 2 ? "active" : ""} onClick={() => setPage(2)}>2</button>
        <button aria-label="Next page" onClick={() => setPage(2)}><Icon name="chevronRight" size={14} /></button>
      </div><select aria-label="Rows per page"><option>10 / page</option></select></div>
    </article>
  );
}

function Insights({ rows }) {
  return (
    <aside className="rp-card rp-insights"><CardTitle>Insights &amp; Recommendations</CardTitle>
      <div className="rp-insight-list">{rows.map((row, index) => <div className="rp-insight" key={row.title} style={{ "--i": index }}>
        <span className={row.tone}><Icon name={row.icon} size={18} /></span><div><b>{row.title}</b><p>{row.text}</p></div>
      </div>)}</div>
      <button className="rp-detail-btn">View Detailed Report <Icon name="chevronRight" size={15} /></button>
    </aside>
  );
}

function StatSkel() {
  return (
    <article className="rp-stat">
      <div className="la-skel la-skel-icon" />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="la-skel la-skel-line" style={{ width: "55%" }} />
        <div className="la-skel la-skel-line" style={{ width: "42%", height: 22, margin: "8px 0" }} />
        <div className="la-skel la-skel-line" style={{ width: "66%" }} />
      </div>
    </article>
  );
}
function CardSkel({ height }) {
  return (
    <article className="rp-card">
      <div className="la-skel la-skel-line" style={{ width: "42%", marginBottom: 14 }} />
      <div className="la-skel" style={{ height, borderRadius: 12 }} />
    </article>
  );
}
// Keeps the real page frame (grids + cards) and shimmers each part, matching
// the loading style used on every other admin page.
function LoadingView() {
  return (
    <div className="la-content-left">
      <section className="rp-kpi-grid">
        {Array.from({ length: 4 }, (_, i) => <StatSkel key={i} />)}
        <article className="rp-report-actions">
          <div className="la-skel" style={{ height: 39, borderRadius: 10 }} />
          <div className="la-skel" style={{ height: 39, borderRadius: 10 }} />
        </article>
      </section>
      <section className="rp-chart-grid">
        <CardSkel height={200} /><CardSkel height={200} /><CardSkel height={200} />
      </section>
      <section className="rp-bottom-grid">
        <CardSkel height={300} /><CardSkel height={300} /><CardSkel height={300} />
      </section>
    </div>
  );
}

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url; link.download = filename; link.click();
  URL.revokeObjectURL(url);
}

function fallbackCsv(rows) {
  const header = ["Month", "Screenings", "High Risk Rate", "Avg. Processing Seconds", "AI Approval Rate", "Emergency Cases", "Trend"];
  const body = rows.map((row) => [row.month, row.screenings, row.high_risk_rate, row.avg_processing_seconds, row.ai_approval_rate, row.emergency_cases, `${row.trend_direction === "down" ? "-" : "+"}${row.trend_pct}%`]);
  return new Blob([[header, ...body].map((row) => row.map((cell) => `"${cell}"`).join(",")).join("\n")], { type: "text/csv;charset=utf-8" });
}

function utcDateRange(days) {
  const now = new Date();
  const end = new Date(Date.UTC(now.getFullYear(), now.getMonth(), now.getDate()));
  const start = new Date(end); start.setUTCDate(start.getUTCDate() - days + 1);
  return { start_date: start.toISOString().slice(0, 10), end_date: end.toISOString().slice(0, 10) };
}

export default function ReportsAdmin({ onLogout, onNav }) {
  const [report, setReport] = useState(null);
  const [params, setParams] = useState({});
  const [loading, setLoading] = useState(true);
  const [demo, setDemo] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [rangeOpen, setRangeOpen] = useState(false);
  const [filterDays, setFilterDays] = useState(8);
  const [exporting, setExporting] = useState(false);
  const [customRange, setCustomRange] = useState(utcDateRange(8));

  const load = useCallback(async (query = {}) => {
    setLoading(true);
    try {
      const data = await api.reports(query);
      setReport(data); setParams(query); setDemo(false);
    } catch (error) {
      console.error("Reports API unavailable:", error);
      setReport(null); setParams(query); setDemo(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  function selectDays(days) {
    const query = utcDateRange(days);
    setFilterDays(days); setCustomRange(query); setRangeOpen(false); load(query);
  }

  function applyCustomRange() {
    if (!customRange.start_date || !customRange.end_date || customRange.start_date > customRange.end_date) return;
    setRangeOpen(false); load(customRange);
  }

  async function exportReport() {
    setExporting(true);
    try {
      const file = await api.exportReport(params);
      triggerDownload(file.blob, file.filename);
    } catch {
      triggerDownload(fallbackCsv((report || DEMO_REPORT).monthly_summary), "mindcare-report.csv");
    } finally {
      setExporting(false);
    }
  }

  const data = report || DEMO_REPORT;
  const kpis = data.kpis;
  const totalChange = kpis.total_screenings.change_pct;
  const riskChange = kpis.high_risk_rate.change_points;
  const processingChange = kpis.average_processing_time.change_pct;
  const approvalChange = kpis.ai_approval_rate.change_points;
  const filterPanel = <>
    <label>Reporting window<select value={filterDays} onChange={(event) => setFilterDays(Number(event.target.value))}><option value={8}>Last 8 days</option><option value={30}>Last 30 days</option><option value={90}>Last 90 days</option></select></label>
    <label>Data scope<select><option>All activity</option></select></label>
    <button onClick={() => selectDays(filterDays)}>Apply Filters</button>
  </>;

  return (
    <div className="la-shell rp-shell">
      {mobileOpen && <button className="rp-nav-scrim" onClick={() => setMobileOpen(false)} aria-label="Close navigation" />}
      <Sidebar active="reports" onNav={onNav} mobileOpen={mobileOpen} onClose={() => setMobileOpen(false)} />
      <main className="la-main rp-main">
        <TopBar title="Reports & Analytics" subtitle={demo ? updatedNow() : updatedLabel(data.updated_at)} searchPlaceholder="Search users, email, phone..."
          onLogout={onLogout} onMenu={() => setMobileOpen(true)} filterPanel={filterPanel} />
        <div className="la-content la-content-nopanel rp-content">{loading ? <LoadingView /> : <div className="la-content-left">
          {demo && <div style={{ marginBottom: 12 }}><DemoNotice>Sample data shown — reporting API isn't connected yet.</DemoNotice></div>}
          <section className="rp-kpi-grid">
            <StatCard icon="bars" tone="purple" title="Total Screenings" value={formatNumber(kpis.total_screenings.value)} trend={`${Math.abs(totalChange).toFixed(1)}%`} direction={totalChange < 0 ? "down" : "up"} positive={totalChange >= 0} index={0} />
            <StatCard icon="alert" tone="danger" title="High Risk Rate" value={`${kpis.high_risk_rate.value_percent.toFixed(2)}%`} trend={`${Math.abs(riskChange).toFixed(2)}%`} direction={riskChange < 0 ? "down" : "up"} positive={riskChange <= 0} index={1} />
            <StatCard icon="clock" tone="blue" title="Average Processing Time" value={formatDuration(kpis.average_processing_time.value_seconds)} trend={`${Math.abs(processingChange).toFixed(1)}%`} direction={processingChange <= 0 ? "down" : "up"} positive={processingChange <= 0} index={2} />
            <StatCard icon="shieldCheck" tone="green" title="AI Approval Rate" value={`${kpis.ai_approval_rate.value_percent.toFixed(2)}%`} trend={`${Math.abs(approvalChange).toFixed(2)}%`} direction={approvalChange < 0 ? "down" : "up"} positive={approvalChange >= 0} index={3} />
            <article className="rp-report-actions rp-reveal" style={{ "--i": 4 }}>
              <button className={`rp-date-btn ${rangeOpen ? "open" : ""}`} onClick={() => setRangeOpen((value) => !value)}>
                <span>{displayDate(data.range.start_date)} - {displayDate(data.range.end_date)}</span><Icon name="calendar" size={17} />
              </button>
              {rangeOpen && <div className="rp-date-menu">
                <button onClick={() => selectDays(8)}>Last 8 days</button><button onClick={() => selectDays(30)}>Last 30 days</button>
                <div className="rp-custom-range"><label>From<input type="date" value={customRange.start_date} onChange={(event) => setCustomRange((value) => ({ ...value, start_date: event.target.value }))} /></label><label>To<input type="date" value={customRange.end_date} onChange={(event) => setCustomRange((value) => ({ ...value, end_date: event.target.value }))} /></label><button onClick={applyCustomRange}>Apply custom range</button></div>
              </div>}
              <button className="rp-export" onClick={exportReport} disabled={exporting}><Icon name="download" size={16} />{exporting ? "Exporting..." : "Export Report"}</button>
            </article>
          </section>
          <section className="rp-chart-grid"><LineChart rows={data.daily_screenings} /><DonutChart rows={data.risk_distribution} total={kpis.total_screenings.value} /><TopicsChart rows={data.popular_topics} /></section>
          <section className="rp-bottom-grid"><StatusChart rows={data.case_status} /><MonthlyTable rows={data.monthly_summary} /><Insights rows={data.insights} /></section>
        </div>}</div>
      </main>
    </div>
  );
}
