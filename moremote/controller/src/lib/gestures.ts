import type { GestureMode } from "../types";
import { rotateDelta } from "./coordinates.ts";

export interface GestureCallbacks {
  click: (button: "left" | "right", nx: number, ny: number) => void;
  /** A real double-click, injected by the agent with a controlled 40ms gap. */
  dblclick: (nx: number, ny: number) => void;
  moveCursor: (nx: number, ny: number) => void; // absolute move
  moveRelative?: (dx: number, dy: number) => void;
  dragStart: (nx: number, ny: number) => void;
  dragMove: (nx: number, ny: number) => void;
  dragEnd: (nx: number, ny: number) => void;
  /** positive dy = scroll down (content moves up), like a real wheel */
  scroll: (dxNotches: number, dyNotches: number) => void;
  zoomAt: (factor: number, clientX: number, clientY: number) => void;
  panBy: (dxPx: number, dyPx: number) => void;
  cursorAt: (nx: number, ny: number) => void; // where to draw the on-screen cursor
  haptic?: () => void;
  /**
   * Two-finger double-tap: snap between fitting the whole desktop and a readable magnification.
   *
   * A remote desktop on a phone has exactly two states anyone actually wants — "show me everything"
   * and "let me read this" — and pinching to get between them is a two-handed operation on a device
   * usually held in one. Every map and photo viewer solves this with double-tap; here single
   * double-tap is already spoken for (it opens folders and it is the one gesture that MUST reach the
   * desktop), so the zoom shortcut takes two fingers, which nothing else on the canvas uses.
   */
  zoomToggleAt?: (clientX: number, clientY: number) => void;
  /** Close the first two-finger tap's context menu before the local zoom shortcut. */
  dismissContext?: () => void;
}

interface Ptr { id: number; x: number; y: number; sx: number; sy: number; st: number; travel: number; }

// Touch slop: how far a finger may travel and still be a tap rather than a swipe.
//
// This was 5, and 5 is not a slop, it is a rounding error. A thumb on a 120 Hz phone moves 5 CSS px
// before it has finished landing, so a tap crossed the line, the gesture committed to "scroll", and
// onUp had no case for "scroll" — no click was sent AT ALL. Not a mis-aimed click: none. That is the
// whole of "the screen does not respond to touch", and it is independent of every video problem.
//
// 12 is in the range every touch platform settled on for the same decision (iOS ~10pt, Android's
// scaled touch slop ~8dp ≈ 12-16 px at typical densities). TAP_RESCUE_MS/PX below are the second
// half: commit late, so a gesture that DID cross the line but was plainly a tap still clicks.
const MOVE_THRESHOLD = 12;
/** A gesture shorter than this and smaller than TAP_RESCUE_PX was a tap, whatever it looked like. */
const TAP_RESCUE_MS = 300;
const TAP_RESCUE_PX = 24;
/** Accumulated spread before zooming engages — keeps scroll jitter from creeping the picture. */
const PINCH_ENGAGE_PX = 8;
const LONGPRESS_MS = 500; // matches Android's own long-press feel, so a slow tap stays a tap
/** Two taps closer than this in time AND space are one double-click. */
const DOUBLE_TAP_MS = 300;
// The position gate is not optional: without it, two quick taps on adjacent list rows collapse
// into a double-click on the first one.
const DOUBLE_TAP_PX = 20;
const PX_PER_NOTCH = 24;
const TRACKPAD_GAIN = 1.7;
/** Two two-finger taps closer together than this are the zoom shortcut, not two right-clicks. */
const TWO_TAP_MS = 340;

// ---- panning momentum -------------------------------------------------------------------------
//
// Panning stopped dead the instant the fingers left the glass, and on a picture that is several
// screens wide — which is the normal case the moment anyone zooms in to read something — that turns
// crossing the desktop into a rowing motion: drag, lift, reposition, drag again. Every scrollable
// surface on both phone platforms has had inertia since 2007 precisely because a finger cannot stay
// on the screen for the length of the content.
//
// The model is the standard one: keep a velocity estimate from the last few moves, and when the
// gesture ends let it decay geometrically at 60Hz until it is below half a pixel a frame.
//
// DECAY is per frame. 0.94 gives a glide of roughly half a second — long enough to be worth having,
// short enough that it never feels like the picture is sliding away from you. MIN_FLING_V exists so
// that a slow, deliberate reposition (which ends with almost no velocity) stops exactly where it was
// released; inertia that fires on every pan would make precise placement impossible.
const PAN_DECAY = 0.94;
const MIN_FLING_V = 0.35;      // px per frame
const MAX_FLING_V = 60;        // px per frame — a flick cannot become a teleport
/** How much of the newest sample to fold into the velocity estimate; the rest is history. */
const V_SMOOTH = 0.55;

/**
 * Three control modes. All of them position the cursor *absolutely*: the phone owns the cursor
 * position, sends it as a normalized point, and draws the cursor itself — so what you see under
 * your finger is exactly where the click lands.
 *
 *  - touch    : phone-native. Tap = click, one-finger swipe = scroll, hold = right-click,
 *               hold-then-move = drag. This is the default: swiping scrolls, as on any phone.
 *  - direct   : one-finger drag actually drags (move windows, select text). Two fingers scroll.
 *  - trackpad : laptop trackpad. Finger moves the cursor relatively; two fingers scroll.
 *
 * Taps click immediately — no waiting to see whether a double-tap follows. A double-tap simply
 * sends two clicks in quick succession, which the desktop already interprets as a double-click.
 * That removes the ~280ms delay that used to sit on every single tap.
 */
export class GestureController {
  private pointers = new Map<number, Ptr>();
  private mode: GestureMode = "touch";

  private qRelative: {dx: number; dy: number} | null = null;
  private phase: "idle" | "down" | "held" | "scroll" | "drag" | "move" = "idle";
  private longTimer: number | null = null;
  /**
   * This gesture started in the black, so it must never become a click.
   *
   * normalizeContentPoint CLAMPS a point onto the picture instead of rejecting it, so a tap in the
   * letterbox does not miss — it lands on the nearest EDGE of the remote desktop. On KDE that edge
   * is the panel, the dock and the hot corners. In portrait the letterbox is 74% of the screen, so
   * three taps out of four fired a real click somewhere the user was not even pointing.
   *
   * Origin-based on purpose: a drag that STARTS on the picture and wanders into the black must keep
   * clamping, because that is how you drag a window to the screen edge.
   */
  private outside = false;

  // last position we sent, normalized — the single source of truth for the cursor
  private cx = 0.5;
  private cy = 0.5;

  private lastX = 0;
  private lastY = 0;

  // The previous tap, for double-tap recognition. Position is kept in BOTH spaces: screen pixels
  // to judge whether the two taps were aimed at the same thing, normalized to place the click.
  private lastTapAt = -Infinity;
  private lastTapCX = 0;
  private lastTapCY = 0;
  private lastTapNx = 0.5;
  private lastTapNy = 0.5;

  // two-finger. twoMode says whether the view has moved yet (a two-finger TAP is
  // decided on — see moveTwo.
  private two = false;
  private twoMode: "undecided" | "moved" = "undecided";
  private twoStart = 0;
  private twoStartDist = 0;
  private twoStartCx = 0;
  private twoStartCy = 0;
  private twoPinching = false;
  private lastCx = 0;
  private lastCy = 0;
  private lastDist = 0;

  // rAF-coalesced output
  private raf = 0;
  private qMove: { nx: number; ny: number; drag: boolean } | null = null;
  private qScrollX = 0;
  private qScrollY = 0;
  private qTwo = false;

  // Momentum: a smoothed velocity while two fingers are panning, and the glide that follows.
  private vx = 0;
  private vy = 0;
  private lastMoveAt = 0;
  private glide = 0;
  /** When the last two-finger tap ended, for the double-tap-to-zoom shortcut. */
  private lastTwoTapAt = -Infinity;
  private lastTwoTapCx = 0;
  private lastTwoTapCy = 0;

  constructor(
    private el: HTMLElement,
    private toNorm: (clientX: number, clientY: number) => { x: number; y: number },
    private getZoom: () => number,
    /** Which axes the picture overflows; see moveTwo. Defaults to the old zoom-based test. */
    private cb: GestureCallbacks,
    private getSensitivity: () => number = () => 1,
    /** Is this screen point actually on the picture, rather than in the letterbox? */
    private inContent: (clientX: number, clientY: number) => boolean = () => true,
    private canPan: () => { x: boolean; y: boolean } =
      () => ({ x: this.getZoom() > 1.01, y: this.getZoom() > 1.01 }),
    /**
     * Is the picture currently drawn a quarter turn round? Every finger movement that means
     * something IN THE DESKTOP (a scroll, a trackpad nudge) has to be turned with it, or the axes
     * come out swapped — see lib/coordinates.rotateDelta. Screen-space work (panning the drawn box,
     * hit-testing, pinch) is unaffected and deliberately does not consult this.
     */
    private isRotated: () => boolean = () => false,
    /** Relative control needs the real cursor visible in the stream. */
    private relativeTrackpad: () => boolean = () => false,
  ) {
    el.addEventListener("pointerdown", this.onDown, { passive: false });
    el.addEventListener("pointermove", this.onMove, { passive: false });
    el.addEventListener("pointerup", this.onUp, { passive: false });
    el.addEventListener("pointercancel", this.onCancel, { passive: false });
    el.addEventListener("lostpointercapture", this.onLostCapture);
    el.addEventListener("contextmenu", this.prevent, { passive: false });
    window.addEventListener("blur", this.cancelAll);
    document.addEventListener("visibilitychange", this.onVisibility);
  }

  setMode(m: GestureMode) {
    this.endAll();
    this.mode = m;
  }

  /** Keep the on-screen cursor where the caller says it is (e.g. after a layout change). */
  setCursor(nx: number, ny: number) {
    this.cx = nx; this.cy = ny;
  }

  destroy() {
    this.el.removeEventListener("pointerdown", this.onDown);
    this.el.removeEventListener("pointermove", this.onMove);
    this.el.removeEventListener("pointerup", this.onUp);
    this.el.removeEventListener("pointercancel", this.onCancel);
    this.el.removeEventListener("lostpointercapture", this.onLostCapture);
    this.el.removeEventListener("contextmenu", this.prevent);
    window.removeEventListener("blur", this.cancelAll);
    document.removeEventListener("visibilitychange", this.onVisibility);
    this.endAll();   // tearing down mid-drag must still release the button
    if (this.raf) cancelAnimationFrame(this.raf);
  }

  private prevent = (e: Event) => e.preventDefault();
  /** Also used by the owner when input is disabled or the connection is lost. */
  cancelAll = () => this.endAll();
  private onVisibility = () => { if (document.hidden) this.cancelAll(); };
  private onLostCapture = (e: PointerEvent) => {
    if (this.pointers.has(e.pointerId)) this.cancelAll();
  };

  /**
   * In "desktop" mode a real mouse is driving, and lib/desktop.ts handles it from the mouse events.
   * A mouse ALSO raises pointer events, so without this guard every click would be delivered twice —
   * once interpreted as a tap here and once as a real button there.
   */
  private get inert() { return this.mode === "desktop"; }

  // ---------------- down ----------------
  private onDown = (e: PointerEvent) => {
    if (this.inert) return;
    e.preventDefault();
    this.stopGlide();   // a finger on the glass always outranks the glide it is interrupting
    try { this.el.setPointerCapture(e.pointerId); } catch { /* */ }
    this.pointers.set(e.pointerId, {
      id: e.pointerId, x: e.clientX, y: e.clientY, sx: e.clientX, sy: e.clientY, st: now(), travel: 0,
    });

    if (this.two) { this.twoMode = "moved"; return; }
    if (this.pointers.size === 2) { this.beginTwo(); return; }

    this.cancelLong();
    this.phase = "down";
    this.lastX = e.clientX;
    this.lastY = e.clientY;
    // Trackpad mode is relative — a finger anywhere is legitimate, including the black.
    this.outside = this.mode !== "trackpad" && !this.inContent(e.clientX, e.clientY);

    // In the absolute modes the cursor goes under the finger straight away, so the desktop
    // hovers/highlights exactly what you are touching before you even lift.
    if (this.mode !== "trackpad" && !this.outside) {
      const t = this.toNorm(e.clientX, e.clientY);
      this.moveTo(t.x, t.y, false);
    }

    // Hold = right-click on release, or drag if you move while still holding. Not armed for a
    // gesture that began in the letterbox: a long press on nothing must not right-click the edge.
    if (!this.outside) {
      this.longTimer = window.setTimeout(() => {
        if (this.phase !== "down") return;
        this.phase = "held";
        this.cb.haptic?.();
      }, LONGPRESS_MS);
    }
  };

  // ---------------- move ----------------
  private onMove = (e: PointerEvent) => {
    if (this.inert) return;
    const p = this.pointers.get(e.pointerId);
    if (!p) return;
    e.preventDefault();
    p.x = e.clientX; p.y = e.clientY;
    p.travel = Math.max(p.travel, dist(p.x, p.y, p.sx, p.sy));

    if (this.two) {
      if (this.pointers.size >= 2) { this.qTwo = true; this.scheduleFlush(); }
      else if (dist(p.x, p.y, p.sx, p.sy) > MOVE_THRESHOLD) this.twoMode = "moved";
      return;
    }
    if (this.pointers.size !== 1) return;
    // A direct drag may clamp after leaving the picture, but may never start in the letterbox.
    if (this.outside && this.mode === "direct") return;

    const dx = p.x - this.lastX;
    const dy = p.y - this.lastY;
    const far = dist(p.x, p.y, p.sx, p.sy) > MOVE_THRESHOLD;

    // Decide, once, what this gesture is.
    if (this.phase === "held" && far) {
      // Held then moved = drag from where the finger has been resting.
      this.phase = "drag";
      this.cb.dragStart(this.cx, this.cy);
    } else if (this.phase === "down" && far) {
      this.cancelLong();
      if (this.mode === "direct") {
        this.phase = "drag";
        const s = this.toNorm(p.sx, p.sy);
        this.moveTo(s.x, s.y, false);
        this.cb.dragStart(s.x, s.y);
        this.lastTapAt = -Infinity;   // a tap that became a drag cannot start a double-click
      } else if (this.mode === "trackpad") {
        this.phase = "move";
      } else {
        this.phase = "scroll"; // touch mode: a swipe scrolls, like on any phone
      }
      // Continue below and deliver this first meaningful delta. Dropping it made every
      // pointer/scroll gesture feel sticky by one event, especially on 120 Hz phones.
    }

    this.lastX = p.x; this.lastY = p.y;

    if (this.mode === "trackpad" && this.relativeTrackpad() && this.cb.moveRelative &&
        (this.phase === "drag" || this.phase === "move")) {
      const d = rotateDelta(dx, dy, this.isRotated());
      const gain = TRACKPAD_GAIN * this.getSensitivity();
      this.qRelative = {dx: (this.qRelative?.dx ?? 0) + d.dx * gain,
        dy: (this.qRelative?.dy ?? 0) + d.dy * gain};
      this.scheduleFlush();
      return;
    }
    if (this.phase === "drag") {
      const t = this.mode === "trackpad" ? this.nudge(dx, dy) : this.toNorm(p.x, p.y);
      this.queueMove(t.x, t.y, true);
    } else if (this.phase === "move") {
      const t = this.nudge(dx, dy);
      this.queueMove(t.x, t.y, false);
    } else if (this.phase === "scroll") {
      // MoOS traditional scroll: swipe up scrolls up the page (owner preference). Turned with the
      // picture, because on a rotated view the phone's "up" is the desktop's "right".
      const d = rotateDelta(dx, dy, this.isRotated());
      this.qScrollX += d.dx;
      this.qScrollY += d.dy;
      this.scheduleFlush();
    }
  };

  /**
   * The system took this touch away — an iOS edge swipe, a notification pull-down, palm rejection.
   *
   * This used to be wired straight to onUp, which is the one thing it must not be: onUp's whole job is
   * to decide what the gesture MEANT and emit it, so a stolen touch was delivered to the remote
   * desktop as a click — or, after a 500ms rest, a RIGHT click — that the user never made. Opening
   * Notification Centre over the canvas would fire a context menu on the server.
   *
   * A cancelled gesture meant nothing. Release anything actually held so no button is left down, and
   * emit nothing else.
   */
  private onCancel = (e: PointerEvent) => {
    if (this.inert || !this.pointers.has(e.pointerId)) return;
    e.preventDefault();
    this.cancelAll();
  };

  // ---------------- up ----------------
  private onUp = (e: PointerEvent) => {
    if (this.inert) return;
    const p = this.pointers.get(e.pointerId);
    if (!p) return;
    e.preventDefault();
    // pointerup can carry a final position with no preceding pointermove.
    if (p.x !== e.clientX || p.y !== e.clientY) this.onMove(e);
    this.flush();
    this.pointers.delete(e.pointerId);
    try { this.el.releasePointerCapture?.(e.pointerId); } catch { /* */ }

    if (this.two) {
      if (this.pointers.size === 0) {
        // TWO-FINGER TAP = RIGHT CLICK, which was missing entirely.
        //
        // Right-click was only reachable by resting a finger for 500ms. That is slow, it is
        // undiscoverable, and it fails the moment the finger drifts past the slop — so on a desktop,
        // where the context menu is half the interface, the second mouse button was effectively absent.
        // A two-finger tap is what iOS, Android, and every remote-desktop client use for it.
        //
        // Guarded on the gesture never having become a pinch or a scroll, and on being brief: two
        // fingers that zoomed, panned or scrolled are not a tap, however they end.
        if (this.twoMode === "undecided" && now() - this.twoStart < TAP_RESCUE_MS && !this.outside) {
          // ...unless this is the SECOND two-finger tap in quick succession, in which case it is the
          // zoom shortcut and the first tap's right-click has already been sent. Sending a second
          // context menu on top of it would be actively wrong (the menu would eat the zoom), so the
          // pair is resolved here rather than by delaying every right-click to wait for a partner.
          const t = now();
          if (t - this.lastTwoTapAt < TWO_TAP_MS
              && dist(this.lastCx, this.lastCy, this.lastTwoTapCx, this.lastTwoTapCy) < DOUBLE_TAP_PX
              && this.cb.zoomToggleAt) {
            this.lastTwoTapAt = -Infinity;
            // Zoom is local view navigation; never send a synthetic left click that could select
            // an item in the context menu opened by the first tap.
            this.cb.dismissContext?.();
            this.cb.zoomToggleAt(this.lastCx, this.lastCy);
            this.cb.haptic?.();
          } else {
            this.lastTwoTapAt = t;
            this.lastTwoTapCx = this.lastCx; this.lastTwoTapCy = this.lastCy;
            this.cb.click("right", this.cx, this.cy);
            this.cb.haptic?.();
          }
        }
        this.two = false; this.phase = "idle"; this.cancelLong();
        this.startGlide();
      }
      return;
    }
    this.cancelLong();
    this.flush(); // never let a queued move land after the button event

    // Before the switch, not inside it: this is what also suppresses the late TAP_RESCUE click
    // below, which would otherwise resurrect exactly the click we are trying not to send.
    // Scrolling that began in the black is left alone — only the click on release is dropped.
    if (this.outside) { this.outside = false; this.phase = "idle"; return; }

    switch (this.phase) {
      case "drag":
        this.cb.dragEnd(this.cx, this.cy);
        break;
      case "held":
        this.cb.click("right", this.cx, this.cy);
        this.lastTapAt = -Infinity;
        break;
      case "down": {
        // A plain tap. Two taps in a row are a DOUBLE-CLICK, but the FIRST tap was already sent
        // immediately so ordinary taps never pay a 300ms recognition delay. The second tap must
        // therefore add exactly ONE click — not call the agent's dblclick verb, which itself
        // injects two presses and turns the pair into a triple-click.
        //
        // Every tap is an absolute warp to wherever the finger was, and one CSS pixel of screen is
        // 2.5-4.4 logical desktop pixels once the picture is fitted to a phone. So three pixels of
        // ordinary thumb wobble put the second click 7-13 logical pixels from the first — past the
        // ~5px radius Qt and GTK both require before they will call it a double-click. Double-tap
        // to open a folder therefore worked only by luck, which reads as "the app is buggy".
        //
        // Force that second click to the FIRST tap's point. The browser's two touch points can
        // wobble several logical desktop pixels apart after fitting a 4K desktop to a phone; using
        // one point gives Qt/GTK the same-position pair they require without adding a third press.
        const quick = now() - p.st < 500;
        if (quick) {
          const near = dist(p.sx, p.sy, this.lastTapCX, this.lastTapCY) < DOUBLE_TAP_PX;
          if (now() - this.lastTapAt < DOUBLE_TAP_MS && near) {
            // The FIRST tap's point: it is the one the user aimed, before any wobble.
            if (!(this.mode === "trackpad" && this.relativeTrackpad()))
              this.moveTo(this.lastTapNx, this.lastTapNy, false);
            this.cb.click("left", this.lastTapNx, this.lastTapNy);
            this.cb.haptic?.();
            this.lastTapAt = -Infinity;   // a triple tap is not two double-clicks
          } else {
            this.cb.click("left", this.cx, this.cy);
            this.lastTapAt = now();
            this.lastTapCX = p.sx; this.lastTapCY = p.sy;
            this.lastTapNx = this.cx; this.lastTapNy = this.cy;
          }
        }
        break;
      }
      case "scroll":
      case "move": {
        this.lastTapAt = -Infinity;
        // THE LATE COMMIT, and the reason a tap can no longer vanish.
        //
        // Deciding what a gesture is on its first movement means deciding before the evidence is in.
        // A finger that travelled 14px in 90ms and stopped is a tap that wobbled; a finger that
        // travelled 14px in 600ms was aiming somewhere. Only the end of the gesture knows which, so
        // ask here: short and small is a tap, and it clicks where it started rather than nowhere.
        //
        // Safe against double-firing because the scroll deltas that went out for a movement this
        // small are a pixel or two — below anything a person can see, let alone intend.
        if (this.mode !== "trackpad" && now() - p.st < TAP_RESCUE_MS && p.travel < TAP_RESCUE_PX) {
          const s = this.toNorm(p.sx, p.sy);   // where the finger LANDED, not where it drifted to
          this.moveTo(s.x, s.y, false);
          this.cb.click("left", s.x, s.y);
        }
        break;
      }
    }
    this.phase = "idle";
  };

  // ---------------- two fingers ----------------
  private beginTwo() {
    this.cancelLong();
    this.flush(); // preserve move-before-release ordering when a second finger interrupts a drag
    this.lastTapAt = -Infinity;
    const interrupted = this.phase === "drag" || this.phase === "move" || this.phase === "scroll";
    this.vx = this.vy = 0;
    this.lastMoveAt = 0;
    // A gesture that turned out to be two-fingered must not leave a button held down.
    if (this.phase === "drag") this.cb.dragEnd(this.cx, this.cy);
    this.phase = "idle";
    this.two = true;
    // A fresh two-finger gesture has decided nothing yet. Resetting here and not on release is what
    // makes two pinches in a row each get their own decision.
    this.twoMode = interrupted ? "moved" : "undecided";
    this.twoPinching = false;
    this.twoStart = now();
    const [a, b] = [...this.pointers.values()];
    this.lastCx = (a.x + b.x) / 2; this.lastCy = (a.y + b.y) / 2;
    this.lastDist = dist(a.x, a.y, b.x, b.y);
    this.twoStartDist = this.lastDist;
    this.twoStartCx = this.lastCx; this.twoStartCy = this.lastCy;
  }

  /** Process the latest position of both fingers together, once per animation frame. */
  private moveTwo() {
    const pts = [...this.pointers.values()];
    if (pts.length < 2) return;
    const [a, b] = pts;
    const cx = (a.x + b.x) / 2, cy = (a.y + b.y) / 2;
    const d = dist(a.x, a.y, b.x, b.y);

    // ── Two fingers do BOTH, the way a photo viewer does ────────────────────
    //
    // This used to pick ONE mode per gesture from whichever accumulator was
    // larger after 10 px, and live it out to the end. Every real pinch also
    // drifts, so a pinch could latch to "scroll" and never zoom again — the
    // "two-finger control is hard" report. And a pan that started as a pinch
    // could never scroll. Guessing the user's intent from 10 px of noise was
    // the mistake; there is no need to guess.
    //
    // Now: spreading always zooms (past a small engage threshold, so ordinary
    // scroll jitter does not creep the picture), and translating always moves —
    // panning the axes the picture OVERFLOWS on and scrolling the remote on the
    // axes that fit. Both can happen in the same frame, which is what a pinch
    // actually is.
    // Net displacement, not accumulated noise: stationary fingers can jitter indefinitely without
    // becoming a pinch. Wait for real intent so a two-finger tap does not scroll the context target.
    const spread = Math.abs(d - this.twoStartDist);
    if (spread > PINCH_ENGAGE_PX) this.twoPinching = true;
    if (this.twoMode === "undecided") {
      if (!this.twoPinching && dist(cx, cy, this.twoStartCx, this.twoStartCy) <= MOVE_THRESHOLD) return;
      this.twoMode = "moved";
      this.lastTwoTapAt = -Infinity;
    }

    if (this.twoPinching && this.lastDist > 0 && d > 0) {
      const factor = d / this.lastDist;
      if (Math.abs(factor - 1) > 0.004) this.cb.zoomAt(factor, cx, cy);
    }

    {
      const dcx = cx - this.lastCx, dcy = cy - this.lastCy;
      // Pan the axis the picture OVERFLOWS on; scroll the axis that fits.
      //
      // The test is overflow, not `zoom > 1.01`: in "100%" view the base is
      // 1/dpr, so a phone can be showing half the desktop at zoom exactly 1.00 —
      // the old gate stayed false and the other half was simply unreachable.
      const pan = this.canPan();
      let scrolled = false;
      if (pan.x || pan.y) {
        const px = pan.x ? dcx : 0, py = pan.y ? dcy : 0;
        this.cb.panBy(px, py);
        // Track the velocity of the PAN only. A two-finger scroll must not fling:
        // the remote's own scroll view has whatever inertia it has, and a second
        // one on top would send phantom notches after the fingers were gone.
        this.sample(px, py);
      }
      // Scrolling means "move the content on the DESKTOP", so it turns with the
      // picture; panning above moves the drawn box on THIS screen and does not.
      // Overflow is in screen space. Mask there BEFORE rotating to desktop space, otherwise a
      // turned view scrolls the overflowing axis and discards the axis that actually fits.
      const sd = rotateDelta(pan.x ? 0 : dcx, pan.y ? 0 : dcy, this.isRotated());
      this.qScrollX += sd.dx; this.qScrollY += sd.dy;
      scrolled = sd.dx !== 0 || sd.dy !== 0;
      if (scrolled) this.scheduleFlush();
    }
    this.lastCx = cx; this.lastCy = cy; this.lastDist = d;
  }

  // ---------------- momentum ----------------

  /** Fold one movement into the velocity estimate, normalised to a 60Hz frame. */
  private sample(dx: number, dy: number) {
    const t = now();
    const dt = this.lastMoveAt ? Math.max(1, t - this.lastMoveAt) : 16;
    this.lastMoveAt = t;
    // A pointermove can arrive at 120Hz or, after a hitch, 200ms late. Per-frame velocity is the
    // unit the glide below decays in, so convert here rather than assuming a cadence.
    const fx = (dx / dt) * 16.67, fy = (dy / dt) * 16.67;
    this.vx = this.vx * (1 - V_SMOOTH) + fx * V_SMOOTH;
    this.vy = this.vy * (1 - V_SMOOTH) + fy * V_SMOOTH;
  }

  /** Let go: glide on if the release was fast enough to have meant it. */
  private startGlide() {
    this.stopGlide();
    // A release that follows a pause is a placement, not a throw — the fingers were already still.
    if (now() - this.lastMoveAt > 90) { this.vx = this.vy = 0; return; }
    const clampV = (v: number) => Math.max(-MAX_FLING_V, Math.min(MAX_FLING_V, v));
    let vx = clampV(this.vx), vy = clampV(this.vy);
    this.vx = this.vy = 0;
    if (Math.hypot(vx, vy) < MIN_FLING_V) return;
    let lastFrame = now();
    const step = () => {
      const t = now();
      const frames = Math.max(0, Math.min(32, t - lastFrame)) / 16.67;
      lastFrame = t;
      const decay = PAN_DECAY ** frames;
      // Integrate the same decay at 60, 90 and 120 Hz; high-refresh phones must not fling twice as fast.
      const travel = (1 - decay) / (1 - PAN_DECAY);
      this.cb.panBy(vx * travel, vy * travel);
      vx *= decay; vy *= decay;
      if (Math.hypot(vx, vy) < MIN_FLING_V) { this.glide = 0; return; }
      this.glide = requestAnimationFrame(step);
    };
    this.glide = requestAnimationFrame(step);
  }

  /** Any new touch cancels the glide — the finger is the authority, always. */
  private stopGlide() {
    if (this.glide) { cancelAnimationFrame(this.glide); this.glide = 0; }
  }

  // ---------------- cursor ----------------

  /**
   * Trackpad mode: convert a finger delta into a new absolute position.
   *
   * Turned with the picture, and the DIVISORS turn with it too — which is the part that is easy to
   * miss. On a rotated view the desktop's x axis runs down the tall side of the phone, so a
   * horizontal finger movement has to be divided by the surface's WIDTH while it advances the
   * desktop's y, and vice versa. Getting only the numerator right leaves the pointer moving in the
   * correct direction at visibly the wrong speed on each axis.
   */
  private nudge(dx: number, dy: number) {
    const r = this.el.getBoundingClientRect();
    const g = TRACKPAD_GAIN * this.getSensitivity();
    const rot = this.isRotated();
    const d = rotateDelta(dx, dy, rot);
    const denomX = Math.max(1, rot ? r.height : r.width);
    const denomY = Math.max(1, rot ? r.width : r.height);
    return {
      x: clamp01(this.cx + (d.dx * g) / denomX),
      y: clamp01(this.cy + (d.dy * g) / denomY),
    };
  }

  private moveTo(nx: number, ny: number, drag: boolean) {
    this.cx = nx; this.cy = ny;
    this.cb.cursorAt(nx, ny);
    if (drag) this.cb.dragMove(nx, ny);
    else this.cb.moveCursor(nx, ny);
  }

  // ---------------- output coalescing ----------------
  private queueMove(nx: number, ny: number, drag: boolean) {
    this.cx = nx; this.cy = ny;
    this.cb.cursorAt(nx, ny);   // draw at full rAF rate; only the network send is coalesced
    this.qMove = { nx, ny, drag };
    this.scheduleFlush();
  }

  private scheduleFlush() {
    if (this.raf) return;
    this.raf = requestAnimationFrame(() => { this.raf = 0; this.flush(); });
  }

  private flush() {
    if (this.raf) { cancelAnimationFrame(this.raf); this.raf = 0; }
    if (this.qTwo) { this.qTwo = false; this.moveTwo(); }
    if (this.qRelative) {
      const d = this.qRelative; this.qRelative = null;
      this.cb.moveRelative?.(d.dx, d.dy);
    }
    if (this.qMove) {
      const m = this.qMove;
      this.qMove = null;
      if (m.drag) this.cb.dragMove(m.nx, m.ny);
      else this.cb.moveCursor(m.nx, m.ny);
    }
    if (this.qScrollX || this.qScrollY) {
      this.cb.scroll(this.qScrollX / PX_PER_NOTCH, this.qScrollY / PX_PER_NOTCH);
      this.qScrollX = 0; this.qScrollY = 0;
    }
  }

  private endAll() {
    // Discard uncommitted work before releasing. A queued drag/scroll must never escape after
    // blur, cancellation, a mode switch or disconnection, even if its animation frame still runs.
    if (this.raf) { cancelAnimationFrame(this.raf); this.raf = 0; }
    this.qMove = null; this.qRelative = null; this.qScrollX = this.qScrollY = 0; this.qTwo = false;
    if (this.phase === "drag") this.cb.dragEnd(this.cx, this.cy);
    this.outside = false;
    this.lastTapAt = -Infinity;
    this.lastTwoTapAt = -Infinity;
    this.phase = "idle";
    this.two = false;
    const ids = [...this.pointers.keys()];
    this.pointers.clear();
    for (const id of ids) { try { this.el.releasePointerCapture?.(id); } catch { /* */ } }
    this.cancelLong();
    this.stopGlide();
    this.vx = this.vy = 0;
  }

  private cancelLong() { if (this.longTimer) { window.clearTimeout(this.longTimer); this.longTimer = null; } }
}

const now = () => performance.now();
const dist = (x1: number, y1: number, x2: number, y2: number) => Math.hypot(x1 - x2, y1 - y2);
const clamp01 = (v: number) => Math.min(1, Math.max(0, v));
