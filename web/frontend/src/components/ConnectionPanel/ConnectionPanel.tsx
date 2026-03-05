import { useState, useEffect, useCallback } from 'react';
import { api } from '../../services/api';
import type { SSHCredentials, USBCheckResponse, ConnectionStatus } from '../../types';
import './ConnectionPanel.css';

interface ConnectionPanelProps {
  onConnect: (credentials: SSHCredentials) => void;
  onDisconnect: () => void;
  connectionStatus: ConnectionStatus;
  error: string | null;
}

export function ConnectionPanel({
  onConnect,
  onDisconnect,
  connectionStatus,
  error,
}: ConnectionPanelProps) {
  const [usbStatus, setUsbStatus] = useState<USBCheckResponse | null>(null);
  const [isCheckingUSB, setIsCheckingUSB] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);

  const [credentials, setCredentials] = useState<SSHCredentials>({
    host: '192.168.55.1',
    port: 22,
    username: 'jetson',
    password: '',
  });

  const checkUSB = useCallback(async () => {
    setIsCheckingUSB(true);
    try {
      const status = await api.checkUSB();
      setUsbStatus(status);

      // Auto-fill host if USB-Ethernet detected
      if (status.usb_ethernet.connected && status.usb_ethernet.ip_address) {
        setCredentials((prev) => ({
          ...prev,
          host: status.usb_ethernet.ip_address!,
        }));
      }
    } catch (err) {
      console.error('USB check failed:', err);
    } finally {
      setIsCheckingUSB(false);
    }
  }, []);

  useEffect(() => {
    checkUSB();
  }, [checkUSB]);

  const testConnection = async () => {
    setIsTesting(true);
    setTestResult(null);

    try {
      const result = await api.testSSH(credentials);
      if (result.success) {
        setTestResult(`Connected! System: ${result.system_info || 'Unknown'}`);
      } else {
        setTestResult(`Failed: ${result.error}`);
      }
    } catch (err) {
      setTestResult(`Error: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setIsTesting(false);
    }
  };

  const handleConnect = () => {
    onConnect(credentials);
  };

  const isConnected = connectionStatus === 'connected';
  const isConnecting = connectionStatus === 'connecting';

  return (
    <div className="connection-panel">
      <div className="panel-header">
        <h2>Connection</h2>
        <div className={`status-indicator ${connectionStatus}`}>
          {connectionStatus}
        </div>
      </div>

      <div className="usb-status">
        <div className="section-header">
          <h3>USB Status</h3>
          <button
            className="secondary small"
            onClick={checkUSB}
            disabled={isCheckingUSB}
          >
            {isCheckingUSB ? 'Checking...' : 'Refresh'}
          </button>
        </div>

        {usbStatus && (
          <div className="status-list">
            <div className={`status-item ${usbStatus.usb_ethernet.connected ? 'connected' : ''}`}>
              <span className="status-dot" />
              <span>USB-Ethernet</span>
              {usbStatus.usb_ethernet.ip_address && (
                <span className="status-detail">{usbStatus.usb_ethernet.ip_address}</span>
              )}
            </div>
            <div className={`status-item ${usbStatus.usb_serial.connected ? 'connected' : ''}`}>
              <span className="status-dot" />
              <span>USB-Serial</span>
              {usbStatus.usb_serial.device && (
                <span className="status-detail">{usbStatus.usb_serial.device}</span>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="ssh-form">
        <h3>SSH Connection</h3>

        <div className="form-group">
          <label htmlFor="host">Host</label>
          <input
            id="host"
            type="text"
            value={credentials.host}
            onChange={(e) => setCredentials({ ...credentials, host: e.target.value })}
            placeholder="192.168.55.1"
            disabled={isConnected || isConnecting}
          />
        </div>

        <div className="form-row">
          <div className="form-group">
            <label htmlFor="username">Username</label>
            <input
              id="username"
              type="text"
              value={credentials.username}
              onChange={(e) => setCredentials({ ...credentials, username: e.target.value })}
              placeholder="jetson"
              disabled={isConnected || isConnecting}
            />
          </div>

          <div className="form-group">
            <label htmlFor="port">Port</label>
            <input
              id="port"
              type="number"
              value={credentials.port}
              onChange={(e) => setCredentials({ ...credentials, port: parseInt(e.target.value) || 22 })}
              placeholder="22"
              disabled={isConnected || isConnecting}
            />
          </div>
        </div>

        <div className="form-group">
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            value={credentials.password}
            onChange={(e) => setCredentials({ ...credentials, password: e.target.value })}
            placeholder="Password"
            disabled={isConnected || isConnecting}
          />
        </div>

        {testResult && (
          <div className={`test-result ${testResult.startsWith('Connected') ? 'success' : 'error'}`}>
            {testResult}
          </div>
        )}

        {error && (
          <div className="test-result error">
            {error}
          </div>
        )}

        <div className="button-group">
          <button
            className="secondary"
            onClick={testConnection}
            disabled={isTesting || isConnected || isConnecting}
          >
            {isTesting ? 'Testing...' : 'Test Connection'}
          </button>

          {isConnected ? (
            <button className="primary" onClick={onDisconnect}>
              Disconnect
            </button>
          ) : (
            <button
              className="primary"
              onClick={handleConnect}
              disabled={isConnecting || !credentials.host || !credentials.username}
            >
              {isConnecting ? 'Connecting...' : 'Connect'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
