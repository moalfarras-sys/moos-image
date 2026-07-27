import { useCallback, useEffect, useRef, useState } from "react";
import { RemoteConnection } from "../lib/ws";
import { GestureController } from "../lib/gestures";
import { DesktopInput } from "../lib/desktop";
import {normalizeContentPoint} from "../lib/coordinates";
import { decodeJpeg, drawableSize, closeDrawable, H264Stream, type Drawable } from "../lib/decode";
import {
  getClipboard, setClipboard, setClipboardImage, listFiles, fileDownloadUrl, uploadFile, powerAction,
  type ClipResult, type FileListing, type FileEntry, type PowerAction,
} from "../lib/api";
import { QUALITY_PRESETS, MODE_LABEL, type GestureMode, type ViewMode, type MonitorInfo } from "../types";
import {
  IconAltTab, IconActual, IconChevronDown, IconClipboard, IconCopy, IconEnter, IconEsc, IconFit,
  IconFolder, IconFullscreen, IconKeyboard, IconLock, IconMore, IconMouse, IconPaste, IconPower,
  IconRefresh, IconSend, IconShield, IconSpeaker, IconSpeakerOff, IconTrackpad, IconUpload,
  IconWindows, IconZoomIn, IconZoomOut,
} from "./icons";

type Conn = "connecting" | "live" | "paused" | "stopped" | "reconnecting" | "idle";
type Sheet = null | "view" | "more" | "clip" | "files";
interface Layout { dispW: number; dispH: number; ox: number; oy: number; }

// Copy text to the phone's clipboard. navigator.clipboard only exists in a *secure context*
// (HTTPS / localhost) — over Tailscale we're served on plain http://100.x, so it's undefined
// and the old code failed silently. Fall back to a legacy selection + execCommand("copy"),
// written the iOS-Safari-compatible way (contentEditable + Range) so it works on iPhone too.
async function copyTextToClipboard(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch { /* fall through to the legacy path */ }
  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.contentEditable = "true";
    ta.readOnly = false;
    ta.style.position = "fixed";
    ta.style.top = "0";
    ta.style.left = "0";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    const range = document.createRange();
    range.selectNodeContents(ta);
    const sel = window.getSelection();
    sel?.removeAllRanges();
    sel?.addRange(range);
    ta.setSelectionRange(0, text.length);
    const ok = document.execCommand("copy");
    document.body.removeChild(ta);
    return ok;
  } catch {
    return false;
  }
}

/**
 * A setting that survives a reload.
 *
 * These are feel preferences, and scroll direction is the one that matters: it was state that
 * reset to its default on every reconnect, so toggling it appeared to do nothing that lasted. A
 * preference the user cannot make stick is worse than no preference at all — it reads as the app
 * ignoring them, which is exactly how "the scrolling is inverted" survived a toggle that existed
 * and worked.
 */
function usePref<T>(key: string, initial: T): [T, (v: T | ((prev: T) => T)) => void] {
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = localStorage.getItem("moremote." + key);
      return raw === null ? initial : (JSON.parse(raw) as T);
    } catch {
      return initial;   // private mode, or a value written by an older build
    }
  });
  const set = useCallback((v: T | ((prev: T) => T)) => {
    setValue((prev) => {
      const next = typeof v === "function" ? (v as (p: T) => T)(prev) : v;
      try { localStorage.setItem("moremote." + key, JSON.stringify(next)); } catch { /* not fatal */ }
      return next;
    });
  }, [key]);
  return [value, set];
}

/**
 * Which control mode a first-time viewer should land in.
 *
 * The touch modes exist to reconstruct a mouse out of a finger. A viewer who HAS a mouse should
 * never meet them: on a computer, "touch" mode turns a click-and-drag into a scroll instead of a
 * text selection, which reads as the REMOTE being broken rather than as a mode being wrong.
 *
 * The test is "is there evidence of a TOUCHSCREEN", and it is phrased that way round on purpose.
 * The obvious version — `(pointer: fine) && !(any-pointer: coarse)` — was written first and the
 * visual check killed it: a headless Firefox answers FALSE to every pointer query, having no input
 * device to describe, so `fine` was false and a 1280x860 desktop window silently came up in touch
 * mode. Any browser that declines to answer lands in the same hole, and the symptom is not an error
 * — it is a computer that drags when it should select, which gets blamed on the server.
 *
 * So require positive evidence for the SPECIAL case (a touchscreen) and let the ordinary case (a
 * mouse) be the default. maxTouchPoints leads because it is a count rather than a capability
 * negotiation, and a device reporting zero touch points is not a phone.
 *
 * A touchscreen laptop therefore starts in touch mode. That is the pre-existing behaviour and it is
 * the safer way to be wrong: the toolbar switches modes in one tap, and this is only the value used
 * when nothing was ever stored.
 */
function defaultMode(): GestureMode {
  try {
    const touch =
      (navigator.maxTouchPoints ?? 0) > 0 ||
      "ontouchstart" in window ||
      (window.matchMedia?.("(any-pointer: coarse)").matches ?? false);
    return touch ? "touch" : "desktop";
  } catch {
    return "desktop";
  }
}

export function RemoteScreen({ token, onExit }: { token: string; onExit: () => void }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const cursorRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const kbbarRef = useRef<HTMLDivElement>(null);
  const connRef = useRef<RemoteConnection | null>(null);
  const gestureRef = useRef<GestureController | null>(null);
  const desktopRef = useRef<DesktopInput | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioRetryRef = useRef<number | null>(null);
  const audioFailsRef = useRef(0);

  const frameRef = useRef<Drawable | null>(null);
  const decodingRef = useRef(false);
  const pendingRef = useRef<ArrayBuffer | null>(null);
  // What the agent is sending right now. A ref because the frame handler runs outside React's
  // render and must never route a frame to the decoder we have just left.
  const codecRef = useRef<"jpeg" | "h264">("jpeg");
  const h264Ref = useRef<H264Stream | null>(null);
  const view = useRef({ zoom: 1, panX: 0, panY: 0 });
  const fpsCount = useRef(0);
  const lastVal = useRef("");
  const composingRef = useRef(false);
  const compositionStartRef = useRef("");
  const cursorNorm = useRef({ x: 0.5, y: 0.5 });
  const hideTimer = useRef<number | null>(null);

  const [status, setStatus] = useState<Conn>("connecting");
  const [mode, setMode] = usePref<GestureMode>("mode", defaultMode());
  const [viewMode, setViewMode] = useState<ViewMode>("fit");
  const [presetIdx, setPresetIdx] = useState(1);
  // Auto quality ON by default. The complaint that keeps coming back is "the remote is slow",
  // and the usual cause is a fixed preset that is too heavy for the link the phone is actually
  // on — a DERP relay or mobile data, not the home LAN it was tuned for. Starting in auto lets
  // the stream drop to a lighter preset within a couple of seconds of high latency and climb
  // back up on a fast link, without the user ever opening the quality menu. They can still turn
  // it off and pin a preset by hand. This is the client half of Fast Remote (host half).
  const [auto, setAuto] = useState(true);
  const latRef = useRef(0);
  const [kbOpen, setKbOpen] = useState(false);
  const [sheet, setSheet] = useState<Sheet>(null);
  const [mods, setMods] = useState<Set<string>>(new Set());
  const [fps, setFps] = useState(0);
  const [latency, setLatency] = useState(0);
  const [toast, setToast] = useState<string | null>(null);
  const [toolbar, setToolbar] = useState(true);
  const [statsOpen, setStatsOpen] = useState(false);
  const [sound, setSound] = useState<"off" | "connecting" | "on" | "unavailable">("off");
  const [codec, setCodec] = useState<"jpeg" | "h264">("jpeg");
  const [screenOk, setScreenOk] = useState(true);
  const [inputOk, setInputOk] = useState(false);
  const [clipboardOk, setClipboardOk] = useState(false);
  const [mouseSensitivity,setMouseSensitivity]=usePref("mouseSensitivity",1);
  const [scrollSensitivity,setScrollSensitivity]=usePref("scrollSensitivity",1);
  const [naturalScroll,setNaturalScroll]=usePref("naturalScroll",true);
  // Off by default: pointer lock hides the local cursor and swallows the mouse until Esc, which is
  // right for a 3D view and wrong for everything else. Opt in per taste, remembered per browser.
  const [pointerLock,setPointerLock]=usePref("pointerLock",false);
  const [haptics,setHaptics]=usePref("haptics",true);
  const mouseSensitivityRef=useRef(mouseSensitivity);mouseSensitivityRef.current=mouseSensitivity;
  const scrollSensitivityRef=useRef(scrollSensitivity);scrollSensitivityRef.current=scrollSensitivity;
  const naturalScrollRef=useRef(naturalScroll);naturalScrollRef.current=naturalScroll;
  const pointerLockRef=useRef(pointerLock);pointerLockRef.current=pointerLock;
  const hapticsRef=useRef(haptics);hapticsRef.current=haptics;
  const [monitors, setMonitors] = useState<MonitorInfo[]>([]);
  const [selMonitor, setSelMonitor] = useState(0);
  const [pcClip, setPcClip] = useState<ClipResult>({ kind: "empty" });
  const [sendText, setSendText] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const [fileList, setFileList] = useState<FileListing | null>(null);
  const [fileBusy, setFileBusy] = useState(false);
  const fileUpRef = useRef<HTMLInputElement>(null);

  const modeRef = useRef(mode); modeRef.current = mode;
  const viewModeRef = useRef(viewMode); viewModeRef.current = viewMode;
  const presetIdxRef = useRef(presetIdx); presetIdxRef.current = presetIdx;

  const showToast = (m: string) => {
    setToast(m);
    window.setTimeout(() => setToast((t) => (t === m ? null : t)), 1900);
  };

  // ---------- toolbar auto-hide ----------
  const bumpToolbar = () => {
    setToolbar(true);
    if (hideTimer.current) window.clearTimeout(hideTimer.current);
    hideTimer.current = window.setTimeout(() => setToolbar(false), 4500);
  };

  // ---------- layout / mapping ----------
  const computeLayout = (): Layout | null => {
    const c = canvasRef.current, f = frameRef.current;
    if (!c || !f) return null;
    const cssW = c.clientWidth, cssH = c.clientHeight;
    const { w: iw, h: ih } = drawableSize(f);
    const dpr = Math.min(window.devicePixelRatio || 1, 2.5);
    const base = viewModeRef.current === "actual" ? 1 / dpr : Math.min(cssW / iw, cssH / ih);
    const z = view.current.zoom;
    const dispW = iw * base * z, dispH = ih * base * z;
    const ox = (cssW - dispW) / 2 + view.current.panX;
    const oy = (cssH - dispH) / 2 + view.current.panY;
    return { dispW, dispH, ox, oy };
  };

  const toNorm = (clientX: number, clientY: number) => {
    const c = canvasRef.current, l = computeLayout();
    if (!c || !l) return { x: 0.5, y: 0.5 };
    const r = c.getBoundingClientRect();
    return normalizeContentPoint(clientX,clientY,{left:r.left+l.ox,top:r.top+l.oy,width:l.dispW,height:l.dispH});
  };

  const minZoom = () => (viewModeRef.current === "actual" ? 0.4 : 1);
  const clampPan = () => {
    const l = computeLayout(), c = canvasRef.current;
    if (!l || !c) return;
    if (view.current.zoom < minZoom()) view.current.zoom = minZoom();
    const maxX = Math.max(0, (l.dispW - c.clientWidth) / 2);
    const maxY = Math.max(0, (l.dispH - c.clientHeight) / 2);
    view.current.panX = Math.min(maxX, Math.max(-maxX, view.current.panX));
    view.current.panY = Math.min(maxY, Math.max(-maxY, view.current.panY));
  };

  // ---------- setup ----------
  useEffect(() => {
    const canvas = canvasRef.current!;
    const ctx = canvas.getContext("2d", { alpha: false })!;
    let raf = 0, disposed = false;

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2.5);
      canvas.width = Math.round(canvas.clientWidth * dpr);
      canvas.height = Math.round(canvas.clientHeight * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    window.addEventListener("resize", resize);
    window.addEventListener("orientationchange", resize);

    const draw = () => {
      if (disposed) return;
      const f = frameRef.current;
      ctx.fillStyle = "#05070d";
      ctx.fillRect(0, 0, canvas.clientWidth, canvas.clientHeight);
      const l = computeLayout();
      if (f && l) {
        ctx.imageSmoothingEnabled = view.current.zoom <= 1.05;
        ctx.imageSmoothingQuality = "high";
        ctx.drawImage(f, l.ox, l.oy, l.dispW, l.dispH);
        const dot = cursorRef.current;
        if (dot) {
          dot.style.transform =
            `translate(${l.ox + cursorNorm.current.x * l.dispW}px, ${l.oy + cursorNorm.current.y * l.dispH}px)`;
        }
      }
      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);

    // One place where a new picture becomes THE picture, whichever codec produced it. The old one
    // is closed here and only here: an ImageBitmap or a VideoFrame that is never closed is a leak
    // the phone pays for in memory, thirty times a second.
    const show = (d: Drawable) => {
      if (disposed) { closeDrawable(d); return; }
      const old = frameRef.current;
      frameRef.current = d;
      fpsCount.current++;
      closeDrawable(old);
    };

    const decodeNext = async (buf: ArrayBuffer) => {
      decodingRef.current = true;
      const d = await decodeJpeg(buf);
      if (d) show(d);
      decodingRef.current = false;
      const next = pendingRef.current; pendingRef.current = null;
      if (next) decodeNext(next);
    };

    // H.264 decodes synchronously into the decoder's own output callback — there is no promise to
    // await and no "still decoding" state to guard, because the frames must go in IN ORDER and the
    // decoder is what paces them.
    const h264 = new H264Stream(show, (why) => {
      // A phone whose decoder gave up must not be left looking at a frozen desktop. Tell the agent
      // this client can no longer take H.264 and it will put the whole room back on JPEG.
      console.warn("H.264 decode failed, falling back to JPEG:", why);
      codecRef.current = "jpeg";
      connRef.current?.setH264(false);
      showToast("Video fell back to JPEG");
    });
    h264Ref.current = h264;

    const conn = new RemoteConnection(token, {
      onHello: (h) => {
        setStatus(h.paused ? "paused" : "live");
        setMonitors(h.monitors ?? []);
        setSelMonitor(h.monitor ?? 0);
        setInputOk(!!h.input?.ready);
        setClipboardOk(!!h.clipboard?.ready);
        pushSettings();
      },
      onStatus: (paused) => setStatus(paused ? "paused" : "live"),
      onFrame: (buf) => {
        if (codecRef.current === "h264") { h264Ref.current?.push(buf); return; }
        if (decodingRef.current) pendingRef.current = buf; else decodeNext(buf);
      },
      onCodec: (codec) => {
        if (codec === codecRef.current) return;
        codecRef.current = codec;
        // Whatever is half-decoded belongs to the codec we just left.
        h264Ref.current?.reset();
        pendingRef.current = null;
        setCodec(codec);
      },
      onStopped: () => setStatus("stopped"),
      onAuthFail: () => onExit(),
      onClose: () => { lastVal.current = ""; setMods(new Set()); setStatus((s) => (s === "stopped" || s === "idle" ? s : "reconnecting")); },
      onPong: (rtt) => { const v = Math.round(rtt); setLatency(v); latRef.current = v; },
      onIdle: () => setStatus("idle"),
      onScreen: (avail) => setScreenOk(avail),
      onInputState: (ready,error) => { setInputOk(ready); if(error)showToast(`Input: ${error}`); },
    }, () => {
      const c=canvasRef.current, l=computeLayout(), f=frameRef.current;
      if(!c||!l||!f)return {};
      const r=c.getBoundingClientRect(), s=drawableSize(f);
      return { content:{left:l.ox,top:l.oy,width:l.dispW,height:l.dispH},
        canvas:{left:r.left,top:r.top,width:r.width,height:r.height}, source:s };
    });
    connRef.current = conn;
    conn.connect();

    const gest = new GestureController(canvas, toNorm, () => view.current.zoom, {
      click: (b, x, y) => conn.click(b, x, y),
      moveCursor: (x, y) => conn.move(x, y),
      dragStart: (x, y) => conn.down("left", x, y),
      dragMove: (x, y) => conn.move(x, y),
      dragEnd: (x, y) => conn.up("left", x, y),
      scroll: (dx, dy) => conn.scroll(dx*scrollSensitivityRef.current, dy*scrollSensitivityRef.current*(naturalScrollRef.current?1:-1)),
      zoomAt: (factor, fx, fy) => {
        const before = toNorm(fx, fy);
        view.current.zoom = Math.min(5, Math.max(minZoom(), view.current.zoom * factor));
        const l = computeLayout(), c = canvasRef.current;
        if (l && c) {
          const r = c.getBoundingClientRect();
          view.current.panX += (fx - r.left) - (l.ox + before.x * l.dispW);
          view.current.panY += (fy - r.top) - (l.oy + before.y * l.dispH);
        }
        clampPan();
      },
      panBy: (dx, dy) => { view.current.panX += dx; view.current.panY += dy; clampPan(); },
      cursorAt: (x, y) => { cursorNorm.current = { x, y }; },
      haptic: () => {if(hapticsRef.current)navigator.vibrate?.(8);},
    }, () => mouseSensitivityRef.current);
    gest.setMode(modeRef.current);
    gestureRef.current = gest;

    // The real-mouse/real-keyboard path. Constructed always, attached only in "desktop" mode (the
    // effect below), because its window-level keydown listener would otherwise steal every
    // keystroke from the phone's hidden-textarea path.
    const desk = new DesktopInput(canvas, toNorm, {
      move: (x, y) => conn.move(x, y),
      moveRelative: (dx, dy) => conn.moveRelative(dx * mouseSensitivityRef.current, dy * mouseSensitivityRef.current),
      down: (b, x, y) => conn.down(b, x, y),
      up: (b, x, y) => conn.up(b, x, y),
      scroll: (dx, dy) => conn.scroll(dx, dy),
      keyCode: (code, down) => conn.keyCode(code, down),
      text: (v) => conn.text(v),
      cursorAt: (x, y) => { cursorNorm.current = { x, y }; },
    }, () => scrollSensitivityRef.current, () => pointerLockRef.current);
    desktopRef.current = desk;
    if (modeRef.current === "desktop") desk.attach();

    const fpsTimer = window.setInterval(() => { setFps(fpsCount.current); fpsCount.current = 0; }, 1000);
    bumpToolbar();

    return () => {
      disposed = true;
      h264Ref.current?.reset();
      h264Ref.current = null;
      cancelAnimationFrame(raf);
      window.clearInterval(fpsTimer);
      if (hideTimer.current) window.clearTimeout(hideTimer.current);
      window.removeEventListener("resize", resize);
      window.removeEventListener("orientationchange", resize);
      gest.destroy();
      desk.destroy();
      desktopRef.current = null;
      conn.disconnect();
      const f = frameRef.current;
      if (f && "close" in f) (f as ImageBitmap).close();
      frameRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    gestureRef.current?.setMode(mode);
    connRef.current?.setInputMode(mode);
    // Exactly one of the two input layers is live at a time. Detaching also releases whatever the
    // remote currently thinks is held, so switching modes mid-drag cannot leave a button down.
    const desk = desktopRef.current;
    if (!desk) return;
    if (mode === "desktop") desk.attach(); else desk.detach();
  }, [mode]);

  // Load the file listing whenever the Files sheet opens (avoids a race with the sheet mount).
  useEffect(() => {
    if (sheet !== "files") return;
    let cancelled = false;
    setFileBusy(true);
    listFiles(token, fileList?.path ?? null)
      .then((l) => { if (!cancelled) setFileList(l); })
      .catch(() => { if (!cancelled) showToast("Can't open that folder"); })
      .finally(() => { if (!cancelled) setFileBusy(false); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sheet, token]);

  // When the iOS keyboard opens, shrink the screen view so it sits right above the
  // keyboard bar (no big black gap), and pin the bar just above the on-screen keyboard.
  useEffect(() => {
    const vv = window.visualViewport;
    if (!vv) return;
    const update = () => {
      const bar = kbbarRef.current;
      const canvas = canvasRef.current;
      if (!canvas) return;
      const kb = Math.max(0, window.innerHeight - vv.height - vv.offsetTop);
      if (bar) bar.style.transform = kbOpen ? `translateY(${-kb}px)` : "";
      const barH = bar?.offsetHeight ?? 92;
      canvas.style.height = kbOpen ? Math.max(140, vv.height - barH) + "px" : "";
      // resize the backing store to the new visible area + let the draw loop refit
      const dpr = Math.min(window.devicePixelRatio || 1, 2.5);
      canvas.width = Math.round(canvas.clientWidth * dpr);
      canvas.height = Math.round(canvas.clientHeight * dpr);
      canvas.getContext("2d")?.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    vv.addEventListener("resize", update);
    vv.addEventListener("scroll", update);
    update();
    return () => { vv.removeEventListener("resize", update); vv.removeEventListener("scroll", update); };
  }, [kbOpen]);

  // ---------- settings (quality + view) ----------
  // Read the preset through a ref: onHello is wired once, so closing over presetIdx directly
  // would make every reconnect re-send the preset that was selected on first render.
  const pushSettings = () => {
    const p = QUALITY_PRESETS[presetIdxRef.current] ?? QUALITY_PRESETS[1];
    const scale = viewModeRef.current === "actual" ? 1.0 : p.scale;
    connRef.current?.settings(p.quality, p.fps, scale);
  };
  useEffect(() => { pushSettings(); /* eslint-disable-next-line */ }, [presetIdx, viewMode]);

  // Auto quality: adapt to the network using round-trip latency (RTT). We deliberately do NOT
  // use fps — with identical-frame skipping, a still screen sends few frames, which is not lag.
  useEffect(() => {
    if (!auto) return;
    const id = window.setInterval(() => {
      const lat = latRef.current;
      setPresetIdx((idx) => {
        if (lat > 250 && idx > 0) return idx - 1;             // laggy → lighter preset
        if (lat > 0 && lat < 120 && idx < QUALITY_PRESETS.length - 1) return idx + 1; // healthy → richer
        return idx;
      });
    }, 2500);
    return () => window.clearInterval(id);
  }, [auto]);

  const selectPreset = (i: number) => { setPresetIdx(i); showToast(`Quality: ${QUALITY_PRESETS[i].label}`); };
  const chooseView = (m: ViewMode) => {
    setViewMode(m);
    view.current = { zoom: m === "actual" ? 1 : 1, panX: 0, panY: 0 };
    showToast(m === "fit" ? "Fit to screen" : "Original size (100%)");
  };
  const zoomBy = (f: number) => { view.current.zoom = Math.min(5, Math.max(minZoom(), view.current.zoom * f)); clampPan(); };
  const resetZoom = () => { view.current = { zoom: 1, panX: 0, panY: 0 }; };

  // ---------- keyboard ----------
  // A real visible input. Tapping it raises the iOS keyboard; we diff its value so typing
  // AND Backspace both work (the field must hold text for iOS to fire delete events).
  const openKeyboard = () => {
    setKbOpen(true);
    const el = inputRef.current;
    if (el) { el.value = ""; lastVal.current = ""; el.focus(); }
  };
  const closeKeyboard = () => {
    const el = inputRef.current;
    if (el) el.value = "";
    lastVal.current = "";
    setMods(new Set());
    setKbOpen(false);
    el?.blur();
  };
  const sendKey = (key: string) => {
    const c = connRef.current; if (!c) return;
    if (mods.size > 0) { c.combo([...mods, key]); setMods(new Set()); } else c.keyTap(key);
  };
  const toggleMod = (m: string) => setMods((s) => { const n = new Set(s); n.has(m) ? n.delete(m) : n.add(m); return n; });

  // Diff the field value into keystrokes (handles text, Backspace, Arabic, autocorrect).
  const onInput = () => {
    const el = inputRef.current!, v = el.value, last = lastVal.current, c = connRef.current;
    if (!c) { lastVal.current = v; return; }
    // Arabic keyboards and other IMEs revise a word while it is being composed. Streaming those
    // intermediate values duplicates letters and Backspaces remotely; send only the commit.
    if (composingRef.current) return;
    if (v.length > last.length && v.startsWith(last)) {
      const added = v.slice(last.length);
      if (mods.size > 0) { for (const ch of added) c.combo([...mods, ch]); setMods(new Set()); el.value = ""; lastVal.current = ""; return; }
      c.text(added);
    } else if (v.length < last.length && last.startsWith(v)) {
      for (let i = 0; i < last.length - v.length; i++) c.keyTap("Backspace");
    } else {
      // replaced (autocorrect): delete the old, type the new
      for (let i = 0; i < last.length; i++) c.keyTap("Backspace");
      if (v) c.text(v);
    }
    lastVal.current = v;
    // resync only if the line gets very long (Backspace-on-empty is handled in onKeyDown)
    if (v.length > 300) { el.value = ""; lastVal.current = ""; }
  };
  const onCompositionStart = () => {
    composingRef.current = true;
    compositionStartRef.current = inputRef.current?.value ?? "";
  };
  const onCompositionEnd = (e: React.CompositionEvent<HTMLInputElement>) => {
    composingRef.current = false;
    const after = inputRef.current?.value ?? "";
    const before = compositionStartRef.current;
    const committed = after.startsWith(before) ? after.slice(before.length) : e.data;
    if (committed) connRef.current?.text(committed);
    lastVal.current = after;
  };
  const onInputKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      sendKey("Enter");
      const el = inputRef.current; if (el) el.value = "";
      lastVal.current = "";
    } else if (e.key === "Backspace" && (inputRef.current?.value.length ?? 0) === 0) {
      // field already empty — still forward the delete
      e.preventDefault();
      sendKey("Backspace");
    }
  };

  // ---------- clipboard (text + images) ----------
  const getPcClip = async () => {
    try {
      const r = await getClipboard(token);
      setPcClip(r);
      showToast(r.kind === "image" ? "Got PC image" : r.kind === "text" ? "Got PC text" : "PC clipboard is empty");
    } catch { showToast("Failed to read PC clipboard"); }
  };
  const sendToPc = async () => {
    if (!sendText) return;
    try { await setClipboard(token, sendText); showToast("Text sent to PC"); }
    catch { showToast("Failed to set PC clipboard"); }
  };
  const copyToPhone = async () => {
    if (pcClip.kind !== "text" || !pcClip.text) return;
    if (await copyTextToClipboard(pcClip.text)) showToast("Copied on phone");
    else showToast("Long-press the text to copy");
  };
  const uploadImage = async (blob: Blob) => {
    if (!blob) return;
    if (blob.size > 24_000_000) { showToast("Image too large (max ~24MB)"); return; }
    try { await setClipboardImage(token, blob); showToast("Image sent to PC — press Paste"); }
    catch { showToast("Failed to send image"); }
  };
  const onPickPhoto = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) uploadImage(f);
    e.target.value = "";
  };
  const onPasteBox = async (e: React.ClipboardEvent<HTMLDivElement>) => {
    const box = e.currentTarget;
    const items = e.clipboardData?.items;
    let handled = false;
    if (items) {
      for (const it of items) {
        if (it.type.startsWith("image/")) {
          const f = it.getAsFile();
          if (f) { e.preventDefault(); await uploadImage(f); handled = true; }
        }
      }
      if (!handled) {
        const text = e.clipboardData.getData("text");
        if (text) { e.preventDefault(); await setClipboard(token, text); showToast("Text sent to PC"); handled = true; }
      }
    }
    // Fallback: iOS often inserts the image into the box without exposing it above.
    if (!handled) setTimeout(() => scanPasteBox(box), 80);
  };
  // iOS may insert a pasted image asynchronously — scan the box and upload any <img>.
  const scanPasteBox = async (box: HTMLDivElement | null) => {
    if (!box) return;
    const img = box.querySelector("img");
    if (img?.src) {
      try { const blob = await (await fetch(img.src)).blob(); if (blob.type.startsWith("image/")) await uploadImage(blob); } catch { /* */ }
      box.innerHTML = "";
      return;
    }
    const txt = box.innerText.trim();
    if (txt) { try { await setClipboard(token, txt); showToast("Text sent to PC"); } catch { /* */ } box.innerHTML = ""; }
  };
  const onPasteBoxInput = (e: React.FormEvent<HTMLDivElement>) => {
    const box = e.currentTarget;
    setTimeout(() => scanPasteBox(box), 40);
  };

  // ---------- file transfer ----------
  const fmtSize = (n: number) =>
    n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(0)} KB` : n < 1073741824 ? `${(n / 1048576).toFixed(1)} MB` : `${(n / 1073741824).toFixed(2)} GB`;
  const navFiles = async (path: string | null) => {
    setFileBusy(true);
    try { setFileList(await listFiles(token, path)); }
    catch { showToast("Can't open that folder"); }
    setFileBusy(false);
  };
  const openFiles = () => setSheet("files"); // the effect below loads the listing on open
  const downloadFile = (en: FileEntry) => {
    const a = document.createElement("a");
    a.href = fileDownloadUrl(token, en.path);
    a.download = en.name;
    document.body.appendChild(a); a.click(); a.remove();
    showToast("Downloading " + en.name);
  };
  const onUploadFiles = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files; const dir = fileList?.path;
    if (!files || !dir) { e.target.value = ""; return; }
    setFileBusy(true);
    try { for (const f of Array.from(files)) await uploadFile(token, dir, f); showToast(`Uploaded ${files.length} to PC`); await navFiles(dir); }
    catch { showToast("Upload failed"); }
    setFileBusy(false);
    e.target.value = "";
  };

  // ---------- toolbar actions ----------
  const c = () => connRef.current;
  const cycleMode = () => {
    const order: GestureMode[] = ["touch", "trackpad", "direct", "desktop"];
    const next = order[(order.indexOf(mode) + 1) % order.length];
    setMode(next); showToast(`Mouse: ${MODE_LABEL[next]}`);
  };
  const taskMgr = () => { c()?.combo(["Control", "Shift", "Escape"]); showToast("Task Manager (safe Ctrl+Alt+Del)"); };

  // ---------- sound ----------
  //
  // The desktop stream carries no audio and never has (the agent has no capture, no encoder and no
  // audio endpoint). The server's sound is a SEPARATE service — moos-cloud-audio, the default sink's
  // monitor as Opus-in-WebM — which `moos-cloud-desktop own` now mounts at /audio on this very
  // origin. So it is a same-origin relative URL from here, which is the whole reason this button can
  // exist: while that service lived on its own plain-http port, an https page was forbidden from
  // touching it and sound could only ever be a second tab.
  //
  // RELATIVE, not "/audio/...": if this page is itself served under a prefix one day, an absolute
  // path would leave that prefix behind.
  const AUDIO_URL = "audio/stream.webm";

  const stopSound = useCallback(() => {
    if (audioRetryRef.current) { window.clearTimeout(audioRetryRef.current); audioRetryRef.current = null; }
    const a = audioRef.current;
    if (a) { a.pause(); a.removeAttribute("src"); a.load(); }
    setSound("off");
  }, []);

  const startSound = useCallback(() => {
    const a = audioRef.current;
    if (!a) return;
    setSound("connecting");
    // Cache-busting is load-bearing, not superstition: the service spawns one encoder per listener
    // and kills it on disconnect, so the previous response is a DEAD stream. Safari will happily
    // re-use it from cache and play nothing at all, reporting no error.
    a.src = `${AUDIO_URL}?t=${Date.now()}`;
    a.play().then(() => setSound("on")).catch(() => {
      // Autoplay policy needs a gesture; this IS one (a click), so a rejection here means the
      // endpoint is not there — which is what happens when the page was opened on the plain-http
      // port, where no /audio mount exists and the agent answers index.html to everything.
      setSound("unavailable");
      showToast("Sound needs the https:// address");
    });
  }, []);

  const toggleSound = () => { if (sound === "off" || sound === "unavailable") startSound(); else stopSound(); };

  // A live WebM stream never "ends" cleanly and has no duration, so the ordinary media events do not
  // mean what they usually mean. `error`/`stalled`/`ended` here mean the encoder went away — which
  // it does by design whenever a listener drops — and the only fix is a fresh URL.
  useEffect(() => {
    const a = audioRef.current;
    if (!a) return;
    const onPlaying = () => { audioFailsRef.current = 0; setSound("on"); };
    const onBroken = () => {
      if (!a.src) return;
      // Bounded, and the bound is the point. Retrying for ever is right for the case this was
      // written for — the encoder is respawned per listener, so a reconnect genuinely does fix it —
      // and wrong for the case that actually happens first: no /audio mount at all, because the
      // server has not been updated yet. Verified against the live server: that returns a clean 404
      // for the stream, so the element errors immediately and an unbounded loop would sit there
      // re-requesting a 404 twice a second for as long as the tab is open, showing "connecting…"
      // and never saying what is wrong.
      if (++audioFailsRef.current > 3) {
        audioFailsRef.current = 0;
        a.pause(); a.removeAttribute("src"); a.load();
        setSound("unavailable");
        showToast("No sound endpoint — run: moos-cloud-desktop doctor");
        return;
      }
      audioRetryRef.current = window.setTimeout(() => {
        if (a.src) { a.src = `${AUDIO_URL}?t=${Date.now()}`; a.play().catch(() => setSound("unavailable")); }
      }, 1200);
    };
    a.addEventListener("playing", onPlaying);
    for (const ev of ["error", "ended", "stalled"] as const) a.addEventListener(ev, onBroken);
    return () => {
      a.removeEventListener("playing", onPlaying);
      for (const ev of ["error", "ended", "stalled"] as const) a.removeEventListener(ev, onBroken);
      if (audioRetryRef.current) window.clearTimeout(audioRetryRef.current);
    };
  }, []);

  const fullscreen = () => {
    const el = document.documentElement as any;
    if (document.fullscreenElement) {
      desktopRef.current?.releaseKeyboardLock();
      document.exitFullscreen?.();
      return;
    }
    if (el.requestFullscreen) {
      el.requestFullscreen()
        .then(() => {
          // Esc, Tab, Ctrl+W and F11 are the browser's until Keyboard Lock is granted, and it is
          // only ever granted in fullscreen — which is why this call lives here and not at startup.
          // Chromium-only and best-effort: without it those four keys stay local, and everything
          // else on the keyboard still reaches the desktop.
          desktopRef.current?.requestKeyboardLock();
          // A desktop is a landscape thing. Fitted into a portrait phone it becomes a stamp with
          // black bars swallowing most of the display — turning the phone is worth more than any
          // amount of pinch-zooming. The lock only exists in an installed/fullscreen context and
          // is absent on iOS entirely, so it is attempted, never depended on.
          (screen.orientation as any)?.lock?.("landscape").catch(() => {});
        })
        .catch(() => showToast("Add to Home Screen for fullscreen"));
    } else {
      // iOS has no Fullscreen API at all. Installing it is the only route, and it is the better
      // one anyway: standalone means no address bar and no Safari toolbar to reclaim the screen.
      showToast("Safari ▸ Share ▸ Add to Home Screen");
    }
  };
  const refreshStream = () => { setStatus("connecting"); connRef.current?.disconnect(); setTimeout(() => connRef.current?.connect(), 120); showToast("Refreshing…"); };
  const reconnect = () => { setStatus("connecting"); connRef.current?.connect(); };
  const disconnect = () => { connRef.current?.disconnect(); onExit(); };

  const chooseMonitor = (i: number) => {
    if (i === selMonitor) return;
    setSelMonitor(i);
    connRef.current?.selectMonitor(i);
    view.current = { zoom: 1, panX: 0, panY: 0 }; // reset zoom/pan; the new screen may differ in size
    showToast(`Screen ${i + 1}`);
  };

  const doPower = async (action: PowerAction, label: string, needConfirm = false) => {
    if (needConfirm && !window.confirm(`${label} the PC?`)) return;
    setSheet(null);
    const ok = await powerAction(token, action);
    showToast(ok ? `${label}…` : `${label} failed`);
  };

  const statusInfo = {
    connecting: { cls: "warn", text: "Connecting…" },
    live: { cls: "", text: "Connected" },
    paused: { cls: "warn", text: "Paused on PC" },
    reconnecting: { cls: "warn", text: "Reconnecting…" },
    stopped: { cls: "bad", text: "Ended on PC" },
    idle: { cls: "bad", text: "Idle timeout" },
  }[status];

  const overlay = status === "stopped" || status === "idle";

  // Healthy means: there is nothing to tell the user. The bar collapses to a dot, and hides with
  // the toolbar. Tapping it opens the numbers (fps / latency / mode) for anyone who wants them;
  // anything actually broken overrides both and keeps the bar open until it is fixed.
  const healthy = status === "live" && screenOk && inputOk && clipboardOk;
  const compactBar = healthy && !statsOpen;

  return (
    <div className="remote" onPointerDown={bumpToolbar}>
      <canvas ref={canvasRef} className="screen-canvas" />
      {/* The server's sound, on this same origin. Never `autoPlay` — the browser would refuse it
          without a gesture and the refusal is indistinguishable from the stream being broken. */}
      <audio ref={audioRef} hidden />
      {/* The video stream carries no cursor (drawing one would re-encode a full frame on every
          pointer move), so this *is* the cursor. It sits exactly where the next click will land. */}
      <div ref={cursorRef} className="remote-cursor">
        <svg width="20" height="24" viewBox="0 0 20 24" aria-hidden="true">
          <path
            d="M0 0 L0 17.4 L4.4 13.3 L7.4 19.8 L10.3 18.5 L7.2 12.2 L12.8 11.9 Z"
            fill="#fff" stroke="#0b0f1a" strokeWidth="1.4" strokeLinejoin="round"
          />
        </svg>
      </div>

      {/* The status bar has to earn the space it takes, and on a phone it was not earning it.
          It sat across the top of the desktop permanently, spelling out "Connected · Video ✓ ·
          Mouse ✓ · Keys ✓ · Clip ✓" — four ticks that say nothing you did not already know from
          the fact that the screen is moving, over the part of the screen you are trying to see.

          So: when everything works it shrinks to a single dot and then fades out with the
          toolbar, and the desktop gets the whole display. Touch anything and it is back.

          When something is actually wrong it does the opposite — it stays put, refuses to hide,
          and names ONLY the thing that broke. A list of ticks is noise; "No video" is news. */}
      <div
        className={
          "topbar"
          + (compactBar ? " mini" : "")
          + (compactBar && !toolbar ? " gone" : "")
        }
        onClick={() => setStatsOpen((v) => !v)}
      >
        <span className={"dot " + statusInfo.cls} />
        {!compactBar && (
          <>
            <b>{statusInfo.text}</b>
            {!screenOk && <span className="bad">· No video</span>}
            {!inputOk && <span className="bad">· No input</span>}
            {!clipboardOk && <span className="bad">· No clipboard</span>}
            {status === "live" && <span>· {fps}fps · {latency}ms · {codec === "h264" ? "H.264" : "JPEG"} · {MODE_LABEL[mode]}</span>}
          </>
        )}
      </div>

      {overlay && (
        <div className="center-msg">
          <IconPower className="" />
          <div>
            <b style={{ color: "var(--text)", fontSize: 17 }}>
              {status === "idle" ? "Disconnected — idle timeout" : "Session ended on the PC"}
            </b>
          </div>
          <div style={{ display: "flex", gap: 12 }}>
            <button className="btn" onClick={reconnect}>Reconnect</button>
            <button className="btn ghost" onClick={onExit}>Sign out</button>
          </div>
        </div>
      )}

      {status === "paused" && (
        <div className="center-msg" style={{ background: "rgba(5,7,13,0.5)" }}>
          <b style={{ color: "var(--text)", fontSize: 16 }}>⏸ Paused on the PC</b>
          <div>Resume from the PC tray or banner.</div>
        </div>
      )}

      {!screenOk && status === "live" && (
        <div className="center-msg" style={{ background: "rgba(5,7,13,0.62)" }}>
          <IconLock className="" />
          <div>
            <b style={{ color: "var(--text)", fontSize: 16 }}>PC is locked</b>
            <div style={{ marginTop: 6, maxWidth: 300 }}>
              Windows hides the lock screen from every app. Unlock the PC once, then on the PC
              tray icon turn on <b>“Never lock — stay reachable”</b> so it stays reachable from now on.
            </div>
          </div>
        </div>
      )}

      {/* keyboard bar: a shortcuts row + a visible input (so typing AND Backspace work). */}
      <div className={"kbbar" + (kbOpen ? " open" : "")} ref={kbbarRef}>
        <div className="keyrow" onMouseDown={(e) => e.preventDefault()}>
          {(["Control", "Alt", "Shift"] as const).map((m) => (
            <button key={m} className={"kkey" + (mods.has(m) ? " on" : "")} onClick={() => toggleMod(m)}>
              {m === "Control" ? "Ctrl" : m}
            </button>
          ))}
          <button className="kkey" onClick={() => c()?.keyTap("Win")}>Win</button>
          <span className="kdiv" />
          <button className="kkey" onClick={() => c()?.combo(["Control", "A"])}>⌃A</button>
          <button className="kkey" onClick={() => c()?.combo(["Control", "C"])}>⌃C</button>
          <button className="kkey" onClick={() => c()?.combo(["Control", "X"])}>⌃X</button>
          <button className="kkey" onClick={() => c()?.combo(["Control", "V"])}>⌃V</button>
          <button className="kkey" onClick={() => c()?.combo(["Control", "Z"])}>⌃Z</button>
          <button className="kkey" onClick={() => c()?.combo(["Alt", "Tab"])}>Alt·Tab</button>
          <span className="kdiv" />
          <button className="kkey" onClick={() => sendKey("Escape")}>Esc</button>
          <button className="kkey" onClick={() => sendKey("Tab")}>Tab</button>
          <button className="kkey" onClick={() => sendKey("ArrowLeft")}>←</button>
          <button className="kkey" onClick={() => sendKey("ArrowUp")}>↑</button>
          <button className="kkey" onClick={() => sendKey("ArrowDown")}>↓</button>
          <button className="kkey" onClick={() => sendKey("ArrowRight")}>→</button>
        </div>
        <div className="kbinput-row">
          <input
            ref={inputRef} className="kbinput" type="text" inputMode="text"
            autoCapitalize="off" autoCorrect="off" autoComplete="off" spellCheck={false}
            placeholder="اكتب هنا — tap & type"
            onInput={onInput} onKeyDown={onInputKeyDown}
            onCompositionStart={onCompositionStart} onCompositionEnd={onCompositionEnd}
          />
          <button className="kbicon" onMouseDown={(e) => e.preventDefault()} onClick={() => sendKey("Backspace")} aria-label="Backspace">⌫</button>
          <button className="kbicon" onMouseDown={(e) => e.preventDefault()} onClick={() => sendKey("Enter")} aria-label="Enter">↵</button>
          <button className="kbdone" onMouseDown={(e) => e.preventDefault()} onClick={closeKeyboard}>Done</button>
        </div>
      </div>

      {/* small affordance: when keyboard closed, the toolbar "Keys" button opens it */}

      {/* floating toolbar */}
      {!kbOpen && (
        <div className={"toolbar" + (toolbar || sheet ? "" : " fade-toolbar")}>
          <button className="tbtn" onClick={openKeyboard}><IconKeyboard /><span>Keys</span></button>
          <button className="tbtn" onClick={() => { setSheet("clip"); getPcClip(); }}><IconClipboard /><span>Clip</span></button>
          <button className="tbtn" onClick={cycleMode}>
            {mode === "trackpad" ? <IconTrackpad /> : <IconMouse />}<span>{MODE_LABEL[mode]}</span>
          </button>
          <button className="tbtn" onClick={() => setSheet("view")}>
            {viewMode === "fit" ? <IconFit /> : <IconActual />}<span>View</span>
          </button>
          <button className={"tbtn" + (sound === "on" ? " on" : "")} onClick={toggleSound}>
            {sound === "on" ? <IconSpeaker /> : <IconSpeakerOff />}
            <span>{sound === "connecting" ? "…" : "Sound"}</span>
          </button>
          <button className="tbtn" onClick={fullscreen}><IconFullscreen /><span>Full</span></button>
          <button className="tbtn accent" onClick={() => setSheet("more")}><IconMore /><span>More</span></button>
        </div>
      )}

      {/* sheets */}
      {sheet && <div className="sheet-backdrop" onClick={() => setSheet(null)} />}

      {sheet === "view" && (
        <div className="sheet">
          <div className="grip" /><h3>Display</h3>
          <div className="row-label">Screen</div>
          <div className="seg">
            <button className={viewMode === "fit" ? "on" : ""} onClick={() => chooseView("fit")}><IconFit /> Fit</button>
            <button className={viewMode === "actual" ? "on" : ""} onClick={() => chooseView("actual")}><IconActual /> 100%</button>
          </div>
          {monitors.length > 1 && (
            <>
              <div className="row-label">Monitor</div>
              <div className="seg">
                {monitors.map((m, i) => (
                  <button key={m.index} className={selMonitor === i ? "on" : ""} onClick={() => chooseMonitor(i)}>
                    {m.primary ? "Main" : `Screen ${i + 1}`}
                  </button>
                ))}
              </div>
            </>
          )}
          <div className="row-label">Zoom</div>
          <div className="zoomrow">
            <button className="cell" onClick={() => zoomBy(0.77)}><IconZoomOut /> Out</button>
            <button className="cell" onClick={resetZoom}>Reset</button>
            <button className="cell" onClick={() => zoomBy(1.3)}><IconZoomIn /> In</button>
          </div>
          <div className="row-label">Quality</div>
          <div className="seg">
            <button className={auto ? "on" : ""} onClick={() => { setAuto(true); showToast("Auto quality — adapts to your network"); }}>Auto</button>
            {QUALITY_PRESETS.map((p, i) => (
              <button key={p.label} className={!auto && presetIdx === i ? "on" : ""} onClick={() => { setAuto(false); selectPreset(i); }}>{p.label}</button>
            ))}
          </div>
        </div>
      )}

      {sheet === "more" && (
        <div className="sheet">
          <div className="grip" /><h3>Controls</h3>
          <div className="row-label">Pointer mode</div>
          <div className="seg">
            <button className={mode === "touch" ? "on" : ""} onClick={() => setMode("touch")}><IconMouse /> Touch</button>
            <button className={mode === "trackpad" ? "on" : ""} onClick={() => setMode("trackpad")}><IconTrackpad /> Trackpad</button>
            <button className={mode === "direct" ? "on" : ""} onClick={() => setMode("direct")}><IconMouse /> Direct</button>
            <button className={mode === "desktop" ? "on" : ""} onClick={() => setMode("desktop")}><IconMouse /> Mouse + Keys</button>
          </div>
          {mode === "desktop" && (
            <>
              <div className="seg">
                <button className={pointerLock?"on":""} onClick={()=>setPointerLock(v=>!v)}>Capture pointer</button>
              </div>
              {/* One line, not the three this started as. Everything in this sheet below the pointer
                  mode was already reachable only by scrolling on a phone, and a section that explains
                  what the buttons above it obviously do is the wrong thing to spend that space on. */}
              <p className="hint">
                All three buttons, the wheel and every key. Fullscreen also captures Esc, Tab and
                Ctrl+W. Capture pointer sends raw movement for 3D and games — Esc releases it.
              </p>
            </>
          )}
          <div className="row-label">Mouse sensitivity · {mouseSensitivity.toFixed(1)}</div>
          <input type="range" min="0.4" max="2.5" step="0.1" value={mouseSensitivity} onChange={e=>setMouseSensitivity(Number(e.target.value))}/>
          <div className="row-label">Scroll sensitivity · {scrollSensitivity.toFixed(1)}</div>
          <input type="range" min="0.4" max="2.5" step="0.1" value={scrollSensitivity} onChange={e=>setScrollSensitivity(Number(e.target.value))}/>
          <div className="seg"><button className={naturalScroll?"on":""} onClick={()=>setNaturalScroll(v=>!v)}>Natural scroll</button><button className={haptics?"on":""} onClick={()=>setHaptics(v=>!v)}>Haptics</button></div>
          <div className="row-label">Actions</div>
          <div className="grid">
            <button className="cell" onClick={openFiles}><IconFolder /> Files</button>
            <button className="cell" onClick={() => { taskMgr(); setSheet(null); }}><IconShield /> Ctrl+Alt+Del</button>
            <button className="cell" onClick={() => c()?.combo(["Control", "C"])}><IconCopy /> Copy</button>
            <button className="cell" onClick={() => c()?.combo(["Control", "V"])}><IconPaste /> Paste</button>
            <button className="cell" onClick={() => { refreshStream(); setSheet(null); }}><IconRefresh /> Refresh</button>
            <button className="cell" onClick={() => { fullscreen(); setSheet(null); }}><IconFullscreen /> Fullscreen</button>
            <button className="cell danger" onClick={disconnect}><IconPower /> Disconnect</button>
          </div>
          <div className="row-label">Power</div>
          <div className="grid">
            <button className="cell" onClick={() => doPower("lock", "Lock")}><IconLock /> Lock</button>
            <button className="cell" onClick={() => doPower("sleep", "Sleep")}><IconPower /> Sleep</button>
            <button className="cell" onClick={() => doPower("signout", "Sign out", true)}><IconLock /> Sign out</button>
            <button className="cell" onClick={() => doPower("restart", "Restart", true)}><IconRefresh /> Restart</button>
            <button className="cell danger" onClick={() => doPower("shutdown", "Shut down", true)}><IconPower /> Shut down</button>
          </div>
          <div className="credit">Mo Remote Personal · by Moalfarras</div>
        </div>
      )}

      {sheet === "files" && (
        <div className="sheet">
          <div className="grip" />
          <h3>Files · {fileList?.title ?? "…"}</h3>
          <div className="file-actions">
            {fileList?.path && <button className="cell" onClick={() => navFiles(fileList.parent)}>⬆ Up</button>}
            {fileList?.path && <button className="cell" onClick={() => fileUpRef.current?.click()}><IconUpload /> Upload here</button>}
            <button className="cell" onClick={() => navFiles(fileList?.path ?? null)}><IconRefresh /> Refresh</button>
          </div>
          <input ref={fileUpRef} type="file" multiple hidden onChange={onUploadFiles} />
          <div className="file-list">
            {fileBusy && <div className="hintline">Loading…</div>}
            {!fileBusy && fileList && fileList.entries.length === 0 && <div className="hintline">Empty folder</div>}
            {!fileBusy && fileList?.entries.map((en) => (
              <button key={en.path} className="file-row" onClick={() => (en.isDir ? navFiles(en.path) : downloadFile(en))}>
                <span className="file-ic">{en.isDir ? "📁" : "📄"}</span>
                <span className="file-name">{en.name}</span>
                <span className="file-meta">{en.isDir ? "›" : fmtSize(en.size)}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {sheet === "clip" && (
        <div className="sheet">
          <div className="grip" /><h3>Clipboard sync</h3>

          <div className="row-label">PC → Phone</div>
          {pcClip.kind === "image" ? (
            <img className="clip-img" src={pcClip.dataUrl} alt="PC clipboard" />
          ) : (
            <textarea className="clip-area" readOnly value={pcClip.text ?? ""} placeholder="Press Get to fetch the PC clipboard" />
          )}
          <div className="cliprow">
            <button className="cell" onClick={getPcClip}><IconRefresh /> Get PC Clipboard</button>
            <button className="cell" onClick={copyToPhone} disabled={pcClip.kind !== "text"}><IconCopy /> Copy</button>
          </div>
          {pcClip.kind === "image" && <div className="hintline">Long-press the image to Save / Copy on your iPhone.</div>}

          <div className="row-label">Phone → PC · text</div>
          <textarea className="clip-area" value={sendText} onChange={(e) => setSendText(e.target.value)} placeholder="Type or paste text…" />
          <button className="cell wide" onClick={sendToPc}><IconSend /> Set PC text</button>

          <div className="row-label">Phone → PC · image</div>
          <button className="cell wide primary" onClick={() => fileRef.current?.click()}><IconClipboard /> Send a photo / screenshot</button>
          <input ref={fileRef} type="file" accept="image/*" hidden onChange={onPickPhoto} />
          <div
            className="paste-box"
            contentEditable
            suppressContentEditableWarning
            onPaste={onPasteBox}
            onInput={onPasteBoxInput}
            data-ph="…or long-press here → Paste a copied image"
          />
        </div>
      )}

      {!toolbar && !kbOpen && !sheet && !overlay && (
        <button className="show-tab" onClick={bumpToolbar}><IconChevronDown /></button>
      )}

      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}
