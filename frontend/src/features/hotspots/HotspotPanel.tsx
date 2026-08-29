"use client";

/**
 * Hotspot detail panel — shows observation details when a marker is clicked.
 */

import type { Hotspot } from "@/types/hotspot";

interface HotspotPanelProps {
  hotspot: Hotspot;
  onClose: () => void;
}

function formatDatetime(isoString: string): string {
  try {
    const dt = new Date(isoString);
    return dt.toLocaleString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
      timeZoneName: "short",
    });
  } catch {
    return isoString;
  }
}

function confidenceColor(confidence: string | null): string {
  if (!confidence) return "text-slate-400";
  const c = confidence.toLowerCase();
  if (c === "high" || c === "h") return "text-red-400";
  if (c === "nominal" || c === "n") return "text-amber-400";
  return "text-emerald-400";
}

function confidenceBadge(confidence: string | null): string {
  if (!confidence) return "bg-slate-700 text-slate-300";
  const c = confidence.toLowerCase();
  if (c === "high" || c === "h")
    return "bg-red-500/15 text-red-400 border border-red-500/30";
  if (c === "nominal" || c === "n")
    return "bg-amber-500/15 text-amber-400 border border-amber-500/30";
  return "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30";
}

interface DetailRowProps {
  label: string;
  value: string | number | null | undefined;
  unit?: string;
  highlight?: boolean;
}

function DetailRow({ label, value, unit, highlight }: DetailRowProps) {
  const displayValue =
    value !== null && value !== undefined ? String(value) : "—";

  return (
    <div className="flex items-center justify-between py-2 border-b border-slate-800/50 last:border-0">
      <span className="text-xs text-slate-400 font-medium">{label}</span>
      <span
        className={`text-sm font-semibold tabular-nums ${
          highlight ? "text-cyan-300" : "text-slate-200"
        }`}
      >
        {displayValue}
        {unit && value !== null && value !== undefined && (
          <span className="text-xs text-slate-500 ml-1">{unit}</span>
        )}
      </span>
    </div>
  );
}

export default function HotspotPanel({ hotspot, onClose }: HotspotPanelProps) {
  return (
    <div className="fixed bottom-4 right-4 z-[1000] w-[380px] max-h-[calc(100vh-2rem)] overflow-y-auto rounded-2xl bg-slate-950/95 backdrop-blur-xl border border-slate-700/60 shadow-2xl shadow-black/50 animate-in slide-in-from-bottom-4 duration-300">
      {/* Header */}
      <div className="sticky top-0 flex items-center justify-between px-5 py-4 bg-slate-950/95 backdrop-blur-xl border-b border-slate-800/60 rounded-t-2xl">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-orange-500 to-red-600 shadow-lg shadow-orange-500/20">
            <svg
              className="w-4 h-4 text-white"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M17.657 18.657A8 8 0 016.343 7.343S7 9 9 10c0-2 .5-5 2.986-7C14 5 16.09 5.777 17.656 7.343A7.975 7.975 0 0120 13a7.975 7.975 0 01-2.343 5.657z"
              />
            </svg>
          </div>
          <div>
            <h3 className="text-sm font-bold text-white">
              Thermal Observation
            </h3>
            <p className="text-[10px] text-slate-500 font-mono">
              {hotspot.id}
            </p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="flex h-7 w-7 items-center justify-center rounded-lg bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-white transition-colors"
          aria-label="Close panel"
        >
          <svg
            className="w-4 h-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      </div>

      {/* Content */}
      <div className="px-5 py-4 space-y-4">
        {/* Location */}
        <div>
          <h4 className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-2">
            Location
          </h4>
          <DetailRow
            label="Latitude"
            value={hotspot.latitude.toFixed(5)}
            highlight
          />
          <DetailRow
            label="Longitude"
            value={hotspot.longitude.toFixed(5)}
            highlight
          />
        </div>

        {/* Detection */}
        <div>
          <h4 className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-2">
            Detection
          </h4>
          <DetailRow
            label="Date & Time"
            value={formatDatetime(hotspot.acquisition_datetime)}
          />
          <DetailRow label="Satellite" value={hotspot.satellite} />
          <DetailRow label="Instrument" value={hotspot.instrument} />
          <div className="flex items-center justify-between py-2 border-b border-slate-800/50">
            <span className="text-xs text-slate-400 font-medium">
              Confidence
            </span>
            <span
              className={`text-xs font-bold px-2.5 py-1 rounded-full ${confidenceBadge(
                hotspot.confidence
              )}`}
            >
              {hotspot.confidence || "—"}
            </span>
          </div>
          <DetailRow
            label="Day/Night"
            value={
              hotspot.daynight === "D"
                ? "Day ☀️"
                : hotspot.daynight === "N"
                ? "Night 🌙"
                : hotspot.daynight
            }
          />
        </div>

        {/* Thermal Measurements */}
        <div>
          <h4 className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-2">
            Thermal Measurements
          </h4>
          <DetailRow
            label="Brightness Temperature"
            value={hotspot.brightness?.toFixed(1)}
            unit="K"
          />
          <DetailRow
            label="Bright TI4"
            value={hotspot.bright_ti4?.toFixed(1)}
            unit="K"
          />
          <DetailRow
            label="Bright TI5"
            value={hotspot.bright_ti5?.toFixed(1)}
            unit="K"
          />
          <DetailRow
            label="Fire Radiative Power"
            value={hotspot.frp?.toFixed(1)}
            unit="MW"
            highlight
          />
        </div>
      </div>

      {/* Footer */}
      <div className="px-5 py-3 border-t border-slate-800/60 bg-slate-900/30 rounded-b-2xl">
        <p className="text-[10px] text-slate-600 text-center">
          Source: {hotspot.source} • Raw satellite observation
        </p>
      </div>
    </div>
  );
}
