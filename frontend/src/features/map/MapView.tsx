"use client";

/**
 * MapView — full-page interactive Leaflet map
 * displaying thermal hotspot observations.
 *
 * Uses react-leaflet with dynamic import (no SSR)
 * because Leaflet requires the browser window object.
 */

import { useEffect } from "react";
import {
  MapContainer,
  TileLayer,
  useMap,
  ZoomControl,
  AttributionControl,
} from "react-leaflet";
import type { Hotspot } from "@/types/hotspot";
import HotspotMarker from "./HotspotMarker";
import "leaflet/dist/leaflet.css";

interface MapViewProps {
  hotspots: Hotspot[];
  selectedHotspot: Hotspot | null;
  onSelectHotspot: (hotspot: Hotspot) => void;
}

/**
 * Auto-fit map bounds when hotspots change.
 */
function FitBounds({ hotspots }: { hotspots: Hotspot[] }) {
  const map = useMap();

  useEffect(() => {
    if (hotspots.length === 0) return;

    const latLngs = hotspots.map(
      (h) => [h.latitude, h.longitude] as [number, number]
    );

    // Import L dynamically since this is client-only
    import("leaflet").then((L) => {
      const bounds = L.latLngBounds(latLngs);
      map.fitBounds(bounds, { padding: [50, 50], maxZoom: 10 });
    });
  }, [hotspots, map]);

  return null;
}

export default function MapView({
  hotspots,
  selectedHotspot,
  onSelectHotspot,
}: MapViewProps) {
  return (
    <MapContainer
      center={[20, 0]}
      zoom={2}
      minZoom={2}
      maxZoom={18}
      zoomControl={false}
      attributionControl={false}
      className="h-full w-full"
      style={{ background: "#0f172a" }}
    >
      {/* Dark-themed map tiles */}
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/">CARTO</a>'
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        maxZoom={20}
        crossOrigin={true}
      />

      <ZoomControl position="bottomright" />
      <AttributionControl position="bottomleft" prefix={false} />

      {/* Auto-fit on data load */}
      <FitBounds hotspots={hotspots} />

      {/* Hotspot markers */}
      {hotspots.map((hotspot) => (
        <HotspotMarker
          key={hotspot.id}
          hotspot={hotspot}
          isSelected={selectedHotspot?.id === hotspot.id}
          onClick={onSelectHotspot}
        />
      ))}
    </MapContainer>
  );
}
