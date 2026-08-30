"use client";

/**
 * MapView — Full-Page Geospatial Intelligence Map.
 *
 * Basemap Modes:
 *   1. 🛰 Satellite Imagery (ESRI World Imagery / NASA GIBS True Color)
 *   2. 🌙 Dark Intelligence (CartoDB Dark Matter)
 *   3. 🗺 Topographic / Streets (OpenStreetMap)
 *
 * Layers:
 *   - NASA FIRMS WMS Real-Time Fire Detections (High-DPI / Crisp)
 *   - Clustered Thermal Events & Hotspot Circle Markers
 */

import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import type { Hotspot } from "@/types/hotspot";
import "leaflet/dist/leaflet.css";

// ── Types ─────────────────────────────────────────────────────────────

export type FirmsTimeWindow = "24h" | "48h" | "7d";
export type FirmsSatelliteLayer = "noaa20" | "noaa21" | "combined";
export type BasemapType = "satellite" | "dark" | "streets";

interface FirmsLayerConfig {
  enabled: boolean;
  timeWindow: FirmsTimeWindow;
  satellite: FirmsSatelliteLayer;
  basemap: BasemapType;
}

interface MapViewProps {
  hotspots: Hotspot[];
  selectedHotspot: Hotspot | null;
  onSelectHotspot: (hotspot: Hotspot) => void;
  /** 0–100. Hotspots below this satellite confidence level are hidden. */
  confidenceThreshold?: number;
}

// ── Basemap Tile Providers ────────────────────────────────────────────

const BASEMAP_TILES: Record<BasemapType, { url: string; attribution: string; maxZoom: number }> = {
  satellite: {
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attribution: "© Esri, Maxar, Earthstar Geographics, NASA GIBS",
    maxZoom: 19,
  },
  dark: {
    url: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
    attribution: "© OpenStreetMap contributors, © CARTO",
    maxZoom: 20,
  },
  streets: {
    url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    attribution: "© OpenStreetMap contributors",
    maxZoom: 19,
  },
};

// ── FIRMS WMS Layer Mapping ───────────────────────────────────────────

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

const FIRMS_MAP_KEY = process.env.NEXT_PUBLIC_FIRMS_MAP_KEY ?? "cc9bbdc3216ebdaab31d9b11fbf502a9";
const FIRMS_WMS_BASE = `https://firms.modaps.eosdis.nasa.gov/mapserver/wms/fires/${FIRMS_MAP_KEY}/`;

// ── Marker Styling ────────────────────────────────────────────────────

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
  if (frp > 100) radius = 12;
  else if (frp > 50) radius = 9;
  else if (frp > 20) radius = 7;
  else if (frp > 5) radius = 5;

  if (isSelected) {
    fillColor = "#ffffff";
    color = "#00d4ff";
    radius = radius + 4;
  }

  return {
    radius,
    fillColor,
    color,
    weight: isSelected ? 2.5 : 1.2,
    opacity: 1,
    fillOpacity: isSelected ? 0.95 : 0.8,
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
      ? `<div style="color:#f97316;margin-top:2px;font-weight:700">FRP: ${hotspot.frp.toFixed(1)} MW</div>`
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

// ── Control Panel HTML Builder ────────────────────────────────────────

function buildLayerControlHTML(cfg: FirmsLayerConfig): string {
  const timeOpts: { value: FirmsTimeWindow; label: string }[] = [
    { value: "24h", label: "24 Hours" },
    { value: "48h", label: "48 Hours" },
    { value: "7d", label: "7 Days" },
  ];
  const satOpts: { value: FirmsSatelliteLayer; label: string }[] = [
    { value: "combined", label: "Combined VIIRS" },
    { value: "noaa20", label: "NOAA-20" },
    { value: "noaa21", label: "NOAA-21" },
  ];
  const basemapOpts: { value: BasemapType; label: string }[] = [
    { value: "satellite", label: "🛰 NASA Satellite" },
    { value: "dark", label: "🌙 Dark Analytics" },
    { value: "streets", label: "🗺 Street Map" },
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
  const basemapOptHTML = basemapOpts
    .map(
      (o) =>
        `<option value="${o.value}"${cfg.basemap === o.value ? " selected" : ""}>${o.label}</option>`
    )
    .join("");

  return `
    <div id="firms-panel" style="
      background:rgba(10,14,23,0.92);
      border:1px solid rgba(255,255,255,0.12);
      border-radius:10px;
      padding:12px 14px;
      min-width:185px;
      font-family:'Inter',sans-serif;
      box-shadow:0 8px 32px rgba(0,0,0,0.65);
      backdrop-filter:blur(10px);
    ">
      <!-- Basemap Selector -->
      <div style="margin-bottom:10px">
        <div style="font-size:10px;color:#94a3b8;margin-bottom:3px;font-weight:600;text-transform:uppercase">Basemap View</div>
        <select id="basemap-select" style="
          width:100%;background:#111827;color:#f1f5f9;border:1px solid rgba(255,255,255,0.16);
          border-radius:6px;padding:5px 7px;font-size:11px;font-weight:600;cursor:pointer;outline:none
        ">${basemapOptHTML}</select>
      </div>

      <div style="height:1px;background:rgba(255,255,255,0.08);margin:8px 0"></div>

      <!-- FIRMS WMS Section -->
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
        <span style="font-size:11px;font-weight:700;color:#f8fafc;letter-spacing:0.04em;text-transform:uppercase">
          🔥 NASA FIRMS WMS
        </span>
        <label style="margin-left:auto;display:flex;align-items:center;cursor:pointer">
          <input
            id="firms-toggle"
            type="checkbox"
            ${cfg.enabled ? "checked" : ""}
            style="width:14px;height:14px;accent-color:#f97316;cursor:pointer"
          />
        </label>
      </div>

      <div id="firms-options" style="display:${cfg.enabled ? "flex" : "none"};flex-direction:column;gap:7px">
        <div>
          <div style="font-size:10px;color:#94a3b8;margin-bottom:3px">Detection Window</div>
          <select id="firms-time" style="
            width:100%;background:#111827;color:#e8eaf0;border:1px solid rgba(255,255,255,0.12);
            border-radius:6px;padding:4px 6px;font-size:11px;cursor:pointer;outline:none
          ">${timeOptHTML}</select>
        </div>
        <div>
          <div style="font-size:10px;color:#8892a4;margin-bottom:3px">Satellite Sensor</div>
          <select id="firms-sat" style="
            width:100%;background:#111827;color:#e8eaf0;border:1px solid rgba(255,255,255,0.12);
            border-radius:6px;padding:4px 6px;font-size:11px;cursor:pointer;outline:none
          ">${satOptHTML}</select>
        </div>

        <div style="
          margin-top:2px;padding:5px 7px;background:rgba(249,115,22,0.08);
          border:1px solid rgba(249,115,22,0.2);border-radius:5px;
          font-size:10px;color:#cbd5e1;line-height:1.4
        ">
          Live crisp satellite fire detections streamed from NASA servers
        </div>
      </div>

      <div style="margin-top:8px;display:flex;align-items:center;gap:6px">
        <span style="width:7px;height:7px;border-radius:50%;background:${cfg.enabled ? "#f97316" : "#475569"};display:inline-block"></span>
        <span style="font-size:10px;color:${cfg.enabled ? "#fb923c" : "#64748b"};font-weight:600">
          ${cfg.enabled ? "NASA WMS Active" : "WMS Inactive"}
        </span>
      </div>
    </div>
  `;
}

// ── MapView Component ─────────────────────────────────────────────────

export default function MapView({
  hotspots,
  selectedHotspot,
  onSelectHotspot,
  confidenceThreshold = 0,
}: MapViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const baseTileRef = useRef<L.TileLayer | null>(null);
  const markersRef = useRef<L.LayerGroup | null>(null);
  const firmsWmsRef = useRef<L.TileLayer.WMS | null>(null);
  const controlDivRef = useRef<HTMLDivElement | null>(null);
  const selectRef = useRef(onSelectHotspot);

  const [firmsConfig, setFirmsConfig] = useState<FirmsLayerConfig>({
    enabled: true,
    timeWindow: "24h",
    satellite: "combined",
    basemap: "satellite", // Default to NASA Satellite Imagery!
  });
  const firmsConfigRef = useRef(firmsConfig);
  firmsConfigRef.current = firmsConfig;

  useEffect(() => {
    selectRef.current = onSelectHotspot;
  }, [onSelectHotspot]);

  // ── Init Map (once) ────────────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current) return;
    const el = containerRef.current as HTMLDivElement & { _leaflet_id?: number };
    if (el._leaflet_id) delete el._leaflet_id;

    const map = L.map(el, {
      center: [20, 10],
      zoom: 3,
      minZoom: 2,
      maxZoom: 18,
      zoomControl: false,
      attributionControl: false,
    });

    // 1. Initial Basemap (Satellite)
    const baseCfg = BASEMAP_TILES[firmsConfigRef.current.basemap];
    const baseLayer = L.tileLayer(baseCfg.url, {
      attribution: baseCfg.attribution,
      maxZoom: baseCfg.maxZoom,
    }).addTo(map);
    baseTileRef.current = baseLayer;

    // 2. Controls
    L.control.zoom({ position: "bottomright" }).addTo(map);
    L.control.attribution({ position: "bottomleft", prefix: false }).addTo(map);

    // 3. Marker Layer Group
    const markers = L.layerGroup().addTo(map);
    markersRef.current = markers;

    // 4. Crisp NASA FIRMS WMS Layer
    if (FIRMS_MAP_KEY) {
      const cfg = firmsConfigRef.current;
      const layerName = FIRMS_LAYER_MAP[cfg.satellite][cfg.timeWindow];
      const wmsLayer = L.tileLayer.wms(FIRMS_WMS_BASE, {
        layers: layerName,
        format: "image/png",
        transparent: true,
        opacity: 0.92,
        version: "1.1.1",
        attribution: '🔥 <a href="https://firms.modaps.eosdis.nasa.gov/" target="_blank">NASA FIRMS</a>',
      });

      if (cfg.enabled) {
        wmsLayer.addTo(map);
      }
      firmsWmsRef.current = wmsLayer;
    }

    // 5. Custom Control Widget
    const LayerControl = L.Control.extend({
      onAdd() {
        const div = L.DomUtil.create("div", "leaflet-bar leaflet-control");
        div.innerHTML = buildLayerControlHTML(firmsConfigRef.current);
        L.DomEvent.disableClickPropagation(div);
        L.DomEvent.disableScrollPropagation(div);

        // Basemap change
        const basemapSelect = div.querySelector<HTMLSelectElement>("#basemap-select");
        if (basemapSelect) {
          basemapSelect.addEventListener("change", () => {
            const newBasemap = basemapSelect.value as BasemapType;
            setFirmsConfig((prev) => {
              const next = { ...prev, basemap: newBasemap };
              firmsConfigRef.current = next;

              // Swap basemap
              if (baseTileRef.current) map.removeLayer(baseTileRef.current);
              const bCfg = BASEMAP_TILES[newBasemap];
              const newBase = L.tileLayer(bCfg.url, {
                attribution: bCfg.attribution,
                maxZoom: bCfg.maxZoom,
              }).addTo(map);
              newBase.bringToBack();
              baseTileRef.current = newBase;

              return next;
            });
          });
        }

        // Toggle FIRMS WMS
        const toggle = div.querySelector<HTMLInputElement>("#firms-toggle");
        const options = div.querySelector<HTMLElement>("#firms-options");
        const statusDot = div.querySelector<HTMLElement>("#firms-panel div:last-child span:first-child");
        const statusText = div.querySelector<HTMLElement>("#firms-panel div:last-child span:last-child");

        if (toggle) {
          toggle.addEventListener("change", () => {
            const newEnabled = toggle.checked;
            if (options) options.style.display = newEnabled ? "flex" : "none";
            if (statusDot) {
              statusDot.style.background = newEnabled ? "#f97316" : "#475569";
            }
            if (statusText) {
              statusText.style.color = newEnabled ? "#fb923c" : "#64748b";
              statusText.textContent = newEnabled ? "NASA WMS Active" : "WMS Inactive";
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

        // Time window change
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

        // Satellite sensor change
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

    const t = setTimeout(() => map.invalidateSize(), 200);

    return () => {
      clearTimeout(t);
      map.remove();
      mapRef.current = null;
      markersRef.current = null;
      firmsWmsRef.current = null;
      baseTileRef.current = null;
    };
  }, []);

  function updateWmsLayer(map: L.Map, cfg: FirmsLayerConfig) {
    const oldWms = firmsWmsRef.current;
    if (oldWms) map.removeLayer(oldWms);

    if (!FIRMS_MAP_KEY) return;

    const layerName = FIRMS_LAYER_MAP[cfg.satellite][cfg.timeWindow];
    const newWms = L.tileLayer.wms(FIRMS_WMS_BASE, {
      layers: layerName,
      format: "image/png",
      transparent: true,
      opacity: 0.92,
      version: "1.1.1",
      attribution: '🔥 <a href="https://firms.modaps.eosdis.nasa.gov/" target="_blank">NASA FIRMS</a>',
    });

    firmsWmsRef.current = newWms;
    if (cfg.enabled) newWms.addTo(map);
  }

  // ── Update Observations Markers ─────────────────────────────────────
  useEffect(() => {
    const map = mapRef.current;
    const layer = markersRef.current;
    if (!map || !layer) return;

    layer.clearLayers();
    if (hotspots.length === 0) return;

    // ── Confidence threshold mapping ──────────────────────────────────
    // VIIRS confidence is stored as "low", "nominal", "high"
    // We map the slider (0–100) to these tiers:
    //   0–33  → show all (low + nominal + high)
    //   34–66 → show nominal + high only
    //   67–100 → show high only
    const threshold = confidenceThreshold ?? 0;
    const allowedConfidences = new Set<string>();
    if (threshold <= 33) {
      allowedConfidences.add("low").add("l").add("nominal").add("n").add("high").add("h");
    } else if (threshold <= 66) {
      allowedConfidences.add("nominal").add("n").add("high").add("h");
    } else {
      allowedConfidences.add("high").add("h");
    }

    const latLngs: L.LatLngTuple[] = [];

    hotspots.forEach((h) => {
      const lat = Number(h.latitude);
      const lon = Number(h.longitude);
      if (isNaN(lat) || isNaN(lon)) return;

      // ── Confidence filter ─────────────────────────────────────────
      const conf = (h.confidence || "").toLowerCase();
      if (!allowedConfidences.has(conf)) return;

      // ── Himalayan snow/glacier false-positive suppression ─────────
      // Above lat 30°N in the Himalayan/Tibetan zone: only keep observations
      // with FRP > 15 MW OR high satellite confidence to filter out snow
      // reflectance artifacts and lone pixel detections in glaciated terrain.
      const isHighAltitudeHimalayas =
        lat > 30.0 && lat < 38.0 && lon > 70.0 && lon < 95.0;
      if (isHighAltitudeHimalayas) {
        const frp = h.frp ?? 0;
        const isHighConf = conf === "high" || conf === "h";
        // Suppress low-FRP non-high-confidence Himalayan pixels
        if (frp < 15 && !isHighConf) return;
      }

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
  }, [hotspots, selectedHotspot, confidenceThreshold]);

  return (
    <div
      ref={containerRef}
      style={{ width: "100%", height: "100%", background: "#0a0e17" }}
    />
  );
}
