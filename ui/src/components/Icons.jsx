import React from "react";
const paths = {
  back: <path d="M20 12H4m6-6-6 6 6 6" />,
  reset: <><path d="M3 11a9 9 0 1 1 2 7M3 4v7h7" /></>,
  settings: <><path d="M4 7h6m4 0h6M4 17h10m4 0h2" /><circle cx="12" cy="7" r="2" /><circle cx="16" cy="17" r="2" /></>,
  close: <path d="m6 6 12 12M18 6 6 18" />,
  attach: <path d="m8 12 7-7a4 4 0 0 1 6 6L10 22a6 6 0 0 1-8-8L13 3m-7 13 9-9a2 2 0 0 1 3 3l-9 9" />,
  mic: <><rect x="9" y="2" width="6" height="12" rx="3" /><path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3M8 22h8" /></>,
  stop: <rect x="6" y="6" width="12" height="12" rx="1" />,
  send: <path d="M12 20V4m-7 7 7-7 7 7" />,
  history: <><path d="M3 11a9 9 0 1 1 2 7M3 4v7h7M12 7v5l3 2" /></>,
  save: <><path d="M4 3h13l4 4v14H3V3h1M7 3v6h10V3M7 21v-7h10v7" /></>,
};
export function Icon({ name }) {
  return <svg className="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">{paths[name]}</svg>;
}
export function IconButton({ icon, label, className = "", type = "button", ...props }) {
  return <button {...props} type={type} className={`icon-button ${className}`} aria-label={label} title={label}><Icon name={icon} /></button>;
}
