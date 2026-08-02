import type { Hello, MouseButton } from "../types";

import { canDecodeH264 } from "./decode.ts";

/** One 60 Hz frame: text the agent types by keysym must not wait longer than this. */
const FAST_FLUSH_MS = 12;
/** Text that needs a clipboard borrow batches into words instead of one round trip per letter. */
const CLIPBOARD_FLUSH_MS = 220;
/** Exactly what the agent can type by keysym — see InputInjector.TryDirectStrokes. */
const FAST_TEXT = /^[a-zA-Z0-9 ]*$/;

interface Handlers {
  onOpen?: () => void;
  onHello?: (h: Hello) => void;
  onStatus?: (paused: boolean, active: number) => void;
  onFrame?: (buf: ArrayBuffer) => void;
  onStopped?: () => void;
  onIdle?: () => void;
  onScreen?: (available: boolean) => void;
  onAuthFail?: () => void;
  /** Whether this close is an outage the connection will automatically recover from. */
  onClose?: (willReconnect: boolean) => void;
  onPong?: (rttMs: number) => void;
  onInputState?: (ready: boolean, error?: string) => void;
  /** Which codec the agent is producing right now. It can change mid-session: the helper drops to
   *  JPEG on its own if the hardware encoder will not open, and climbs back when it will. */
  onCodec?: (codec: "jpeg" | "h264") => void;
}

/**
 * One live connection to the agent: receives JPEG frames, sends input.
 * Auto-reconnects with backoff unless the token was rejected or we disconnect on purpose.
 */
export class RemoteConnection {
  private token: string;
  private h: Handlers;
  private inputMeta?: () => any;
  private ws: WebSocket | null = null;
  private closedByUs = false;
  private backoff = 500;
  private reconnectTimer: number | null = null;
  private pingTimer: number | null = null;
  /** When a pong last arrived. The stall watchdog in startPing() is the only reader. */
  private lastPongAt = 0;
  private seq = 0;
  private mode = "trackpad";
  private display = 0;
  private source = { w: 0, h: 0 };
  private generation = 0;
  private pendingText="";
  private textTimer:number|null=null;

  constructor(token: string, handlers: Handlers, inputMeta?: () => any) {
    this.token = token;
    this.h = handlers;
    this.inputMeta = inputMeta;
  }

  connect() {
    this.stopReconnect();
    const generation=++this.generation;
    try{this.ws?.close();}catch{/* ignore */}
    this.closedByUs = false;
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws`);
    ws.binaryType = "arraybuffer";
    this.ws = ws;

    ws.onopen = () => {
      this.backoff = 500;
      ws.send(JSON.stringify({ type: "auth", token: this.token }));
    // Tell the agent what this browser can actually decode, before it picks an encoder. We never
    // let it guess: WebCodecs is absent outside a secure context, so a phone on the old plain-http
    // LAN address answers false here and correctly keeps the JPEG stream it can read.
    ws.send(JSON.stringify({ type: "video", h264: canDecodeH264() }));
      this.h.onOpen?.();
      this.startPing();
    };

    ws.onmessage = (ev) => {
      if (typeof ev.data === "string") {
        let m: any;
        try {
          m = JSON.parse(ev.data);
        } catch {
          return;
        }
        switch (m.type) {
          case "hello":
            this.source = m.screen ?? this.source;
            this.display = m.monitor ?? 0;
            this.h.onHello?.(m as Hello);
            break;
          case "status":
            this.h.onStatus?.(!!m.paused, m.active ?? 0);
            break;
          case "stopped":
            this.closedByUs = true;
            this.h.onStopped?.();
            break;
          case "idle":
            this.closedByUs = true;
            this.h.onIdle?.();
            break;
          case "screen":
            this.h.onScreen?.(!!m.available);
            break;
          case "codec":
            this.h.onCodec?.(m.codec === "h264" ? "h264" : "jpeg");
            break;
          case "pong":
            this.lastPongAt = performance.now();
            if (typeof m.t === "number") this.h.onPong?.(Math.max(0, performance.now() - m.t));
            break;
          case "inputState":
            this.h.onInputState?.(!!m.ready,m.error);
            break;
          case "error":
            if (m.error === "unauthorized") {
              this.closedByUs = true;
              this.h.onAuthFail?.();
            }
            break;
        }
      } else {
        this.h.onFrame?.(ev.data as ArrayBuffer);
      }
    };

    ws.onclose = () => {
      if(generation!==this.generation)return;
      this.stopPing();
      const willReconnect = !this.closedByUs;
      this.h.onClose?.(willReconnect);
      if (willReconnect) {
        const delay = this.backoff;
        this.reconnectTimer = window.setTimeout(() => {
          this.reconnectTimer = null;
          if (generation === this.generation && !this.closedByUs) this.connect();
        }, delay);
        this.backoff = Math.min(this.backoff * 1.6, 5000);
      }
    };

    ws.onerror = () => {
      /* onclose handles reconnect */
    };
  }

  disconnect() {
    this.flushText();
    this.generation++;
    this.closedByUs = true;
    this.stopReconnect();
    this.stopPing();
    try {
      this.ws?.close();
    } catch {
      /* ignore */
    }
  }

  /**
   * Ping every 2s AND check that the pongs come back.
   *
   * The ping half was already here; the check was not, and that is the difference between a heartbeat
   * and a decoration. A TCP connection that has stopped carrying data does not close — it sits there,
   * readyState OPEN, for as long as the OS keeps retransmitting. So a wedged session reported "Live"
   * with a frozen picture indefinitely, and there was nothing to reconnect because nothing had noticed.
   * This is the other half of "it feels like it disconnects": it does not disconnect, which is worse,
   * because a disconnect is something the client already knows how to recover from.
   *
   * STALL_MS is 8s: four missed pings on a link whose measured RTT is 21-34ms. Long enough that a phone
   * changing networks or a laptop waking is not called dead, short enough that a person has not yet
   * decided the product is broken. Closing the socket is all this has to do — onclose already owns the
   * backoff and the reconnect.
   */
  private static readonly STALL_MS = 8000;

  private startPing() {
    this.stopPing();
    this.lastPongAt = performance.now();
    this.pingTimer = window.setInterval(() => {
      this.send({ type: "ping", t: performance.now() });
      if (performance.now() - this.lastPongAt > RemoteConnection.STALL_MS && this.ws?.readyState === WebSocket.OPEN) {
        // Not closedByUs: this must reconnect, and it must be reported as a reconnect rather than a
        // deliberate exit, or the UI would show "signed out" for a network blip.
        try { this.ws.close(); } catch { /* the close handler does the rest */ }
      }
    }, 2000);
  }
  private stopPing() {
    if (this.pingTimer) window.clearInterval(this.pingTimer);
    this.pingTimer = null;
  }
  private stopReconnect() {
    if (this.reconnectTimer !== null) window.clearTimeout(this.reconnectTimer);
    this.reconnectTimer = null;
  }

  /** Re-declare what this client can decode. Used when the decoder gives up mid-session: the agent
   *  needs to know, or it keeps sending a codec nobody in the room can read. */
  setH264(can: boolean) {
    this.send({ type: "video", h264: can });
  }

  /**
   * "Nobody is looking at this any more" — and, later, "they are again".
   *
   * A hidden tab does not close its socket. The browser throttles its timers and its rAF loop to
   * almost nothing, the WebSocket keeps delivering at full rate, and the frames pile up in a receive
   * buffer the page is not draining. Caught on the live machine, on a tab that had merely been
   * switched away from:
   *
   *     Recv-Q 7301038   127.0.0.1:44548 -> 127.0.0.1:8765
   *
   * Seven megabytes of desktop nobody watched. On a phone that is battery and mobile data spent on a
   * screen in a pocket; coming back to it means several seconds of the past replaying before the
   * present arrives, which is exactly the "it freezes and then jumps" report.
   *
   * The agent stops the encoder only when EVERY viewer has looked away, so this is a vote and not a
   * command — see ScreenCapture.SessionWatching.
   */
  setWatching(watching: boolean) {
    this.send({ type: "video", watching });
  }

  /** Is the socket usable right now? The caller uses this to avoid queuing work for a dead link. */
  get open() {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  /**
   * Ask for an IDR because THIS client has nothing to decode against any more.
   *
   * Rate-limited here as well as in the agent, and deliberately so: the two limits guard different
   * things. The agent's stops any one client costing the whole room bandwidth; this one stops a
   * struggling phone from spending its own uplink on requests. A keyframe is the most expensive
   * frame there is, so the moment it is most tempting to ask repeatedly is the moment asking
   * repeatedly makes things worst.
   */
  private lastKeyframeAsk = 0;
  requestKeyframe() {
    const t = performance.now();
    if (t - this.lastKeyframeAsk < 1000) return;
    this.lastKeyframeAsk = t;
    this.send({ type: "keyframe" });
  }

  private send(obj: unknown) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(obj));
  }

  setInputMode(mode: string) { this.mode = mode; }
  private input(obj: Record<string, unknown>) {
    const vv = window.visualViewport;
    this.send({ ...obj, seq: ++this.seq, ts: Date.now(), mode: this.mode, display: this.display,
      viewport: { w: vv?.width ?? window.innerWidth, h: vv?.height ?? window.innerHeight,
        dpr: window.devicePixelRatio || 1, orientation: screen.orientation?.type ?? "unknown" },
      source: this.source, ...(this.inputMeta?.() ?? {}) });
  }

  // ---- input API ----
  // Every mode is absolute now: the phone tracks the cursor itself (even in trackpad mode, where
  // it integrates finger deltas) and sends a normalized point. The agent positions the pointer
  // via the portal, so the click lands exactly under the drawn cursor — no drift to accumulate.
  move(x: number, y: number) {
    this.input({ type: "move", x, y });
  }
  moveRelative(dx: number, dy: number) {
    this.input({ type: "moveRelative", dx, dy });
  }
  down(button: MouseButton, x: number, y: number) {
    this.input({ type: "down", button, x, y });
  }
  up(button: MouseButton, x: number, y: number) {
    this.input({ type: "up", button, x, y });
  }
  click(button: MouseButton, x: number, y: number) {
    this.input({ type: "click", button, x, y });
  }
  dblclick(x: number, y: number) {
    this.input({ type: "dblclick", x, y });
  }
  scroll(dx: number, dy: number) {
    this.input({ type: "scroll", dx, dy });
  }
  keyTap(key: string) {
    this.flushText();
    this.input({ type: "key", key });
  }
  keyDown(key: string) {
    this.flushText();
    this.input({ type: "key", key, down: true });
  }
  keyUp(key: string) {
    this.flushText();
    this.input({ type: "key", key, down: false });
  }
  /** A PHYSICAL key position (a browser KeyboardEvent.code). The agent prefers `code` over `key`
   *  when both are present, so this deliberately sends only the position — see StreamSession's
   *  "key" case and InputInjector.PhysicalCodes. */
  keyCode(code: string, down: boolean) {
    this.flushText();
    this.input({ type: "key", code, down });
  }
  combo(keys: string[]) {
    this.flushText();
    this.input({ type: "combo", keys });
  }
  text(value: string) {
    this.pendingText+=value;
    if(this.textTimer)window.clearTimeout(this.textTimer);
    // How long to coalesce depends on how the agent will have to type this.
    //
    // Text it can inject by keysym goes out within one 60 Hz frame, exactly as before — English
    // typing must not get slower to serve Arabic. Anything else (Arabic, punctuation needing a
    // shift level) is typed by briefly borrowing the clipboard, and that borrow is expensive: the
    // agent must set the selection AND read it back before pasting, because wl-copy returns before
    // the compositor will serve the new content (live-proven on 2026-08-03 — an unconfirmed paste
    // dropped whole words). 45 ms was shorter than the gap between two letters of ordinary typing,
    // so every letter still paid for its own borrow. 220 ms is longer than that gap and shorter
    // than a pause between words, so a WORD becomes one borrow — which is the difference between
    // Arabic that arrives and Arabic that arrives in pieces.
    //
    // The test mirrors the agent's own fast-path rule (InputInjector.TryDirectStrokes).
    const fast = FAST_TEXT.test(this.pendingText);
    this.textTimer=window.setTimeout(()=>this.flushText(),fast?FAST_FLUSH_MS:CLIPBOARD_FLUSH_MS);
  }
  private flushText(){if(this.textTimer)window.clearTimeout(this.textTimer);this.textTimer=null;if(!this.pendingText)return;const value=this.pendingText;this.pendingText="";this.input({type:"text",value});}
  /**
   * `width` is the real request — an absolute encode width in pixels. `scale` rides along because
   * an agent older than this build only understands the fraction, and being served a sensible
   * picture by an old server beats being served none.
   */
  settings(quality: number, fps: number, width: number, scale: number) {
    this.send({ type: "settings", quality, fps, width, scale });
  }
  selectMonitor(index: number) {
    this.send({ type: "selectMonitor", index });
  }
}
