import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { useEffect, useRef } from 'react';
import type { RiskLevel, ThermalEventSummary } from '../types';

// Fix leaflet default icon paths broken by bundlers
delete (L.Icon.Default.prototype as unknown as Record<string, unknown>)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

const RISK_COLORS: Record<RiskLevel, string> = {
  LOW:      '#4ade80',
  MODERATE: '#facc15',
  HIGH:     '#f97316',
  EXTREME:  '#ef4444',
};

const RISK_RADIUS: Record<RiskLevel, number> = {
  LOW:      6,
  MODERATE: 8,
  HIGH:     11,
  EXTREME:  14,
};

function makeMarker(event: ThermalEventSummary, selected: boolean) {
  const color = RISK_COLORS[event.risk_level] ?? '#888';
  const r = RISK_RADIUS[event.risk_level] ?? 7;
  const isDemo = event.source === 'DEMO';
  const size = selected ? r * 2.6 : r * 2;
  const border = selected ? 3 : isDemo ? 2 : 1.5;
  const borderColor = selected ? '#fff' : isDemo ? '#00d4d8' : color;
  const glow = selected
    ? `0 0 14px ${color}, 0 0 4px #fff`
    : event.risk_level === 'EXTREME'
    ? `0 0 10px ${color}`
    : 'none';

  const html = `
    <div style="
      width:${size}px; height:${size}px;
      border-radius:50%;
      background:${color};
      border:${border}px solid ${borderColor};
      box-shadow:${glow};
      opacity:${selected ? 1 : 0.82};
      transition: all 0.15s;
    "></div>`;

  return L.divIcon({
    html,
    className: '',
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

interface Props {
  events: ThermalEventSummary[];
  selectedId: number | null;
  onSelect: (id: number) => void;
}

export function MapView({ events, selectedId, onSelect }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const markersRef = useRef<Map<number, L.Marker>>(new Map());
  const eventsRef = useRef(events);
  const onSelectRef = useRef(onSelect);
  eventsRef.current = events;
  onSelectRef.current = onSelect;

  // ── Init map once ──────────────────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = L.map(containerRef.current, {
      center: [20, 0],
      zoom: 3,
      zoomControl: true,
      attributionControl: false,
    });

    L.tileLayer(
      'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
      { maxZoom: 19 }
    ).addTo(map);

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
      markersRef.current.clear();
    };
  }, []);

  // ── Sync markers ───────────────────────────────────────────────────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const incoming = new Map(events.map(e => [e.id, e]));

    // Remove stale markers
    for (const [id, marker] of markersRef.current) {
      if (!incoming.has(id)) {
        marker.remove();
        markersRef.current.delete(id);
      }
    }

    // Add / update markers
    for (const event of events) {
      const existing = markersRef.current.get(event.id);
      const selected = event.id === selectedId;
      const icon = makeMarker(event, selected);

      if (existing) {
        existing.setIcon(icon);
      } else {
        const marker = L.marker([event.latitude, event.longitude], { icon })
          .addTo(map)
          .on('click', () => onSelectRef.current(event.id));

        const frpStr = event.frp != null ? `${event.frp.toFixed(0)} MW` : 'N/A';
        marker.bindTooltip(
          `<b style="color:${RISK_COLORS[event.risk_level]}">${event.risk_level}</b> — ${frpStr}<br/>
           ${event.source === 'DEMO' ? '<span style="color:#00d4d8">DEMO</span>' : 'FIRMS'}`,
          { className: 'ts-tooltip', direction: 'top', offset: [0, -8] }
        );
        markersRef.current.set(event.id, marker);
      }
    }
  }, [events, selectedId]);

  // ── Pan to selected event ───────────────────────────────────────────────
  useEffect(() => {
    if (!selectedId || !mapRef.current) return;
    const ev = eventsRef.current.find(e => e.id === selectedId);
    if (ev) {
      mapRef.current.flyTo([ev.latitude, ev.longitude], Math.max(mapRef.current.getZoom(), 9), {
        duration: 0.8,
      });
    }
  }, [selectedId]);

  // ── Auto-fit on first load ─────────────────────────────────────────────
  useEffect(() => {
    if (!mapRef.current || events.length === 0) return;
    try {
      const bounds = L.latLngBounds(events.map(e => [e.latitude, e.longitude]));
      if (bounds.isValid()) {
        mapRef.current.fitBounds(bounds, { padding: [40, 40], maxZoom: 8, animate: false });
      }
    } catch { /* ignore invalid bounds */ }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [events.length > 0]);

  return (
    <>
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
      <style>{`
        .ts-tooltip {
          background: #111118ee;
          border: 1px solid #2a2a3a;
          color: #e8e8f0;
          font-size: 11px;
          padding: 4px 8px;
          border-radius: 6px;
        }
        .ts-tooltip::before { display: none; }
        .leaflet-tooltip-top.ts-tooltip::before {
          display: block;
          border-top-color: #2a2a3a;
        }
      `}</style>
    </>
  );
}
