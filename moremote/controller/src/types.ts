// Bump this on each frontend change so you can confirm the phone loaded the latest build.
export const BUILD = "v9 · fast Arabic + instant touch";

export interface ServerStatus {
  name: string;
  version: string;
  firstRun: boolean;
  locked: boolean;
  lockoutSeconds: number;
}

export interface MonitorInfo {
  index: number;
  name: string;
  primary: boolean;
}

export interface Hello {
  type: "hello";
  screen: { w: number; h: number };
  quality: number;
  fps: number;
  paused: boolean;
  cursor: boolean;
  monitors?: MonitorInfo[];
  monitor?: number;
  input?: { ready: boolean; backend: string; error?: string };
  clipboard?: { ready: boolean };
}

export type MouseButton = "left" | "right" | "middle";

/**
 * touch    = phone-native: tap clicks, swipe scrolls, hold = right-click, hold+move = drag
 * direct   = one-finger drag really drags (move windows, select text); two fingers scroll
 * trackpad = laptop trackpad: the finger moves the cursor relatively
 */
export type GestureMode = "touch" | "trackpad" | "direct";

export const MODE_LABEL: Record<GestureMode, string> = {
  touch: "Touch",
  trackpad: "Trackpad",
  direct: "Drag",
};

/** fit = scale whole screen into the view; actual = 1:1 device pixels (pan around) */
export type ViewMode = "fit" | "actual";

export interface QualityPreset {
  label: string;
  quality: number;
  fps: number;
  scale: number;
}

// Frames are only produced when the screen actually changes, so a high fps cap costs nothing on
// a still desktop. scale is a fraction of the encoder's target width (1920), so it is the real
// resolution knob: 0.5 -> 960px wide, 1.0 -> 1920px.
export const QUALITY_PRESETS: QualityPreset[] = [
  { label: "Low", quality: 45, fps: 30, scale: 0.5 },
  { label: "Balanced", quality: 62, fps: 30, scale: 0.7 },
  { label: "High", quality: 80, fps: 30, scale: 1.0 },
];
