/**
 * API service for communicating with the FastAPI backend.
 */

import type {
  USBCheckResponse,
  PingRequest,
  PingResponse,
  SSHCredentials,
  SSHTestResponse,
  FingerprintStatus,
  FingerprintCaptureResponse,
} from '../types';

const API_BASE = '/api';

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {},
): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new ApiError(response.status, error.detail || 'Request failed');
  }

  return response.json();
}

export const api = {
  /**
   * Check USB connections to Jetson Nano.
   */
  checkUSB: (): Promise<USBCheckResponse> => {
    return request<USBCheckResponse>('/connection/usb/check');
  },

  /**
   * Ping a host to check if it's reachable.
   */
  ping: (data: PingRequest): Promise<PingResponse> => {
    return request<PingResponse>('/connection/ping', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  /**
   * Test SSH connection with provided credentials.
   */
  testSSH: (credentials: SSHCredentials): Promise<SSHTestResponse> => {
    return request<SSHTestResponse>('/connection/ssh/test', {
      method: 'POST',
      body: JSON.stringify(credentials),
    });
  },

  // Fingerprint APIs
  fingerprint: {
    /**
     * Connect to Jetson for fingerprint operations.
     */
    connect: (credentials: SSHCredentials): Promise<{ success: boolean; error?: string }> => {
      return request('/fingerprint/connect', {
        method: 'POST',
        body: JSON.stringify({ credentials }),
      });
    },

    /**
     * Disconnect from Jetson.
     */
    disconnect: (): Promise<{ success: boolean }> => {
      return request('/fingerprint/disconnect', { method: 'POST' });
    },

    /**
     * Get fingerprint sensor status.
     */
    getStatus: (): Promise<FingerprintStatus> => {
      return request<FingerprintStatus>('/fingerprint/status');
    },

    /**
     * Capture a single fingerprint image.
     */
    capture: (): Promise<FingerprintCaptureResponse> => {
      return request<FingerprintCaptureResponse>('/fingerprint/capture', { method: 'POST' });
    },

    /**
     * Control LED.
     */
    led: (color: number): Promise<{ success: boolean }> => {
      return request('/fingerprint/led', {
        method: 'POST',
        body: JSON.stringify({ color }),
      });
    },

    /**
     * Match fingerprint.
     */
    match: (): Promise<{ matched: boolean; user_id: number; error?: string }> => {
      return request('/fingerprint/match', { method: 'POST' });
    },

    /**
     * Add new fingerprint.
     */
    add: (): Promise<{ success: boolean; user_id: number; error?: string }> => {
      return request('/fingerprint/add', { method: 'POST' });
    },

    /**
     * Delete fingerprint(s).
     */
    delete: (userId: number): Promise<{ success: boolean }> => {
      return request('/fingerprint/delete', {
        method: 'POST',
        body: JSON.stringify({ user_id: userId }),
      });
    },
  },
};

export { ApiError };
