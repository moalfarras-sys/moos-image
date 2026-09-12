/**
 * Real mouse and real keyboard, for when the viewer is a COMPUTER and not a phone.
 *
 * WHY THIS IS A SEPARATE FILE FROM gestures.ts
 *
 * gestures.ts translates fingers into intent: a tap has to become a click, a swipe has to become a
 * scroll, a long press has to become a right-click, and every one of those is a guess that has to
 * be made from a single contact point. On a computer there is nothing to guess. There are three
 * buttons, a wheel with a sign, a cursor with its own position, and a keyboard with ~100 physical
 * keys — so the correct translation is no translation. Mixing the two would mean every gesture
 * heuristic gets an "unless it is a mouse" branch, which is how both paths end up subtly wrong.
 *
 * The two are mutually exclusive: GestureController goes inert while mode is "desktop" (it listens
 * on pointer events, which a mouse also raises, so leaving it live would double every click).
 *
 * WHAT "FULL SUPPORT" ACTUALLY REQUIRES, AND WHERE EACH PIECE LIVES
 *
 *   left / middle / right      MouseEvent.button 0/1/2 -> the agent's existing three-button path
 *   drag                       mousedown ... mouseup, with the release caught on WINDOW so that
 *                              letting go outside the canvas still releases the remote button
 *   wheel, both axes           WheelEvent, with deltaMode normalised to notches
 *   held navigation / games   physical down+up, so the REMOTE's repeat timer drives repeat
 *   any shortcut               physical positions, because a keysym only reaches shift level 1
 *   text / keypad / repeat    the viewer's committed character, independent of host layout
 *   Esc / Tab / Ctrl+W         only capturable via the Keyboard Lock API, in fullscreen, Chromium
 *   composed text              the desktop input owns the IME commit — see sendText() below
 */

export interface DesktopCallbacks {
  move: (nx: number, ny: number) => void;
  moveRelative: (dx: number, dy: number) => void;
  down: (button: "left" | "middle" | "right", nx: number, ny: number) => void;
  up: (button: "left" | "middle" | "right", nx: number, ny: number) => void;
  /** positive dy = scroll down, exactly as a real wheel reports it */
  scroll: (dxNotches: number, dyNotches: number) => void;
  /** a PHYSICAL key position (KeyboardEvent.code) */
  keyCode: (code: string, down: boolean) => void;
  /** a CHARACTER, for when the viewer's layout disagrees with the wire */
  text: (value: string) => void;
  cursorAt: (nx: number, ny: number) => void;
  /**
   * The viewer pressed Ctrl/Cmd+V. The chord is deliberately NOT forwarded here — the owner waits
   * briefly for the browser's `paste` event, sends the local clipboard to the remote, and only then
   * presses Ctrl+V there. If no paste arrives (a browser that will not hand it over, nothing on the
   * clipboard) the owner forwards the chord anyway, so the key is never simply dead.
   */
  pasteIntent?: () => void;
  /** Focus the desktop IME input without opening the phone typing bar. */
  focusKeyboard?: () => void;
}

const BUTTONS = ["left", "middle", "right"] as const;
type Button = (typeof BUTTONS)[number];

// One wheel step in deltaMode 0 (pixels). Chromium reports 100 for a notch; the agent expands a notch
// back to 15 libinput pixels, so this pair is the whole scroll calibration and the two must be read
// together. 100/15 made a real wheel notch travel a seventh of the distance it should — which is why
// scrolling a page felt like dragging it. Matching the agent's own notch size removes the mismatch
// without touching the phone's gesture path, which is calibrated separately in gestures.ts.
const PX_PER_NOTCH = 15;
// deltaMode 1 counts text lines, and Firefox reports 3 of them for one physical detent — while
// Chromium reports deltaY 100 in pixel mode for the same detent. Dividing by a literal 3 therefore
// produced 1.0 wire notches on Firefox against 6.67 on Chromium, and the agent multiplies both by
// the same PixelsPerNotch — so one turn of the same wheel scrolled nearly seven times further on
// Chrome. Expressing the line divisor in terms of the pixel one makes a detent a detent in both.
// (PX_PER_NOTCH itself is deliberately untouched: the phone shares that calibration.)
const LINES_PER_NOTCH = 3 / (100 / PX_PER_NOTCH);   // = 0.45
const PAGES_TO_NOTCHES = 3; // deltaMode 2 is rare (Firefox on some platforms)
const MAX_NOTCHES = 20;     // the agent clamps here too; matching avoids a silent difference

export class DesktopInput {
  private attached = false;
  private held = new Set<Button>();
  private heldCodes = new Set<string>();
  private suspendedShift = new Set<string>();
  private locked = false;
  private cx = 0.5;
  private cy = 0.5;

  // rAF coalescing: a mouse can report far more moves than 60/s and every one of them would be a
  // websocket frame. Only the newest position in a frame can matter, so only it is sent.
  private raf = 0;
  private qMove: { nx: number; ny: number } | null = null;
  private qRel: { dx: number; dy: number } | null = null;
  private qScrollX = 0;
  private qScrollY = 0;

  constructor(
    private el: HTMLElement,
    private toNorm: (clientX: number, clientY: number) => { x: number; y: number },
    private cb: DesktopCallbacks,
    private getScrollSensitivity: () => number = () => 1,
    private getPointerLockWanted: () => boolean = () => false,
    private inContent: (clientX: number, clientY: number) => boolean = () => true,
  ) {}

  attach() {
    if (this.attached) return;
    this.attached = true;
    this.locked = document.pointerLockElement === this.el;
    this.el.addEventListener("mousedown", this.onDown, { passive: false });
    this.el.addEventListener("mousemove", this.onMove, { passive: false });
    this.el.addEventListener("wheel", this.onWheel, { passive: false });
    this.el.addEventListener("contextmenu", this.prevent, { passive: false });
    // Releases and keys go on window: a button released off-canvas, or a key pressed while the
    // toolbar has focus, still belongs to the remote desktop.
    window.addEventListener("mouseup", this.onUp, { passive: false });
    window.addEventListener("mousemove", this.onWindowMove, { passive: false });
    window.addEventListener("keydown", this.onKeyDown, { passive: false });
    window.addEventListener("keyup", this.onKeyUp, { passive: false });
    window.addEventListener("blur", this.releaseAll);
    document.addEventListener("visibilitychange", this.onVisibility);
    document.addEventListener("pointerlockchange", this.onLockChange);
  }

  detach() {
    if (!this.attached) return;
    this.attached = false;
    this.el.removeEventListener("mousedown", this.onDown);
    this.el.removeEventListener("mousemove", this.onMove);
    this.el.removeEventListener("wheel", this.onWheel);
    this.el.removeEventListener("contextmenu", this.prevent);
    window.removeEventListener("mouseup", this.onUp);
    window.removeEventListener("mousemove", this.onWindowMove);
    window.removeEventListener("keydown", this.onKeyDown);
    window.removeEventListener("keyup", this.onKeyUp);
    window.removeEventListener("blur", this.releaseAll);
    document.removeEventListener("visibilitychange", this.onVisibility);
    document.removeEventListener("pointerlockchange", this.onLockChange);
    this.releaseAll();
    this.releaseKeyboardLock();
    this.exitPointerLock();
    this.locked = false;
    if (this.raf) { cancelAnimationFrame(this.raf); this.raf = 0; }
  }

  destroy() { this.detach(); }

  /**
   * Hand the tab the keys the browser normally keeps (Esc, Tab, Ctrl+W, F11...).
   *
   * Only works in fullscreen and only on Chromium, and that is not a bug to route around: the API
   * exists precisely because a page that could silently swallow Ctrl+W and Esc outside fullscreen
   * would be able to trap the user in it. Called on fullscreen entry; failure is not an error.
   */
  async requestKeyboardLock() {
    const kb = (navigator as Navigator & { keyboard?: { lock?: (k?: string[]) => Promise<void> } }).keyboard;
    try { await kb?.lock?.(); } catch { /* not fullscreen, or not supported */ }
  }

  releaseKeyboardLock() {
    const kb = (navigator as Navigator & { keyboard?: { unlock?: () => void } }).keyboard;
    try { kb?.unlock?.(); } catch { /* */ }
  }

  requestPointerLock() {
    try { void Promise.resolve(this.el.requestPointerLock?.()).catch(() => {}); } catch { /* unsupported */ }
  }
  exitPointerLock() { try { if (document.pointerLockElement === this.el) document.exitPointerLock?.(); } catch { /* */ } }
  get pointerLocked() { return this.locked; }

  setCursor(nx: number, ny: number) { this.cx = nx; this.cy = ny; }

  /** Release everything the remote thinks is held. Must be idempotent — it runs on blur, on tab
   *  hide, and on teardown, and a double release must not turn into a phantom press. */
  releaseAll = () => {
    // Input queued before a tab switch/disconnect must not be delivered after the releases.
    if (this.raf) { cancelAnimationFrame(this.raf); this.raf = 0; }
    if (this.qMove) { this.cx = this.qMove.nx; this.cy = this.qMove.ny; }
    this.qMove = this.qRel = null;
    this.qScrollX = this.qScrollY = 0;
    for (const b of this.held) this.cb.up(b, this.cx, this.cy);
    this.held.clear();
    for (const c of this.heldCodes) this.cb.keyCode(c, false);
    this.heldCodes.clear();
    this.suspendedShift.clear();
  };

  // ---------------------------------------------------------------- mouse

  private prevent = (e: Event) => e.preventDefault();

  private onVisibility = () => { if (document.hidden) this.releaseAll(); };

  private onLockChange = () => {
    const wasLocked = this.locked;
    this.locked = document.pointerLockElement === this.el;
    if (wasLocked && !this.locked) this.releaseAll();
    // A pending absolute warp from before pointer lock would undo the first relative movement.
    if (this.locked) this.qMove = null;
  };

  private onDown = (e: MouseEvent) => {
    const b = BUTTONS[e.button];
    if (!b) return;                       // 3/4 are back/forward; the desktop has no use for them
    if (!this.locked && !this.inContent(e.clientX, e.clientY)) return;
    e.preventDefault();
    // Focus the canvas so keys land here rather than in whatever was focused before.
    if (this.cb.focusKeyboard) this.cb.focusKeyboard();
    else this.el.focus?.({ preventScroll: true });
    if (this.getPointerLockWanted() && !this.locked) this.requestPointerLock();
    this.flush();                         // flush before updating the cursor to the press position
    this.restoreShift(e);
    const p = this.locked ? { x: this.cx, y: this.cy } : this.toNorm(e.clientX, e.clientY);
    this.cx = p.x; this.cy = p.y;
    this.cb.cursorAt(p.x, p.y);
    this.held.add(b);
    this.cb.down(b, p.x, p.y);
  };

  private onUp = (e: MouseEvent) => {
    const b = BUTTONS[e.button];
    if (!b || !this.held.has(b)) return;   // a release we never saw the press for is not ours
    e.preventDefault();
    this.held.delete(b);
    this.flush();
    const p = this.locked ? { x: this.cx, y: this.cy } : this.toNorm(e.clientX, e.clientY);
    this.cx = p.x; this.cy = p.y;
    this.cb.cursorAt(p.x, p.y);
    this.cb.up(b, p.x, p.y);
  };

  private onMove = (e: MouseEvent) => {
    if (this.locked) {
      // Pointer lock exists for the case absolute positioning cannot serve: a 3D view or a game
      // that warps the cursor itself, where the local pointer would otherwise hit the window edge
      // and stop while the remote one is still mid-turn.
      const dx = e.movementX || 0, dy = e.movementY || 0;
      if (!dx && !dy) return;
      this.qRel = { dx: (this.qRel?.dx ?? 0) + dx, dy: (this.qRel?.dy ?? 0) + dy };
      this.schedule();
      return;
    }
    if (!this.held.size && !this.inContent(e.clientX, e.clientY)) return;
    const p = this.toNorm(e.clientX, e.clientY);
    this.qMove = { nx: p.x, ny: p.y };
    this.schedule();
  };

  private onWindowMove = (e: MouseEvent) => {
    if (this.held.size && e.target !== this.el) this.onMove(e);
  };

  private onWheel = (e: WheelEvent) => {
    if (!this.locked && !this.inContent(e.clientX, e.clientY)) return;
    e.preventDefault();
    this.restoreShift(e);
    if (!this.locked) {
      const p = this.toNorm(e.clientX, e.clientY);
      this.qMove = { nx: p.x, ny: p.y };
    }
    // deltaMode is the units the browser chose, and ignoring it is the classic wheel bug: the same
    // physical notch is ~100 in pixel mode and 3 in line mode, so reading deltaY raw makes the
    // remote scroll 30x too far on Firefox or 30x too little on Chromium, depending which one the
    // sensitivity was tuned against.
    const div = e.deltaMode === 1 ? LINES_PER_NOTCH
              : e.deltaMode === 2 ? 1 / PAGES_TO_NOTCHES
              : PX_PER_NOTCH;
    const s = this.getScrollSensitivity();
    // No natural-scroll inversion here on purpose. A wheel already reports the direction the user
    // turned it; the phone's setting exists because a swipe has no inherent direction.
    this.qScrollY += (e.deltaY / div) * s;
    this.qScrollX += (e.deltaX / div) * s;
    this.schedule();
  };

  // ---------------------------------------------------------------- keyboard

  /** Text follows the viewer's layout; named keys and shortcuts retain their positions.
   * Matching a US key table never proves the remote uses US: it may still be Arabic
   * after the previous text batch. Explicit pointer lock keeps physical game controls.
   */
  private decideKey(e: KeyboardEvent): "physical" | "character" | "ignore" {
    if (["Dead", "Process", "Unidentified", "AltGraph"].includes(e.key)) return "ignore";
    // Caps Lock belongs to the viewer's text layout. Its next e.key already has
    // the requested case; toggling the remote too would apply that case twice.
    if (e.key === "CapsLock" && !this.locked) return "ignore";
    if (e.getModifierState?.("AltGraph") && Array.from(e.key).length === 1) return "character";
    if (e.ctrlKey || e.altKey || e.metaKey || this.locked) return e.code ? "physical" : "ignore";
    return Array.from(e.key).length === 1 ? "character" : e.code ? "physical" : "ignore";
  }

  /** Text injection owns its shift level; leave held Shift available for the next shortcut. */
  private suspendShift() {
    for (const code of ["ShiftLeft", "ShiftRight"]) {
      if (this.heldCodes.delete(code)) {
        this.cb.keyCode(code, false);
        this.suspendedShift.add(code);
      }
    }
  }

  private restoreShift(e: {shiftKey: boolean}) {
    if (e.shiftKey) {
      for (const code of this.suspendedShift) {
        this.cb.keyCode(code, true);
        this.heldCodes.add(code);
      }
    }
    this.suspendedShift.clear();
  }

  /** Both key characters and IME commits own their shift level. */
  sendText(value: string) {
    if (!value || !this.attached) return;
    this.suspendShift();
    this.cb.text(value);
  }

  /**
   * Whether this keystroke belongs to the LOCAL page rather than the remote desktop.
   *
   * The controller has its own text fields — the PIN pad, "Send text", the file rename box — and a
   * remote-desktop layer that captured the keyboard unconditionally would make every one of them
   * impossible to type into, which looks like the app being frozen. Focus is the right arbiter:
   * if a local editable control has it, the keys are its own.
   */
  private localEditable(e: KeyboardEvent) {
    const t = e.target as HTMLElement | null;
    if (!t) return false;
    if (t.dataset?.remoteKeyboard === "true") return false;
    const tag = t.tagName;
    if (["INPUT", "TEXTAREA", "SELECT", "BUTTON", "SUMMARY", "A"].includes(tag) || t.isContentEditable) return true;
    // Sliders/buttons have keyboard behavior too. Clicking the focusable canvas returns control
    // to the desktop; arrows and Space while a local control owns focus must remain local.
    return Boolean(t.closest?.('button,input,textarea,select,summary,a[href],[role="button"],[role="dialog"],[role="slider"],[contenteditable="true"]'));
  }

  private onKeyDown = (e: KeyboardEvent) => {
    if (e.defaultPrevented) return;       // e.g. Escape already closed a local React dialog
    if (e.isComposing) return;             // an IME is mid-word; its commit arrives as input text
    if (this.localEditable(e)) return;
    if (e.getModifierState?.("AltGraph")) {
      // Some browsers already emitted a synthetic ControlLeft before announcing AltGraph. Retire
      // it before committed text, so AltGr+Q cannot become Ctrl+Alt+Q on the remote.
      for (const code of ["ControlLeft", "ControlRight", "AltLeft", "AltRight"]) {
        if (this.heldCodes.delete(code)) this.cb.keyCode(code, false);
      }
    }

    // PASTE IS THE ONE CHORD THAT MEANS SOMETHING DIFFERENT ON EACH SIDE OF THE WIRE.
    //
    // Every other shortcut is a position to forward. Ctrl+V is not: the user pressed it because
    // something is on THIS computer's clipboard, and forwarding the chord pastes whatever is on the
    // REMOTE's clipboard instead — usually nothing, occasionally something they copied an hour ago.
    // Copying a URL from your own browser and pasting it into the remote is the single most common
    // thing anyone does with a remote desktop, and it silently did the wrong thing.
    //
    // Preventing the default here would suppress the browser's `paste` event, which is the only way
    // a page is allowed to read the clipboard without a permission prompt. So this key alone is left
    // alone, and the owner listens for the paste (see the desktop paste bridge in RemoteScreen).
    if ((e.ctrlKey || e.metaKey) && !e.altKey && (e.code === "KeyV" || e.key === "v" || e.key === "V")) {
      this.cb.pasteIntent?.();
      return;                              // no preventDefault: let `paste` fire
    }

    const decision = this.decideKey(e);
    if (decision === "ignore") return;

    // preventDefault on EVERY key we forward, not just the ones the browser would visibly act on.
    //
    // The phone path types through a hidden input, and if that input still holds focus an
    // un-prevented keystroke reaches it too — so the character goes out once as a physical key and
    // once again through the text coalescer, and you get "aa" for every "a". Cheap to prevent,
    // invisible when it goes wrong, so prevent unconditionally.
    e.preventDefault();

    if (decision === "character") {
      // Repeats of a character key are real keystrokes (holding Backspace, holding a letter), so
      // they are forwarded rather than deduplicated the way the physical path does.
      this.sendText(e.key);
      return;
    }

    this.restoreShift(e);

    // The agent deduplicates a repeated down itself and lets the REMOTE repeat timer drive repeat,
    // so sending the repeats is harmless; not sending them saves a frame per repeat.
    if (e.repeat || this.heldCodes.has(e.code) || !e.code) return;
    this.heldCodes.add(e.code);
    this.cb.keyCode(e.code, true);
  };

  private onKeyUp = (e: KeyboardEvent) => {
    if (this.suspendedShift.delete(e.code)) { e.preventDefault(); return; }
    // Release by position unconditionally, and WITHOUT re-asking decideKey: a key pressed while the
    // layouts agreed must not stay down on the remote because a modifier changed before it came up.
    // Not gated on localEditable either — if focus moved into a text field mid-chord, the release
    // still has to arrive or Ctrl stays stuck on the server.
    if (this.heldCodes.delete(e.code)) {
      e.preventDefault();
      this.cb.keyCode(e.code, false);
    }
  };

  // ---------------------------------------------------------------- output

  private schedule() {
    if (this.raf) return;
    this.raf = requestAnimationFrame(() => { this.raf = 0; this.flush(); });
  }

  private flush() {
    if (this.raf) { cancelAnimationFrame(this.raf); this.raf = 0; }
    if (this.qMove) {
      const { nx, ny } = this.qMove; this.qMove = null;
      this.cx = nx; this.cy = ny;
      this.cb.cursorAt(nx, ny);
      this.cb.move(nx, ny);
    }
    if (this.qRel) {
      const { dx, dy } = this.qRel; this.qRel = null;
      this.cb.moveRelative(dx, dy);
    }
    if (this.qScrollX || this.qScrollY) {
      const dx = clamp(this.qScrollX), dy = clamp(this.qScrollY);
      // KEEP the sub-notch remainder instead of discarding it.
      //
      // This used to zero both accumulators unconditionally, which quietly made slow scrolling do
      // nothing at all: a trackpad emits a few pixels per frame, that is a small fraction of a notch,
      // clamp/round it away and the remainder was thrown out before it could ever add up to one. The
      // wheel worked and the trackpad appeared dead.
      //
      // On top of that the round trip was lossy by a factor of ~7: divided by PX_PER_NOTCH (100) here
      // and multiplied back by the agent's PixelsPerNotch (15) there. Sending the fraction and letting
      // it accumulate is what makes a slow scroll a slow scroll rather than a discarded one.
      this.qScrollX -= dx; this.qScrollY -= dy;
      if (dx || dy) this.cb.scroll(dx, dy);
    }
  }
}

function clamp(n: number) {
  return Math.max(-MAX_NOTCHES, Math.min(MAX_NOTCHES, n));
}
