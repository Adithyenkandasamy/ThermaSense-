import { useEffect, useState } from "react";

import { API_BASE_URL } from "../api/client";

export function useWebSocket(path = "/api/v1/ws/events") {
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const wsBase = API_BASE_URL.replace(/^http/, "ws");
    const socket = new WebSocket(`${wsBase}${path}`);
    socket.onopen = () => setConnected(true);
    socket.onclose = () => setConnected(false);
    socket.onerror = () => setConnected(false);
    return () => socket.close();
  }, [path]);

  return { connected };
}
