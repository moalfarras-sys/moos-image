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
 *   held keys / key repeat     physical down+up, so the REMOTE's repeat timer drives repeat
 *   any shortcut               physical positions, because a keysym only reaches shift level 1
 *   the keypad as its own keys Numpad1 is not Digit1 and spreadsheets know the difference
 *   Esc / Tab / Ctrl+W         only capturable via the Keyboard Lock API, in fullscreen, Chromium
 *   other-layout text          falls back to the character path — see decideKey() below
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
}

const BUTTONS = ["left", "middle", "right"] as const;
type Button = (typeof BUTTONS)[number];

/**
 * What each physical key produces on a plain US layout, unshifted and shifted.
 *
 * This table is not here to type anything. It answers one question — "does the keyboard in front of
 * this person agree with the positions we are about to send?" — and it is the whole reason a desktop
 * viewer can have held keys AND correct Arabic in the same session. See decideKey().
 */
const US_LAYOUT: Record<string, [string, string]> = {
  KeyA: ["a", "A"], KeyB: ["b", "B"], KeyC: ["c", "C"], KeyD: ["d", "D"], KeyE: ["e", "E"],
  KeyF: ["f", "F"], KeyG: ["g", "G"], KeyH: ["h", "H"], KeyI: ["i", "I"], KeyJ: ["j", "J"],
  KeyK: ["k", "K"], KeyL: ["l", "L"], KeyM: ["m", "M"], KeyN: ["n", "N"], KeyO: ["o", "O"],
  KeyP: ["p", "P"], KeyQ: ["q", "Q"], KeyR: ["r", "R"], KeyS: ["s", "S"], KeyT: ["t", "T"],
  KeyU: ["u", "U"], KeyV: ["v", "V"], KeyW: ["w", "W"], KeyX: ["x", "X"], KeyY: ["y", "Y"],
  KeyZ: ["z", "Z"],
  Digit1: ["1", "!"], Digit2: ["2", "@"], Digit3: ["3", "#"], Digit4: ["4", "$"],
  Digit5: ["5", "%"], Digit6: ["6", "^"], Digit7: ["7", "&"], Digit8: ["8", "*"],
  Digit9: ["9", "("], Digit0: ["0", ")"],
  Minus: ["-", "_"], Equal: ["=", "+"], BracketLeft: ["[", "{"], BracketRight: ["]", "}"],
  Backslash: ["\\", "|"], Semicolon: [";", ":"], Quote: ["'", '"'], Backquote: ["`", "~"],
  Comma: [",", "<"], Period: [".", ">"], Slash: ["/", "?"], Space: [" ", " "],
  Numpad0: ["0", "0"], Numpad1: ["1", "1"], Numpad2: ["2", "2"], Numpad3: ["3", "3"],
  Numpad4: ["4", "4"], Numpad5: ["5", "5"], Numpad6: ["6", "6"], Numpad7: ["7", "7"],
  Numpad8: ["8", "8"], Numpad9: ["9", "9"], NumpadDecimal: [".", "."],
  NumpadAdd: ["+", "+"], NumpadSubtract: ["-", "-"], NumpadMultiply: ["*", "*"],
  NumpadDivide: ["/", "/"],
};

// One wheel step in deltaMode 0 (pixels). Chromium reports 100 for a notch; the agent expands a notch
// back to 15 libinput pixels, so this pair is the whole scroll calibration and the two must be read
// together. 100/15 made a real wheel notch travel a seventh of the distance it should — which is why
// scrolling a page felt like dragging it. Matching the agent's own notch size removes the mismatch
// without touching the phone's gesture path, which is calibrated separately in gestures.ts.
const PX_PER_NOTCH = 15;
const LINES_PER_NOTCH = 3;  // deltaMode 1 counts text lines
const PAGES_TO_NOTCHES = 3; // deltaMode 2 is rare (Firefox on some platforms)
const MAX_NOTCHES = 20;     // the agent clamps here too; matching avoids a silent difference

export class DesktopInput {
  private attached = false;
  private held = new Set<Button>();
  private heldCodes = new Set<string>();
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
  ) {}

  attach() {
    if (this.attached) return;
    this.attached = true;
    this.el.addEventListener("mousedown", this.onDown, { passive: false });
    this.el.addEventListener("mousemove", this.onMove, { passive: false });
    this.el.addEventListener("wheel", this.onWheel, { passive: false });
    this.el.addEventListener("contextmenu", this.prevent, { passive: false });
    // Releases and keys go on window: a button released off-canvas, or a key pressed while the
    // toolbar has focus, still belongs to the remote desktop.
    window.addEventListener("mouseup", this.onUp, { passive: false });
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
    window.removeEventListener("keydown", this.onKeyDown);
    window.removeEventListener("keyup", this.onKeyUp);
    window.removeEventListener("blur", this.releaseAll);
    document.removeEventListener("visibilitychange", this.onVisibility);
    document.removeEventListener("pointerlockchange", this.onLockChange);
    this.releaseAll();
    this.exitPointerLock();
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

  requestPointerLock() { try { this.el.requestPointerLock?.(); } catch { /* */ } }
  exitPointerLock() { try { if (document.pointerLockElement === this.el) document.exitPointerLock?.(); } catch { /* */ } }
  get pointerLocked() { return this.locked; }

  setCursor(nx: number, ny: number) { this.cx = nx; this.cy = ny; }

  /** Release everything the remote thinks is held. Must be idempotent — it runs on blur, on tab
   *  hide, and on teardown, and a double release must not turn into a phantom press. */
  releaseAll = () => {
    for (const b of this.held) this.cb.up(b, this.cx, this.cy);
    this.held.clear();
    for (const c of this.heldCodes) this.cb.keyCode(c, false);
    this.heldCodes.clear();
  };

  // ---------------------------------------------------------------- mouse

  private prevent = (e: Event) => e.preventDefault();

  private onVisibility = () => { if (document.hidden) this.releaseAll(); };

  private onLockChange = () => {
    this.locked = document.pointerLockElement === this.el;
  };

  private onDown = (e: MouseEvent) => {
    const b = BUTTONS[e.button];
    if (!b) return;                       // 3/4 are back/forward; the desktop has no use for them
    e.preventDefault();
    // Focus the canvas so keys land here rather than in whatever was focused before.
    (this.el as HTMLElement).focus?.({ preventScroll: true });
    if (this.getPointerLockWanted() && !this.locked) this.requestPointerLock();
    const p = this.locked ? { x: this.cx, y: this.cy } : this.toNorm(e.clientX, e.clientY);
    this.cx = p.x; this.cy = p.y;
    this.held.add(b);
    this.flush();                         // never let a queued move land after the press
    this.cb.down(b, p.x, p.y);
  };

  private onUp = (e: MouseEvent) => {
    const b = BUTTONS[e.button];
    if (!b || !this.held.has(b)) return;   // a release we never saw the press for is not ours
    e.preventDefault();
    this.held.delete(b);
    const p = this.locked ? { x: this.cx, y: this.cy } : this.toNorm(e.clientX, e.clientY);
    this.cx = p.x; this.cy = p.y;
    this.flush();
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
    const p = this.toNorm(e.clientX, e.clientY);
    this.qMove = { nx: p.x, ny: p.y };
    this.schedule();
  };

  private onWheel = (e: WheelEvent) => {
    e.preventDefault();
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

  /**
   * Physical position, or character?
   *
   * Physical is what makes a keyboard a keyboard: holding a key, every Ctrl-chord, the keypad, the
   * function row. But a position only produces the RIGHT character if the layout in front of the
   * viewer agrees with the one on the server — and on an Arabic or AZERTY keyboard it does not.
   *
   * So ask the browser. It reports both the position (`code`) and what that key actually produced
   * (`key`). If `key` is what a US layout would have produced from that position, the two agree and
   * the physical path is safe and better. If it disagrees — ش from KeyA, é from Digit2 — then the
   * viewer's layout is doing work the server's cannot reproduce, and the character path (which
   * types by keysym, or borrows the clipboard for anything harder) is the only one that arrives
   * intact.
   *
   * Modifier chords always go physical regardless: Ctrl+C is a position chord, not a character, and
   * an Arabic keyboard's Ctrl+ت is still Ctrl+C's key.
   */
  private decideKey(e: KeyboardEvent): "physical" | "character" | "ignore" {
    if (e.ctrlKey || e.altKey || e.metaKey) return "physical";
    // Anything that is not exactly one character is a named key (Enter, Tab, F5, ArrowLeft...).
    // Those have no character to disagree about.
    if (e.key.length !== 1) return "physical";
    const us = US_LAYOUT[e.code];
    if (!us) return "character";                       // a position we have no expectation for
    if (e.key === us[0] || e.key === us[1]) return "physical";
    return "character";
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
    const tag = t.tagName;
    return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || t.isContentEditable;
  }

  private onKeyDown = (e: KeyboardEvent) => {
    if (e.isComposing) return;             // an IME is mid-word; its commit arrives as input text
    if (this.localEditable(e)) return;
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
      this.cb.text(e.key);
      return;
    }

    // The agent deduplicates a repeated down itself and lets the REMOTE repeat timer drive repeat,
    // so sending the repeats is harmless; not sending them saves a frame per repeat.
    if (e.repeat) return;
    this.heldCodes.add(e.code);
    this.cb.keyCode(e.code, true);
  };

  private onKeyUp = (e: KeyboardEvent) => {
    if (e.isComposing) return;
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
