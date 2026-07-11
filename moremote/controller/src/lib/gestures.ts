import type { GestureMode } from "../types";

export interface GestureCallbacks {
  click: (button: "left" | "right", nx: number, ny: number) => void;
  doubleClick: (nx: number, ny: number) => void;
  moveCursor: (nx: number, ny: number) => void; // absolute move
  moveRelative: (dxPx: number, dyPx: number) => void;
  dragStart: (nx: number, ny: number) => void;
  dragMove: (nx: number, ny: number) => void;
  dragEnd: (nx: number, ny: number) => void;
  scroll: (dxNotches: number, dyNotches: number) => void;
  zoomAt: (factor: number, clientX: number, clientY: number) => void;
  panBy: (dxPx: number, dyPx: number) => void;
  cursorAt: (nx: number, ny: number) => void; // visual indicator
  haptic?: () => void;
}

interface Ptr { id: number; x: number; y: number; sx: number; sy: number; st: number; }

const MOVE_THRESHOLD = 10;
const LONGPRESS_MS = 500;
const DOUBLETAP_MS = 280;
const DOUBLETAP_DIST = 34;
const PX_PER_NOTCH = 26;
const TRACKPAD_GAIN = 1.8;

/**
 * Three control modes:
 *  - touch    : touchscreen feel — tap = click, swipe = scroll, long-press = right click
 *  - trackpad : laptop-trackpad — drag = relative cursor move, two-finger = scroll
 *  - direct   : press-drag — tap = click, drag = hold-and-drag (move windows / select)
 * Double-tap → real double click. Two fingers → pinch-zoom the view (+ pan when zoomed).
 */
export class GestureController {
  private pointers = new Map<number, Ptr>();
  private mode: GestureMode = "touch";

  private phase: "idle" | "down" | "point" | "scroll" | "drag" | "trackdrag" | "long" = "idle";
  private longTimer: number | null = null;

  // tap / double-tap
  private singleTimer: number | null = null;
  private isSecondTap = false;
  private lastTapT = 0;
  private lastTapX = 0;
  private lastTapY = 0;

  // scrolling
  private lastMoveX = 0;
  private lastMoveY = 0;

  // trackpad virtual cursor
  private vx = 0.5;
  private vy = 0.5;

  // two-finger
  private two = false;
  private lastCx = 0;
  private lastCy = 0;
  private lastDist = 0;
  private twoStarted=0;
  private twoMoved=false;

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
  ) {
    el.addEventListener("pointerdown", this.onDown, { passive: false });
    el.addEventListener("pointermove", this.onMove, { passive: false });
    el.addEventListener("pointerup", this.onUp, { passive: false });
    el.addEventListener("pointercancel", this.onUp, { passive: false });
    el.addEventListener("contextmenu", this.prevent, { passive: false });
  }

  setMode(m: GestureMode) {
    this.mode = m;
    this.resetSingle();
  }

  destroy() {
    this.el.removeEventListener("pointerdown", this.onDown);
    this.el.removeEventListener("pointermove", this.onMove);
    this.el.removeEventListener("pointerup", this.onUp);
    this.el.removeEventListener("pointercancel", this.onUp);
    this.el.removeEventListener("contextmenu", this.prevent);
    for (const id of this.pointers.keys()) { try { this.el.releasePointerCapture?.(id); } catch { /* */ } }
    this.pointers.clear();
    this.clearTimers();
    if (this.raf) cancelAnimationFrame(this.raf);
  }

  private prevent = (e: Event) => e.preventDefault();

  // ---------------- down ----------------
  private onDown = (e: PointerEvent) => {
    e.preventDefault();
    try { this.el.setPointerCapture(e.pointerId); } catch { /* */ }
    const p: Ptr = { id: e.pointerId, x: e.clientX, y: e.clientY, sx: e.clientX, sy: e.clientY, st: now() };
    this.pointers.set(e.pointerId, p);

    if (this.pointers.size === 2) { this.beginTwo(); return; }
    if (this.pointers.size > 2) return;

    this.clearTimers();
    this.isSecondTap =
      now() - this.lastTapT < DOUBLETAP_MS && dist(e.clientX, e.clientY, this.lastTapX, this.lastTapY) < DOUBLETAP_DIST;
    this.phase = "down";
    this.lastMoveX = e.clientX;
    this.lastMoveY = e.clientY;

    if (!this.isSecondTap) {
      this.longTimer = window.setTimeout(() => {
        if (this.phase === "down") {
          this.phase = "long";
          const t = this.target(p);
          this.cb.haptic?.();
          this.cb.cursorAt(t.x, t.y);
          this.cb.click("right", t.x, t.y);
        }
      }, LONGPRESS_MS);
    }
  };

  // ---------------- move ----------------
  private onMove = (e: PointerEvent) => {
    const p = this.pointers.get(e.pointerId);
    if (!p) return;
    e.preventDefault();
    p.x = e.clientX; p.y = e.clientY;

    if (this.two && this.pointers.size >= 2) { this.moveTwo(); return; }
    if (this.pointers.size !== 1) return;

    const far = dist(p.x, p.y, p.sx, p.sy) > MOVE_THRESHOLD;
    if (this.phase === "down" && far) {
      this.cancelLong();
      const secondTapDrag = this.isSecondTap;
      this.isSecondTap = false; // after choosing the gesture it is no longer a tap
      if(this.mode==="trackpad"&&secondTapDrag){this.phase="trackdrag";this.cb.dragStart(this.vx,this.vy);
      } else if (this.mode === "direct") {
        this.phase = "drag";
        const s = this.toNorm(p.sx, p.sy);
        this.cb.dragStart(s.x, s.y);
      } else {
        this.phase = this.mode === "touch" ? "point" : "scroll";
        if (this.mode === "touch") {
          const s = this.toNorm(p.sx, p.sy);
          this.cb.moveCursor(s.x, s.y); // aim the wheel at the touch point
          this.cb.cursorAt(s.x, s.y);
        }
      }
      this.lastMoveX = p.x; this.lastMoveY = p.y;
    }

    if(this.phase==="trackdrag"){
      const dx=p.x-this.lastMoveX,dy=p.y-this.lastMoveY;this.lastMoveX=p.x;this.lastMoveY=p.y;
      if(Math.hypot(dx,dy)>=.7)this.cb.moveRelative(dx*TRACKPAD_GAIN,dy*TRACKPAD_GAIN);
    } else if (this.phase === "drag") {
      const t = this.toNorm(p.x, p.y);
      this.queueMove(t.x, t.y, true);
      this.cb.cursorAt(t.x, t.y);
    } else if(this.phase==="point"){
      const t=this.toNorm(p.x,p.y);this.queueMove(t.x,t.y,false);this.cb.cursorAt(t.x,t.y);
    } else if (this.phase === "scroll") {
      const dx = p.x - this.lastMoveX;
      const dy = p.y - this.lastMoveY;
      this.lastMoveX = p.x; this.lastMoveY = p.y;
      if (this.mode === "trackpad") {
        const gain = Math.hypot(dx, dy) > 14 ? TRACKPAD_GAIN * 1.25 : TRACKPAD_GAIN;
        if (Math.hypot(dx,dy) >= 0.7) this.cb.moveRelative(dx * gain, dy * gain);
      } else {
        // touch mode: one finger scrolls
        this.qScrollX += dx; this.qScrollY += dy;
        this.scheduleFlush();
      }
    }
  };

  // ---------------- up ----------------
  private onUp = (e: PointerEvent) => {
    const p = this.pointers.get(e.pointerId);
    this.pointers.delete(e.pointerId);
    try { this.el.releasePointerCapture?.(e.pointerId); } catch { /* */ }

    if (this.two) {
      if (this.pointers.size < 2) { if(!this.twoMoved&&now()-this.twoStarted<350)this.cb.click("right",this.vx,this.vy);this.two = false; this.phase = "idle"; this.clearTimers(); }
      return;
    }
    if (!p) return;
    this.cancelLong();

    const moved = dist(p.x, p.y, p.sx, p.sy) > MOVE_THRESHOLD;
    const quick = now() - p.st < 400;

    if (this.phase === "drag") { const t = this.toNorm(p.x, p.y); this.cb.dragEnd(t.x, t.y); this.phase = "idle"; return; }
    if(this.phase==="trackdrag"){this.cb.dragEnd(this.vx,this.vy);this.phase="idle";return;}
    if (this.phase === "long") { this.phase = "idle"; this.lastTapT = 0; return; }
    if (this.phase === "scroll") { this.phase = "idle"; this.lastTapT = 0; return; }
    if(this.phase==="point"){this.phase="idle";this.lastTapT=0;return;}

    if (this.phase === "down" && !moved && quick) this.handleTap(this.target(p), p.x, p.y);
    this.phase = "idle";
  };

  // ---------------- tap / double-tap ----------------
  private handleTap(t: { x: number; y: number }, clientX: number, clientY: number) {
    this.cb.cursorAt(t.x, t.y);
    if (this.isSecondTap) {
      if (this.singleTimer) { window.clearTimeout(this.singleTimer); this.singleTimer = null; }
      this.cb.haptic?.();
      this.cb.doubleClick(t.x, t.y);
      this.lastTapT = 0;
      this.isSecondTap = false;
      return;
    }
    this.lastTapT = now();
    this.lastTapX = clientX;
    this.lastTapY = clientY;
    if (this.singleTimer) window.clearTimeout(this.singleTimer);
    this.singleTimer = window.setTimeout(() => {
      this.cb.click("left", t.x, t.y);
      this.singleTimer = null;
    }, DOUBLETAP_MS);
  }

  /** the cursor target for the current pointer, per mode */
  private target(p: Ptr): { x: number; y: number } {
    if (this.mode === "trackpad") return { x: this.vx, y: this.vy };
    return this.toNorm(p.x, p.y);
  }

  // ---------------- two fingers ----------------
  private beginTwo() {
    this.cancelLong();
    if (this.singleTimer) { window.clearTimeout(this.singleTimer); this.singleTimer = null; }
    this.phase = "idle";
    this.two = true;
    this.twoStarted=now();this.twoMoved=false;
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
    if(Math.hypot(cx-this.lastCx,cy-this.lastCy)>4||Math.abs(d-this.lastDist)>4)this.twoMoved=true;

    if (this.lastDist > 0) {
      const factor = d / this.lastDist;
      if (Math.abs(factor - 1) > 0.001) this.cb.zoomAt(factor, cx, cy);
    }
    const dcx = cx - this.lastCx, dcy = cy - this.lastCy;
    const zoomed = this.getZoom() > 1.01;
    if (zoomed) {
      this.cb.panBy(dcx, dcy);
    } else {
      this.qScrollX += dcx; this.qScrollY += dcy; this.scheduleFlush();
    }
    this.lastCx = cx; this.lastCy = cy; this.lastDist = d;
  }

  // ---------------- output coalescing ----------------
  private queueMove(nx: number, ny: number, drag: boolean) {
    this.qMove = { nx, ny, drag };
    this.scheduleFlush();
  }
  private scheduleFlush() {
    if (this.raf) return;
    this.raf = requestAnimationFrame(() => {
      this.raf = 0;
      if (this.qMove) {
        if (this.qMove.drag) this.cb.dragMove(this.qMove.nx, this.qMove.ny);
        else this.cb.moveCursor(this.qMove.nx, this.qMove.ny);
        this.qMove = null;
      }
      if (this.qScrollX || this.qScrollY) {
        this.cb.scroll(this.qScrollX / PX_PER_NOTCH, this.qScrollY / PX_PER_NOTCH);
        this.qScrollX = 0; this.qScrollY = 0;
      }
    });
  }

  private cancelLong() { if (this.longTimer) { window.clearTimeout(this.longTimer); this.longTimer = null; } }
  private clearTimers() {
    this.cancelLong();
    if (this.singleTimer) { window.clearTimeout(this.singleTimer); this.singleTimer = null; }
  }
  private resetSingle() { this.phase = "idle"; this.clearTimers(); this.two = false; this.pointers.clear(); }
}

const now = () => performance.now();
const dist = (x1: number, y1: number, x2: number, y2: number) => Math.hypot(x1 - x2, y1 - y2);
