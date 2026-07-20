import type { Hello, MouseButton } from "../types";

import { canDecodeH264 } from "./decode";

interface Handlers {
  onOpen?: () => void;
  onHello?: (h: Hello) => void;
  onStatus?: (paused: boolean, active: number) => void;
  onFrame?: (buf: ArrayBuffer) => void;
  onStopped?: () => void;
  onIdle?: () => void;
  onScreen?: (available: boolean) => void;
  onAuthFail?: () => void;
  onClose?: () => void;
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
  private ws: WebSocket | null = null;
  private closedByUs = false;
  private backoff = 500;
  private pingTimer: number | null = null;
  private seq = 0;
  private mode = "trackpad";
  private display = 0;
  private source = { w: 0, h: 0 };
  private generation = 0;
  private pendingText="";
  private textTimer:number|null=null;

  constructor(private token: string, private h: Handlers, private inputMeta?: () => any) {}

  connect() {
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
      this.h.onClose?.();
      if (!this.closedByUs) {
        setTimeout(() => this.connect(), this.backoff);
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
    this.stopPing();
    try {
      this.ws?.close();
    } catch {
      /* ignore */
    }
  }

  private startPing() {
    this.stopPing();
    this.pingTimer = window.setInterval(() => this.send({ type: "ping", t: performance.now() }), 2000);
  }
  private stopPing() {
    if (this.pingTimer) window.clearInterval(this.pingTimer);
    this.pingTimer = null;
  }

  /** Re-declare what this client can decode. Used when the decoder gives up mid-session: the agent
   *  needs to know, or it keeps sending a codec nobody in the room can read. */
  setH264(can: boolean) {
    this.send({ type: "video", h264: can });
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
  combo(keys: string[]) {
    this.flushText();
    this.input({ type: "combo", keys });
  }
  text(value: string) {
    this.pendingText+=value;
    if(this.textTimer)window.clearTimeout(this.textTimer);
    // Coalesce adjacent mobile input events without adding visible keyboard latency. 45ms rather
    // than 12: anything the agent cannot type by keysym (Arabic, and punctuation that needs a
    // shift level) is typed by briefly borrowing the clipboard, and at 12ms that was one clipboard
    // round trip PER LETTER. Batching into words makes Arabic one paste instead of five, and 45ms
    // is still well under the ~100ms where typing starts to feel detached.
    this.textTimer=window.setTimeout(()=>this.flushText(),45);
  }
  private flushText(){if(this.textTimer)window.clearTimeout(this.textTimer);this.textTimer=null;if(!this.pendingText)return;const value=this.pendingText;this.pendingText="";this.input({type:"text",value});}
  settings(quality: number, fps: number, scale: number) {
    this.send({ type: "settings", quality, fps, scale });
  }
  selectMonitor(index: number) {
    this.send({ type: "selectMonitor", index });
  }
}
