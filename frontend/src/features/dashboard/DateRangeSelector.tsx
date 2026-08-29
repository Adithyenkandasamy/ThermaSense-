"use client";

/**
 * Day range selector — 1 to 5 days.
 */

interface DateRangeSelectorProps {
  value: number;
  onChange: (days: number) => void;
}

const DAY_OPTIONS = [1, 2, 3, 4, 5];

export default function DateRangeSelector({
  value,
  onChange,
}: DateRangeSelectorProps) {
  return (
    <div className="space-y-2">
      <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400">
        Date Range
      </label>
      <div className="flex gap-1.5">
        {DAY_OPTIONS.map((day) => {
          const isActive = value === day;
          return (
            <button
              key={day}
              onClick={() => onChange(day)}
              className={`flex-1 rounded-lg py-2 text-sm font-semibold transition-all duration-200 ${
                isActive
                  ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/50 shadow-[0_0_12px_rgba(6,182,212,0.15)]"
                  : "bg-slate-800/50 text-slate-400 border border-slate-700 hover:border-slate-600 hover:text-slate-300"
              }`}
            >
              {day}d
            </button>
          );
        })}
      </div>
      <p className="text-[11px] text-slate-500">
        {value === 1 ? "Last 24 hours" : `Last ${value} days`}
      </p>
    </div>
  );
}
