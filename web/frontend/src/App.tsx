import { useRef, useCallback, useState } from 'react';
import { ConnectionPanel } from './components/ConnectionPanel';
import { Terminal } from './components/Terminal';
import { FingerprintPanel } from './components/Fingerprint';
import { useWebSocket } from './hooks/useWebSocket';
import type { SSHCredentials, TerminalSize } from './types';
import './App.css';

function App() {
  const dataHandlerRef = useRef<((data: Uint8Array) => void) | null>(null);
  const terminalSizeRef = useRef<TerminalSize>({ rows: 24, cols: 80 });
  const [sshCredentials, setSshCredentials] = useState<SSHCredentials | null>(null);

  const handleData = useCallback((data: Uint8Array) => {
    dataHandlerRef.current?.(data);
  }, []);

  const { status, error, connect, disconnect, send, resize } = useWebSocket({
    onData: handleData,
    onConnect: (sessionId) => {
      console.log('Connected with session:', sessionId);
    },
    onDisconnect: () => {
      console.log('Disconnected');
    },
    onError: (err) => {
      console.error('WebSocket error:', err);
    },
  });

  const handleConnect = useCallback(
    (credentials: SSHCredentials) => {
      setSshCredentials(credentials);
      connect(credentials, terminalSizeRef.current);
    },
    [connect],
  );

  const handleDisconnect = useCallback(() => {
    disconnect();
    setSshCredentials(null);
  }, [disconnect]);

  const registerDataHandler = useCallback((handler: (data: Uint8Array) => void) => {
    dataHandlerRef.current = handler;
  }, []);

  const handleTerminalInput = useCallback(
    (data: string) => {
      if (status === 'connected') {
        send(data);
      }
    },
    [status, send],
  );

  const handleTerminalResize = useCallback(
    (size: TerminalSize) => {
      terminalSizeRef.current = size;
      if (status === 'connected') {
        resize(size);
      }
    },
    [status, resize],
  );

  return (
    <div className="app">
      <header className="app-header">
        <h1>Jetson Nano Remote</h1>
        <span className="version">v1.0.0</span>
      </header>

      <main className="app-main">
        <aside className="sidebar">
          <ConnectionPanel
            onConnect={handleConnect}
            onDisconnect={handleDisconnect}
            connectionStatus={status}
            error={error}
          />
          <FingerprintPanel
            sshCredentials={sshCredentials}
            sshConnected={status === 'connected'}
          />
        </aside>

        <section className="content">
          <Terminal
            connectionStatus={status}
            onData={registerDataHandler}
            onInput={handleTerminalInput}
            onResize={handleTerminalResize}
          />
        </section>
      </main>
    </div>
  );
}

export default App;
