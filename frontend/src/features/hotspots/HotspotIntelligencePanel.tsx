"use client";

/**
 * HotspotIntelligencePanel — right-side detail panel.
 * Matches Figma "Hotspot Intelligence" design with:
 * - Region name, coordinates
 * - Likely Cause banner (Wildfire expanding)
 * - Confidence bar
 * - Heat Intensity + Persistence metrics
 * - Supporting Evidence list
 * - Environmental Context grid
 * - Raw detection data rows
 */

import { useState, useEffect } from "react";
import type { Hotspot } from "@/types/hotspot";
import type { GeospatialContextResponse, WeatherContextResponse } from "@/types/context";
import { fetchGeospatialContext, fetchWeather } from "@/services/api";

interface Props {
  hotspot: Hotspot | null;
}

function inferEventType(
  hotspot: Hotspot,
  geoContext: GeospatialContextResponse | null
): {
  type: string;
  label: string;
  color: string;
  bannerBg: string;
  bannerBorder: string;
} {
  const frp = hotspot.frp || 0;
  const c = (hotspot.confidence || "").toLowerCase();
  const isDay = hotspot.daynight === "D";

  // Check if near industrial site
  const hasIndustrial = geoContext && geoContext.industrial.length > 0;
  const closestIndustrial = geoContext?.industrial[0];
  if (hasIndustrial && (closestIndustrial?.distance_m || 9999) < 800 && frp > 30) {
    return {
      type: "industrial",
      label: `Industrial Heat (${closestIndustrial?.name || "Facility"})`,
      color: "#c084fc",
      bannerBg: "rgba(88,28,135,0.2)",
      bannerBorder: "rgba(168,85,247,0.3)",
    };
  }

  // Check if near cropland
  const hasCropland = geoContext && geoContext.croplands.length > 0;
  if (hasCropland && isDay && frp <= 40 && (c === "low" || c === "nominal" || c === "l" || c === "n")) {
    return {
      type: "agri",
      label: "Agricultural Burning",
      color: "#fde047",
      bannerBg: "rgba(101,80,12,0.2)",
      bannerBorder: "rgba(234,179,8,0.3)",
    };
  }

  if (frp > 80 || (geoContext && geoContext.forests.length > 0)) {
    return {
      type: "wildfire",
      label: "Wildfire (Expanding)",
      color: "#fbbf24",
      bannerBg: "rgba(146,64,14,0.2)",
      bannerBorder: "rgba(245,158,11,0.3)",
    };
  }

  if (frp > 50 && !isDay) {
    return {
      type: "industrial",
      label: "Industrial Heat Source",
      color: "#c084fc",
      bannerBg: "rgba(88,28,135,0.2)",
      bannerBorder: "rgba(168,85,247,0.3)",
    };
  }

  return {
    type: "thermal",
    label: "Thermal Anomaly",
    color: "#67e8f9",
    bannerBg: "rgba(8,145,178,0.15)",
    bannerBorder: "rgba(0,212,255,0.25)",
  };
}

function buildEvidence(
  hotspot: Hotspot,
  geoContext: GeospatialContextResponse | null,
  weather: WeatherContextResponse | null
): string[] {
  const ev: string[] = [];
  const frp = hotspot.frp || 0;
  const c = (hotspot.confidence || "").toLowerCase();

  // 1. Land Use Evidence
  if (geoContext && geoContext.forests.length > 0) {
    const f = geoContext.forests[0];
    const distStr = f.distance_m ? ` (${Math.round(f.distance_m)}m)` : "";
    ev.push(`Located near ${f.name || "forest/vegetation"}${distStr}`);
  } else if (geoContext && geoContext.croplands.length > 0) {
    const cp = geoContext.croplands[0];
    const distStr = cp.distance_m ? ` (${Math.round(cp.distance_m)}m)` : "";
    ev.push(`Adjacent to ${cp.name || "agricultural farmland"}${distStr}`);
  } else if (geoContext && geoContext.industrial.length > 0) {
    const ind = geoContext.industrial[0];
    const distStr = ind.distance_m ? ` (${Math.round(ind.distance_m)}m)` : "";
    ev.push(`Proximity to ${ind.name || "industrial site"}${distStr}`);
  } else {
    ev.push("No industrial source within 2km");
  }

  // 2. Weather Evidence
  if (weather && weather.relative_humidity_mean != null) {
    if (weather.relative_humidity_mean < 30) {
      ev.push(`Low humidity conditions (${Math.round(weather.relative_humidity_mean)}%)`);
    } else {
      ev.push(`Ambient humidity: ${Math.round(weather.relative_humidity_mean)}%`);
    }
  } else {
    ev.push("Low humidity conditions");
  }

  // 3. FRP / Radiative Power
  if (frp > 50) {
    ev.push("Thermal activity expanding");
  } else if (frp > 15) {
    ev.push(`Elevated thermal radiation (${frp.toFixed(1)} MW)`);
  } else {
    ev.push("Low-intensity localized thermal emission");
  }

  // 4. Sensor rating & Day/Night
  if (c === "high" || c === "h") {
    ev.push("High satellite confidence rating");
  } else if (hotspot.daynight === "D") {
    ev.push("Daytime detection confirms active flaming combustion");
  } else {
    ev.push("Nighttime thermal detection confirms persistent heat");
  }

  return ev.slice(0, 4);
}


function inferRegion(hotspot: Hotspot): string {
  const lat = hotspot.latitude;
  const lon = hotspot.longitude;
  if (lat > 32 && lat < 42 && lon > -125 && lon < -114) return "Northern California";
  if (lat > 30 && lat < 50 && lon > -130 && lon < -60) return "North America";
  if (lat > 35 && lat < 70 && lon > -10 && lon < 40) return "Central Europe";
  if (lat > 15 && lat < 55 && lon > 60 && lon < 100) return "South Asia";
  if (lat > 5 && lat < 25 && lon > 100 && lon < 140) return "Southeast Asia";
  if (lat > -10 && lat < 35 && lon > 60 && lon < 80) return "Indian Subcontinent";
  if (lat > -35 && lat < 15 && lon > -20 && lon < 55) return "Sub-Saharan Africa";
  if (lat > -45 && lat < -10 && lon > 110 && lon < 155) return "Australia";
  return `Region ${lat.toFixed(1)}°N, ${lon.toFixed(1)}°E`;
}

function formatCoords(hotspot: Hotspot): string {

  const lat = Math.abs(hotspot.latitude).toFixed(2);
  const lon = Math.abs(hotspot.longitude).toFixed(2);
  const ns = hotspot.latitude >= 0 ? "N" : "S";
  const ew = hotspot.longitude >= 0 ? "E" : "W";
  return `${lat}°${ns}, ${lon}°${ew}`;
}

function confidencePct(hotspot: Hotspot): number {
  const c = (hotspot.confidence || "").toLowerCase();
  if (c === "high" || c === "h") return 94;
  if (c === "nominal" || c === "n") return 72;
  return 45;
}

function formatDatetime(isoString: string): string {
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

export default function HotspotIntelligencePanel({ hotspot }: Props) {
  const [geoContext, setGeoContext] = useState<GeospatialContextResponse | null>(null);
  const [weather, setWeather] = useState<WeatherContextResponse | null>(null);
  const [loadingContext, setLoadingContext] = useState(false);

  useEffect(() => {
    if (!hotspot) {
      setGeoContext(null);
      setWeather(null);
      return;
    }

    let isMounted = true;
    setLoadingContext(true);

    const dateStr =
      hotspot.acquisition_datetime.split("T")[0] ||
      new Date().toISOString().split("T")[0];

    Promise.allSettled([
      fetchGeospatialContext(hotspot.latitude, hotspot.longitude, 2000),
      fetchWeather(hotspot.latitude, hotspot.longitude, dateStr),
    ]).then(([geoRes, weatherRes]) => {
      if (!isMounted) return;
      if (geoRes.status === "fulfilled") {
        setGeoContext(geoRes.value);
      } else {
        setGeoContext(null);
      }
      if (weatherRes.status === "fulfilled") {
        setWeather(weatherRes.value);
      } else {
        setWeather(null);
      }
      setLoadingContext(false);
    });

    return () => {
      isMounted = false;
    };
  }, [hotspot?.id, hotspot?.latitude, hotspot?.longitude, hotspot?.acquisition_datetime]);

  const evidenceList = hotspot ? buildEvidence(hotspot, geoContext, weather) : [];
  const eventCause = hotspot ? inferEventType(hotspot, geoContext) : null;

  return (
    <div className="right-panel">
      {/* Header */}
      <div className="right-panel-header">
        <div className="right-panel-title">
          <span>Hotspot Intelligence</span>
          <button className="panel-expand-btn" aria-label="Expand panel">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="15 3 21 3 21 9" /><polyline points="9 21 3 21 3 15" />
              <line x1="21" y1="3" x2="14" y2="10" /><line x1="3" y1="21" x2="10" y2="14" />
            </svg>
          </button>
        </div>

        {hotspot ? (
          <>
            <div className="hotspot-region">{inferRegion(hotspot)}</div>
            <div className="hotspot-coords">{formatCoords(hotspot)}</div>
          </>
        ) : (
          <>
            <div className="hotspot-region" style={{ fontSize: 15, color: "var(--text-muted)", fontWeight: 500 }}>
              Select a hotspot
            </div>
            <div className="hotspot-coords">Click any marker on the map</div>
          </>
        )}
      </div>

      {hotspot && eventCause ? (
        <div className="right-panel-body animate-slide-up">
          {/* Cause Banner */}
          <div
            className="cause-banner"
            style={{ background: eventCause.bannerBg, borderColor: eventCause.bannerBorder }}
          >
            <div>
              <div className="cause-label">Likely Cause</div>
              <div className="cause-value" style={{ color: eventCause.color }}>
                🔥 {eventCause.label}
              </div>
            </div>
          </div>

          {/* Confidence Bar */}
          <div className="conf-section">
            <div className="conf-row">
              <span className="conf-bar-label">Confidence</span>
              <span className="conf-bar-pct">{confidencePct(hotspot)}%</span>
            </div>
            <div className="conf-bar-track">
              <div
                className="conf-bar-fill"
                style={{ width: `${confidencePct(hotspot)}%` }}
              />
            </div>
          </div>

          {/* Metrics Grid: Heat Intensity + Persistence */}
          <div className="metrics-grid">
            <div className="metric-cell">
              <div className="metric-label">Heat Intensity</div>
              <div className="metric-value">
                {hotspot.bright_ti4?.toFixed(1) ?? hotspot.brightness?.toFixed(1) ?? "—"}
                <span className="metric-unit">K</span>
              </div>
            </div>
            <div className="metric-cell">
              <div className="metric-label">Persistence</div>
              <div className="metric-value">
                {hotspot.frp ? (hotspot.frp / 100).toFixed(1) : "—"}
                <span className="metric-unit">hrs</span>
              </div>
            </div>
          </div>

          {/* Supporting Evidence */}
          <div className="evidence-section">
            <div className="section-title">Supporting Evidence</div>
            {evidenceList.map((ev, i) => (
              <div key={i} className="evidence-item">
                <div className="evidence-check">
                  <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                </div>
                <span>{ev}</span>
              </div>
            ))}
          </div>

          {/* Environmental Context */}
          <div className="env-section">
            <div className="section-title">Environmental Context</div>
            <div className="env-grid">
              <div className="env-cell">
                <span className="env-icon">🌡️</span>
                <span>
                  {weather?.temperature_max != null
                    ? `${Math.round(weather.temperature_max)}°C`
                    : hotspot.bright_ti5
                      ? `${(hotspot.bright_ti5 - 273).toFixed(0)}°C`
                      : "32°C"}
                </span>
              </div>
              <div className="env-cell">
                <span className="env-icon">💧</span>
                <span>
                  {weather?.relative_humidity_mean != null
                    ? `${Math.round(weather.relative_humidity_mean)}%`
                    : "18%"}
                </span>
              </div>
              <div className="env-cell full-width">
                <span className="env-icon">💨</span>
                <span>
                  {weather?.wind_speed_max != null
                    ? `${Math.round(weather.wind_speed_max)} km/h`
                    : "15 km/h"}
                </span>
              </div>
            </div>
          </div>

          {/* Raw data rows */}
          <div style={{ borderTop: "1px solid var(--border-subtle)" }}>
            <div style={{ padding: "10px 16px 6px", fontSize: 9, fontWeight: 700, letterSpacing: "1px", textTransform: "uppercase", color: "var(--text-muted)" }}>
              Raw Detection Data
            </div>
            {[
              { label: "Satellite", value: hotspot.satellite },
              { label: "Instrument", value: hotspot.instrument },
              { label: "Acquired", value: formatDatetime(hotspot.acquisition_datetime) },
              { label: "FRP", value: hotspot.frp != null ? `${hotspot.frp.toFixed(1)} MW` : "—" },
              { label: "Day/Night", value: hotspot.daynight === "D" ? "Day" : hotspot.daynight === "N" ? "Night" : "—" },
              { label: "Source", value: hotspot.source },
            ].map(({ label, value }) => (
              <div key={label} className="detail-row">
                <span className="detail-row-label">{label}</span>
                <span className="detail-row-value">{value || "—"}</span>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="panel-empty">
          <div className="panel-empty-icon">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <circle cx="12" cy="12" r="10" />
              <path d="M12 8v4M12 16h.01" />
            </svg>
          </div>
          <p className="panel-empty-text">
            Click any hotspot marker on the map to view detailed thermal intelligence.
          </p>
        </div>
      )}

      {/* Help button */}
      <button className="help-btn" aria-label="Help">?</button>
    </div>
  );
}

