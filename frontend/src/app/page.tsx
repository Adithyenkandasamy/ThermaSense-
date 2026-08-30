"use client";

/**
 * ThermaSense — Main application page.
 *
 * Layout matches Figma design:
 *   [TopNav]
 *   [LeftSidebar | StatsBar + Map + RecentEvents | HotspotIntelligencePanel]
 */

import { useState, useCallback, useEffect } from "react";
import dynamic from "next/dynamic";
import type { SatelliteSource, Hotspot, RegionOption } from "@/types/hotspot";
import type { ThermalAlert } from "@/types/export";
import { REGION_BBOXES } from "@/types/hotspot";
import { fetchHotspots } from "@/services/api";

// Components
import TopNav from "@/components/TopNav";
import LeftSidebar from "@/features/dashboard/LeftSidebar";
import StatsBar from "@/features/dashboard/StatsBar";
import RecentEventsOverlay from "@/features/map/RecentEventsOverlay";
import HotspotIntelligencePanel from "@/features/hotspots/HotspotIntelligencePanel";
import LoadingSpinner from "@/components/LoadingSpinner";

// Leaflet: no SSR
const MapView = dynamic(() => import("@/features/map/MapView"), {
  ssr: false,
  loading: () => (
    <div style={{
      width: "100%", height: "100%",
      background: "#0a0e17",
      display: "flex", alignItems: "center", justifyContent: "center",
    }}>
      <LoadingSpinner size="lg" message="Initializing map..." />
    </div>
  ),
});

export default function Home() {
  // ── State ──────────────────────────────────────────────
  const [satellites, setSatellites] = useState<SatelliteSource[]>(["NOAA-20"]);
  const [dayRange, setDayRange] = useState<number>(1);
  const [region, setRegion] = useState<RegionOption>("all");
  const [confidenceThreshold, setConfidenceThreshold] = useState<number>(80);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hotspots, setHotspots] = useState<Hotspot[]>([]);
  const [selectedHotspot, setSelectedHotspot] = useState<Hotspot | null>(null);
  const [lastFetched, setLastFetched] = useState<Date | null>(null);

  // ── Fetch handler ──────────────────────────────────────
  const handleFetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    setSelectedHotspot(null);

    try {
      const all: Hotspot[] = [];
      const bbox = REGION_BBOXES[region];
      for (const sat of satellites) {
        const res = await fetchHotspots({ satellite: sat, days: dayRange, bbox });
        all.push(...res.observations);
      }
      setHotspots(all);
      setLastFetched(new Date());

      if (all.length === 0) {
        setError("No thermal observations found. Try a wider date range or different satellite.");
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Unexpected error";
      setError(msg);
      setHotspots([]);
    } finally {
      setLoading(false);
    }
  }, [satellites, dayRange, region]);

  // Initial load
  useEffect(() => {
    handleFetch();
  }, [handleFetch]);

  // ── Select handler ─────────────────────────────────────
  const handleSelect = useCallback((h: Hotspot) => {
    setSelectedHotspot((prev) => (prev?.id === h.id ? null : h));
  }, []);

  const handleSelectAlert = useCallback((a: ThermalAlert) => {
    setSelectedHotspot({
      id: a.event_id || a.alert_id,
      latitude: a.latitude,
      longitude: a.longitude,
      acquisition_datetime: a.triggered_at,
      satellite: "NOAA-20",
      instrument: "VIIRS",
      brightness: null,
      bright_ti4: null,
      bright_ti5: null,
      frp: a.frp || 0,
      confidence: a.severity === "CRITICAL" ? "high" : "nominal",
      daynight: "D",
      source: "ALERT_TRIGGERED",
    });
  }, []);

  const handleClose = useCallback(() => setSelectedHotspot(null), []);

  return (
    <div className="app-shell">
      {/* Top Navigation */}
      <TopNav
        hotspotsCount={hotspots.length}
        lastFetched={lastFetched}
        onSelectAlert={handleSelectAlert}
      />

      {/* Body */}
      <div className="app-body">
        {/* Left Sidebar */}
        <LeftSidebar
          satellites={satellites}
          onSatellitesChange={setSatellites}
          dayRange={dayRange}
          onDayRangeChange={setDayRange}
          region={region}
          onRegionChange={setRegion}
          confidenceThreshold={confidenceThreshold}
          onConfidenceChange={setConfidenceThreshold}
          onFetch={handleFetch}
          loading={loading}
          error={error}
          hotspots={hotspots}
        />

        {/* Center: Stats + Map */}
        <div className="center-content">
          {/* Stats Bar */}
          <StatsBar hotspots={hotspots} />

          {/* Map + Overlays */}
          <div className="map-container">
            <MapView
              hotspots={hotspots}
              selectedHotspot={selectedHotspot}
              onSelectHotspot={handleSelect}
              confidenceThreshold={confidenceThreshold}
            />

            {/* Recent Events overlay */}
            <RecentEventsOverlay hotspots={hotspots} onSelect={handleSelect} />

            {/* Empty state */}
            {!loading && hotspots.length === 0 && !error && (
              <div className="map-empty-state">
                <div className="map-empty-card">
                  <div style={{ marginBottom: 14, display: "flex", justifyContent: "center" }}>
                    <div style={{
                      width: 52, height: 52, borderRadius: 13,
                      background: "var(--bg-elevated)",
                      border: "1px solid var(--border-subtle)",
                      display: "flex", alignItems: "center", justifyContent: "center",
                      color: "var(--text-muted)",
                    }}>
                      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                        <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/>
                        <circle cx="12" cy="10" r="3"/>
                      </svg>
                    </div>
                  </div>
                  <h2 style={{ fontSize: 15, fontWeight: 700, color: "var(--text-primary)", marginBottom: 6 }}>
                    Ready to Explore
                  </h2>
                  <p style={{ fontSize: 12, color: "var(--text-muted)", lineHeight: 1.6 }}>
                    Configure satellite source and date range in the sidebar, then click{" "}
                    <span style={{ color: "var(--cyan)", fontWeight: 600 }}>Fetch Thermal Data</span>.
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right Panel — Hotspot Intelligence */}
        <HotspotIntelligencePanel hotspot={selectedHotspot} />
      </div>

      {/* Loading overlay */}
      {loading && (
        <div className="loading-overlay">
          <div className="loading-card">
            <div className="spinner" />
            <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-secondary)" }}>
              Fetching Thermal Data
            </div>
            <div className="loading-text" style={{ fontSize: 11 }}>
              Connecting to NASA FIRMS...
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
