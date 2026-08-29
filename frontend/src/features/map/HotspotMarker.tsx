"use client";

/**
 * HotspotMarker — individual marker on the Leaflet map
 * for a thermal observation. Color-coded by confidence.
 */

import { CircleMarker, Tooltip } from "react-leaflet";
import type { Hotspot } from "@/types/hotspot";

interface HotspotMarkerProps {
  hotspot: Hotspot;
  isSelected: boolean;
  onClick: (hotspot: Hotspot) => void;
}

function getMarkerStyle(hotspot: Hotspot, isSelected: boolean) {
  const confidence = (hotspot.confidence || "").toLowerCase();
  const frp = hotspot.frp || 0;

  // Base color by confidence
  let fillColor = "#38bdf8"; // default cyan
  let color = "#0ea5e9";

  if (confidence === "high" || confidence === "h") {
    fillColor = "#f87171";
    color = "#ef4444";
  } else if (confidence === "nominal" || confidence === "n") {
    fillColor = "#fbbf24";
    color = "#f59e0b";
  } else if (confidence === "low" || confidence === "l") {
    fillColor = "#34d399";
    color = "#10b981";
  }

  // Radius scales with FRP (fire radiative power)
  let radius = 5;
  if (frp > 100) radius = 12;
  else if (frp > 50) radius = 10;
  else if (frp > 20) radius = 8;
  else if (frp > 5) radius = 6;

  if (isSelected) {
    fillColor = "#ffffff";
    color = "#06b6d4";
    radius = radius + 3;
  }

  return {
    radius,
    fillColor,
    color,
    weight: isSelected ? 3 : 1.5,
    opacity: 1,
    fillOpacity: isSelected ? 0.9 : 0.7,
  };
}

function formatTime(isoString: string): string {
  try {
    const dt = new Date(isoString);
    return dt.toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  } catch {
    return isoString;
  }
}

export default function HotspotMarker({
  hotspot,
  isSelected,
  onClick,
}: HotspotMarkerProps) {
  const style = getMarkerStyle(hotspot, isSelected);

  return (
    <CircleMarker
      center={[hotspot.latitude, hotspot.longitude]}
      {...style}
      eventHandlers={{
        click: () => onClick(hotspot),
      }}
    >
      <Tooltip
        direction="top"
        offset={[0, -8]}
        className="thermasense-tooltip"
      >
        <div className="text-xs">
          <div className="font-bold">
            {hotspot.satellite} • {hotspot.confidence || "—"} confidence
          </div>
          <div className="text-slate-300">
            {formatTime(hotspot.acquisition_datetime)}
          </div>
          {hotspot.frp !== null && (
            <div className="text-orange-300">FRP: {hotspot.frp.toFixed(1)} MW</div>
          )}
        </div>
      </Tooltip>
    </CircleMarker>
  );
}
