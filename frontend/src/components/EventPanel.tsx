import { useEffect, useState } from 'react';
import { api } from '../api';
import type { FullAnalysis } from '../types';

interface Props {
  eventId: number | null;
  onClose: () => void;
}

export function EventPanel({ eventId, onClose }: Props) {
  const [data, setData] = useState<FullAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!eventId) { setData(null); return; }
    setLoading(true);
    setError(null);

    api.analysis(eventId)
      .then(setData)
      .catch(async () => {
        // Analysis may not exist yet — load context/history separately
        try {
          const [ev, ctx, hist] = await Promise.all([
            api.event(eventId),
            api.context(eventId),
            api.history(eventId),
          ]);
          setData({ event: ev, context: ctx, history: hist, analysis: null as unknown as FullAnalysis['analysis'] });
        } catch (e2) {
          setError(String(e2));
        }
      })
      .finally(() => setLoading(false));
  }, [eventId]);

  if (!eventId) {
    return (
      <aside style={panelStyle}>
        <div style={{ padding: '16px', textAlign: 'center', color: 'var(--text-dim)', marginTop: 60 }}>
          <div style={{ fontSize: 28, marginBottom: 10 }}>📍</div>
          <div style={{ fontSize: 11, lineHeight: 1.6 }}>
            Click a map marker or<br />select an alert to investigate
          </div>
        </div>
      </aside>
    );
  }

  return (
    <aside style={panelStyle}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 14px', borderBottom: '1px solid var(--border)' }}>
        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.1em', color: 'var(--text-muted)' }}>
          EVENT INTELLIGENCE
        </span>
        <button className="btn-ghost" onClick={onClose} style={{ padding: '2px 8px', fontSize: 14 }}>✕</button>
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: '0 14px 14px' }}>
        {loading && (
          <div style={{ textAlign: 'center', padding: 40 }}>
            <div className="spinner" style={{ width: 20, height: 20, margin: '0 auto 10px' }} />
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Loading analysis…</div>
          </div>
        )}
        {error && <div style={{ color: 'var(--extreme)', padding: 12, fontSize: 11 }}>{error}</div>}
        {!loading && !error && data && <PanelContent data={data} />}
      </div>
    </aside>
  );
}

function PanelContent({ data }: { data: FullAnalysis }) {
  const { event, context, history, analysis } = data;
  const isDemo = event.source === 'DEMO';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14, paddingTop: 12 }}>
      {/* Source badge */}
      <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
        <span className={`badge badge-${isDemo ? 'DEMO' : 'LIVE'}`}>
          {isDemo ? '⚡ DEMO' : '🛰 LIVE · NASA FIRMS'}
        </span>
        {analysis && (
          <span className={`badge badge-${analysis.risk_level}`}>
            {analysis.risk_level}
          </span>
        )}
      </div>

      <Section title="EVENT">
        <Row label="Event ID" value={`#${event.id}`} />
        <Row label="Date" value={`${event.acq_date} ${event.acq_time?.slice(0,2)}:${event.acq_time?.slice(2)} UTC`} />
        <Row label="Satellite" value={event.satellite ?? '—'} />
        <Row label="Source" value={event.source} />
        <Row label="Coordinates" value={`${event.latitude.toFixed(4)}°, ${event.longitude.toFixed(4)}°`} />
      </Section>

      <Section title="THERMAL MEASUREMENTS">
        <Row label="FRP" value={event.frp != null ? `${event.frp} MW` : '—'} highlight />
        <Row label="Brightness" value={event.brightness != null ? `${event.brightness} K` : '—'} />
        <Row label="Confidence" value={event.confidence ?? '—'} />
        <Row label="Day/Night" value={event.daynight === 'D' ? '☀ Daytime' : event.daynight === 'N' ? '🌙 Nighttime' : '—'} />
      </Section>

      {context && (
        <Section title="LOCATION CONTEXT">
          <Row label="Land Cover" value={context.land_cover} highlight />
          <Row label="Nearby Facilities" value={context.nearby_facilities.length} />
          {context.nearest_facility && (
            <>
              <Row label="Nearest Facility" value={context.nearest_facility.name} />
              <Row label="Type" value={context.nearest_facility.type} />
              <Row label="Distance" value={`${context.nearest_facility_km?.toFixed(2)} km`} highlight />
            </>
          )}
          {context.nearby_facilities.slice(0, 3).map((f, i) => (
            <Row key={i} label={`  ${f.type}`} value={`${f.name} — ${f.distance_km.toFixed(1)} km`} />
          ))}
        </Section>
      )}

      {history && (
        <Section title="HISTORICAL ACTIVITY">
          <Row label="Has History" value={history.has_history ? 'Yes' : 'No — first detection'} />
          {history.has_history && (
            <>
              <Row label="Detections (7d / 30d / 90d)" value={`${history.detections_7d} / ${history.detections_30d} / ${history.detections_90d}`} />
              <Row label="Active Days (90d)" value={history.active_days} />
              <Row label="Baseline FRP" value={history.historical_baseline != null ? `${history.historical_baseline} MW` : 'N/A'} />
              <Row
                label="Anomaly Ratio"
                value={history.anomaly_ratio != null ? `${history.anomaly_ratio.toFixed(2)}× baseline` : 'N/A'}
                highlight={!!history.anomaly_ratio && history.anomaly_ratio > 2}
              />
              <Row label="Persistence Score" value={`${(history.persistence_score * 100).toFixed(0)}%`} />
            </>
          )}
        </Section>
      )}

      {analysis && (
        <>
          <Section title="CLASSIFICATION">
            <Row label="Type" value={analysis.classification} highlight />
            <Row label="Confidence" value={`${(analysis.confidence * 100).toFixed(0)}%`} />
          </Section>

          <Section title="RISK ASSESSMENT">
            <Row label="Risk Level" value={analysis.risk_level} highlight />
            <RiskBar score={analysis.risk_score} level={analysis.risk_level} />
            <Row label="Risk Score" value={`${analysis.risk_score.toFixed(1)} / 100`} />
            <Row label="Industrial Context" value={`${(analysis.industrial_context_score * 100).toFixed(0)}%`} />
          </Section>

          <Section title="AI INVESTIGATION">
            <div style={{ marginBottom: 6, display: 'flex', gap: 6, alignItems: 'center' }}>
              <span style={{ fontSize: 10, color: 'var(--text-dim)' }}>ENGINE</span>
              <span style={{ fontSize: 10, color: 'var(--cyan)', fontWeight: 700 }}>
                {analysis.ai_mode === 'GROQ' ? '🤖 GROQ LLaMA' : '⚙ FALLBACK'}
              </span>
            </div>

            {analysis.summary && (
              <div style={{ padding: '8px 10px', background: 'var(--bg)', borderRadius: 6, border: '1px solid var(--border-lite)', fontSize: 12, lineHeight: 1.6, marginBottom: 8 }}>
                {analysis.summary}
              </div>
            )}

            {analysis.reasoning && (
              <div>
                <div style={{ fontSize: 10, color: 'var(--text-dim)', marginBottom: 4 }}>REASONING</div>
                {analysis.reasoning.split('\n').filter(Boolean).map((line, i) => (
                  <div key={i} style={{ fontSize: 11, color: 'var(--text-muted)', padding: '3px 0', borderBottom: '1px solid var(--border-lite)' }}>
                    › {line}
                  </div>
                ))}
              </div>
            )}

            {analysis.recommended_action && (
              <div style={{ marginTop: 10, padding: '8px 10px', background: '#00d4d808', border: '1px solid var(--cyan-border)', borderRadius: 6 }}>
                <div style={{ fontSize: 10, color: 'var(--cyan)', marginBottom: 4, fontWeight: 700 }}>RECOMMENDED ACTION</div>
                <div style={{ fontSize: 11, lineHeight: 1.6 }}>{analysis.recommended_action}</div>
              </div>
            )}
          </Section>
        </>
      )}

      {!analysis && (
        <div style={{ padding: '10px', background: 'var(--bg)', borderRadius: 6, fontSize: 11, color: 'var(--text-muted)', textAlign: 'center' }}>
          Analysis not yet available for this event.
        </div>
      )}
    </div>
  );
}

// ── Sub-components ───────────────────────────────────────────────────────────
function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h2 style={{ marginBottom: 8, paddingBottom: 4, borderBottom: '1px solid var(--border-lite)' }}>{title}</h2>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>{children}</div>
    </div>
  );
}

function Row({ label, value, highlight }: { label: string; value: string | number | boolean; highlight?: boolean }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, fontSize: 11, alignItems: 'baseline' }}>
      <span style={{ color: 'var(--text-dim)', flexShrink: 0 }}>{label}</span>
      <span style={{ color: highlight ? 'var(--cyan)' : 'var(--text)', textAlign: 'right', fontWeight: highlight ? 600 : 400 }}>
        {String(value)}
      </span>
    </div>
  );
}

function RiskBar({ score, level }: { score: number; level: string }) {
  const colors: Record<string, string> = { LOW: 'var(--low)', MODERATE: 'var(--mod)', HIGH: 'var(--high)', EXTREME: 'var(--extreme)' };
  const color = colors[level] ?? 'var(--cyan)';
  return (
    <div style={{ height: 5, background: 'var(--bg)', borderRadius: 3, overflow: 'hidden', marginBottom: 4 }}>
      <div style={{ height: '100%', width: `${Math.min(score, 100)}%`, background: color, borderRadius: 3, transition: 'width 0.4s' }} />
    </div>
  );
}

const panelStyle: React.CSSProperties = {
  width: 300,
  minWidth: 300,
  background: 'var(--bg-panel)',
  borderLeft: '1px solid var(--border)',
  display: 'flex',
  flexDirection: 'column',
  overflow: 'hidden',
};
