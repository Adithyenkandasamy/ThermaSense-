"use client";

/**
 * Satellite source filter — NOAA-20 / NOAA-21 toggle checkboxes.
 */

import type { SatelliteSource } from "@/types/hotspot";

interface SatelliteFilterProps {
  selected: SatelliteSource[];
  onChange: (sources: SatelliteSource[]) => void;
}

const SOURCES: { id: SatelliteSource; label: string; satellite: string }[] = [
  { id: "NOAA-20", label: "NOAA-20", satellite: "VIIRS_NOAA20_NRT" },
  { id: "NOAA-21", label: "NOAA-21", satellite: "VIIRS_NOAA21_NRT" },
];

export default function SatelliteFilter({
  selected,
  onChange,
}: SatelliteFilterProps) {
  const toggle = (source: SatelliteSource) => {
    if (selected.includes(source)) {
      // Don't allow empty selection
      if (selected.length > 1) {
        onChange(selected.filter((s) => s !== source));
      }
    } else {
      onChange([...selected, source]);
    }
  };

  return (
    <div className="space-y-2">
      <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400">
        Satellite Source
      </label>
      <div className="flex flex-col gap-2">
        {SOURCES.map((source) => {
          const isActive = selected.includes(source.id);
          return (
            <button
              key={source.id}
              onClick={() => toggle(source.id)}
              className={`flex items-center gap-3 rounded-lg border px-3 py-2.5 text-sm font-medium transition-all duration-200 ${
                isActive
                  ? "border-cyan-500/50 bg-cyan-500/10 text-cyan-300 shadow-[0_0_15px_rgba(6,182,212,0.1)]"
                  : "border-slate-700 bg-slate-800/50 text-slate-400 hover:border-slate-600 hover:text-slate-300"
              }`}
            >
              <div
                className={`h-3 w-3 rounded-sm border-2 transition-colors ${
                  isActive
                    ? "border-cyan-400 bg-cyan-400"
                    : "border-slate-600 bg-transparent"
                }`}
              />
              <span className="flex-1 text-left">{source.label}</span>
              <span className="text-[10px] text-slate-500 font-mono">
                {source.satellite.replace("_NRT", "")}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
