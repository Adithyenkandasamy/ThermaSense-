"use client";

/**
 * RecentEventsOverlay — bottom map overlay showing active clustered thermal events.
 * Connects to live backend ThermalEvent entities with fallback to raw observations.
 */

import { useState, useEffect } from "react";
import type { Hotspot } from "@/types/hotspot";
import type { ThermalEvent } from "@/types/event";
import { fetchEvents } from "@/services/api";

interface RecentEventsOverlayProps {
  hotspots: Hotspot[];
  onSelect: (hotspot: Hotspot) => void;
}

function inferConfBadge(confStr?: string | null): { label: string; cls: string } {
  const c = (confStr || "").toLowerCase();
  if (c === "high" || c === "h") return { label: "HIGH CONF.", cls: "high" };
  if (c === "nominal" || c === "n") return { label: "VERIFIED", cls: "verified" };
  return { label: "MEDIUM CONF.", cls: "medium" };
}

function inferLocation(lat: number, lon: number): string {
  if (lat > 30 && lat < 50 && lon > -130 && lon < -60) return "North America";
  if (lat > 35 && lat < 70 && lon > -10 && lon < 40) return "Mediterranean / EU";
  if (lat > 15 && lat < 55 && lon > 60 && lon < 150) return "Central Asia";
  if (lat > -10 && lat < 35 && lon > 60 && lon < 100) return "South Asia";
  if (lat > -40 && lat < 15 && lon > -80 && lon < -30) return "South America";
  if (lat > -35 && lat < 35 && lon > -20 && lon < 55) return "Africa";
  if (lat > -45 && lat < -10 && lon > 110 && lon < 155) return "Australia";
  if (lat > 5 && lat < 55 && lon > 100 && lon < 150) return "Southeast Asia";
  return `${lat > 0 ? "N" : "S"} ${Math.abs(lat).toFixed(1)}°, ${lon > 0 ? "E" : "W"} ${Math.abs(lon).toFixed(1)}°`;
}

function formatEventTime(isoString: string): string {
  try {
    const dt = new Date(isoString);
    return (
      dt.toLocaleTimeString("en-US", {
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
        timeZone: "UTC",
      }) + " UTC"
    );
  } catch {
    return "—";
  }
}

export default function RecentEventsOverlay({
  hotspots,
  onSelect,
}: RecentEventsOverlayProps) {
  const [events, setEvents] = useState<ThermalEvent[]>([]);

  useEffect(() => {
    let isMounted = true;
    async function loadRecentEvents() {
      try {
        const res = await fetchEvents({ status: "active", limit: 3 });
        if (isMounted && res.events && res.events.length > 0) {
          setEvents(res.events);
        }
      } catch {
        // Fallback to hotspot prop
      }
    }
    loadRecentEvents();
    return () => {
      isMounted = false;
    };
  }, [hotspots.length]);

  if (events.length === 0 && hotspots.length === 0) return null;

  // Render from real events if available, otherwise fallback to top hotspots
  if (events.length > 0) {
    return (
      <div className="events-overlay">
        <div className="events-overlay-inner">
          <div className="events-label">Active Clustered Events</div>
          <div className="events-cards">
            {events.map((ev) => {
              const conf = inferConfBadge(ev.max_confidence);
              const loc = inferLocation(ev.centroid_latitude, ev.centroid_longitude);
              const totalFrp = ev.total_frp || 0;
              const obsCount = ev.observation_count || 1;

              // Synthesize a hotspot representation for the click handler
              const dummyHotspot: Hotspot = {
                id: ev.observations?.[0]?.id || ev.id,
                latitude: ev.centroid_latitude,
                longitude: ev.centroid_longitude,
                acquisition_datetime: ev.started_at,
                satellite: ev.observations?.[0]?.satellite || "VIIRS",
                instrument: "VIIRS",
                brightness: ev.observations?.[0]?.brightness || null,
                bright_ti4: null,
                bright_ti5: null,
                frp: totalFrp,
                confidence: ev.max_confidence || "nominal",
                daynight: "D",
                source: "FIRMS_CLUSTERED",
              };

              return (
                <div
                  key={ev.id}
                  className="event-card"
                  onClick={() => onSelect(dummyHotspot)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => e.key === "Enter" && onSelect(dummyHotspot)}
                >
                  <div className="event-time">{formatEventTime(ev.started_at)}</div>
                  <div className="event-type" style={{ color: totalFrp > 100 ? "#f97316" : "#00d4ff" }}>
                    {totalFrp > 100 ? "Severe Fire Event" : "Thermal Cluster"}
                    <span style={{ fontSize: 10, color: "#94a3b8", marginLeft: 4 }}>
                      ({obsCount} obs)
                    </span>
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

  // Fallback to top 3 hotspots
  const recent = [...hotspots]
    .sort(
      (a, b) =>
        new Date(b.acquisition_datetime).getTime() -
        new Date(a.acquisition_datetime).getTime()
    )
    .slice(0, 3);

  return (
    <div className="events-overlay">
      <div className="events-overlay-inner">
        <div className="events-label">Recent Thermal Events</div>
        <div className="events-cards">
          {recent.map((h) => {
            const conf = inferConfBadge(h.confidence);
            const loc = inferLocation(h.latitude, h.longitude);
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
                <div className="event-type" style={{ color: "#00d4ff" }}>
                  Thermal Anomaly
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
