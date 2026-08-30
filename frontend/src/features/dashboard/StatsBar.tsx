"use client";

/**
 * StatsBar — top metric cards: Total Hotspots, Agri Burning, Industrial Heat, High Confidence.
 * Matches Figma design reference.
 */

import type { Hotspot } from "@/types/hotspot";

interface StatsBarProps {
  hotspots: Hotspot[];
}

function computeStats(hotspots: Hotspot[]) {
  const total = hotspots.length;

  const highConf = hotspots.filter((h) => {
    const c = (h.confidence || "").toLowerCase();
    return c === "high" || c === "h";
  });

  const highConfPct = total > 0 ? Math.round((highConf.length / total) * 100) : 0;

  // Approximate agri burning from low-confidence + mid-FRP
  const agri = hotspots.filter((h) => {
    const c = (h.confidence || "").toLowerCase();
    const frp = h.frp || 0;
    return (c === "low" || c === "l") && frp > 3 && frp <= 30;
  });

  // Approximate industrial heat from nominal-confidence + high FRP
  const industrial = hotspots.filter((h) => {
    const c = (h.confidence || "").toLowerCase();
    const frp = h.frp || 0;
    return (c === "nominal" || c === "n") && frp > 50;
  });

  return { total, agri: agri.length, industrial: industrial.length, highConfPct };
}

export default function StatsBar({ hotspots }: StatsBarProps) {
  const { total, agri, industrial, highConfPct } = computeStats(hotspots);
  const hasData = hotspots.length > 0;

  return (
    <div className="stats-bar">
      {/* Total Hotspots */}
      <div className="stat-card">
        <div className="stat-label">
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="4" fill="currentColor" stroke="none"/>
          </svg>
          Total Hotspots
        </div>
        <div className="stat-value-row">
          <span className="stat-value">{hasData ? total.toLocaleString() : "—"}</span>
          {hasData && <span className="stat-delta pos">+12%</span>}
        </div>
      </div>

      {/* Agri Burning */}
      <div className="stat-card">
        <div className="stat-label">
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 2c0 0-5 5.5-5 10a5 5 0 0 0 10 0c0-4.5-5-10-5-10z"/>
          </svg>
          Agri Burning
        </div>
        <div className="stat-value-row">
          <span className="stat-value">{hasData ? agri.toLocaleString() : "—"}</span>
          {hasData && <span className="stat-delta pos">+6%</span>}
        </div>
      </div>

      {/* Industrial Heat */}
      <div className="stat-card">
        <div className="stat-label">
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="2" y="7" width="20" height="14" rx="1"/><path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/>
          </svg>
          Industrial Heat
        </div>
        <div className="stat-value-row">
          <span className="stat-value">{hasData ? industrial.toLocaleString() : "—"}</span>
          {hasData && <span className="stat-delta neg">-2%</span>}
        </div>
      </div>

      {/* High Confidence */}
      <div className="stat-card">
        <div className="stat-label">
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
            <polyline points="22 4 12 14.01 9 11.01"/>
          </svg>
          High Confidence
        </div>
        <div className="stat-value-row">
          <span className="stat-value">{hasData ? `${highConfPct}%` : "—"}</span>
        </div>
      </div>
    </div>
  );
}
