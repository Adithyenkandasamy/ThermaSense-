import { useCallback, useEffect, useRef, useState } from 'react';
import { WS_URL } from './api';
import type { WsMessage } from './types';

export type WsStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

interface UseWebSocketReturn {
  status: WsStatus;
  lastMessage: WsMessage | null;
  send: (msg: string) => void;
}

const PING_INTERVAL_MS = 20_000;
const RECONNECT_DELAY_MS = 3_000;
const MAX_RECONNECT_DELAY_MS = 30_000;

export function useWebSocket(
  onMessage: (msg: WsMessage) => void
): UseWebSocketReturn {
  const [status, setStatus] = useState<WsStatus>('connecting');
  const [lastMessage, setLastMessage] = useState<WsMessage | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const pingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const reconnectDelayRef = useRef(RECONNECT_DELAY_MS);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const unmountedRef = useRef(false);
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  const connect = useCallback(() => {
    if (unmountedRef.current) return;
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return;

    setStatus('connecting');
    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      if (unmountedRef.current) { ws.close(); return; }
      setStatus('connected');
      reconnectDelayRef.current = RECONNECT_DELAY_MS;

      pingRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) ws.send('ping');
      }, PING_INTERVAL_MS);
    };

    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data) as WsMessage;
        if (msg.type === 'PONG') return; // silent
        setLastMessage(msg);
        onMessageRef.current(msg);
      } catch { /* ignore malformed */ }
    };

    ws.onerror = () => setStatus('error');

    ws.onclose = () => {
      if (pingRef.current) { clearInterval(pingRef.current); pingRef.current = null; }
      if (unmountedRef.current) return;
      setStatus('disconnected');
      const delay = Math.min(reconnectDelayRef.current, MAX_RECONNECT_DELAY_MS);
      reconnectDelayRef.current = delay * 1.5;
      reconnectTimerRef.current = setTimeout(connect, delay);
    };
  }, []);

  useEffect(() => {
    unmountedRef.current = false;
    connect();
    return () => {
      unmountedRef.current = true;
      if (pingRef.current) clearInterval(pingRef.current);
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const send = useCallback((msg: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) wsRef.current.send(msg);
  }, []);

  return { status, lastMessage, send };
}
