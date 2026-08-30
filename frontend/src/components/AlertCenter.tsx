import type { Alert } from '../types';

interface Props {
  alerts: Alert[];
  selectedId: number | null;
  onSelect: (id: number) => void;
}

const RISK_ICONS: Record<string, string> = {
  LOW: '🟢', MODERATE: '🟡', HIGH: '🟠', EXTREME: '🔴',
};

export function AlertCenter({ alerts, selectedId, onSelect }: Props) {
  return (
    <aside style={{
      width: 240,
      minWidth: 240,
      background: 'var(--bg-panel)',
      borderRight: '1px solid var(--border)',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
    }}>
      <div style={{
        padding: '12px 14px 10px',
        borderBottom: '1px solid var(--border)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        <h2>ALERT CENTER</h2>
        {alerts.length > 0 && (
          <span style={{
            background: 'var(--extreme)', color: '#fff',
            borderRadius: '50%', width: 16, height: 16,
            fontSize: 9, fontWeight: 700, display: 'flex',
            alignItems: 'center', justifyContent: 'center',
          }}>
            {alerts.length > 99 ? '99+' : alerts.length}
          </span>
        )}
      </div>

      <div style={{ flex: 1, overflow: 'auto' }}>
        {alerts.length === 0 ? (
          <div style={{ padding: '20px 14px', textAlign: 'center', color: 'var(--text-dim)', fontSize: 11 }}>
            No HIGH/EXTREME alerts<br />in the last 24 hours
          </div>
        ) : (
          alerts.map((alert, i) => (
            <AlertRow
              key={`${alert.event_id}-${i}`}
              alert={alert}
              selected={selectedId === alert.event_id}
              onSelect={() => onSelect(alert.event_id)}
            />
          ))
        )}
      </div>
    </aside>
  );
}

function AlertRow({ alert, selected, onSelect }: { alert: Alert; selected: boolean; onSelect: () => void }) {
  const time = new Date(alert.timestamp);
  const timeStr = time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  const isHigh = alert.risk_level === 'HIGH' || alert.risk_level === 'EXTREME';

  return (
    <div
      onClick={onSelect}
      style={{
        padding: '10px 14px',
        borderBottom: '1px solid var(--border-lite)',
        cursor: 'pointer',
        background: selected
          ? 'var(--bg-hover)'
          : isHigh && !selected
          ? '#ef444408'
          : 'transparent',
        borderLeft: selected
          ? '2px solid var(--cyan)'
          : isHigh
          ? '2px solid var(--extreme)'
          : '2px solid transparent',
        transition: 'background 0.1s',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
        <span>{RISK_ICONS[alert.risk_level] ?? '⚪'}</span>
        <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.06em', color: getRiskColor(alert.risk_level) }}>
          {alert.risk_level}
        </span>
        {alert.simulated && (
          <span style={{ fontSize: 9, color: 'var(--cyan)', marginLeft: 'auto' }}>DEMO</span>
        )}
        <span style={{ fontSize: 9, color: 'var(--text-dim)', marginLeft: alert.simulated ? 0 : 'auto' }}>{timeStr}</span>
      </div>

      <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text)', marginBottom: 2 }}>
        {formatClassification(alert.classification)}
      </div>

      <div style={{ fontSize: 10, color: 'var(--text-muted)', lineHeight: 1.4 }}>
        {alert.summary.slice(0, 80)}{alert.summary.length > 80 ? '…' : ''}
      </div>

      <div style={{ display: 'flex', gap: 10, marginTop: 4, fontSize: 10, color: 'var(--text-dim)' }}>
        <span>Risk {alert.risk_score.toFixed(0)}</span>
        {alert.frp && <span>FRP {alert.frp.toFixed(0)} MW</span>}
        <span>#{alert.event_id}</span>
      </div>
    </div>
  );
}

function getRiskColor(level: string) {
  const m: Record<string, string> = {
    LOW: 'var(--low)', MODERATE: 'var(--mod)', HIGH: 'var(--high)', EXTREME: 'var(--extreme)',
  };
  return m[level] ?? 'var(--text)';
}

function formatClassification(cls: string) {
  return cls.replace(/_/g, ' ');
}
