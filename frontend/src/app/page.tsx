"use client";

/**
 * ThermaSense — Main application page.
 *
 * Composes the interactive map, sidebar controls,
 * and hotspot detail panel into a full-page dashboard.
 */

import { useState, useCallback, useMemo } from "react";
import dynamic from "next/dynamic";
import type { SatelliteSource, Hotspot } from "@/types/hotspot";
import { fetchHotspots } from "@/services/api";
import Sidebar from "@/features/dashboard/Sidebar";
import HotspotPanel from "@/features/hotspots/HotspotPanel";
import LoadingSpinner from "@/components/LoadingSpinner";

// Dynamic import for Leaflet (no SSR — requires window)
const MapView = dynamic(() => import("@/features/map/MapView"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full w-full items-center justify-center bg-slate-950">
      <LoadingSpinner size="lg" message="Loading map..." />
    </div>
  ),
});

export default function Home() {
  // ── State ───────────────────────────────────────────────
  const [satellites, setSatellites] = useState<SatelliteSource[]>(["NOAA-20"]);
  const [dayRange, setDayRange] = useState<number>(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hotspots, setHotspots] = useState<Hotspot[]>([]);
  const [selectedHotspot, setSelectedHotspot] = useState<Hotspot | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // ── Fetch handler ───────────────────────────────────────
  const handleFetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    setSelectedHotspot(null);

    try {
      // Fetch from each selected satellite source
      const allObservations: Hotspot[] = [];

      for (const sat of satellites) {
        const response = await fetchHotspots({
          satellite: sat,
          days: dayRange,
        });
        allObservations.push(...response.observations);
      }

      setHotspots(allObservations);

      if (allObservations.length === 0) {
        setError(
          "No thermal observations found for the selected parameters. Try a wider date range."
        );
      }
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "An unexpected error occurred";
      setError(message);
      setHotspots([]);
    } finally {
      setLoading(false);
      setSidebarOpen(false); // Close sidebar on mobile after fetch
    }
  }, [satellites, dayRange]);

  // ── Marker click handler ────────────────────────────────
  const handleSelectHotspot = useCallback((hotspot: Hotspot) => {
    setSelectedHotspot((prev) =>
      prev?.id === hotspot.id ? null : hotspot
    );
  }, []);

  const handleClosePanel = useCallback(() => {
    setSelectedHotspot(null);
  }, []);

  return (
    <div className="relative h-screen w-screen overflow-hidden">
      {/* Sidebar */}
      <Sidebar
        satellites={satellites}
        onSatellitesChange={setSatellites}
        dayRange={dayRange}
        onDayRangeChange={setDayRange}
        onFetch={handleFetch}
        loading={loading}
        error={error}
        hotspots={hotspots}
        sidebarOpen={sidebarOpen}
        onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
      />

      {/* Map — offset by sidebar width on large screens */}
      <div className="h-full w-full lg:pl-80">
        <MapView
          hotspots={hotspots}
          selectedHotspot={selectedHotspot}
          onSelectHotspot={handleSelectHotspot}
        />
      </div>

      {/* Hotspot detail panel */}
      {selectedHotspot && (
        <HotspotPanel
          hotspot={selectedHotspot}
          onClose={handleClosePanel}
        />
      )}

      {/* Loading overlay */}
      {loading && (
        <div className="fixed inset-0 z-[998] flex items-center justify-center bg-slate-950/60 backdrop-blur-sm lg:pl-80">
          <div className="rounded-2xl bg-slate-900/90 border border-slate-700/50 px-8 py-6 shadow-2xl">
            <LoadingSpinner
              size="lg"
              message="Fetching thermal data from NASA FIRMS..."
            />
          </div>
        </div>
      )}

      {/* Empty state (no data yet) */}
      {!loading && hotspots.length === 0 && !error && (
        <div className="fixed inset-0 z-[10] pointer-events-none flex items-center justify-center lg:pl-80">
          <div className="text-center pointer-events-auto">
            <div className="mb-4 flex justify-center">
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-slate-800/60 border border-slate-700/40">
                <svg
                  className="w-8 h-8 text-slate-500"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.5}
                    d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"
                  />
                </svg>
              </div>
            </div>
            <h2 className="text-lg font-semibold text-slate-300 mb-1">
              Ready to Explore
            </h2>
            <p className="text-sm text-slate-500 max-w-xs">
              Select a satellite source and date range, then click{" "}
              <span className="text-cyan-400 font-medium">
                Fetch Thermal Data
              </span>{" "}
              to view observations.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
