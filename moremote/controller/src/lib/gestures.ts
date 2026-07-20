import type { GestureMode } from "../types";

export interface GestureCallbacks {
  click: (button: "left" | "right", nx: number, ny: number) => void;
  moveCursor: (nx: number, ny: number) => void; // absolute move
  dragStart: (nx: number, ny: number) => void;
  dragMove: (nx: number, ny: number) => void;
  dragEnd: (nx: number, ny: number) => void;
  /** positive dy = scroll down (content moves up), like a real wheel */
  scroll: (dxNotches: number, dyNotches: number) => void;
  zoomAt: (factor: number, clientX: number, clientY: number) => void;
  panBy: (dxPx: number, dyPx: number) => void;
  cursorAt: (nx: number, ny: number) => void; // where to draw the on-screen cursor
  haptic?: () => void;
}

interface Ptr { id: number; x: number; y: number; sx: number; sy: number; st: number; }

const MOVE_THRESHOLD = 5;
const LONGPRESS_MS = 500; // matches Android's own long-press feel, so a slow tap stays a tap
const PX_PER_NOTCH = 24;
const TRACKPAD_GAIN = 1.7;

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

  private phase: "idle" | "down" | "held" | "scroll" | "drag" | "move" = "idle";
  private longTimer: number | null = null;

  // last position we sent, normalized — the single source of truth for the cursor
  private cx = 0.5;
  private cy = 0.5;

  private lastX = 0;
  private lastY = 0;

  // two-finger
  private two = false;
  private lastCx = 0;
  private lastCy = 0;
  private lastDist = 0;

  // rAF-coalesced output
  private raf = 0;
  private qMove: { nx: number; ny: number; drag: boolean } | null = null;
  private qScrollX = 0;
  private qScrollY = 0;

  constructor(
    private el: HTMLElement,
    private toNorm: (clientX: number, clientY: number) => { x: number; y: number },
    private getZoom: () => number,
    private cb: GestureCallbacks,
    private getSensitivity: () => number = () => 1,
  ) {
    el.addEventListener("pointerdown", this.onDown, { passive: false });
    el.addEventListener("pointermove", this.onMove, { passive: false });
    el.addEventListener("pointerup", this.onUp, { passive: false });
    el.addEventListener("pointercancel", this.onUp, { passive: false });
    el.addEventListener("contextmenu", this.prevent, { passive: false });
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
    this.el.removeEventListener("pointercancel", this.onUp);
    this.el.removeEventListener("contextmenu", this.prevent);
    for (const id of this.pointers.keys()) { try { this.el.releasePointerCapture?.(id); } catch { /* */ } }
    this.endAll();   // tearing down mid-drag must still release the button
    if (this.raf) cancelAnimationFrame(this.raf);
  }

  private prevent = (e: Event) => e.preventDefault();

  // ---------------- down ----------------
  private onDown = (e: PointerEvent) => {
    e.preventDefault();
    try { this.el.setPointerCapture(e.pointerId); } catch { /* */ }
    this.pointers.set(e.pointerId, {
      id: e.pointerId, x: e.clientX, y: e.clientY, sx: e.clientX, sy: e.clientY, st: now(),
    });

    if (this.pointers.size === 2) { this.beginTwo(); return; }
    if (this.pointers.size > 2) return;

    this.cancelLong();
    this.phase = "down";
    this.lastX = e.clientX;
    this.lastY = e.clientY;

    // In the absolute modes the cursor goes under the finger straight away, so the desktop
    // hovers/highlights exactly what you are touching before you even lift.
    if (this.mode !== "trackpad") {
      const t = this.toNorm(e.clientX, e.clientY);
      this.moveTo(t.x, t.y, false);
    }

    // Hold = right-click on release, or drag if you move while still holding.
    this.longTimer = window.setTimeout(() => {
      if (this.phase !== "down") return;
      this.phase = "held";
      this.cb.haptic?.();
    }, LONGPRESS_MS);
  };

  // ---------------- move ----------------
  private onMove = (e: PointerEvent) => {
    const p = this.pointers.get(e.pointerId);
    if (!p) return;
    e.preventDefault();
    p.x = e.clientX; p.y = e.clientY;

    if (this.two && this.pointers.size >= 2) { this.moveTwo(); return; }
    if (this.pointers.size !== 1) return;

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
      } else if (this.mode === "trackpad") {
        this.phase = "move";
      } else {
        this.phase = "scroll"; // touch mode: a swipe scrolls, like on any phone
      }
      // Continue below and deliver this first meaningful delta. Dropping it made every
      // pointer/scroll gesture feel sticky by one event, especially on 120 Hz phones.
    }

    this.lastX = p.x; this.lastY = p.y;

    if (this.phase === "drag") {
      const t = this.mode === "trackpad" ? this.nudge(dx, dy) : this.toNorm(p.x, p.y);
      this.queueMove(t.x, t.y, true);
    } else if (this.phase === "move") {
      const t = this.nudge(dx, dy);
      this.queueMove(t.x, t.y, false);
    } else if (this.phase === "scroll") {
      this.qScrollX += dx;   // MoOS traditional scroll: swipe up scrolls up the page (owner preference)
      this.qScrollY += dy;
      this.scheduleFlush();
    }
  };

  // ---------------- up ----------------
  private onUp = (e: PointerEvent) => {
    const p = this.pointers.get(e.pointerId);
    this.pointers.delete(e.pointerId);
    try { this.el.releasePointerCapture?.(e.pointerId); } catch { /* */ }

    if (this.two) {
      if (this.pointers.size < 2) { this.two = false; this.phase = "idle"; this.cancelLong(); }
      return;
    }
    if (!p) return;
    this.cancelLong();
    this.flush(); // never let a queued move land after the button event

    switch (this.phase) {
      case "drag":
        this.cb.dragEnd(this.cx, this.cy);
        break;
      case "held":
        this.cb.click("right", this.cx, this.cy);
        break;
      case "down": {
        // A plain tap: click right away. Two taps in a row become a real double-click on the PC.
        const quick = now() - p.st < 500;
        if (quick) this.cb.click("left", this.cx, this.cy);
        break;
      }
    }
    this.phase = "idle";
  };

  // ---------------- two fingers ----------------
  private beginTwo() {
    this.cancelLong();
    // A gesture that turned out to be two-fingered must not leave a button held down.
    if (this.phase === "drag") this.cb.dragEnd(this.cx, this.cy);
    this.phase = "idle";
    this.two = true;
    const [a, b] = [...this.pointers.values()];
    this.lastCx = (a.x + b.x) / 2; this.lastCy = (a.y + b.y) / 2;
    this.lastDist = dist(a.x, a.y, b.x, b.y);
  }

  private moveTwo() {
    const pts = [...this.pointers.values()];
    if (pts.length < 2) return;
    const [a, b] = pts;
    const cx = (a.x + b.x) / 2, cy = (a.y + b.y) / 2;
    const d = dist(a.x, a.y, b.x, b.y);

    if (this.lastDist > 0) {
      const factor = d / this.lastDist;
      if (Math.abs(factor - 1) > 0.002) this.cb.zoomAt(factor, cx, cy);
    }
    const dcx = cx - this.lastCx, dcy = cy - this.lastCy;
    if (this.getZoom() > 1.01) {
      this.cb.panBy(dcx, dcy);       // zoomed in: two fingers pan the view
    } else {
      this.qScrollX += dcx;          // otherwise they scroll the remote screen (traditional direction)
      this.qScrollY += dcy;
      this.scheduleFlush();
    }
    this.lastCx = cx; this.lastCy = cy; this.lastDist = d;
  }

  // ---------------- cursor ----------------

  /** Trackpad mode: convert a finger delta into a new absolute position. */
  private nudge(dx: number, dy: number) {
    const r = this.el.getBoundingClientRect();
    const g = TRACKPAD_GAIN * this.getSensitivity();
    return {
      x: clamp01(this.cx + (dx * g) / Math.max(1, r.width)),
      y: clamp01(this.cy + (dy * g) / Math.max(1, r.height)),
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
    if (this.phase === "drag") this.cb.dragEnd(this.cx, this.cy);
    this.phase = "idle";
    this.two = false;
    this.pointers.clear();
    this.cancelLong();
  }

  private cancelLong() { if (this.longTimer) { window.clearTimeout(this.longTimer); this.longTimer = null; } }
}

const now = () => performance.now();
const dist = (x1: number, y1: number, x2: number, y2: number) => Math.hypot(x1 - x2, y1 - y2);
const clamp01 = (v: number) => Math.min(1, Math.max(0, v));
