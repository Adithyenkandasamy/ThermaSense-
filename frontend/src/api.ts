import type {
  Alert,
  EventContext,
  EventHistory,
  FullAnalysis,
  SimulateRequest,
  SimulateResponse,
  Stats,
  ThermalEventDetail,
  ThermalEventSummary,
} from './types';

const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';
export const WS_URL = (import.meta.env.VITE_WS_URL ?? 'ws://localhost:8000') + '/api/v1/ws/events';

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}`);
  return res.json() as Promise<T>;
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body != null ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`POST ${path} → ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// ── Events ───────────────────────────────────────────────────────────────────
export const api = {
  health: () => get<{ status: string; checks: Record<string, unknown> }>('/health'),

  events: (days = 1, page = 1, perPage = 200) =>
    get<{ total: number; items: ThermalEventSummary[] }>(
      `/api/v1/events?days=${days}&page=${page}&per_page=${perPage}`
    ),

  latest: (limit = 200) =>
    get<ThermalEventSummary[]>(`/api/v1/events/latest?limit=${limit}`),

  stats: () => get<Stats>('/api/v1/events/stats'),

  event: (id: number) => get<ThermalEventDetail>(`/api/v1/events/${id}`),

  context: (id: number, radius = 10) =>
    get<EventContext>(`/api/v1/events/${id}/context?radius_km=${radius}`),

  history: (id: number) => get<EventHistory>(`/api/v1/events/${id}/history`),

  analysis: (id: number) => get<FullAnalysis>(`/api/v1/events/${id}/analysis`),

  analyze: (id: number) => post<{ event_id: number; classification: string; risk_level: string; risk_score: number }>(
    `/api/v1/events/${id}/analyze`
  ),

  // ── Alerts ─────────────────────────────────────────────────────────────────
  alerts: () => get<Alert[]>('/api/v1/alerts/recent?hours=24'),

  // ── Demo simulation ────────────────────────────────────────────────────────
  simulate: (req: SimulateRequest) => post<SimulateResponse>('/api/v1/demo/simulate', req),
};
