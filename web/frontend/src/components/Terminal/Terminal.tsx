import { useEffect, useRef, useCallback } from 'react';
import { Terminal as XTerm } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import '@xterm/xterm/css/xterm.css';
import type { ConnectionStatus, TerminalSize } from '../../types';
import './Terminal.css';

interface TerminalProps {
  connectionStatus: ConnectionStatus;
  onData: (handler: (data: Uint8Array) => void) => void;
  onInput: (data: string) => void;
  onResize: (size: TerminalSize) => void;
}

export function Terminal({
  connectionStatus,
  onData,
  onInput,
  onResize,
}: TerminalProps) {
  const terminalRef = useRef<HTMLDivElement>(null);
  const xtermRef = useRef<XTerm | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);

  // Initialize terminal
  useEffect(() => {
    if (!terminalRef.current || xtermRef.current) return;

    const xterm = new XTerm({
      cursorBlink: true,
      cursorStyle: 'block',
      fontSize: 14,
      fontFamily: 'Menlo, Monaco, "Courier New", monospace',
      theme: {
        background: '#0d1117',
        foreground: '#c9d1d9',
        cursor: '#c9d1d9',
        cursorAccent: '#0d1117',
        selectionBackground: '#264f78',
        black: '#0d1117',
        red: '#ff7b72',
        green: '#7ee787',
        yellow: '#d29922',
        blue: '#79c0ff',
        magenta: '#d2a8ff',
        cyan: '#a5d6ff',
        white: '#c9d1d9',
        brightBlack: '#6e7681',
        brightRed: '#ffa198',
        brightGreen: '#7ee787',
        brightYellow: '#e3b341',
        brightBlue: '#a5d6ff',
        brightMagenta: '#d2a8ff',
        brightCyan: '#a5d6ff',
        brightWhite: '#ffffff',
      },
    });

    const fitAddon = new FitAddon();
    xterm.loadAddon(fitAddon);

    xterm.open(terminalRef.current);
    fitAddon.fit();

    xtermRef.current = xterm;
    fitAddonRef.current = fitAddon;

    // Handle user input
    xterm.onData((data) => {
      onInput(data);
    });

    // Initial resize notification
    onResize({
      rows: xterm.rows,
      cols: xterm.cols,
    });

    // Handle window resize
    const handleResize = () => {
      if (fitAddonRef.current && xtermRef.current) {
        fitAddonRef.current.fit();
        onResize({
          rows: xtermRef.current.rows,
          cols: xtermRef.current.cols,
        });
      }
    };

    window.addEventListener('resize', handleResize);

    // ResizeObserver for container size changes
    const resizeObserver = new ResizeObserver(handleResize);
    resizeObserver.observe(terminalRef.current);

    return () => {
      window.removeEventListener('resize', handleResize);
      resizeObserver.disconnect();
      xterm.dispose();
      xtermRef.current = null;
      fitAddonRef.current = null;
    };
  }, [onInput, onResize]);

  // Register data handler
  const handleIncomingData = useCallback((data: Uint8Array) => {
    if (xtermRef.current) {
      xtermRef.current.write(data);
    }
  }, []);

  useEffect(() => {
    onData(handleIncomingData);
  }, [onData, handleIncomingData]);

  // Clear terminal on disconnect
  useEffect(() => {
    if (connectionStatus === 'disconnected' && xtermRef.current) {
      xtermRef.current.clear();
      xtermRef.current.write('\r\n\x1b[33mDisconnected from server.\x1b[0m\r\n');
    }
  }, [connectionStatus]);

  // Show connection status messages
  useEffect(() => {
    if (!xtermRef.current) return;

    if (connectionStatus === 'connecting') {
      xtermRef.current.write('\x1b[36mConnecting...\x1b[0m\r\n');
    } else if (connectionStatus === 'connected') {
      xtermRef.current.write('\x1b[32mConnected!\x1b[0m\r\n\r\n');
    } else if (connectionStatus === 'error') {
      xtermRef.current.write('\x1b[31mConnection error.\x1b[0m\r\n');
    }
  }, [connectionStatus]);

  // Focus terminal on click
  const handleClick = () => {
    xtermRef.current?.focus();
  };

  return (
    <div className="terminal-container" onClick={handleClick}>
      <div className="terminal-header">
        <span className="terminal-title">Terminal</span>
        <div className="terminal-controls">
          <span className={`terminal-status ${connectionStatus}`}>
            {connectionStatus}
          </span>
        </div>
      </div>
      <div className="terminal-content" ref={terminalRef} />
    </div>
  );
}
