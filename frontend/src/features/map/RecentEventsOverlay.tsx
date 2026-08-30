"use client";

/**
 * RecentEventsOverlay — bottom map overlay showing the 3 most recent thermal events.
 * Matches Figma "Recent Thermal Events" panel.
 */

import type { Hotspot } from "@/types/hotspot";

interface RecentEventsOverlayProps {
  hotspots: Hotspot[];
  onSelect: (hotspot: Hotspot) => void;
}

function inferEventType(hotspot: Hotspot): { type: string; color: string } {
  const frp = hotspot.frp || 0;
  const c = (hotspot.confidence || "").toLowerCase();
  const isDay = hotspot.daynight === "D";

  if (frp > 100) return { type: "Wildfire", color: "#f97316" };
  if (frp > 50 && !isDay) return { type: "Industrial Heat", color: "#8b5cf6" };
  if (frp > 15 && (c === "low" || c === "l")) return { type: "Agri Burning", color: "#eab308" };
  if (frp > 8) return { type: "Vegetation Fire", color: "#84cc16" };
  return { type: "Thermal Anomaly", color: "#00d4ff" };
}

function inferConfBadge(hotspot: Hotspot): { label: string; cls: string } {
  const c = (hotspot.confidence || "").toLowerCase();
  if (c === "high" || c === "h") return { label: "HIGH CONF.", cls: "high" };
  if (c === "nominal" || c === "n") return { label: "VERIFIED", cls: "verified" };
  return { label: "MEDIUM CONF.", cls: "medium" };
}

function inferLocation(hotspot: Hotspot): string {
  const lat = hotspot.latitude;
  const lon = hotspot.longitude;

  // Rough location heuristics
  if (lat > 30 && lat < 50 && lon > -130 && lon < -60) return "North America";
  if (lat > 35 && lat < 70 && lon > -10 && lon < 40) return "Europe";
  if (lat > 15 && lat < 55 && lon > 60 && lon < 150) return "Central Asia";
  if (lat > -10 && lat < 35 && lon > 60 && lon < 100) return "South Asia";
  if (lat > -40 && lat < 15 && lon > -80 && lon < -30) return "South America";
  if (lat > -35 && lat < 35 && lon > -20 && lon < 55) return "Africa";
  if (lat > -45 && lat < -10 && lon > 110 && lon < 155) return "Australia";
  if (lat > 5 && lat < 55 && lon > 100 && lon < 150) return "Southeast Asia";
  return `${lat > 0 ? "N" : "S"} ${Math.abs(lat).toFixed(1)}°`;
}

function formatEventTime(isoString: string): string {
  try {
    const dt = new Date(isoString);
    return dt.toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
      timeZone: "UTC",
    }) + " UTC";
  } catch {
    return "—";
  }
}

export default function RecentEventsOverlay({
  hotspots,
  onSelect,
}: RecentEventsOverlayProps) {
  if (hotspots.length === 0) return null;

  // Take most recent 3 by acquisition time
  const recent = [...hotspots]
    .sort((a, b) =>
      new Date(b.acquisition_datetime).getTime() - new Date(a.acquisition_datetime).getTime()
    )
    .slice(0, 3);

  return (
    <div className="events-overlay">
      <div className="events-overlay-inner">
        <div className="events-label">Recent Thermal Events</div>
        <div className="events-cards">
          {recent.map((h) => {
            const { type, color } = inferEventType(h);
            const conf = inferConfBadge(h);
            const loc = inferLocation(h);
            return (
              <div
                key={h.id}
                className="event-card"
                onClick={() => onSelect(h)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => e.key === "Enter" && onSelect(h)}
              >
                <div className="event-time">{formatEventTime(h.acquisition_datetime)}</div>
                <div className="event-type" style={{ color }}>
                  {type}
                </div>
                <div className="event-location">{loc}</div>
                <span className={`event-conf-badge ${conf.cls}`}>{conf.label}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
