/* Shared admin line-icon set (used by every admin page). */
const PATHS = {
  // sidebar
  grid:    <><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></>,
  users:   <><circle cx="9" cy="8" r="3" /><path d="M3 20c0-3.3 2.7-5 6-5s6 1.7 6 5" /><path d="M16 5.5a2.8 2.8 0 0 1 0 5.5M18 20c0-2.3-.8-3.8-2-4.6" /></>,
  cases:   <><rect x="6" y="4" width="12" height="17" rx="2" /><path d="M9.5 4V2.8h5V4" /><path d="M8 13h2.2l1-2 1.8 4 1-2H16" /></>,
  shield:  <path d="M12 3l7 3v5c0 5-3 8-7 10-4-2-7-5-7-10V6z" />,
  alert:   <><path d="M12 3.5l9 16.5H3z" /><path d="M12 10v4.5M12 17.5h.01" /></>,
  expert:  <><circle cx="9" cy="8" r="3.2" /><path d="M3.5 19a5.5 5.5 0 0 1 11 0" /><path d="M16 4.6c1.6-1.4 4-.3 4 1.7 0 1.6-2 3-4 4.3-2-1.3-4-2.7-4-4.3 0-2 2.4-3.1 4-1.7Z" /></>,
  sparkle: <path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z" />,
  book:    <><path d="M5 4.5A1.5 1.5 0 0 1 6.5 3H19v15.5H6.5A1.5 1.5 0 0 0 5 20z" /><path d="M19 18.5H6.5A1.5 1.5 0 0 0 5 20" /></>,
  folder:  <path d="M3 7a2 2 0 0 1 2-2h3.5l2 2H19a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />,
  bars:    <path d="M4 20V11M10 20V5M16 20v-6M22 20H2" />,
  logs:    <><path d="M8 6h13M8 12h13M8 18h13" /><path d="M3.5 6h.01M3.5 12h.01M3.5 18h.01" /></>,
  gear:    <><circle cx="12" cy="12" r="3" /><path d="M12 2.5v2.5M12 19v2.5M21.5 12H19M5 12H2.5M18.4 5.6l-1.8 1.8M7.4 16.6l-1.8 1.8M18.4 18.4l-1.8-1.8M7.4 7.4 5.6 5.6" /></>,
  // top bar / controls
  search:  <><circle cx="11" cy="11" r="7" /><path d="M21 21l-4.3-4.3" /></>,
  filter:  <path d="M3 5h18l-7 8.2V20l-4-2v-4.8z" />,
  bell:    <><path d="M6 9a6 6 0 1 1 12 0c0 5 2 6 2 6H4s2-1 2-6z" /><path d="M10 20a2 2 0 0 0 4 0" /></>,
  chevronDown:  <path d="M6 9l6 6 6-6" />,
  chevronLeft:  <path d="M15 6l-6 6 6 6" />,
  chevronRight: <path d="M9 6l6 6-6 6" />,
  chevronsLeft:  <><path d="M17 6l-6 6 6 6" /><path d="M11 6l-6 6 6 6" /></>,
  chevronsRight: <><path d="M7 6l6 6-6 6" /><path d="M13 6l6 6-6 6" /></>,
  close:   <path d="M6 6l12 12M18 6L6 18" />,
  sort:    <><path d="M7 4v15" /><path d="M4 16l3 3 3-3" /><path d="M14 6h7M14 11h5M14 16h3" /></>,
  plus:    <><path d="M12 5v14" /><path d="M5 12h14" /></>,
  // stat / status
  checkCircle: <><circle cx="12" cy="12" r="9" /><path d="M8 12l3 3 5-6" /></>,
  file:    <><path d="M7 3h7l4 4v14H7z" /><path d="M14 3v4h4" /></>,
  clock:   <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  alert:   <><path d="M12 3.5l9 16.5H3z" /><path d="M12 10v4.5M12 17.5h.01" /></>,
  arrowUp: <><path d="M12 19V6" /><path d="M6 12l6-6 6 6" /></>,
  // actions
  eye:     <><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z" /><circle cx="12" cy="12" r="3" /></>,
  pencil:  <><path d="M4 20h4L18 10l-4-4L4 16z" /><path d="M13.5 6.5l4 4" /></>,
  dots:    <g fill="currentColor" stroke="none"><circle cx="5" cy="12" r="1.6" /><circle cx="12" cy="12" r="1.6" /><circle cx="19" cy="12" r="1.6" /></g>,
  check:   <path d="M5 12l4 4 10-10" />,
  publish: <><path d="M12 3v12" /><path d="M7 8l5-5 5 5" /><path d="M5 21h14" /></>,
  // resource types
  headphones: <><path d="M4 14v-2a8 8 0 0 1 16 0v2" /><rect x="3" y="13.5" width="4" height="6.5" rx="1.6" /><rect x="17" y="13.5" width="4" height="6.5" rx="1.6" /></>,
  article: <><path d="M6 3h9l3 3v15H6z" /><path d="M15 3v3h3" /><path d="M9 11h6M9 14.5h6M9 8h3" /></>,
  play:    <><circle cx="12" cy="12" r="9" /><path d="M10 8.5l5.5 3.5-5.5 3.5z" fill="currentColor" stroke="none" /></>,
  tool:    <><path d="M4 7h8M18 7h2M4 17h2M12 17h8" /><circle cx="15" cy="7" r="2.4" /><circle cx="9" cy="17" r="2.4" /></>,
  phone:   <path d="M5 4h4l2 5-3 2c1 3 3 5 6 6l2-3 5 2v4c0 1-1 2-2 2C9 22 2 15 2 6c0-1 1-2 3-2z" />,
  link:    <><path d="M9 15l6-6" /><path d="M10 6l1-1a4 4 0 0 1 6 6l-1 1" /><path d="M14 18l-1 1a4 4 0 0 1-6-6l1-1" /></>,
};

export default function Icon({ name, size = 18, className = "", stroke = 1.7 }) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round">
      {PATHS[name]}
    </svg>
  );
}
