"use client";

/**
 * HotspotIntelligencePanel — right-side detail panel.
 *
 * PRIMARY FEATURE: Calls the backend attribution engine to classify every
 * selected hotspot into one of 4 cause types:
 *   - vegetation_fire        (Wildfire / Forest Fire)
 *   - agricultural_burning   (Crop Residue / Stubble Burning)
 *   - industrial_heat        (Factory / Smelter / Kiln)
 *   - gas_flare              (Petrochemical / Oil Field Flare)
 *
 * The classification result is the FIRST and LARGEST thing the user sees.
 */

import { useState, useEffect } from "react";
import type { Hotspot } from "@/types/hotspot";
import type { GeospatialContextResponse, WeatherContextResponse } from "@/types/context";
import type { AttributionResult, CauseType } from "@/types/attribution";
import { fetchGeospatialContext, fetchWeather, fetchAttribution } from "@/services/api";

interface Props {
  hotspot: Hotspot | null;
}

// ── Cause display metadata ────────────────────────────────────────────────────
const CAUSE_META: Record<CauseType | "unknown", {
  label: string;
  shortLabel: string;
  icon: string;
  color: string;
  bgColor: string;
  borderColor: string;
  description: string;
}> = {
  vegetation_fire: {
    label: "Vegetation Fire / Wildfire",
    shortLabel: "VEGETATION FIRE",
    icon: "🔥",
    color: "#fb923c",
    bgColor: "rgba(154,52,18,0.25)",
    borderColor: "rgba(251,146,60,0.5)",
    description: "Active forest or grassland combustion detected",
  },
  agricultural_burning: {
    label: "Agricultural Burning",
    shortLabel: "CROP / FIELD BURNING",
    icon: "🌾",
    color: "#fde047",
    bgColor: "rgba(101,80,12,0.25)",
    borderColor: "rgba(250,204,21,0.5)",
    description: "Crop residue / stubble burning on farmland",
  },
  industrial_heat: {
    label: "Industrial Heat Source",
    shortLabel: "INDUSTRIAL HEAT",
    icon: "🏭",
    color: "#c084fc",
    bgColor: "rgba(88,28,135,0.25)",
    borderColor: "rgba(192,132,252,0.5)",
    description: "High-temperature emission from factory or smelter",
  },
  gas_flare: {
    label: "Gas Flare",
    shortLabel: "OIL / GAS FLARE",
    icon: "🛢️",
    color: "#f87171",
    bgColor: "rgba(127,29,29,0.25)",
    borderColor: "rgba(248,113,113,0.5)",
    description: "Continuous petrochemical gas flare stack emission",
  },
  volcanic_activity: {
    label: "Volcanic Activity",
    shortLabel: "VOLCANIC",
    icon: "🌋",
    color: "#ef4444",
    bgColor: "rgba(127,29,29,0.3)",
    borderColor: "rgba(239,68,68,0.5)",
    description: "Volcanic eruption or lava flow thermal signature",
  },
  unknown: {
    label: "Unclassified Thermal Anomaly",
    shortLabel: "THERMAL ANOMALY",
    icon: "🌡️",
    color: "#67e8f9",
    bgColor: "rgba(8,145,178,0.15)",
    borderColor: "rgba(0,212,255,0.25)",
    description: "Insufficient data for cause attribution",
  },
};

const SOURCE_BADGE: Record<string, { label: string; color: string }> = {
  satellite: { label: "Satellite", color: "#38bdf8" },
  geospatial: { label: "GIS", color: "#86efac" },
  weather: { label: "Weather", color: "#fde68a" },
};

function inferRegion(hotspot: Hotspot): string {
  const { latitude: lat, longitude: lon } = hotspot;
  if (lat > 28 && lat < 35 && lon > 79 && lon < 82) return "Uttarakhand, India";
  if (lat > 30 && lat < 32 && lon > 73 && lon < 76) return "Punjab, India";
  if (lat > 21 && lat < 24 && lon > 84 && lon < 88) return "Jharkhand, India";
  if (lat > 26 && lat < 28 && lon > 94 && lon < 97) return "Assam, India";
  if (lat > 32 && lat < 42 && lon > -125 && lon < -114) return "Northern California";
  if (lat > 30 && lat < 50 && lon > -130 && lon < -60) return "North America";
  if (lat > 35 && lat < 70 && lon > -10 && lon < 40) return "Central Europe";
  if (lat > 15 && lat < 55 && lon > 60 && lon < 100) return "South Asia";
  if (lat > 5 && lat < 25 && lon > 100 && lon < 140) return "Southeast Asia";
  if (lat > -10 && lat < 35 && lon > 60 && lon < 80) return "Indian Subcontinent";
  if (lat > -35 && lat < 15 && lon > -20 && lon < 55) return "Sub-Saharan Africa";
  if (lat > -45 && lat < -10 && lon > 110 && lon < 155) return "Australia";
  return `${Math.abs(lat).toFixed(2)} lat, ${Math.abs(lon).toFixed(2)} lon`;
}

function formatCoords(hotspot: Hotspot): string {
  const lat = Math.abs(hotspot.latitude).toFixed(4);
  const lon = Math.abs(hotspot.longitude).toFixed(4);
  return `${lat}${hotspot.latitude >= 0 ? "N" : "S"}, ${lon}${hotspot.longitude >= 0 ? "E" : "W"}`;
}

function formatDatetime(isoString: string): string {
  try {
    return new Date(isoString).toLocaleString("en-US", {
      month: "short", day: "numeric",
      hour: "2-digit", minute: "2-digit", hour12: false,
    });
  } catch { return isoString; }
}

// ─────────────────────────────────────────────────────────────────────────────

export default function HotspotIntelligencePanel({ hotspot }: Props) {
  const [attribution, setAttribution] = useState<AttributionResult | null>(null);
  const [geoContext, setGeoContext] = useState<GeospatialContextResponse | null>(null);
  const [weather, setWeather] = useState<WeatherContextResponse | null>(null);
  const [loadingAttribution, setLoadingAttribution] = useState(false);
  const [attributionError, setAttributionError] = useState<string | null>(null);

  useEffect(() => {
    if (!hotspot) {
      setAttribution(null);
      setGeoContext(null);
      setWeather(null);
      setAttributionError(null);
      return;
    }

    let isMounted = true;
    setLoadingAttribution(true);
    setAttribution(null);
    setAttributionError(null);

    const dateStr = hotspot.acquisition_datetime.split("T")[0] || new Date().toISOString().split("T")[0];

    Promise.allSettled([
      fetchAttribution(hotspot.id),
      fetchGeospatialContext(hotspot.latitude, hotspot.longitude, 2000),
      fetchWeather(hotspot.latitude, hotspot.longitude, dateStr),
    ]).then(([attrRes, geoRes, weatherRes]) => {
      if (!isMounted) return;
      if (attrRes.status === "fulfilled") {
        setAttribution(attrRes.value);
      } else {
        setAttributionError("Attribution engine could not classify this observation.");
      }
      if (geoRes.status === "fulfilled") setGeoContext(geoRes.value);
      if (weatherRes.status === "fulfilled") setWeather(weatherRes.value);
      setLoadingAttribution(false);
    });

    return () => { isMounted = false; };
  }, [hotspot?.id, hotspot?.latitude, hotspot?.longitude]);

  const cause = (attribution?.primary_cause ?? "unknown") as CauseType | "unknown";
  const meta = CAUSE_META[cause] ?? CAUSE_META.unknown;
  const confidencePct = attribution ? Math.round(attribution.confidence * 100) : 0;

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

      {hotspot ? (
        <div className="right-panel-body animate-slide-up">

          {/* ── CLASSIFICATION HERO BLOCK ─────────────────────────────── */}
          <div style={{
            margin: "0 0 2px 0",
            padding: "14px 16px 16px",
            background: meta.bgColor,
            borderBottom: `2px solid ${meta.borderColor}`,
          }}>
            <div style={{
              fontSize: 9, fontWeight: 700, letterSpacing: "1.5px",
              textTransform: "uppercase", color: meta.color,
              marginBottom: 8, opacity: 0.8,
            }}>
              AI Cause Classification
            </div>

            {loadingAttribution ? (
              <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 0" }}>
                <div style={{
                  width: 14, height: 14, borderRadius: "50%",
                  border: `2px solid ${meta.color}`, borderTopColor: "transparent",
                  animation: "spin 0.8s linear infinite",
                }} />
                <span style={{ color: "var(--text-muted)", fontSize: 12 }}>Running attribution engine…</span>
              </div>
            ) : (
              <>
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
                  <span style={{ fontSize: 26 }}>{meta.icon}</span>
                  <div>
                    <div style={{
                      fontSize: 18, fontWeight: 800, color: meta.color,
                      lineHeight: 1.1, letterSpacing: "0.5px",
                    }}>
                      {meta.shortLabel}
                    </div>
                    <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>
                      {meta.description}
                    </div>
                  </div>
                </div>

                <div>
                  <div style={{
                    display: "flex", justifyContent: "space-between",
                    fontSize: 10, color: "var(--text-muted)", marginBottom: 4,
                  }}>
                    <span style={{ fontWeight: 600, letterSpacing: "0.5px", textTransform: "uppercase" }}>
                      Classification Confidence
                    </span>
                    <span style={{ fontWeight: 800, color: meta.color, fontSize: 13 }}>
                      {confidencePct}%
                    </span>
                  </div>
                  <div style={{ height: 6, borderRadius: 3, background: "rgba(255,255,255,0.08)", overflow: "hidden" }}>
                    <div style={{
                      height: "100%", borderRadius: 3,
                      width: `${confidencePct}%`,
                      background: `linear-gradient(90deg, ${meta.color}88, ${meta.color})`,
                      transition: "width 0.8s ease",
                    }} />
                  </div>
                </div>

                {attributionError && (
                  <div style={{ fontSize: 10, color: "#f87171", marginTop: 6, opacity: 0.8 }}>
                    {attributionError}
                  </div>
                )}
              </>
            )}
          </div>

          {/* ── ALL CAUSE SCORES ──────────────────────────────────────── */}
          {attribution && attribution.possible_causes && attribution.possible_causes.length > 1 && (
            <div style={{ padding: "10px 16px 8px", borderBottom: "1px solid var(--border-subtle)" }}>
              <div style={{
                fontSize: 9, fontWeight: 700, letterSpacing: "1px",
                textTransform: "uppercase", color: "var(--text-muted)", marginBottom: 8,
              }}>
                All Cause Scores
              </div>
              {attribution.possible_causes.slice(0, 4).map((c) => {
                const m = CAUSE_META[c.cause as CauseType] ?? CAUSE_META.unknown;
                const pct = Math.round((c.normalized_score ?? 0) * 100);
                const isTop = c.cause === cause;
                return (
                  <div key={c.cause} style={{ marginBottom: 5 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, marginBottom: 2 }}>
                      <span style={{ color: isTop ? m.color : "var(--text-muted)", fontWeight: isTop ? 700 : 400 }}>
                        {m.icon} {m.shortLabel}
                      </span>
                      <span style={{ color: isTop ? m.color : "var(--text-muted)", fontWeight: 600 }}>
                        {pct}%
                      </span>
                    </div>
                    <div style={{ height: 3, borderRadius: 2, background: "rgba(255,255,255,0.06)", overflow: "hidden" }}>
                      <div style={{
                        height: "100%", borderRadius: 2, width: `${pct}%`,
                        background: isTop ? m.color : "rgba(255,255,255,0.15)",
                        transition: "width 0.6s ease",
                      }} />
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* ── EVIDENCE CHAIN ────────────────────────────────────────── */}
          {attribution && attribution.evidence && attribution.evidence.length > 0 && (
            <div style={{ padding: "10px 16px 10px", borderBottom: "1px solid var(--border-subtle)" }}>
              <div style={{
                fontSize: 9, fontWeight: 700, letterSpacing: "1px",
                textTransform: "uppercase", color: "var(--text-muted)", marginBottom: 8,
              }}>
                Multi-Source Evidence Chain
              </div>
              {attribution.evidence.slice(0, 6).map((ev, i) => {
                const badge = SOURCE_BADGE[ev.source] ?? { label: ev.source, color: "#aaa" };
                const isContradicts = ev.impact === "contradicts";
                return (
                  <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: 8, marginBottom: 7 }}>
                    <div style={{
                      flexShrink: 0, width: 14, height: 14, borderRadius: "50%",
                      background: isContradicts ? "rgba(239,68,68,0.2)" : "rgba(74,222,128,0.15)",
                      border: `1px solid ${isContradicts ? "#f87171" : "#4ade80"}`,
                      display: "flex", alignItems: "center", justifyContent: "center", marginTop: 1,
                    }}>
                      <svg width="7" height="7" viewBox="0 0 24 24" fill="none" stroke={isContradicts ? "#f87171" : "#4ade80"} strokeWidth="3">
                        {isContradicts
                          ? <><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></>
                          : <polyline points="20 6 9 17 4 12"/>}
                      </svg>
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 5, marginBottom: 2 }}>
                        <span style={{
                          fontSize: 8, fontWeight: 700, padding: "1px 5px", borderRadius: 3,
                          background: `${badge.color}22`, color: badge.color,
                          border: `1px solid ${badge.color}44`,
                          letterSpacing: "0.5px", textTransform: "uppercase",
                        }}>
                          {badge.label}
                        </span>
                        <span style={{ fontSize: 10, fontWeight: 600, color: "var(--text-primary)" }}>
                          {ev.factor}
                        </span>
                      </div>
                      <div style={{ fontSize: 10, color: "var(--text-muted)", lineHeight: 1.4 }}>
                        {ev.value}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* ── ENVIRONMENTAL CONTEXT ─────────────────────────────────── */}
          <div className="env-section">
            <div className="section-title">Environmental Context</div>
            <div className="env-grid">
              <div className="env-cell">
                <span className="env-icon">🌡️</span>
                <span>
                  {weather?.temperature_max != null
                    ? `${Math.round(weather.temperature_max)}°C`
                    : hotspot.bright_ti5 ? `${(hotspot.bright_ti5 - 273).toFixed(0)}°C` : "—"}
                </span>
              </div>
              <div className="env-cell">
                <span className="env-icon">💧</span>
                <span>
                  {weather?.relative_humidity_mean != null
                    ? `${Math.round(weather.relative_humidity_mean)}%` : "—"}
                </span>
              </div>
              <div className="env-cell full-width">
                <span className="env-icon">💨</span>
                <span>
                  {weather?.wind_speed_max != null
                    ? `${Math.round(weather.wind_speed_max)} km/h` : "—"}
                </span>
              </div>
            </div>
          </div>

          {/* ── RAW DATA ─────────────────────────────────────────────── */}
          <div style={{ borderTop: "1px solid var(--border-subtle)" }}>
            <div style={{ padding: "10px 16px 6px", fontSize: 9, fontWeight: 700, letterSpacing: "1px", textTransform: "uppercase", color: "var(--text-muted)" }}>
              Raw Detection Data
            </div>
            {[
              { label: "Satellite", value: hotspot.satellite },
              { label: "Instrument", value: hotspot.instrument },
              { label: "Acquired", value: formatDatetime(hotspot.acquisition_datetime) },
              { label: "FRP", value: hotspot.frp != null ? `${hotspot.frp.toFixed(1)} MW` : "—" },
              { label: "Brightness", value: hotspot.bright_ti4 != null ? `${hotspot.bright_ti4.toFixed(1)} K` : hotspot.brightness != null ? `${hotspot.brightness.toFixed(1)} K` : "—" },
              { label: "Day/Night", value: hotspot.daynight === "D" ? "Day" : hotspot.daynight === "N" ? "Night" : "—" },
              { label: "Source", value: hotspot.source },
              { label: "Obs ID", value: hotspot.id?.slice(0, 8) + "…" },
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
            Click any hotspot marker on the map to view the AI cause classification and evidence chain.
          </p>
        </div>
      )}

      <button className="help-btn" aria-label="Help">?</button>
    </div>
  );
}
