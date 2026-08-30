import { useCallback, useEffect, useState } from 'react';
import { api } from './api';
import { AlertCenter } from './components/AlertCenter';
import { EventPanel } from './components/EventPanel';
import { Header } from './components/Header';
import { MapView } from './components/MapView';
import { SimulateModal } from './components/SimulateModal';
import type { Alert, Stats, ThermalEventSummary, WsEventAnalyzed, WsMessage, WsThermalAlert } from './types';
import { useWebSocket } from './useWebSocket';
import './index.css';

export default function App() {
  const [events, setEvents] = useState<ThermalEventSummary[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [showSimulate, setShowSimulate] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const [backendOk, setBackendOk] = useState(true);

  // ── Load initial data ────────────────────────────────────────────────────
  const loadEvents = useCallback(async () => {
    try {
      const data = await api.latest(300);
      setEvents(data);
      setLastUpdate(new Date());
      setBackendOk(true);
    } catch { setBackendOk(false); }
  }, []);

  const loadStats = useCallback(async () => {
    try { setStats(await api.stats()); } catch { /* silent */ }
  }, []);

  const loadAlerts = useCallback(async () => {
    try { setAlerts(await api.alerts()); } catch { /* silent */ }
  }, []);

  useEffect(() => {
    loadEvents();
    loadStats();
    loadAlerts();
    const t = setInterval(() => { loadStats(); }, 60_000);
    return () => clearInterval(t);
  }, [loadEvents, loadStats, loadAlerts]);

  // ── WebSocket handler ────────────────────────────────────────────────────
  const handleWsMessage = useCallback((msg: WsMessage) => {
    if (msg.type === 'THERMAL_EVENT_ANALYZED') {
      const m = msg as WsEventAnalyzed;
      // Add/update event in the list
      setEvents(prev => {
        const exists = prev.find(e => e.id === m.event_id);
        if (exists) {
          return prev.map(e =>
            e.id === m.event_id
              ? { ...e, risk_level: m.risk_level, risk_score: m.risk_score }
              : e
          );
        }
        // New event — prepend a minimal entry; full data loads when selected
        const newEv: ThermalEventSummary = {
          id: m.event_id,
          source: m.simulated ? 'DEMO' : 'VIIRS_SNPP_NRT',
          latitude: m.latitude,
          longitude: m.longitude,
          acq_date: new Date().toISOString().slice(0, 10),
          acq_time: new Date().toTimeString().slice(0, 5).replace(':', ''),
          frp: m.frp,
          brightness: null,
          confidence: null,
          satellite: m.simulated ? 'DEMO-SAT' : null,
          risk_level: m.risk_level,
          risk_score: m.risk_score,
          ai_summary: null,
        };
        return [newEv, ...prev];
      });
      setLastUpdate(new Date());
      loadStats();
    }

    if (msg.type === 'THERMAL_ALERT') {
      const m = msg as WsThermalAlert;
      const newAlert: Alert = {
        event_id: m.event_id,
        risk_level: m.risk_level,
        risk_score: m.risk_score,
        classification: m.classification,
        latitude: m.latitude,
        longitude: m.longitude,
        frp: null,
        timestamp: m.timestamp,
        summary: m.summary,
        simulated: m.simulated,
        confidence: null,
      };
      setAlerts(prev => [newAlert, ...prev.slice(0, 49)]);
    }
  }, [loadStats]);

  const { status: wsStatus } = useWebSocket(handleWsMessage);

  // ── Simulation complete handler ──────────────────────────────────────────
  const handleSimulated = useCallback((eventId: number) => {
    setShowSimulate(false);
    setSelectedId(eventId);
    loadEvents();
  }, [loadEvents]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
      <Header
        wsStatus={wsStatus}
        stats={stats}
        lastUpdate={lastUpdate}
        backendOk={backendOk}
        onSimulate={() => setShowSimulate(true)}
      />

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {/* Left: Alert Center */}
        <AlertCenter
          alerts={alerts}
          onSelect={(id) => setSelectedId(id)}
          selectedId={selectedId}
        />

        {/* Centre: Map */}
        <div style={{ flex: 1, position: 'relative' }}>
          <MapView
            events={events}
            selectedId={selectedId}
            onSelect={setSelectedId}
          />
        </div>

        {/* Right: Event Intelligence Panel */}
        <EventPanel
          eventId={selectedId}
          onClose={() => setSelectedId(null)}
        />
      </div>

      {/* Simulate Modal */}
      {showSimulate && (
        <SimulateModal
          onClose={() => setShowSimulate(false)}
          onComplete={handleSimulated}
        />
      )}
    </div>
  );
}
