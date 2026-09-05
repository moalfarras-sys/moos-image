// Bump this on each frontend change so you can confirm the phone loaded the latest build.
//
// It earns its place: a precaching service worker means the phone can keep running an old
// bundle after the agent is updated, and this line on the connect screen is the only way to
// tell at a glance which one you are looking at. v14 also described behaviour that no longer
// exists ("fill-screen portrait" was the automatic quarter-turn, now removed), so it was
// actively misleading while debugging exactly that.
export const BUILD = "v38 · Precise control, fluent typing, calm workspace";

export interface ServerStatus {
  name: string;
  version: string;
  firstRun: boolean;
  locked: boolean;
  lockoutSeconds: number;
  hostPowerAllowed: boolean;
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
  /** The picture already contains the compositor's real cursor. */
  cursorEmbedded?: boolean;
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
  { label: "Data saver", detail: "576p · 30", quality: 52, fps: 30, width: 1024 },
  { label: "Balanced",   detail: "768p · 30", quality: 68, fps: 30, width: 1366 },
  { label: "Sharp",      detail: "1080p · 30", quality: 80, fps: 30, width: 1920 },
  { label: "Ultra",      detail: "1440p · 60", quality: 85, fps: 60, width: 2560 },
];

/**
 * How much of the phone's real pixel density the picture is allowed to use.
 *
 * This was the bare literal `2.5`, repeated in five places with no comment, and it was costing
 * exactly the sharpness the owner reported as "دقة سيئة". Measured against the live agent from a
 * device-emulated iPhone (DPR 3, 390x844 CSS):
 *
 *     cap 2.5   canvas backing store 975x1915   encoded stream 974x548
 *     screen                                    1170 real device pixels wide
 *
 * So the whole chain — canvas, encode request, and the picture drawn into it — ran at 83% of the
 * device's linear resolution, and the browser upscaled the last 20% back for display. On a screen
 * already showing a 1920-wide desktop squeezed into 974 pixels, that second loss is the one that
 * takes text from "small" to "smeared".
 *
 * 3 rather than "uncapped": the cap exists to stop a phone from asking the encoder for pixels it
 * cannot pay for, and a GPU-less VPS is the machine that pays. What makes 3 affordable is measured
 * on the machine that actually encodes — MoOS Cloud, llvmpipe, 8 vCPU, three live Plasma sessions,
 * 300 frames of 1080p through the shipped x264 settings:
 *
 *     974x548    (cap 2.5)   533,752 px/frame   2.67 s   137% CPU   -> 112 fps of headroom
 *     1170x658   (cap 3)     769,860 px/frame   3.37 s   135% CPU   ->  89 fps of headroom
 *
 * +44% pixels for +26% encode time, still about three times the 30fps the presets ask for. A
 * device reporting DPR 4 would be a different measurement, and this cap is what stops it from
 * being taken on trust.
 */
export const MAX_DPR = 3;

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

/**
 * When the controller chrome belongs in a RIGHT-HAND rail instead of a bottom dock.
 *
 * The remote MoOS desktop keeps its Horizon Bar bottom-centred. The controller therefore reserves
 * a separate grid track: a thumb-reachable bottom dock on a portrait phone, and a right-hand rail
 * when a fine pointer or short landscape viewport is available. Neither track overlaps encoded
 * pixels, even while the controls animate or hide.
 *
 * WHY NOT `(hover: hover) and (pointer: fine)`, WHICH IS WHAT THIS USED TO BE
 *
 * Those two test the PRIMARY pointer, and on a Windows touchscreen laptop the primary pointer is
 * the touchscreen even when a mouse and trackpad are attached. So `pointer: fine` is FALSE on a
 * very ordinary computer, the rule never applied, and the desktop layout stayed phone-like —
 * which is exactly the reported symptom. This file already documents the same class of
 * trap for gesture mode ("A touchscreen laptop therefore starts in touch mode"), and a browser
 * that declines to answer pointer queries at all — headless Firefox does — fell into the same
 * hole and got a phone layout on a 1280x860 window.
 *
 * `any-*` asks the honest question: is a fine, hovering pointer AVAILABLE on this machine. The
 * viewport clause then covers a browser that answers nothing. A phone in landscape is under 900px
 * and is caught by the short-landscape rail rule declared after this one.
 *
 * CSS AND JS MUST USE THIS EXACT STRING. styles.css chooses the reserved track and RemoteScreen
 * chooses the matching reveal affordance; if they disagree the gesture opens the wrong edge. That is
 * why this is one exported constant and why test_remote_toolbar_edge.py asserts the stylesheet
 * contains it verbatim.
 */
export const POINTER_BAR_QUERY =
  "(any-hover: hover) and (any-pointer: fine), (min-width: 900px) and (orientation: landscape)";
