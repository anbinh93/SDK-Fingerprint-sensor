/**
 * TypeScript interfaces matching the backend Pydantic models.
 */

export interface USBStatus {
  connected: boolean;
  device: string | null;
  ip_address: string | null;
  details: string | null;
}

export interface USBCheckResponse {
  usb_ethernet: USBStatus;
  usb_serial: USBStatus;
  any_connected: boolean;
}

export interface PingRequest {
  host: string;
  timeout?: number;
}

export interface PingResponse {
  success: boolean;
  host: string;
  latency_ms: number | null;
  error: string | null;
}

export interface SSHCredentials {
  host: string;
  port?: number;
  username: string;
  password?: string;
  key_path?: string;
}

export interface SSHTestResponse {
  success: boolean;
  host: string;
  username: string;
  error: string | null;
  system_info: string | null;
}

export interface TerminalSize {
  rows: number;
  cols: number;
}

// WebSocket message types
export type WSMessageType =
  | 'connect'
  | 'connected'
  | 'error'
  | 'resize'
  | 'input'
  | 'disconnected';

export interface WSConnectMessage {
  type: 'connect';
  credentials: SSHCredentials;
  size: TerminalSize;
}

export interface WSConnectedMessage {
  type: 'connected';
  sessionId: string;
}

export interface WSErrorMessage {
  type: 'error';
  message: string;
}

export interface WSResizeMessage {
  type: 'resize';
  rows: number;
  cols: number;
}

export interface WSInputMessage {
  type: 'input';
  data: string;
}

export interface WSDisconnectedMessage {
  type: 'disconnected';
}

export type WSMessage =
  | WSConnectMessage
  | WSConnectedMessage
  | WSErrorMessage
  | WSResizeMessage
  | WSInputMessage
  | WSDisconnectedMessage;

// Connection state
export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error';

// Fingerprint types
export interface FingerprintStatus {
  connected: boolean;
  jetson_connected: boolean;
  user_count: number;
  compare_level: number;
  error: string | null;
}

export interface FingerprintImage {
  data: string;  // base64
  width: number;
  height: number;
  quality: number;
  has_finger: boolean;
}

export interface FingerprintCaptureResponse {
  success: boolean;
  image_base64: string | null;
  width: number;
  height: number;
  quality: number;
  has_finger: boolean;
  error: string | null;
}

// Fingerprint WebSocket messages
export interface FPStreamImageMessage {
  type: 'image';
  data: string;
  width: number;
  height: number;
  quality: number;
  has_finger: boolean;
}

export interface FPStreamControlMessage {
  type: 'start' | 'stop' | 'led' | 'capture_once';
  fps?: number;
  color?: number;
}

export type FPStreamMessage = FPStreamImageMessage | { type: 'connected' | 'started' | 'stopped' | 'error'; message?: string; fps?: number };
