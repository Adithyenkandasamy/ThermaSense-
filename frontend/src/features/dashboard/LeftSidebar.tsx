"use client";

/**
 * LeftSidebar — satellite source, region, analysis parameters, event legend.
 * Matches the Figma design reference.
 */

import { useRef } from "react";
import type { SatelliteSource, Hotspot, RegionOption } from "@/types/hotspot";
import LoadingSpinner from "@/components/LoadingSpinner";

interface LeftSidebarProps {
  satellites: SatelliteSource[];
  onSatellitesChange: (sources: SatelliteSource[]) => void;
  dayRange: number;
  onDayRangeChange: (days: number) => void;
  region: RegionOption;
  onRegionChange: (r: RegionOption) => void;
  confidenceThreshold: number;
  onConfidenceChange: (v: number) => void;
  onFetch: () => void;
  loading: boolean;
  error: string | null;
  hotspots: Hotspot[];
}

const SAT_SOURCES: { id: SatelliteSource; label: string }[] = [
  { id: "NOAA-20", label: "NOAA-20" },
  { id: "NOAA-21", label: "NOAA-21" },
];

const DATE_OPTIONS = [
  { value: 1, label: "Last 24 Hours" },
  { value: 2, label: "Last 2 Days" },
  { value: 3, label: "Last 3 Days" },
  { value: 4, label: "Last 4 Days" },
  { value: 5, label: "Last 5 Days" },
];

const REGION_OPTIONS: { value: RegionOption; label: string }[] = [
  { value: "all", label: "All Active Regions" },
  { value: "mediterranean", label: "Southern Europe / Mediterranean" },
  { value: "india", label: "India & South Asia" },
  { value: "california", label: "North America (California)" },
];

const LEGEND_ITEMS = [
  { color: "#f97316", label: "Wildfire", icon: "🔥" },
  { color: "#84cc16", label: "Vegetation Fire", icon: "🌿" },
  { color: "#eab308", label: "Agri Burning", icon: "🌾" },
  { color: "#8b5cf6", label: "Industrial Heat", icon: "🏭" },
  { color: "#ef4444", label: "Volcanic", icon: "🌋" },
];

export default function LeftSidebar({
  satellites,
  onSatellitesChange,
  dayRange,
  onDayRangeChange,
  region,
  onRegionChange,
  confidenceThreshold,
  onConfidenceChange,
  onFetch,
  loading,
  error,
  hotspots,
}: LeftSidebarProps) {
  const sliderRef = useRef<HTMLInputElement>(null);

  const toggleSat = (id: SatelliteSource) => {
    if (satellites.includes(id)) {
      if (satellites.length > 1) onSatellitesChange(satellites.filter((s) => s !== id));
    } else {
      onSatellitesChange([...satellites, id]);
    }
  };

  return (
    <aside className="left-sidebar">
      {/* Satellite Source */}
      <div className="sidebar-section">
        <div className="sidebar-label">Satellite Source</div>
        <div className="sat-pill-group">
          {SAT_SOURCES.map((s) => (
            <button
              key={s.id}
              className={`sat-pill${satellites.includes(s.id) ? " active" : ""}`}
              onClick={() => toggleSat(s.id)}
              aria-pressed={satellites.includes(s.id)}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      {/* Analysis Parameters */}
      <div className="sidebar-section">
        <div className="sidebar-label">Analysis Parameters</div>

        {/* Region Selector */}
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 6 }}>
            Geographic Region
          </div>
          <select
            className="date-select"
            value={region}
            onChange={(e) => onRegionChange(e.target.value as RegionOption)}
            id="region-select"
          >
            {REGION_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        {/* Date Range */}
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 6 }}>
            Date Range (UTC)
          </div>
          <select
            className="date-select"
            value={dayRange}
            onChange={(e) => onDayRangeChange(Number(e.target.value))}
            id="date-range-select"
          >
            {DATE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        {/* Confidence Threshold */}
        <div style={{ marginBottom: 14 }}>
          <div className="conf-label-row">
            <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
              Confidence Threshold
            </span>
            <span className="conf-value">{confidenceThreshold}%</span>
          </div>
          <input
            ref={sliderRef}
            type="range"
            min={0}
            max={100}
            value={confidenceThreshold}
            onChange={(e) => onConfidenceChange(Number(e.target.value))}
            className="conf-slider"
            style={{ "--val": `${confidenceThreshold}%` } as React.CSSProperties}
            id="confidence-slider"
          />
        </div>

        {/* Fetch Button */}
        <button
          className="fetch-btn"
          onClick={onFetch}
          disabled={loading}
          id="fetch-btn"
        >
          {loading ? (
            <>
              <LoadingSpinner size="sm" />
              Fetching...
            </>
          ) : (
            <>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <polyline points="23 4 23 10 17 10" />
                <polyline points="1 20 1 14 7 14" />
                <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
              </svg>
              Fetch Thermal Data
            </>
          )}
        </button>

        {/* Error message */}
        {error && (
          <div style={{
            marginTop: 8,
            padding: "6px 10px",
            background: "rgba(239,68,68,0.1)",
            border: "1px solid rgba(239,68,68,0.3)",
            borderRadius: "var(--radius-sm)",
            color: "#f87171",
            fontSize: 11,
            lineHeight: 1.4,
          }}>
            {error}
          </div>
        )}
      </div>

      {/* Event Legend */}
      <div className="sidebar-section">
        <div className="sidebar-label">Event Legend</div>
        <div className="legend-list">
          {LEGEND_ITEMS.map((item) => (
            <div key={item.label} className="legend-item">
              <span className="legend-dot" style={{ background: item.color }} />
              <span style={{ fontSize: 13, marginRight: 6 }}>{item.icon}</span>
              <span className="legend-name">{item.label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Sidebar Footer */}
      <div className="sidebar-footer">
        <div className="footer-stat">
          <span className="footer-stat-label">Observations</span>
          <span className="footer-stat-value">{hotspots.length}</span>
        </div>
        <div className="footer-stat">
          <span className="footer-stat-label">Sources</span>
          <span className="footer-stat-value">{satellites.length}</span>
        </div>
      </div>
    </aside>
  );
}
