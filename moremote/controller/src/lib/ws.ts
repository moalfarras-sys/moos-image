import type { Hello, MouseButton } from "../types";

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
  move(x: number, y: number) {
    this.input({ type: "move", x, y });
  }
  moveRelative(dx: number, dy: number) {
    this.input({ type: "moveRelative", dx, dy });
  }
  down(button: MouseButton, x: number, y: number) {
    this.input(this.mode === "trackpad" ? { type: "downCurrent", button } : { type: "down", button, x, y });
  }
  up(button: MouseButton, x: number, y: number) {
    this.input(this.mode === "trackpad" ? { type: "upCurrent", button } : { type: "up", button, x, y });
  }
  click(button: MouseButton, x: number, y: number) {
    this.input(this.mode === "trackpad" ? { type: "clickCurrent", button } : { type: "click", button, x, y });
  }
  dblclick(x: number, y: number) {
    this.input(this.mode === "trackpad" ? { type: "dblclickCurrent" } : { type: "dblclick", x, y });
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
