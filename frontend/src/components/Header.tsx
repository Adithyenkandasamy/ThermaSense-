import type { Stats } from '../types';
import type { WsStatus } from '../useWebSocket';

interface Props {
  wsStatus: WsStatus;
  stats: Stats | null;
  lastUpdate: Date | null;
  backendOk: boolean;
  onSimulate: () => void;
}

export function Header({ wsStatus, stats, lastUpdate, backendOk, onSimulate }: Props) {
  const isLive = wsStatus === 'connected' && backendOk;

  return (
    <header style={{
      display: 'flex', alignItems: 'center', gap: 16,
      padding: '0 20px', height: 52,
      background: 'var(--bg-panel)',
      borderBottom: '1px solid var(--border)',
      flexShrink: 0,
    }}>
      {/* Brand */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 180 }}>
        <span style={{
          fontSize: 18, fontWeight: 900, letterSpacing: '0.12em',
          color: 'var(--cyan)', fontFamily: 'monospace',
        }}>
          THERMASENSE
        </span>
        <span style={{ fontSize: 9, color: 'var(--text-dim)', letterSpacing: '0.05em' }}>v0.2</span>
      </div>

      {/* Live indicator */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{
          width: 7, height: 7, borderRadius: '50%',
          background: isLive ? 'var(--low)' : wsStatus === 'connecting' ? 'var(--mod)' : 'var(--extreme)',
          boxShadow: isLive ? '0 0 6px var(--low)' : 'none',
          display: 'inline-block',
          animation: isLive ? 'pulse 2s infinite' : 'none',
        }} />
        <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.1em', color: 'var(--text-muted)' }}>
          {isLive ? 'LIVE' : wsStatus === 'connecting' ? 'CONNECTING' : 'DISCONNECTED'}
        </span>
      </div>

      <div style={{ flex: 1 }} />

      {/* Stats chips */}
      {stats && (
        <div style={{ display: 'flex', gap: 16, fontSize: 11 }}>
          <StatChip label="EVENTS" value={stats.events_last_24h} />
          <StatChip label="HIGH" value={stats.high_count} color="var(--high)" />
          <StatChip label="EXTREME" value={stats.extreme_count} color="var(--extreme)" />
          {lastUpdate && (
            <StatChip label="UPDATED" value={lastUpdate.toLocaleTimeString()} />
          )}
        </div>
      )}

      {/* Simulate button */}
      <button
        className="btn-primary"
        onClick={onSimulate}
        style={{ marginLeft: 8, whiteSpace: 'nowrap', letterSpacing: '0.06em' }}
      >
        ⚡ SIMULATE EVENT
      </button>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>
    </header>
  );
}

function StatChip({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', lineHeight: 1.2 }}>
      <span style={{ fontSize: 9, color: 'var(--text-dim)', letterSpacing: '0.08em' }}>{label}</span>
      <span style={{ fontWeight: 700, color: color ?? 'var(--text-muted)', fontSize: 13 }}>{value}</span>
    </div>
  );
}
