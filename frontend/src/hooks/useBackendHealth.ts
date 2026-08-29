import { useEffect, useState } from "react";

import { getHealth, type HealthResponse } from "../api/health";

type BackendHealthState = {
  loading: boolean;
  online: boolean;
  health: HealthResponse | null;
  error: string | null;
};

export function useBackendHealth(): BackendHealthState {
  const [state, setState] = useState<BackendHealthState>({
    loading: true,
    online: false,
    health: null,
    error: null,
  });

  useEffect(() => {
    const controller = new AbortController();

    async function checkHealth() {
      try {
        const health = await getHealth(controller.signal);
        setState({
          loading: false,
          online: health.status === "ok",
          health,
          error: health.status === "ok" ? null : "Backend is reachable but degraded.",
        });
      } catch (error) {
        setState({
          loading: false,
          online: false,
          health: null,
          error: error instanceof Error ? error.message : "Backend is unreachable.",
        });
      }
    }

    void checkHealth();
    const interval = window.setInterval(checkHealth, 10000);

    return () => {
      controller.abort();
      window.clearInterval(interval);
    };
  }, []);

  return state;
}
