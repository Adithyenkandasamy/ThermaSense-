import { useState } from 'react';
import { api } from '../api';
import type { Scenario, SimulateResponse } from '../types';

interface Props {
  onClose: () => void;
  onComplete: (eventId: number) => void;
}

const SCENARIOS: { value: Scenario; label: string; description: string }[] = [
  { value: 'industrial',   label: 'Industrial Thermal',    description: 'Near refinery — expects INDUSTRIAL_THERMAL' },
  { value: 'extreme',      label: 'Extreme Industrial',    description: 'Very high FRP near facility — expects EXTREME risk' },
  { value: 'wildfire',     label: 'Wildfire',              description: 'Remote high FRP — expects WILDFIRE' },
  { value: 'agricultural', label: 'Agricultural Burning',  description: 'Low FRP open land — expects AGRICULTURAL_BURNING' },
  { value: 'mining',       label: 'Mining Activity',       description: 'Near quarry — expects MINING_ACTIVITY' },
  { value: 'persistent',   label: 'Persistent Industrial', description: 'Near power plant — moderate persistent signature' },
];

const RISK_COLORS: Record<string, string> = {
  LOW: 'var(--low)', MODERATE: 'var(--mod)', HIGH: 'var(--high)', EXTREME: 'var(--extreme)',
};

type Phase = 'idle' | 'creating' | 'analyzing' | 'done' | 'error';

export function SimulateModal({ onClose, onComplete }: Props) {
  const [scenario, setScenario] = useState<Scenario>('industrial');
  const [frp, setFrp] = useState('185');
  const [brightness, setBrightness] = useState('342');
  const [confidence, setConfidence] = useState('high');
  const [phase, setPhase] = useState<Phase>('idle');
  const [result, setResult] = useState<SimulateResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState('');

  const selectedScenario = SCENARIOS.find(s => s.value === scenario)!;

  async function run() {
    setPhase('creating');
    setResult(null);
    setErrorMsg('');
    try {
      setPhase('analyzing');
      const res = await api.simulate({
        scenario,
        frp: frp ? Number(frp) : undefined,
        brightness: brightness ? Number(brightness) : undefined,
        confidence: confidence || undefined,
      });
      setResult(res);
      setPhase('done');
    } catch (e) {
      setErrorMsg(String(e));
      setPhase('error');
    }
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 1000,
      background: '#000000cc',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <div style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-lg)',
        width: 480,
        maxHeight: '90vh',
        overflow: 'auto',
        boxShadow: '0 24px 64px #000a',
      }}>
        {/* Header */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '16px 20px',
          borderBottom: '1px solid var(--border)',
        }}>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, letterSpacing: '0.08em' }}>⚡ SIMULATE THERMAL EVENT</div>
            <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>
              Synthetic event — same pipeline as real FIRMS data
            </div>
          </div>
          <button className="btn-ghost" onClick={onClose} style={{ padding: '2px 8px', fontSize: 14 }}>✕</button>
        </div>

        <div style={{ padding: '20px' }}>
          {phase === 'idle' || phase === 'error' ? (
            <>
              {/* Scenario picker */}
              <div style={{ marginBottom: 16 }}>
                <label>SCENARIO</label>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 4 }}>
                  {SCENARIOS.map(s => (
                    <label key={s.value} style={{
                      display: 'flex', alignItems: 'flex-start', gap: 10,
                      padding: '8px 12px',
                      background: scenario === s.value ? 'var(--cyan-dim)' : 'var(--bg)',
                      border: `1px solid ${scenario === s.value ? 'var(--cyan-border)' : 'var(--border)'}`,
                      borderRadius: 6, cursor: 'pointer',
                    }}>
                      <input
                        type="radio"
                        name="scenario"
                        value={s.value}
                        checked={scenario === s.value}
                        onChange={() => setScenario(s.value)}
                        style={{ marginTop: 2 }}
                      />
                      <div>
                        <div style={{ fontSize: 12, fontWeight: 600, color: scenario === s.value ? 'var(--cyan)' : 'var(--text)' }}>
                          {s.label}
                        </div>
                        <div style={{ fontSize: 10, color: 'var(--text-dim)' }}>{s.description}</div>
                      </div>
                    </label>
                  ))}
                </div>
              </div>

              {/* Parameters */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 16 }}>
                <div>
                  <label>FRP (MW)</label>
                  <input type="number" value={frp} onChange={e => setFrp(e.target.value)} placeholder="auto" />
                </div>
                <div>
                  <label>BRIGHTNESS (K)</label>
                  <input type="number" value={brightness} onChange={e => setBrightness(e.target.value)} placeholder="auto" />
                </div>
                <div style={{ gridColumn: '1 / -1' }}>
                  <label>CONFIDENCE</label>
                  <select value={confidence} onChange={e => setConfidence(e.target.value)}>
                    <option value="high">High</option>
                    <option value="nominal">Nominal</option>
                    <option value="low">Low</option>
                  </select>
                </div>
              </div>

              <div style={{ padding: '8px 12px', background: 'var(--bg)', borderRadius: 6, fontSize: 10, color: 'var(--text-dim)', marginBottom: 16 }}>
                📍 Location uses preset coordinates for <b style={{ color: 'var(--text-muted)' }}>{selectedScenario.label}</b>.
                The existing classification engine will determine the final result.
              </div>

              {phase === 'error' && (
                <div style={{ padding: '8px 12px', background: '#ef444415', border: '1px solid #ef444440', borderRadius: 6, color: 'var(--extreme)', fontSize: 11, marginBottom: 12 }}>
                  {errorMsg}
                </div>
              )}

              <button className="btn-primary" style={{ width: '100%', padding: '10px', fontSize: 13 }} onClick={run}>
                SIMULATE THERMAL EVENT
              </button>
            </>
          ) : phase === 'creating' || phase === 'analyzing' ? (
            <div style={{ textAlign: 'center', padding: '40px 20px' }}>
              <div className="spinner" style={{ width: 28, height: 28, margin: '0 auto 16px', borderWidth: 3 }} />
              <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 6 }}>
                {phase === 'creating' ? 'Creating thermal event…' : 'Analyzing thermal event…'}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.6 }}>
                Running full pipeline:<br />
                context · facilities · history · classification · risk · AI
              </div>
            </div>
          ) : result ? (
            <ResultView result={result} onClose={onClose} onInvestigate={() => onComplete(result.event_id)} />
          ) : null}
        </div>
      </div>
    </div>
  );
}

function ResultView({ result, onClose, onInvestigate }: { result: SimulateResponse; onClose: () => void; onInvestigate: () => void }) {
  const riskColor = RISK_COLORS[result.risk_level] ?? 'var(--text)';
  const isAlert = result.alert_broadcast;

  return (
    <div>
      {/* Alert banner */}
      {isAlert && (
        <div style={{
          padding: '12px 14px',
          background: `${riskColor}15`,
          border: `1px solid ${riskColor}40`,
          borderRadius: 8,
          marginBottom: 16,
          animation: 'alertPulse 1s ease-out',
        }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: riskColor }}>
            🚨 {result.risk_level}-RISK THERMAL EVENT
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
            Alert broadcast to all connected clients
          </div>
        </div>
      )}

      {/* Result grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 16 }}>
        <ResultCard label="CLASSIFICATION" value={result.classification.replace(/_/g, ' ')} color="var(--cyan)" />
        <ResultCard label="RISK LEVEL" value={result.risk_level} color={riskColor} />
        <ResultCard label="RISK SCORE" value={`${result.risk_score.toFixed(1)} / 100`} />
        <ResultCard label="AI MODE" value={result.ai_mode} />
        <ResultCard label="EVENT ID" value={`#${result.event_id}`} />
        <ResultCard label="SOURCE" value="DEMO · SIMULATED" color="var(--cyan)" />
      </div>

      <div style={{ padding: '8px 12px', background: 'var(--bg)', borderRadius: 6, fontSize: 11, color: 'var(--text-muted)', marginBottom: 16, lineHeight: 1.6 }}>
        {result.message}
      </div>

      <div style={{ display: 'flex', gap: 10 }}>
        <button className="btn-primary" style={{ flex: 1, padding: '10px' }} onClick={onInvestigate}>
          VIEW FULL INVESTIGATION
        </button>
        <button className="btn-ghost" onClick={onClose}>Close</button>
      </div>

      <style>{`
        @keyframes alertPulse {
          0% { opacity: 0; transform: scale(0.97); }
          100% { opacity: 1; transform: scale(1); }
        }
      `}</style>
    </div>
  );
}

function ResultCard({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ padding: '8px 10px', background: 'var(--bg)', borderRadius: 6, border: '1px solid var(--border-lite)' }}>
      <div style={{ fontSize: 9, color: 'var(--text-dim)', marginBottom: 2, letterSpacing: '0.06em' }}>{label}</div>
      <div style={{ fontSize: 12, fontWeight: 700, color: color ?? 'var(--text)' }}>{value}</div>
    </div>
  );
}
