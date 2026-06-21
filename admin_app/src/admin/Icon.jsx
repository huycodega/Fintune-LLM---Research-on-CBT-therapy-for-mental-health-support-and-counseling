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
  arrowUp: <><path d="M12 19V6" /><path d="M6 12l6-6 6 6" /></>,
  arrowDown: <><path d="M12 5v13" /><path d="M6 12l6 6 6-6" /></>,
  download: <><path d="M12 3v12" /><path d="M7 10l5 5 5-5" /><path d="M5 21h14" /></>,
  calendar: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M8 3v4M16 3v4M3 10h18" /></>,
  info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8h.01" /></>,
  menu: <path d="M4 7h16M4 12h16M4 17h16" />,
  shieldCheck: <><path d="M12 3l7 3v5c0 5-3 8-7 10-4-2-7-5-7-10V6z" /><path d="M8.5 12l2.2 2.2 4.8-5" /></>,
  lock: <><rect x="5" y="10" width="14" height="11" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v3" /></>,
  refresh: <><path d="M20 7v5h-5" /><path d="M4 17v-5h5" /><path d="M6.1 8a7 7 0 0 1 11.7-2.1L20 8M4 16l2.2 2.1A7 7 0 0 0 18 16" /></>,
  sliders: <><path d="M4 6h10M18 6h2M4 12h3M11 12h9M4 18h8M16 18h4" /><circle cx="16" cy="6" r="2" /><circle cx="9" cy="12" r="2" /><circle cx="14" cy="18" r="2" /></>,
  mail: <><rect x="3" y="5" width="18" height="14" rx="2" /><path d="M4 7l8 6 8-6" /></>,
  message: <><path d="M4 4h16v13H9l-5 4z" /><path d="M8 9h8M8 13h5" /></>,
  plug: <><path d="M8 3v5M16 3v5M6 8h12v3a6 6 0 0 1-12 0zM12 17v4" /></>,
  backup: <><path d="M5 18a4 4 0 0 1 1-7.9A6 6 0 0 1 17.5 8 4.5 4.5 0 0 1 18 17H8" /><path d="M12 20v-8M8.5 15.5 12 12l3.5 3.5" /></>,
  restore: <><path d="M4 8V3m0 0h5M4 3l3.5 3.5A8 8 0 1 1 5 15" /><path d="M12 8v5l3 2" /></>,
  key: <><circle cx="8" cy="15" r="4" /><path d="M11 12l8-8M15 8l3 3M17 6l2 2" /></>,
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
  flag:    <><path d="M6 21V4" /><path d="M6 4h11l-2 3.5L17 11H6z" /></>,
  xCircle: <><circle cx="12" cy="12" r="9" /><path d="M15 9l-6 6M9 9l6 6" /></>,
  heart:   <path d="M12 20s-6.5-4-9-8.2A4.4 4.4 0 0 1 12 7a4.4 4.4 0 0 1 9 4.8C18.5 16 12 20 12 20z" />,
  external: <><path d="M14 4h6v6" /><path d="M20 4l-9 9" /><path d="M19 14v5a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" /></>,
};

export default function Icon({ name, size = 18, className = "", stroke = 1.7 }) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round">
      {PATHS[name]}
    </svg>
  );
}
