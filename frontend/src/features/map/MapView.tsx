"use client";

/**
 * MapView — full-page interactive Leaflet map.
 *
 * Layers:
 *   1. OSM base tiles (dark-filtered)
 *   2. NASA FIRMS WMS fire detections (togglable, configurable time window + satellite)
 *   3. Our own ThermalObservation circle markers (color-coded by confidence + FRP)
 *
 * Phase 6: NASA FIRMS Live Map Layer
 */

import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import type { Hotspot } from "@/types/hotspot";
import "leaflet/dist/leaflet.css";

// ── Types ─────────────────────────────────────────────────────────────

export type FirmsTimeWindow = "24h" | "48h" | "7d";
export type FirmsSatelliteLayer = "noaa20" | "noaa21" | "combined";

interface FirmsLayerConfig {
  enabled: boolean;
  timeWindow: FirmsTimeWindow;
  satellite: FirmsSatelliteLayer;
}

interface MapViewProps {
  hotspots: Hotspot[];
  selectedHotspot: Hotspot | null;
  onSelectHotspot: (hotspot: Hotspot) => void;
}

// ── FIRMS WMS Layer names ─────────────────────────────────────────────
// https://firms.modaps.eosdis.nasa.gov/mapserver/wms/
const FIRMS_LAYER_MAP: Record<FirmsSatelliteLayer, Record<FirmsTimeWindow, string>> = {
  noaa20: {
    "24h": "fires_viirs_noaa20_24",
    "48h": "fires_viirs_noaa20_48",
    "7d": "fires_viirs_noaa20_7",
  },
  noaa21: {
    "24h": "fires_viirs_noaa21_24",
    "48h": "fires_viirs_noaa21_48",
    "7d": "fires_viirs_noaa21_7",
  },
  combined: {
    "24h": "fires_viirs_24",
    "48h": "fires_viirs_48",
    "7d": "fires_viirs_7",
  },
};

const FIRMS_MAP_KEY = process.env.NEXT_PUBLIC_FIRMS_MAP_KEY ?? "";
const FIRMS_WMS_BASE = `https://firms.modaps.eosdis.nasa.gov/mapserver/wms/fires/${FIRMS_MAP_KEY}/`;

// ── Marker helpers ─────────────────────────────────────────────────────

function getMarkerStyle(hotspot: Hotspot, isSelected: boolean) {
  const confidence = (hotspot.confidence || "").toLowerCase();
  const frp = hotspot.frp || 0;

  let fillColor = "#00d4ff";
  let color = "#0077b6";

  if (confidence === "high" || confidence === "h") {
    fillColor = "#f97316";
    color = "#ea580c";
  } else if (confidence === "nominal" || confidence === "n") {
    fillColor = "#eab308";
    color = "#ca8a04";
  } else if (confidence === "low" || confidence === "l") {
    fillColor = "#22c55e";
    color = "#16a34a";
  }

  let radius = 5;
  if (frp > 100) radius = 13;
  else if (frp > 50) radius = 10;
  else if (frp > 20) radius = 8;
  else if (frp > 5) radius = 6;

  if (isSelected) {
    fillColor = "#ffffff";
    color = "#00d4ff";
    radius = radius + 4;
  }

  return {
    radius,
    fillColor,
    color,
    weight: isSelected ? 2.5 : 1.5,
    opacity: 1,
    fillOpacity: isSelected ? 0.95 : 0.75,
  };
}

function formatTooltipTime(isoString: string): string {
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
    return isoString;
  }
}

function createTooltip(hotspot: Hotspot): string {
  const frpStr =
    hotspot.frp != null
      ? `<div style="color:#f97316;margin-top:2px">FRP: ${hotspot.frp.toFixed(1)} MW</div>`
      : "";
  return `
    <div style="font-size:12px;font-family:'Inter',sans-serif">
      <div style="font-weight:700;color:#e8eaf0;margin-bottom:2px">
        ${hotspot.satellite} · <span style="color:#00d4ff">${hotspot.confidence || "—"}</span>
      </div>
      <div style="color:#8892a4">${formatTooltipTime(hotspot.acquisition_datetime)}</div>
      ${frpStr}
    </div>
  `;
}

// ── Layer Toggle Panel (pure DOM, no React state, inserted into map) ──

function buildLayerControlHTML(cfg: FirmsLayerConfig): string {
  const timeOpts: { value: FirmsTimeWindow; label: string }[] = [
    { value: "24h", label: "24 Hours" },
    { value: "48h", label: "48 Hours" },
    { value: "7d", label: "7 Days" },
  ];
  const satOpts: { value: FirmsSatelliteLayer; label: string }[] = [
    { value: "noaa20", label: "NOAA-20" },
    { value: "noaa21", label: "NOAA-21" },
    { value: "combined", label: "Combined" },
  ];

  const timeOptHTML = timeOpts
    .map(
      (o) =>
        `<option value="${o.value}"${cfg.timeWindow === o.value ? " selected" : ""}>${o.label}</option>`
    )
    .join("");
  const satOptHTML = satOpts
    .map(
      (o) =>
        `<option value="${o.value}"${cfg.satellite === o.value ? " selected" : ""}>${o.label}</option>`
    )
    .join("");

  return `
    <div id="firms-panel" style="
      background:rgba(10,14,23,0.93);
      border:1px solid rgba(255,255,255,0.10);
      border-radius:10px;
      padding:12px 14px;
      min-width:172px;
      font-family:'Inter',sans-serif;
      box-shadow:0 4px 24px rgba(0,0,0,0.5);
      backdrop-filter:blur(8px);
    ">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">
        <span style="font-size:11px;font-weight:700;color:#e8eaf0;letter-spacing:0.04em;text-transform:uppercase">
          🛰 NASA FIRMS
        </span>
        <label style="margin-left:auto;display:flex;align-items:center;cursor:pointer">
          <input
            id="firms-toggle"
            type="checkbox"
            ${cfg.enabled ? "checked" : ""}
            style="width:14px;height:14px;accent-color:#00d4ff;cursor:pointer"
          />
        </label>
      </div>

      <div id="firms-options" style="display:${cfg.enabled ? "flex" : "none"};flex-direction:column;gap:7px">
        <div>
          <div style="font-size:10px;color:#8892a4;margin-bottom:3px">Time Window</div>
          <select id="firms-time" style="
            width:100%;background:#111827;color:#e8eaf0;border:1px solid rgba(255,255,255,0.12);
            border-radius:6px;padding:4px 6px;font-size:11px;cursor:pointer;outline:none
          ">${timeOptHTML}</select>
        </div>
        <div>
          <div style="font-size:10px;color:#8892a4;margin-bottom:3px">Satellite</div>
          <select id="firms-sat" style="
            width:100%;background:#111827;color:#e8eaf0;border:1px solid rgba(255,255,255,0.12);
            border-radius:6px;padding:4px 6px;font-size:11px;cursor:pointer;outline:none
          ">${satOptHTML}</select>
        </div>

        <div style="
          margin-top:2px;padding:5px 7px;background:rgba(0,212,255,0.06);
          border:1px solid rgba(0,212,255,0.15);border-radius:5px;
          font-size:10px;color:#8892a4;line-height:1.4
        ">
          Live NASA fire detections overlaid on map tiles
        </div>
      </div>

      <div style="margin-top:8px;display:flex;align-items:center;gap:5px">
        <span style="width:8px;height:8px;border-radius:50%;background:${cfg.enabled ? "#f97316" : "#374151"};display:inline-block;transition:background .2s"></span>
        <span style="font-size:10px;color:${cfg.enabled ? "#f97316" : "#6b7280"}">
          ${cfg.enabled ? "Layer active" : "Layer off"}
        </span>
      </div>
    </div>
  `;
}

// ── Main component ────────────────────────────────────────────────────

export default function MapView({
  hotspots,
  selectedHotspot,
  onSelectHotspot,
}: MapViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const markersRef = useRef<L.LayerGroup | null>(null);
  const firmsWmsRef = useRef<L.TileLayer.WMS | null>(null);
  const controlDivRef = useRef<HTMLDivElement | null>(null);
  const selectRef = useRef(onSelectHotspot);

  const [firmsConfig, setFirmsConfig] = useState<FirmsLayerConfig>({
    enabled: true,
    timeWindow: "24h",
    satellite: "combined",
  });
  // Keep a ref so DOM event handlers always see current value
  const firmsConfigRef = useRef(firmsConfig);
  firmsConfigRef.current = firmsConfig;

  useEffect(() => {
    selectRef.current = onSelectHotspot;
  }, [onSelectHotspot]);

  // ── Init map (once) ────────────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current) return;
    const el = containerRef.current as HTMLDivElement & { _leaflet_id?: number };
    if (el._leaflet_id) delete el._leaflet_id;

    const map = L.map(el, {
      center: [20, 0],
      zoom: 2,
      minZoom: 2,
      maxZoom: 18,
      zoomControl: false,
      attributionControl: false,
    });

    // Base tile layer
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 19,
    }).addTo(map);

    // Controls
    L.control.zoom({ position: "bottomright" }).addTo(map);
    L.control.attribution({ position: "bottomleft", prefix: false }).addTo(map);

    // Marker layer group
    const markers = L.layerGroup().addTo(map);
    markersRef.current = markers;

    // ── NASA FIRMS WMS layer ─────────────────────────────────────────
    if (FIRMS_MAP_KEY) {
      const cfg = firmsConfigRef.current;
      const layerName = FIRMS_LAYER_MAP[cfg.satellite][cfg.timeWindow];
      const wmsLayer = L.tileLayer.wms(FIRMS_WMS_BASE, {
        layers: layerName,
        format: "image/png",
        transparent: true,
        opacity: 0.85,
        attribution: '🔥 <a href="https://firms.modaps.eosdis.nasa.gov/" target="_blank">NASA FIRMS</a>',
        // Leaflet defaults to EPSG:3857 which FIRMS WMS supports
      });

      if (cfg.enabled) {
        wmsLayer.addTo(map);
      }
      firmsWmsRef.current = wmsLayer;
    }

    // ── Custom layer toggle control ──────────────────────────────────
    const LayerControl = L.Control.extend({
      onAdd() {
        const div = L.DomUtil.create("div", "leaflet-bar leaflet-control");
        div.innerHTML = buildLayerControlHTML(firmsConfigRef.current);
        L.DomEvent.disableClickPropagation(div);
        L.DomEvent.disableScrollPropagation(div);

        // Wire up toggle checkbox
        const toggle = div.querySelector<HTMLInputElement>("#firms-toggle");
        const options = div.querySelector<HTMLElement>("#firms-options");
        const statusDot = div.querySelector<HTMLElement>("#firms-panel div:last-child span:first-child");
        const statusText = div.querySelector<HTMLElement>("#firms-panel div:last-child span:last-child");

        if (toggle) {
          toggle.addEventListener("change", () => {
            const newEnabled = toggle.checked;
            if (options) options.style.display = newEnabled ? "flex" : "none";
            if (statusDot) {
              statusDot.style.background = newEnabled ? "#f97316" : "#374151";
            }
            if (statusText) {
              statusText.style.color = newEnabled ? "#f97316" : "#6b7280";
              statusText.textContent = newEnabled ? "Layer active" : "Layer off";
            }

            setFirmsConfig((prev) => {
              const next = { ...prev, enabled: newEnabled };
              firmsConfigRef.current = next;
              const wms = firmsWmsRef.current;
              if (wms) {
                if (newEnabled) wms.addTo(map);
                else map.removeLayer(wms);
              }
              return next;
            });
          });
        }

        // Wire up time window selector
        const timeSelect = div.querySelector<HTMLSelectElement>("#firms-time");
        if (timeSelect) {
          timeSelect.addEventListener("change", () => {
            const newTime = timeSelect.value as FirmsTimeWindow;
            setFirmsConfig((prev) => {
              const next = { ...prev, timeWindow: newTime };
              firmsConfigRef.current = next;
              updateWmsLayer(map, next);
              return next;
            });
          });
        }

        // Wire up satellite selector
        const satSelect = div.querySelector<HTMLSelectElement>("#firms-sat");
        if (satSelect) {
          satSelect.addEventListener("change", () => {
            const newSat = satSelect.value as FirmsSatelliteLayer;
            setFirmsConfig((prev) => {
              const next = { ...prev, satellite: newSat };
              firmsConfigRef.current = next;
              updateWmsLayer(map, next);
              return next;
            });
          });
        }

        controlDivRef.current = div;
        return div;
      },
    });

    new LayerControl({ position: "topright" }).addTo(map);
    mapRef.current = map;

    // Invalidate size after layout
    const t = setTimeout(() => map.invalidateSize(), 200);

    return () => {
      clearTimeout(t);
      map.remove();
      mapRef.current = null;
      markersRef.current = null;
      firmsWmsRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Update FIRMS WMS when config changes ───────────────────────────
  // (also called from DOM event handlers above via updateWmsLayer)
  function updateWmsLayer(map: L.Map, cfg: FirmsLayerConfig) {
    const oldWms = firmsWmsRef.current;
    if (oldWms) map.removeLayer(oldWms);

    if (!FIRMS_MAP_KEY) return;

    const layerName = FIRMS_LAYER_MAP[cfg.satellite][cfg.timeWindow];
    const newWms = L.tileLayer.wms(FIRMS_WMS_BASE, {
      layers: layerName,
      format: "image/png",
      transparent: true,
      opacity: 0.85,
      attribution: '🔥 <a href="https://firms.modaps.eosdis.nasa.gov/" target="_blank">NASA FIRMS</a>',
    });

    firmsWmsRef.current = newWms;
    if (cfg.enabled) newWms.addTo(map);
  }

  // ── Update markers when hotspots / selection changes ───────────────
  useEffect(() => {
    const map = mapRef.current;
    const layer = markersRef.current;
    if (!map || !layer) return;

    layer.clearLayers();
    if (hotspots.length === 0) return;

    const latLngs: L.LatLngTuple[] = [];

    hotspots.forEach((h) => {
      const lat = Number(h.latitude);
      const lon = Number(h.longitude);
      if (isNaN(lat) || isNaN(lon)) return;

      const isSelected = selectedHotspot?.id === h.id;
      const style = getMarkerStyle(h, isSelected);
      latLngs.push([lat, lon]);

      const marker = L.circleMarker([lat, lon], style);
      marker.bindTooltip(createTooltip(h), {
        direction: "top",
        offset: [0, -8],
        className: "thermasense-tooltip",
      });
      marker.on("click", () => selectRef.current(h));
      marker.addTo(layer);
    });

    if (latLngs.length > 0) {
      map.invalidateSize();
      map.fitBounds(L.latLngBounds(latLngs), { padding: [50, 50], maxZoom: 9 });
    }
  }, [hotspots, selectedHotspot]);

  return (
    <div
      ref={containerRef}
      style={{ width: "100%", height: "100%", background: "#0a0e17" }}
    />
  );
}
