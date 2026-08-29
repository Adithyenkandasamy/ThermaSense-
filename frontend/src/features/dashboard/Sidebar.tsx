"use client";

/**
 * Dashboard sidebar — controls and summary for the thermal map.
 */

import type { SatelliteSource, Hotspot } from "@/types/hotspot";
import SatelliteFilter from "./SatelliteFilter";
import DateRangeSelector from "./DateRangeSelector";
import LoadingSpinner from "@/components/LoadingSpinner";

interface SidebarProps {
  satellites: SatelliteSource[];
  onSatellitesChange: (sources: SatelliteSource[]) => void;
  dayRange: number;
  onDayRangeChange: (days: number) => void;
  onFetch: () => void;
  loading: boolean;
  error: string | null;
  hotspots: Hotspot[];
  sidebarOpen: boolean;
  onToggleSidebar: () => void;
}

export default function Sidebar({
  satellites,
  onSatellitesChange,
  dayRange,
  onDayRangeChange,
  onFetch,
  loading,
  error,
  hotspots,
  sidebarOpen,
  onToggleSidebar,
}: SidebarProps) {
  return (
    <>
      {/* Mobile toggle button */}
      <button
        onClick={onToggleSidebar}
        className="fixed top-4 left-4 z-[1000] lg:hidden rounded-lg bg-slate-900/90 border border-slate-700 p-2.5 text-slate-300 backdrop-blur-sm hover:bg-slate-800 transition-colors shadow-xl"
        aria-label="Toggle sidebar"
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          {sidebarOpen ? (
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          ) : (
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          )}
        </svg>
      </button>

      {/* Sidebar panel */}
      <aside
        className={`fixed top-0 left-0 z-[999] h-full w-80 bg-slate-950/95 backdrop-blur-xl border-r border-slate-800/60 flex flex-col transition-transform duration-300 ease-in-out shadow-2xl ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        }`}
      >
        {/* ── Header ─────────────────────────────────────────── */}
        <div className="px-5 pt-6 pb-4 border-b border-slate-800/60">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600 shadow-lg shadow-cyan-500/20">
              <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 18.657A8 8 0 016.343 7.343S7 9 9 10c0-2 .5-5 2.986-7C14 5 16.09 5.777 17.656 7.343A7.975 7.975 0 0120 13a7.975 7.975 0 01-2.343 5.657z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.879 16.121A3 3 0 1012.015 11L11 14H9c0 .768.293 1.536.879 2.121z" />
              </svg>
            </div>
            <div>
              <h1 className="text-lg font-bold text-white tracking-tight">ThermaSense</h1>
              <p className="text-[11px] text-slate-500 font-medium">Geospatial Thermal Intelligence</p>
            </div>
          </div>
        </div>

        {/* ── Controls ───────────────────────────────────────── */}
        <div className="flex-1 overflow-y-auto px-5 py-5 space-y-6">
          <SatelliteFilter
            selected={satellites}
            onChange={onSatellitesChange}
          />

          <DateRangeSelector
            value={dayRange}
            onChange={onDayRangeChange}
          />

          {/* Fetch button */}
          <button
            onClick={onFetch}
            disabled={loading}
            className="w-full rounded-lg bg-gradient-to-r from-cyan-500 to-blue-600 px-4 py-3 text-sm font-bold text-white shadow-lg shadow-cyan-500/25 transition-all duration-200 hover:shadow-cyan-500/40 hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:shadow-cyan-500/25 active:scale-[0.98]"
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <LoadingSpinner size="sm" />
                Fetching data...
              </span>
            ) : (
              <span className="flex items-center justify-center gap-2">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                Fetch Thermal Data
              </span>
            )}
          </button>

          {/* Error message */}
          {error && (
            <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
              <div className="flex items-start gap-2">
                <svg className="w-4 h-4 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
                </svg>
                <p>{error}</p>
              </div>
            </div>
          )}
        </div>

        {/* ── Stats Footer ───────────────────────────────────── */}
        <div className="border-t border-slate-800/60 px-5 py-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-lg bg-slate-900/60 border border-slate-800 px-3 py-2.5">
              <p className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">
                Observations
              </p>
              <p className="text-xl font-bold text-white tabular-nums">
                {hotspots.length.toLocaleString()}
              </p>
            </div>
            <div className="rounded-lg bg-slate-900/60 border border-slate-800 px-3 py-2.5">
              <p className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">
                Sources
              </p>
              <p className="text-xl font-bold text-cyan-400 tabular-nums">
                {satellites.length}
              </p>
            </div>
          </div>
          <p className="mt-3 text-center text-[10px] text-slate-600">
            Powered by NASA FIRMS
          </p>
        </div>
      </aside>
    </>
  );
}
