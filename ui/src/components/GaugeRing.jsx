import React from "react";

// Shared geometry keeps the technical indicators visually consistent.
export function GaugeRing({ value, active = false }) {
  const percent = Number.isFinite(value) ? Math.min(100, Math.max(0, value)) : null;
  return <svg className="gauge-ring" viewBox="0 0 32 32" aria-hidden="true" focusable="false">
    <circle className="gauge-track" cx="16" cy="16" r="12" />
    <circle className="gauge-fill" cx="16" cy="16" r="12" pathLength="100"
      strokeDasharray={`${active ? 28 : percent ?? 0} 100`} transform="rotate(-90 16 16)" />
    {!active && <text x="16" y="16" dy=".35em" textAnchor="middle">{percent === null ? "–" : <>{Math.round(percent)}<tspan className="gauge-unit">%</tspan></>}</text>}
  </svg>;
}
