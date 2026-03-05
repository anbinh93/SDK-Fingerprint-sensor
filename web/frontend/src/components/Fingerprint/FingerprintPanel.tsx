import { useState, useEffect, useRef, useCallback } from 'react';
import { FingerprintCanvas } from './FingerprintCanvas';
import { api } from '../../services/api';
import type { FingerprintStatus, FingerprintImage, SSHCredentials } from '../../types';
import './FingerprintPanel.css';

interface FingerprintPanelProps {
  sshCredentials: SSHCredentials | null;
  sshConnected: boolean;
}

const LED_COLORS = {
  off: 0,
  red: 1,
  green: 2,
  blue: 4,
  white: 7,
};

export function FingerprintPanel({ sshCredentials, sshConnected }: FingerprintPanelProps) {
  const [status, setStatus] = useState<FingerprintStatus | null>(null);
  const [connected, setConnected] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [currentImage, setCurrentImage] = useState<FingerprintImage | null>(null);
  const [fps, setFps] = useState(5);
  const [actualFps, setActualFps] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const frameCountRef = useRef(0);
  const lastFpsUpdateRef = useRef(Date.now());

  // Connect to fingerprint service
  const connectFingerprint = useCallback(async () => {
    if (!sshCredentials) {
      setError('SSH credentials not available');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const result = await api.fingerprint.connect(sshCredentials);
      if (result.success) {
        setConnected(true);
        // Fetch status
        const statusResult = await api.fingerprint.getStatus();
        setStatus(statusResult);
      } else {
        setError(result.error || 'Connection failed');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Connection failed');
    } finally {
      setIsLoading(false);
    }
  }, [sshCredentials]);

  // Disconnect from fingerprint service
  const disconnectFingerprint = useCallback(async () => {
    stopStreaming();
    await api.fingerprint.disconnect();
    setConnected(false);
    setStatus(null);
    setCurrentImage(null);
  }, []);

  // Start WebSocket streaming
  const startStreaming = useCallback(() => {
    if (wsRef.current) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${window.location.host}/api/fingerprint/ws/stream`);

    ws.onopen = () => {
      ws.send(JSON.stringify({ type: 'start', fps }));
      setStreaming(true);
      frameCountRef.current = 0;
      lastFpsUpdateRef.current = Date.now();
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);

        if (msg.type === 'image') {
          setCurrentImage({
            data: msg.data,
            width: msg.width,
            height: msg.height,
            quality: msg.quality,
            has_finger: msg.has_finger,
          });

          // Calculate actual FPS
          frameCountRef.current++;
          const now = Date.now();
          const elapsed = now - lastFpsUpdateRef.current;
          if (elapsed >= 1000) {
            setActualFps(Math.round(frameCountRef.current * 1000 / elapsed));
            frameCountRef.current = 0;
            lastFpsUpdateRef.current = now;
          }
        } else if (msg.type === 'error') {
          setError(msg.message);
          setStreaming(false);
          // Reset connected state if connection lost
          if (msg.message.includes('Not connected')) {
            setConnected(false);
          }
        }
      } catch (e) {
        console.error('Failed to parse message:', e);
      }
    };

    ws.onerror = () => {
      setError('WebSocket error');
      setStreaming(false);
    };

    ws.onclose = () => {
      setStreaming(false);
      wsRef.current = null;
    };

    wsRef.current = ws;
  }, [fps]);

  // Stop streaming
  const stopStreaming = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.send(JSON.stringify({ type: 'stop' }));
      wsRef.current.close();
      wsRef.current = null;
    }
    setStreaming(false);
    setActualFps(0);
  }, []);

  // Capture single image
  const captureOnce = useCallback(async () => {
    setIsLoading(true);
    try {
      const result = await api.fingerprint.capture();
      if (result.success && result.image_base64) {
        setCurrentImage({
          data: result.image_base64,
          width: result.width,
          height: result.height,
          quality: result.quality,
          has_finger: result.has_finger,
        });
      } else {
        setError(result.error || 'Capture failed');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Capture failed');
    } finally {
      setIsLoading(false);
    }
  }, []);

  // LED control
  const controlLED = useCallback(async (color: number) => {
    try {
      await api.fingerprint.led(color);
    } catch (e) {
      console.error('LED control failed:', e);
    }
  }, []);

  // Match fingerprint
  const matchFingerprint = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      await api.fingerprint.led(LED_COLORS.blue);
      const result = await api.fingerprint.match();
      if (result.matched) {
        setError(null);
        alert(`Matched! User ID: ${result.user_id}`);
        await api.fingerprint.led(LED_COLORS.green);
      } else {
        setError('No match found');
        await api.fingerprint.led(LED_COLORS.red);
      }
      setTimeout(() => api.fingerprint.led(LED_COLORS.off), 1000);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Match failed');
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Add fingerprint
  const addFingerprint = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      await api.fingerprint.led(LED_COLORS.green);
      const result = await api.fingerprint.add();
      if (result.success) {
        alert(`Added! User ID: ${result.user_id}`);
        // Refresh status
        const statusResult = await api.fingerprint.getStatus();
        setStatus(statusResult);
      } else {
        setError(result.error || 'Add failed');
        await api.fingerprint.led(LED_COLORS.red);
      }
      setTimeout(() => api.fingerprint.led(LED_COLORS.off), 1000);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Add failed');
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  // Auto-connect when SSH is connected
  useEffect(() => {
    if (sshConnected && sshCredentials && !connected) {
      connectFingerprint();
    }
  }, [sshConnected, sshCredentials, connected, connectFingerprint]);

  return (
    <div className="fingerprint-panel">
      <div className="panel-header">
        <h2>Fingerprint Sensor</h2>
        <div className={`status-indicator ${connected && status?.connected ? 'connected' : 'disconnected'}`}>
          {connected && status?.connected ? 'Sensor Ready' : connected ? 'Sensor Not Found' : 'Disconnected'}
        </div>
      </div>

      {error && (
        <div className="error-message">
          {error}
          <button onClick={() => setError(null)}>Dismiss</button>
        </div>
      )}

      {!sshConnected ? (
        <div className="info-message">
          Connect to Jetson Nano via SSH first to use the fingerprint sensor.
        </div>
      ) : !connected ? (
        <div className="connect-section">
          <button
            className="primary"
            onClick={connectFingerprint}
            disabled={isLoading}
          >
            {isLoading ? 'Connecting...' : 'Connect to Sensor'}
          </button>
        </div>
      ) : (
        <>
          {status && (
            <div className="status-info">
              <div className="status-item">
                <span className="label">Registered Users:</span>
                <span className="value">{status.user_count}</span>
              </div>
              <div className="status-item">
                <span className="label">Compare Level:</span>
                <span className="value">{status.compare_level}/9</span>
              </div>
            </div>
          )}

          <div className="canvas-section">
            <FingerprintCanvas
              imageData={currentImage?.data || null}
              width={currentImage?.width}
              height={currentImage?.height}
              quality={currentImage?.quality || 0}
              hasFinger={currentImage?.has_finger || false}
              size={280}
            />

            {streaming && (
              <div className="fps-counter">
                {actualFps} FPS
              </div>
            )}
          </div>

          <div className="controls-section">
            <div className="control-group">
              <label>Stream FPS:</label>
              <input
                type="range"
                min="1"
                max="15"
                value={fps}
                onChange={(e) => setFps(parseInt(e.target.value))}
                disabled={streaming}
              />
              <span>{fps}</span>
            </div>

            <div className="button-row">
              {streaming ? (
                <button className="secondary" onClick={stopStreaming}>
                  Stop Stream
                </button>
              ) : (
                <button className="primary" onClick={startStreaming} disabled={isLoading}>
                  Start Stream
                </button>
              )}
              <button className="secondary" onClick={captureOnce} disabled={isLoading || streaming}>
                Capture Once
              </button>
            </div>

            <div className="button-row">
              <button className="secondary" onClick={matchFingerprint} disabled={isLoading || streaming}>
                Match
              </button>
              <button className="secondary" onClick={addFingerprint} disabled={isLoading || streaming}>
                Enroll
              </button>
            </div>

            <div className="led-controls">
              <label>LED:</label>
              <div className="led-buttons">
                <button className="led-btn off" onClick={() => controlLED(LED_COLORS.off)}>Off</button>
                <button className="led-btn red" onClick={() => controlLED(LED_COLORS.red)}>R</button>
                <button className="led-btn green" onClick={() => controlLED(LED_COLORS.green)}>G</button>
                <button className="led-btn blue" onClick={() => controlLED(LED_COLORS.blue)}>B</button>
                <button className="led-btn white" onClick={() => controlLED(LED_COLORS.white)}>W</button>
              </div>
            </div>
          </div>

          <button
            className="disconnect-btn"
            onClick={disconnectFingerprint}
          >
            Disconnect Sensor
          </button>
        </>
      )}
    </div>
  );
}
