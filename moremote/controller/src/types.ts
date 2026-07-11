// Bump this on each frontend change so you can confirm the phone loaded the latest build.
export const BUILD = "v7 · reliable Wayland input";

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

/** touch = touchscreen (swipe scrolls, tap clicks); trackpad = relative; direct = press-drag */
export type GestureMode = "touch" | "trackpad" | "direct";

export const MODE_LABEL: Record<GestureMode, string> = {
  touch: "Touch",
  trackpad: "Trackpad",
  direct: "Direct",
};

/** fit = scale whole screen into the view; actual = 1:1 device pixels (pan around) */
export type ViewMode = "fit" | "actual";

export interface QualityPreset {
  label: string;
  quality: number;
  fps: number;
  scale: number;
}

export const QUALITY_PRESETS: QualityPreset[] = [
  { label: "Low", quality: 40, fps: 24, scale: 0.55 },
  { label: "Balanced", quality: 62, fps: 18, scale: 0.8 },
  { label: "High", quality: 85, fps: 12, scale: 1.0 },
];
