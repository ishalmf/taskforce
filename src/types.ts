export interface AppSettings {
  durationMs: number;
  volume: number;
  soundEnabled: boolean;
  startAtLogin: boolean;
  position: {
    x: number | null;
    y: number | null;
  };
}

export interface IntegrationStatus {
  opencode: boolean;
  gemini: boolean;
}

export interface SignalPayload {
  durationMs: number;
  volume: number;
  soundEnabled: boolean;
  sequence: number;
}
