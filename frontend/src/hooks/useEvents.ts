import { useEffect, useState } from "react";

import { listLatestEvents } from "../api/events";
import type { ThermalEventSummary } from "../types/event";

export function useEvents() {
  const [events, setEvents] = useState<ThermalEventSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    listLatestEvents(controller.signal)
      .then(setEvents)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Failed to load events"));
    return () => controller.abort();
  }, []);

  return { events, error };
}
