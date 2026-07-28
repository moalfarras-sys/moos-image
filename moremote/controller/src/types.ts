// Bump this on each frontend change so you can confirm the phone loaded the latest build.
export const BUILD = "v14 · fill-screen portrait + display-matched resolution";

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
 * desktop  = the viewer has a real mouse and a real keyboard; nothing is interpreted. Handled by
 *            lib/desktop.ts, and GestureController goes inert so a mouse is not read twice.
 *            The agent validates this string too (StreamSession.ValidateEnvelope) — a mode it does
 *            not know is dropped before any handler runs, silently.
 */
export type GestureMode = "touch" | "trackpad" | "direct" | "desktop";

/**
 * THERE ARE THREE INTERACTION MODELS, NOT FOUR.
 *
 * `touch` and `direct` differ in exactly one branch of GestureController — what a one-finger swipe
 * becomes, a scroll or a drag. Everything else about them is identical: same absolute cursor, same
 * tap, same long-press right-click, same two-finger scroll and pinch. Presenting that as two
 * separate top-level "modes" asked the user to hold a distinction the code does not really make,
 * and put four buttons where three belong.
 *
 * So the UI offers Touch / Trackpad / Mouse+keys, and the touch-vs-direct difference is a switch
 * inside Touch called what it actually is: one-finger drag. The wire values are unchanged — the
 * agent still validates all four, which it must, because an older cached client still sends
 * "direct" as a mode of its own.
 */
export const DRAG_MODE: GestureMode = "direct";

/** One line each, because a mode nobody can predict is a mode nobody will pick deliberately. */
export const MODE_HINT: Record<GestureMode, string> = {
  touch: "Tap · swipe scrolls · hold = right-click · hold then move = drag",
  direct: "Tap to click · one finger drags · two fingers scroll",
  trackpad: "Slide to move the pointer, like a laptop trackpad",
  desktop: "A real mouse and keyboard — nothing is interpreted",
};

export const MODE_LABEL: Record<GestureMode, string> = {
  touch: "Touch",
  trackpad: "Trackpad",
  direct: "Drag",
  // Short on purpose. This label goes in a toolbar button and in the status line, and at 390px
  // "Mouse + Keys" wrapped to two lines and crushed the icon above it. The Controls sheet spells the
  // mode out in full, where there is room for it.
  desktop: "Desktop",
};

/** fit = scale whole screen into the view; actual = 1:1 device pixels (pan around) */
export type ViewMode = "fit" | "actual";

export interface QualityPreset {
  label: string;
  /** What it actually looks like, for the UI — the honest version of the label. */
  detail: string;
  quality: number;
  fps: number;
  /** Encode width in PIXELS. See the note below on why this is not a fraction any more. */
  width: number;
}

/**
 * A preset is a RESOLUTION now, not a fraction.
 *
 * It used to be `scale`, a fraction of whatever the source happened to be — so "Balanced" was 1344
 * pixels wide on a 1080p desktop and 1792 on a 4K one, and the client could not even find out
 * which it had got, because `hello` reports the LOGICAL desktop size (1707x960 on this 4K screen)
 * rather than the source pixels the encoder sees. A setting whose meaning depends on the machine,
 * and which the machine will not tell you, cannot be reasoned about by anyone.
 *
 * The ceiling moved too. 1920 was never a hardware limit; measured on an RTX 2080 SUPER with the
 * worst-case content there is (pattern=snow), the encoder holds 60.3fps at both 1920x1080 and
 * 2560x1440, and only runs out at 4K60. On a 4K desktop the old cap threw away half the linear
 * detail before the encoder ever saw it — which is why no bitrate ever made the text crisp.
 *
 * Frames are only produced when the screen actually changes, so a high fps costs nothing on a
 * still desktop: it is spent only when there is motion, which is exactly when it is wanted.
 */
export const QUALITY_PRESETS: QualityPreset[] = [
  { label: "Data saver", detail: "540p · 30", quality: 45, fps: 30, width: 960 },
  { label: "Balanced",   detail: "768p · 30", quality: 62, fps: 30, width: 1366 },
  { label: "Sharp",      detail: "1080p · 30", quality: 80, fps: 30, width: 1920 },
  { label: "Ultra",      detail: "1440p · 60", quality: 85, fps: 60, width: 2560 },
];

/**
 * How far the automatic ladder may climb on its own.
 *
 * Auto steps on ROUND-TRIP TIME, and RTT is not bandwidth. A link can be 20ms away and still only
 * have 5 Mbit/s of uplink — a fibre router with a saturated upstream, a hotel, a phone on a good
 * signal with a slow plan — and Ultra asks for roughly thirteen. Climbing into it on the strength
 * of a low ping would stall exactly the person whose link looked healthiest.
 *
 * So Ultra is a decision, not a guess: auto tops out at Sharp, and anyone who knows their link can
 * pick the last step by hand.
 */
export const AUTO_MAX_PRESET = 2;
