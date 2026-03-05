/**
 * WebSocket hook for terminal communication.
 */

import { useCallback, useRef, useState } from 'react';
import type {
  ConnectionStatus,
  SSHCredentials,
  TerminalSize,
  WSMessage,
} from '../types';

interface UseWebSocketOptions {
  onData: (data: Uint8Array) => void;
  onConnect?: (sessionId: string) => void;
  onDisconnect?: () => void;
  onError?: (error: string) => void;
}

interface UseWebSocketReturn {
  status: ConnectionStatus;
  sessionId: string | null;
  error: string | null;
  connect: (credentials: SSHCredentials, size: TerminalSize) => void;
  disconnect: () => void;
  send: (data: string | Uint8Array) => void;
  resize: (size: TerminalSize) => void;
}

// Create encoder once for performance
const textEncoder = new TextEncoder();

const CONNECTION_TIMEOUT_MS = 10000;

export function useWebSocket(options: UseWebSocketOptions): UseWebSocketReturn {
  const { onData, onConnect, onDisconnect, onError } = options;

  const [status, setStatus] = useState<ConnectionStatus>('disconnected');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const errorStateRef = useRef(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearConnectionTimeout = () => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  };

  const connect = useCallback(
    (credentials: SSHCredentials, size: TerminalSize) => {
      if (wsRef.current) {
        wsRef.current.close();
      }

      setStatus('connecting');
      setError(null);
      errorStateRef.current = false;

      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/ws/terminal`;

      const ws = new WebSocket(wsUrl);
      ws.binaryType = 'arraybuffer';
      wsRef.current = ws;

      // Connection timeout
      timeoutRef.current = setTimeout(() => {
        if (ws.readyState !== WebSocket.OPEN) {
          ws.close();
          errorStateRef.current = true;
          setError('Connection timeout');
          setStatus('error');
          onError?.('Connection timeout');
        }
      }, CONNECTION_TIMEOUT_MS);

      ws.onopen = () => {
        clearConnectionTimeout();
        // Send connect message with credentials
        const connectMsg: WSMessage = {
          type: 'connect',
          credentials,
          size,
        };
        ws.send(JSON.stringify(connectMsg));
      };

      ws.onmessage = (event) => {
        if (event.data instanceof ArrayBuffer) {
          // Binary data from terminal
          onData(new Uint8Array(event.data));
        } else {
          // JSON message
          try {
            const msg: WSMessage = JSON.parse(event.data);
            handleMessage(msg);
          } catch {
            console.error('Invalid JSON message:', event.data);
          }
        }
      };

      ws.onerror = () => {
        clearConnectionTimeout();
        errorStateRef.current = true;
        setError('WebSocket connection error');
        setStatus('error');
        onError?.('WebSocket connection error');
      };

      ws.onclose = () => {
        clearConnectionTimeout();
        if (!errorStateRef.current) {
          setStatus('disconnected');
        }
        setSessionId(null);
        wsRef.current = null;
        onDisconnect?.();
      };

      const handleMessage = (msg: WSMessage) => {
        switch (msg.type) {
          case 'connected':
            errorStateRef.current = false;
            setStatus('connected');
            setSessionId(msg.sessionId);
            onConnect?.(msg.sessionId);
            break;

          case 'error':
            errorStateRef.current = true;
            setError(msg.message);
            setStatus('error');
            onError?.(msg.message);
            break;

          case 'disconnected':
            setStatus('disconnected');
            setSessionId(null);
            onDisconnect?.();
            break;
        }
      };
    },
    [onData, onConnect, onDisconnect, onError],
  );

  const disconnect = useCallback(() => {
    clearConnectionTimeout();
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setStatus('disconnected');
    setSessionId(null);
  }, []);

  const send = useCallback((data: string | Uint8Array) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      if (typeof data === 'string') {
        // Send as binary for terminal input
        wsRef.current.send(textEncoder.encode(data));
      } else {
        wsRef.current.send(data);
      }
    }
  }, []);

  const resize = useCallback((size: TerminalSize) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      const msg: WSMessage = {
        type: 'resize',
        rows: size.rows,
        cols: size.cols,
      };
      wsRef.current.send(JSON.stringify(msg));
    }
  }, []);

  return {
    status,
    sessionId,
    error,
    connect,
    disconnect,
    send,
    resize,
  };
}
