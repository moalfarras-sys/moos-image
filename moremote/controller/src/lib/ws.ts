import type { Hello, MouseButton } from "../types";

import { h264GivenUp } from "./h264state.ts";
import { canDecodeH264 } from "./decode.ts";

/** One 60 Hz frame: text the agent types by keysym must not wait longer than this. */
const FAST_FLUSH_MS = 12;
/** Text that needs a group switch or exact-Unicode fallback batches into committed words. */
const COMPLEX_TEXT_FLUSH_MS = 220;
/** Exactly what the agent can type by keysym — see InputInjector.TryDirectStrokes. */
const FAST_TEXT = /^[a-zA-Z0-9 ]*$/;
/** Mirrors InputInjector.PasteCoalesceMax: never hold more than one gather's worth. */
const TEXT_COALESCE_MAX = 240;
/** A re-arming debounce never fires under continuous input; nothing waits past this.
 *
 * This is the bound that decides how long typing can appear to go NOWHERE. The
 * debounce above re-arms on every keystroke, so at ordinary Arabic cadence
 * (~200 ms between letters) it never fires at all and this cap is the only thing
 * that delivers. At 700 ms that meant text surfacing in lumps two thirds of a
 * second apart, which is what "the writing does not arrive" describes from the
 * phone — it arrives, in a rhythm slow enough to read as a broken link.
 *
 * 250 ms keeps the per-word borrow the 220 ms window exists to protect (a real
 * pause between words still flushes through the debounce first) while capping
 * the worst case at a quarter second. */
const TEXT_COALESCE_MAX_MS = 250;
/** Words typed while the socket is down wait here for the reconnect; beyond this we are not
 *  "briefly offline", we are transcribing into a void, and silently replaying a screenful of
 *  stale text into whatever window has focus by then would be worse than dropping it. */
const OFFLINE_TEXT_MAX = 960;
/** How long a resume probe waits for proof of life before declaring the socket a zombie. */
const PROBE_MS = 2000;

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
  private connectTimer: number | null = null;
  private pingTimer: number | null = null;
  private authenticated = false;
  private aliveVersion = 0;
  private watching = true;
  /** When ANY message last arrived — frames included. The stall watchdog and probe() read it.
   *  It was pong-only once, and that killed live sessions: under load the tiny JSON pong queues
   *  behind megabytes of frames, so the one proof of life the watchdog accepted was exactly the
   *  message congestion delays most. A socket delivering video is not stalled. */
  private lastAliveAt = 0;
  private seq = 0;
  private mode = "trackpad";
  private display = 0;
  private source = { w: 0, h: 0 };
  private generation = 0;
  private pendingText="";
  private textTimer:number|null=null;
  /** When the oldest still-unflushed chunk was queued; 0 when the buffer is empty. */
  private textQueuedAt=0;

  constructor(token: string, handlers: Handlers, inputMeta?: () => any) {
    this.token = token;
    this.h = handlers;
    this.inputMeta = inputMeta;
  }

  connect() {
    this.stopReconnect();
    this.stopPing();
    this.stopConnectTimeout();
    this.authenticated = false;
    const generation=++this.generation;
    try{this.ws?.close();}catch{/* ignore */}
    this.closedByUs = false;
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws`);
    ws.binaryType = "arraybuffer";
    this.ws = ws;
    // A network change can leave CONNECTING open-ended just as it can an established socket.
    this.connectTimer = window.setTimeout(() => {
      if (generation === this.generation) this.finishConnection(generation);
    }, 10000);

    ws.onopen = () => {
      if (generation !== this.generation || this.closedByUs) return;
      ws.send(JSON.stringify({ type: "auth", token: this.token }));
    // Tell the agent what this browser can actually decode, before it picks an encoder. We never
    // let it guess: WebCodecs is absent outside a secure context, so a phone on the old plain-http
    // LAN address answers false here and correctly keeps the JPEG stream it can read.
    //
    // AND IT MUST RESPECT A DECISION THIS TAB HAS ALREADY MADE. canDecodeH264() only answers "is
    // WebCodecs available in principle" — it knows nothing about the three decode failures that
    // may have just happened. This path was unbounded while the RETRY path was bounded to three,
    // so every reconnect handed the room a clean slate and the cycle started again. Measured on
    // the cloud server: the three-strikes rule stopped the retries correctly, and then a session
    // END/START one second apart re-offered H.264 immediately. Sessions there reconnect every one
    // to two minutes, and every codec change is a pipeline rebuild the user sees as the screen
    // cutting out — so this is the difference between "settles down" and "never stops".
    ws.send(JSON.stringify({ type: "video", h264: canDecodeH264() && !h264GivenUp(), watching: this.watching }));
      this.h.onOpen?.();
      this.startPing();
    };

    ws.onmessage = (ev) => {
      if (generation !== this.generation || this.closedByUs) return;
      this.lastAliveAt = performance.now();
      this.aliveVersion++;
      if (typeof ev.data === "string") {
        let m: any;
        try {
          m = JSON.parse(ev.data);
        } catch {
          return;
        }
        switch (m.type) {
          case "hello":
            this.authenticated = true;
            this.backoff = 500;
            this.stopConnectTimeout();
            this.source = m.screen ?? this.source;
            this.display = m.monitor ?? 0;
            this.h.onHello?.(m as Hello);
            // Words queued while the socket was down deliver now that the session is authed
            // again — a moment late, in order, instead of silently gone (see flushText).
            if (this.pendingText && !this.textTimer)
              this.textTimer = window.setTimeout(() => this.flushText(), 80);
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
            // Aliveness is already stamped for every message at the top of onmessage; the pong's
            // remaining job is the RTT sample.
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
      this.finishConnection(generation);
    };

    ws.onerror = () => {
      /* onclose handles reconnect */
    };
  }

  disconnect() {
    this.flushText();
    this.clearText();
    this.generation++;
    this.closedByUs = true;
    this.authenticated = false;
    this.stopReconnect();
    this.stopPing();
    this.stopConnectTimeout();
    try {
      this.ws?.close();
    } catch {
      /* ignore */
    }
    this.ws = null;
  }

  /** Retire immediately: WebSocket.close() may wait indefinitely for an unreachable peer. */
  private finishConnection(generation: number) {
    if (generation !== this.generation) return;
    const retired = this.ws;
    this.ws = null;
    this.authenticated = false;
    const nextGeneration = ++this.generation;
    this.stopPing();
    this.stopConnectTimeout();
    // Invalidate callbacks before close(), which can deliver onclose synchronously in tests.
    try { retired?.close(); } catch { /* already closed */ }
    const willReconnect = !this.closedByUs;
    if (!willReconnect) this.clearText();
    this.h.onClose?.(willReconnect);
    if (willReconnect && nextGeneration === this.generation && !this.closedByUs) {
      const delay = this.backoff;
      this.reconnectTimer = window.setTimeout(() => {
        this.reconnectTimer = null;
        if (nextGeneration === this.generation && !this.closedByUs) this.connect();
      }, delay);
      this.backoff = Math.min(this.backoff * 1.6, 5000);
    }
  }

  private stopConnectTimeout() {
    if (this.connectTimer !== null) window.clearTimeout(this.connectTimer);
    this.connectTimer = null;
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
    this.lastAliveAt = performance.now();
    this.pingTimer = window.setInterval(() => {
      this.send({ type: "ping", t: performance.now() });
      if (performance.now() - this.lastAliveAt > RemoteConnection.STALL_MS && this.ws?.readyState === WebSocket.OPEN) {
        // Not closedByUs: this must reconnect, and it must be reported as a reconnect rather than a
        // deliberate exit, or the UI would show "signed out" for a network blip.
        this.finishConnection(this.generation);
      }
    }, 2000);
  }

  /**
   * "We just came back — is this socket real?"
   *
   * iOS suspends a backgrounded PWA whole: timers, sockets, everything. The server usually aborts
   * the connection while we are away, but the phone's own object still reads OPEN — a zombie. The
   * old resume path optimistically wrote into it and then waited out the full stall watchdog
   * before recovering, which read as "come back to the app, stare at a frozen desktop for ten
   * seconds". One ping with a short deadline answers the question at machine speed: any message
   * back (a pong, a frame, anything) proves life; silence closes the zombie so onclose can run
   * the reconnect it already owns.
   */
  probe() {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN || this.closedByUs) return;
    const generation = this.generation;
    const aliveVersion = this.aliveVersion;
    const asked = performance.now();
    this.send({ type: "ping", t: asked });
    window.setTimeout(() => {
      if (generation === this.generation && this.aliveVersion === aliveVersion && !this.closedByUs) {
        this.finishConnection(generation);
      }
    }, PROBE_MS);
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
    this.watching = watching;
    this.send({ type: "video", watching });
  }

  /** Is the socket usable right now? The caller uses this to avoid queuing work for a dead link. */
  get open() {
    return this.authenticated && this.ws?.readyState === WebSocket.OPEN;
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
  private lastKeyframeAsk = -Infinity;
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
    if (!this.open) return;
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
  // Anything that can MOVE THE CARET has to flush the coalescing buffer first, for
  // the same reason every key event does. A tap is a caret move: type an Arabic word,
  // tap the Send button within the coalescing window, and the click arrives while the
  // word is still queued here — so the word pastes into whatever the tap just focused.
  // Widening the window to 220 ms made that five times easier to hit than it was.
  down(button: MouseButton, x: number, y: number) {
    this.flushText();
    this.input({ type: "down", button, x, y });
  }
  up(button: MouseButton, x: number, y: number) {
    this.input({ type: "up", button, x, y });
  }
  click(button: MouseButton, x: number, y: number) {
    this.flushText();
    this.input({ type: "click", button, x, y });
  }
  dblclick(x: number, y: number) {
    this.flushText();
    this.input({ type: "dblclick", x, y });
  }
  downCurrent(button: MouseButton) {
    this.flushText();
    this.input({type: "downCurrent", button});
  }
  upCurrent(button: MouseButton) {
    this.input({type: "upCurrent", button});
  }
  clickCurrent(button: MouseButton) {
    this.flushText();
    this.input({type: "clickCurrent", button});
  }
  dblclickCurrent() {
    this.flushText();
    this.input({type: "dblclickCurrent"});
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
    if (this.closedByUs || !value) return;
    this.pendingText+=value;
    // Offline, the buffer holds what the user keeps typing until the reconnect delivers it.
    // Oldest first: the start of what they said beats the end of it, and past the cap the
    // session is not "briefly down" any more.
    if(!this.open && this.pendingText.length>OFFLINE_TEXT_MAX)
      this.pendingText=this.pendingText.slice(0,OFFLINE_TEXT_MAX);
    if(this.textTimer)window.clearTimeout(this.textTimer);
    // How long to coalesce depends on how the agent will have to type this.
    //
    // Text it can inject by keysym goes out within one 60 Hz frame — English must not get slower
    // to serve Arabic. Complex committed text is slower for honest reasons: Arabic selects and
    // confirms its real keymap group; symbols use the known US group; a character no installed
    // group carries takes the exact UTF-8 compatibility path. A 220 ms window is longer than an
    // ordinary inter-letter gap and shorter than a pause between words, so the client sends one
    // committed word rather than making the agent switch mechanisms for every letter.
    //
    // The test mirrors the agent's own fast-path rule (InputInjector.TryDirectStrokes).
    const fast = FAST_TEXT.test(this.pendingText);
    // The debounce re-arms on every keystroke, so input whose gaps never reach the
    // window — dictation, swipe typing, a fast typist — would defer the flush for as
    // long as it continues, holding a growing buffer that a dropped socket loses
    // entirely. Two bounds close that: the agent's own gather cap (240 chars), and an
    // age cap so a queued word is never held for more than about three windows.
    if (this.pendingText.length >= TEXT_COALESCE_MAX) { this.flushText(); return; }
    if (!this.textQueuedAt) this.textQueuedAt = Date.now();
    if (Date.now() - this.textQueuedAt >= TEXT_COALESCE_MAX_MS) { this.flushText(); return; }
    const remaining = TEXT_COALESCE_MAX_MS - (Date.now() - this.textQueuedAt);
    this.textTimer=window.setTimeout(()=>this.flushText(),Math.min(remaining,fast?FAST_FLUSH_MS:COMPLEX_TEXT_FLUSH_MS));
  }
  private clearText() {
    if (this.textTimer !== null) window.clearTimeout(this.textTimer);
    this.textTimer = null;
    this.pendingText = "";
    this.textQueuedAt = 0;
  }
  private flushText(){
    if(this.textTimer)window.clearTimeout(this.textTimer);
    this.textTimer=null;
    if(!this.pendingText)return;
    // A dead socket used to swallow this silently: the buffer was cleared HERE and send()
    // dropped the message, which is exactly how words vanished around every reconnect. Keep
    // the buffer instead — the hello handler flushes it once the session is authed again.
    if(!this.open)return;
    this.textQueuedAt=0;
    const value=this.pendingText;this.pendingText="";this.input({type:"text",value});
  }
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
