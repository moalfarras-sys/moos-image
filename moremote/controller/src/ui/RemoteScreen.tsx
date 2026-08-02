import { useCallback, useEffect, useRef, useState } from "react";
import { RemoteConnection } from "../lib/ws";
import { GestureController } from "../lib/gestures";
import { DesktopInput } from "../lib/desktop";
import {normalizeContentPoint, normalizeRotatedPoint, projectPoint} from "../lib/coordinates";
import { decodeJpeg, drawableSize, closeDrawable, canDecodeH264, H264Stream, type Drawable } from "../lib/decode";
import {
  getClipboard, setClipboard, setClipboardImage, listFiles, fileDownloadUrl, audioStreamUrl, uploadFile, powerAction,
  listTrustedDevices, revokeTrustedDevice,
  type ClipResult, type FileListing, type FileEntry, type PowerAction, type TrustedDeviceInfo,
} from "../lib/api";
import { pickStartPreset, readDeviceHints, describeHints } from "../lib/quality";
import { remoteAlertPermission, requestRemoteAlertPermission, showRemoteAlert } from "../lib/notifications";
import { QUALITY_PRESETS, AUTO_MAX_PRESET, BUILD, MODE_LABEL, MODE_HINT, type GestureMode, type ViewMode, type MonitorInfo } from "../types";
import {
  IconAltTab, IconActual, IconArrowUp, IconBackspace, IconChevronDown, IconClipboard, IconClose,
  IconCopy, IconEnter, IconEsc, IconFile, IconFit, IconFolder, IconFullscreen, IconKeyboard,
  IconLock, IconMore, IconMouse, IconPaste, IconPause, IconPower, IconRefresh, IconRotate, IconSend, IconSettings, IconShield,
  IconSpeaker, IconSpeakerOff, IconTrackpad, IconUpload,
  IconWindows, IconZoomIn, IconZoomOut,
} from "./icons";

type Conn = "connecting" | "live" | "paused" | "stopped" | "reconnecting" | "idle";
type Sheet = null | "view" | "more" | "clip" | "files";
type PendingPower = { action: PowerAction; label: string };
/**
 * The on-screen rectangle the picture occupies, and whether it is drawn turned a quarter turn
 * inside it. `dispW`/`dispH` are always the SCREEN box — so letterboxing, panning, zoom clamping
 * and hit-testing keep working on a plain axis-aligned rectangle, and only the draw call and the
 * two coordinate helpers ever need to know about the rotation.
 */
interface Layout { dispW: number; dispH: number; ox: number; oy: number; rot: boolean; }

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

/**
 * A settings row: title (and optional explanation) on the left, its control on the right.
 *
 * This is the shape the whole sheet is built from, and it exists as a component so every
 * row is the same height and the same alignment. The previous sheet reached for a
 * `.seg` button per boolean — a button whose only "on" signal was a background tint, which
 * on a phone in daylight is not a signal at all.
 */
function Row({ title, sub, children }: { title: string; sub?: string; children: React.ReactNode }) {
  return (
    <div className="row">
      <div className="row-main">
        <div className="row-title">{title}</div>
        {sub && <div className="row-sub">{sub}</div>}
      </div>
      {children}
    </div>
  );
}

/**
 * A real switch, not a tinted button.
 *
 * role/aria-checked rather than a styled <input>: the sheet is scrollable and a native
 * checkbox drags oddly inside one on iOS, and this way the accessible state is explicit
 * rather than inferred from a class name. The knob moves, so on/off reads at a glance
 * without reading the label — which is the entire reason to use a switch here.
 */
function Switch({ on, onToggle }: { on: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      className="switch"
      onClick={onToggle}
    />
  );
}

/**
 * A bottom sheet is a modal dialog, not merely a card drawn above a scrim.
 * Own focus while it is open, close on Escape, wrap Tab inside it, and restore
 * the invoking control afterwards. This keeps phone screen-readers and desktop
 * keyboard users on the same interaction path as touch users.
 */
function SheetPanel({ label, onClose, children, role = "dialog", descriptionId,
  initialFocusSelector = ".sheet-close", dismissible = true }: {
  label: string;
  onClose: () => void;
  children: React.ReactNode;
  role?: "dialog" | "alertdialog";
  descriptionId?: string;
  initialFocusSelector?: string;
  dismissible?: boolean;
}) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const panel = panelRef.current;
    if (!panel) return;
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const focusable = () => Array.from(panel.querySelectorAll<HTMLElement>(
      'button:not([disabled]), input:not([disabled]), textarea:not([disabled]), summary, [contenteditable="true"], [tabindex]:not([tabindex="-1"])',
    )).filter((item) => !item.hidden && item.getAttribute("aria-hidden") !== "true");

    (panel.querySelector<HTMLElement>(initialFocusSelector) ?? focusable()[0] ?? panel).focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        if (dismissible) onClose();
        return;
      }
      if (event.key !== "Tab") return;
      const items = focusable();
      if (items.length === 0) {
        event.preventDefault();
        panel.focus();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    panel.addEventListener("keydown", onKeyDown);
    return () => {
      panel.removeEventListener("keydown", onKeyDown);
      previous?.focus();
    };
  }, [dismissible, initialFocusSelector, onClose]);

  return (
    <div ref={panelRef} className="sheet" role={role} aria-modal="true" aria-label={label}
         aria-describedby={descriptionId} tabIndex={-1}>
      <button type="button" className="sheet-close" onClick={onClose} disabled={!dismissible}
              aria-label={`Close ${label}`}><IconClose /></button>
      {children}
    </div>
  );
}

export function RemoteScreen({ token, hostPowerAllowed, onExit }: {
  token: string;
  hostPowerAllowed: boolean;
  onExit: () => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const cursorRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const kbbarRef = useRef<HTMLDivElement>(null);
  const connRef = useRef<RemoteConnection | null>(null);
  const gestureRef = useRef<GestureController | null>(null);
  const desktopRef = useRef<DesktopInput | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioRetryRef = useRef<number | null>(null);
  const audioGenerationRef = useRef(0);
  const refreshTimerRef = useRef<number | null>(null);
  const audioFailsRef = useRef(0);

  const frameRef = useRef<Drawable | null>(null);
  const decodingRef = useRef(false);
  const pendingRef = useRef<ArrayBuffer | null>(null);
  // What the agent is sending right now. A ref because the frame handler runs outside React's
  // render and must never route a frame to the decoder we have just left.
  const codecRef = useRef<"jpeg" | "h264">("jpeg");
  const h264Ref = useRef<H264Stream | null>(null);
  /** How many times we have re-offered H.264 after a decode failure, and the pending re-offer. */
  const h264RetriesRef = useRef(0);
  const h264RetryTimer = useRef<number | null>(null);
  const view = useRef({ zoom: 1, panX: 0, panY: 0 });
  const fpsCount = useRef(0);
  const lastVal = useRef("");
  const composingRef = useRef(false);
  const compositionStartRef = useRef("");
  const cursorNorm = useRef({ x: 0.5, y: 0.5 });
  // The remote desktop's pixel size, from `hello`. A ref because the input-geometry callback runs
  // outside React's render and needs it before the first frame exists — see that callback for why
  // being frameless there used to mean being ignored.
  const screenSizeRef = useRef({ w: 0, h: 0 });
  // Bumped by anything that changes what belongs on screen. The draw loop compares against it and
  // skips the blit when nothing has — see the draw loop for why that matters on a phone.
  const drawEpochRef = useRef(0);
  const invalidate = useCallback(() => { drawEpochRef.current++; }, []);
  const hideTimer = useRef<number | null>(null);
  const toastTimer = useRef<number | null>(null);

  const [status, setStatus] = useState<Conn>("connecting");
  const [mode, setMode] = usePref<GestureMode>("mode", defaultMode());
  const [viewMode, setViewMode] = usePref<ViewMode>("viewMode", "fit");
  // What this device says about itself, read once. Used for the OPENING rung only — the RTT
  // ladder below owns every step after that and can undo an optimistic guess within ~4s.
  const deviceHints = useRef(readDeviceHints(
    Math.round(Math.max(screen.width, screen.height) * (window.devicePixelRatio || 1)))).current;
  // A quality the owner picked by hand is a durable choice: reopening at the
  // device-hint guess every session was half of "it is always blurry".
  const [presetIdx, setPresetIdx] = usePref("presetIdx", pickStartPreset(deviceHints));
  // Auto quality ON by default. The complaint that keeps coming back is "the remote is slow",
  // and the usual cause is a fixed preset that is too heavy for the link the phone is actually
  // on — a DERP relay or mobile data, not the home LAN it was tuned for. Starting in auto lets
  // the stream drop to a lighter preset within a couple of seconds of high latency and climb
  // back up on a fast link, without the user ever opening the quality menu. They can still turn
  // it off and pin a preset by hand. This is the client half of Fast Remote (host half).
  const [auto, setAuto] = usePref("autoQuality", true);
  const latRef = useRef(0);
  const [kbOpen, setKbOpen] = useState(false);
  const [sheet, setSheet] = useState<Sheet>(null);
  const [trustedDevices, setTrustedDevices] = useState<TrustedDeviceInfo[] | null>(null);
  const [deviceBusy, setDeviceBusy] = useState("");
  const closeSheet = useCallback(() => setSheet(null), []);
  const [powerConfirm, setPowerConfirm] = useState<PendingPower | null>(null);
  const [powerBusy, setPowerBusy] = useState(false);
  const powerInFlightRef = useRef(false);
  const cancelPowerConfirm = useCallback(() => {
    setPowerConfirm(null);
    setSheet("more");
  }, []);
  const [mods, setMods] = useState<Set<string>>(new Set());
  const [fps, setFps] = useState(0);
  const [latency, setLatency] = useState(0);
  const [toast, setToast] = useState<string | null>(null);
  const [toolbar, setToolbar] = useState(true);
  /** Is the viewport taller than it is wide? Drives whether the Fill-screen control is offered. */
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
  const [backgroundAlerts,setBackgroundAlerts]=usePref("backgroundAlerts",false);
  /**
   * Which way up the desktop is drawn — AND WHETHER THAT IS THE APP'S DECISION OR THE USER'S.
   *
   * This started as a boolean ("fill the screen: yes/no") and a boolean is the wrong shape, because
   * it conflates two different questions the user has: *should it turn?* and *may it change its mind
   * while I am using it?* An automatic rule that re-decides on every viewport change is exactly what
   * makes a remote desktop feel unstable — the address bar slides, the soft keyboard opens, and the
   * whole picture flips a quarter turn under your thumb. Nothing you did caused it and nothing tells
   * you why.
   *
   *   auto  — turn it when the phone is upright and turning genuinely wins (the default)
   *   on    — LOCKED turned. It stays sideways whatever the viewport does.
   *   off   — LOCKED upright. Never turned, even if that wastes most of the screen.
   *
   * The two locks are the point: "I decide when it turns, or I lock it" is the request, and a lock
   * that only holds in one direction is not a lock.
   */
  type Orient = "auto" | "on" | "off";
  const [orient,setOrient]=usePref<Orient>("orient","auto");
  const mouseSensitivityRef=useRef(mouseSensitivity);mouseSensitivityRef.current=mouseSensitivity;
  const scrollSensitivityRef=useRef(scrollSensitivity);scrollSensitivityRef.current=scrollSensitivity;
  const naturalScrollRef=useRef(naturalScroll);naturalScrollRef.current=naturalScroll;
  const pointerLockRef=useRef(pointerLock);pointerLockRef.current=pointerLock;
  const hapticsRef=useRef(haptics);hapticsRef.current=haptics;
  const backgroundAlertsRef=useRef(backgroundAlerts);backgroundAlertsRef.current=backgroundAlerts;
  // One alert describes one outage. Reconnect attempts may fail every five seconds for hours;
  // only a successfully authenticated hello is allowed to arm the next alert.
  const connectionAlertedRef=useRef(false);
  const connectionEstablishedRef=useRef(false);
  /**
   * Magnify around the caret while the keyboard is up.
   *
   * OFF by default, and that is a deliberate reversal of where this started. The complaint being
   * answered is "the screen goes up and gets choked when I type" — it is a complaint about the
   * picture MOVING, and an automatic 2.2x zoom is more movement, not less. Tested against a real
   * session it also lands wherever the pointer happens to be, which is frequently a blank part of
   * an editor: the viewer loses the whole desktop and gains a magnified view of nothing.
   *
   * What typing needs unconditionally is the LIFT — the caret out from under the keyboard — and
   * that always happens. Magnification is a genuine help when you are editing text and a genuine
   * nuisance when you are not, so it is a switch the user owns rather than a decision made for them.
   */
  const [typingZoom,setTypingZoom]=usePref("typingZoom",false);
  const typingZoomRef=useRef(typingZoom);typingZoomRef.current=typingZoom;
  const orientRef=useRef(orient);orientRef.current=orient;
  /**
   * How much of the bottom of the canvas is hidden behind the soft keyboard and its bar, in CSS px.
   *
   * The canvas is NOT shrunk to fit above them any more (see the keyboard effect for why that was
   * the wrong shape), so this is the one number that tells the rest of the layout where the usable
   * screen actually ends: clampPan grants exactly this much extra upward travel, so a picture that
   * fits perfectly can still be lifted clear of the keyboard.
   */
  const kbInsetRef=useRef(0);
  /**
   * The rotation decision, frozen for as long as the keyboard is open.
   *
   * Opening the keyboard changes the shape of the visible area — on a 375x667 phone a 260px keyboard
   * leaves a band that is WIDER THAN IT IS TALL — and the automatic rule reads that as "landscape,
   * so stop turning the picture". So tapping into a text box flipped the entire desktop a quarter
   * turn, and closing the keyboard flipped it back. You cannot type into something that moves when
   * you reach for it. The answer is not a cleverer rule: it is to stop asking the question while the
   * user is mid-task. null = not latched.
   */
  const kbRotLatch=useRef<boolean|null>(null);
  /** The view to put back when the keyboard closes, saved when it opened. */
  const kbSavedView=useRef<{zoom:number;panX:number;panY:number}|null>(null);
  const [monitors, setMonitors] = useState<MonitorInfo[]>([]);
  const [selMonitor, setSelMonitor] = useState(0);
  const [pcClip, setPcClip] = useState<ClipResult>({ kind: "empty" });
  const [sendText, setSendText] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const [fileList, setFileList] = useState<FileListing | null>(null);
  const [fileBusy, setFileBusy] = useState(false);
  const [uploadProgress, setUploadProgress] = useState("");
  const fileUpRef = useRef<HTMLInputElement>(null);

  const kbOpenRef = useRef(kbOpen); kbOpenRef.current = kbOpen;
  const modeRef = useRef(mode); modeRef.current = mode;
  const viewModeRef = useRef(viewMode); viewModeRef.current = viewMode;
  const presetIdxRef = useRef(presetIdx); presetIdxRef.current = presetIdx;

  const showToast = (m: string) => {
    setToast(m);
    if (toastTimer.current) window.clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => {
      toastTimer.current = null;
      setToast((t) => (t === m ? null : t));
    }, 1900);
  };

  const toggleBackgroundAlerts = async () => {
    if (backgroundAlerts && remoteAlertPermission() === "granted") {
      setBackgroundAlerts(false);
      showToast("Background alerts off");
      return;
    }
    if (remoteAlertPermission() === "unsupported") {
      setBackgroundAlerts(false);
      showToast("Background alerts need the installed HTTPS app");
      return;
    }
    if (await requestRemoteAlertPermission()) {
      setBackgroundAlerts(true);
      showToast("Background alerts on");
    } else {
      setBackgroundAlerts(false);
      showToast("Notification permission was not granted");
    }
  };

  useEffect(() => {
    if (sheet !== "more") return;
    let live = true;
    setTrustedDevices(null);
    void listTrustedDevices(token).then(devices => {
      if (live) setTrustedDevices(devices);
    }).catch(() => {
      if (live) { setTrustedDevices([]); showToast("Could not load trusted devices"); }
    });
    return () => { live = false; };
  }, [sheet, token]);

  const revokeDevice = async (device: TrustedDeviceInfo) => {
    if (deviceBusy) return;
    setDeviceBusy(device.id);
    try {
      if (!await revokeTrustedDevice(token, device.id)) throw new Error("revoke failed");
      if (device.current) { await onExit(); return; }
      setTrustedDevices(list => list?.filter(item => item.id !== device.id) ?? []);
      showToast(`${device.name} removed`);
    } catch {
      showToast("Could not remove that device");
    } finally {
      setDeviceBusy("");
    }
  };

  // ---------- toolbar auto-hide ----------
  const bumpToolbar = () => {
    setToolbar(true);
    if (hideTimer.current) window.clearTimeout(hideTimer.current);
    hideTimer.current = window.setTimeout(() => setToolbar(false), 6000);
  };

  // ---------- layout / mapping ----------

  /**
   * Should the picture be turned a quarter turn?
   *
   * ORIENTATION IS THE USER'S TO CONTROL. The owner asked for exactly that, twice ("put a lock —
   * when I want it to rotate I turn it on, otherwise I lock it"), and reported that the picture was
   * "going landscape on the phone" on its own. So nothing here turns the phone or the picture behind
   * the user's back. There are three answers and the default is the calm one:
   *
   *   • Auto (default) — FOLLOW THE PHONE. The picture stays upright and simply fits however the
   *     phone is held: portrait letterboxes it, landscape fills it. It used to auto-rotate the
   *     desktop a quarter turn to fill a portrait phone, which made a phone held upright show a
   *     sideways desktop — the "الشاشة عم تعمل عرضي" the owner reported. That is gone.
   *   • 🔒 Sideways — turn the picture a quarter turn ON PURPOSE, for holding the phone upright but
   *     wanting the desktop big. This is the opt-in that replaces the old automatic behaviour.
   *   • 🔒 Upright — never turn it.
   */
  const shouldRotate = (_iw: number, _ih: number) => {
    // A locked orientation is a promise, answered before anything is measured.
    const mode = orientRef.current;
    if (mode === "off") return false;   // 🔒 Upright
    if (mode === "on") return true;     // 🔒 Sideways — the deliberate quarter turn
    // Auto. While the keyboard is open the answer stays whatever it was when the keyboard opened —
    // see kbRotLatch for why re-deciding mid-sentence is the worst possible moment.
    if (kbRotLatch.current !== null) return kbRotLatch.current;
    // Follow the phone: the picture stays upright and fits the viewport as it is. To get the big
    // rotated view, hold the phone in landscape, or choose 🔒 Sideways.
    return false;
  };

  const computeLayout = (): Layout | null => {
    const c = canvasRef.current, f = frameRef.current;
    if (!c || !f) return null;
    const cssW = c.clientWidth, cssH = c.clientHeight;
    const { w: iw, h: ih } = drawableSize(f);
    const rot = shouldRotate(iw, ih);
    // The source's dimensions AS THEY APPEAR ON SCREEN. Everything downstream — fitting, panning,
    // clamping, hit-testing — then works in screen space and never has to branch on the rotation.
    const sw = rot ? ih : iw, sh = rot ? iw : ih;
    const dpr = Math.min(window.devicePixelRatio || 1, 2.5);
    const base = viewModeRef.current === "actual" ? 1 / dpr : Math.min(cssW / sw, cssH / sh);
    const z = view.current.zoom;
    const dispW = sw * base * z, dispH = sh * base * z;
    const ox = (cssW - dispW) / 2 + view.current.panX;
    const oy = (cssH - dispH) / 2 + view.current.panY;
    return { dispW, dispH, ox, oy, rot };
  };

  const toNorm = (clientX: number, clientY: number) => {
    const c = canvasRef.current, l = computeLayout();
    if (!c || !l) return { x: 0.5, y: 0.5 };
    const r = c.getBoundingClientRect();
    const box = {left:r.left+l.ox,top:r.top+l.oy,width:l.dispW,height:l.dispH};
    return l.rot ? normalizeRotatedPoint(clientX,clientY,box) : normalizeContentPoint(clientX,clientY,box);
  };

  /**
   * Is this screen point on the PICTURE, or in the black around it?
   *
   * normalizeContentPoint clamps rather than rejects, so a tap in the letterbox does not miss —
   * it lands on the nearest edge of the remote desktop, which is exactly where KDE keeps the
   * panel, the dock and the hot corners. In portrait the letterbox is 74% of the screen.
   *
   * Returns true when there is no frame yet, so the very first taps of a session are never eaten.
   */
  const inContent = (clientX: number, clientY: number) => {
    const c = canvasRef.current, l = computeLayout();
    if (!c || !l) return true;
    const r = c.getBoundingClientRect();
    const x = clientX - r.left - l.ox, y = clientY - r.top - l.oy;
    const T = 8;   // forgiveness, so aiming at the very first or last row still works
    return x >= -T && y >= -T && x <= l.dispW + T && y <= l.dispH + T;
  };

  /**
   * Which axes the picture actually overflows on. Two-finger drag pans an overflowing axis and
   * scrolls the remote desktop on one that fits — the honest test, where `zoom > 1.01` was not:
   * in "100%" view the base is 1/dpr, so a phone can be showing half the desktop at zoom exactly
   * 1.00 with panning locked out and no way to reach the other half.
   */
  const canPan = () => {
    const l = computeLayout(), c = canvasRef.current;
    if (!l || !c) return { x: false, y: false };
    return { x: l.dispW > c.clientWidth + 1, y: l.dispH > c.clientHeight + 1 };
  };

  const minZoom = () => (viewModeRef.current === "actual" ? 0.4 : 1);
  const clampPan = () => {
    const l = computeLayout(), c = canvasRef.current;
    if (!l || !c) return;
    if (view.current.zoom < minZoom()) view.current.zoom = minZoom();
    const maxX = Math.max(0, (l.dispW - c.clientWidth) / 2);
    const maxY = Math.max(0, (l.dispH - c.clientHeight) / 2);
    view.current.panX = Math.min(maxX, Math.max(-maxX, view.current.panX));
    // UPWARD TRAVEL IS ALLOWED PAST THE NORMAL LIMIT WHILE THE KEYBOARD IS UP.
    //
    // A picture that fits exactly has no overflow, so the symmetric clamp pins panY to 0 — and a
    // picture pinned at 0 has its bottom third behind the keyboard, which is where the text field
    // you are typing into invariably is. The old code solved that by SHRINKING the canvas to the
    // band above the keyboard, which is what made the picture "choke": on a 390-wide phone the
    // desktop collapsed into a 234x416 stamp with black on all four sides.
    //
    // Lifting is the honest fix. The canvas keeps its full size, the picture slides up by up to the
    // height of what is covering it, and the part you are working on comes out from underneath.
    // Downward travel is unchanged — there is nothing hidden at the top to reach.
    const lift = kbInsetRef.current;
    view.current.panY = Math.min(maxY, Math.max(-(maxY + lift), view.current.panY));
  };

  // ---------- setup ----------
  useEffect(() => {
    const canvas = canvasRef.current!;
    // desynchronized: let the canvas bypass the page's normal compositing lock-step.
    //
    // The default contract is that a canvas paint lands atomically with the rest of the DOM, which
    // costs this canvas a compositor round trip it does not need: nothing else on the page is
    // synchronised with the video, and a toolbar arriving one frame apart from a desktop frame is
    // not something anyone can see. The flag is designed for exactly this class of surface (it is
    // what low-latency ink and video canvases use) and is ignored where it is not supported, so the
    // worst case is the behaviour we already had. alpha:false stays: an opaque canvas skips
    // per-pixel blending on every blit.
    const ctx = canvas.getContext("2d", { alpha: false, desynchronized: true })!;
    let raf = 0, disposed = false;

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2.5);
      canvas.width = Math.round(canvas.clientWidth * dpr);
      canvas.height = Math.round(canvas.clientHeight * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      // A pan that was legal before the rotation is not legal after it. Landscape at zoom 5 can
      // sit at panX 1311; portrait's legal maximum is 780, so without this the picture is blitted
      // entirely off the surface and the screen goes black with nothing to explain it.
      clampPan();
      drawEpochRef.current++;   // the surface itself changed size
    };
    resize();
    window.addEventListener("resize", resize);
    window.addEventListener("orientationchange", resize);

    // Repaint when there is something new to paint, not 60 times a second regardless.
    //
    // This loop cleared the canvas and re-drew a 1080p bitmap on every animation frame whether or not
    // a frame had arrived, whether or not the view had moved, and whether or not the desktop was even
    // changing. On a still screen — which is most of the time, and the case the whole
    // identical-frame-skipping design exists to make cheap — that is 60 full-surface blits a second
    // for an image identical to the one already on screen. On a phone it is the single largest battery
    // cost in the client, and it competes with the H.264 decode for the same main thread.
    //
    // Anything that changes what should be on screen bumps drawEpoch: a new frame, a zoom, a pan, a
    // resize, a cursor move. The rAF loop stays running — it is the cheapest way to stay in step with
    // the compositor — but it returns immediately when nothing has changed.
    const drawState = { epoch: -1 };
    const draw = () => {
      if (disposed) return;
      if (drawEpochRef.current === drawState.epoch) { raf = requestAnimationFrame(draw); return; }
      drawState.epoch = drawEpochRef.current;
      const f = frameRef.current;
      ctx.fillStyle = "#05070d";
      ctx.fillRect(0, 0, canvas.clientWidth, canvas.clientHeight);
      const l = computeLayout();
      if (f && l) {
        // Smoothing has to follow what the canvas ACTUALLY resamples at, not a zoom multiplier.
        // `zoom` multiplies `base`, and base is 0.20 on a portrait phone and 0.75 on a laptop — so
        // at zoom 1.5 a phone is still DOWNSCALING by 24% with smoothing switched off. Nearest
        // neighbour on downscaled text drops whole stems and shimmers every frame, which is why
        // pinching in to read something made it worse rather than better.
        const smoothDpr = Math.min(window.devicePixelRatio || 1, 2.5);
        // The screen extent of the SOURCE'S WIDTH — which is the box's height once the picture is
        // turned. Comparing the wrong one against the source width would report a 2x downscale as a
        // 2x upscale on a rotated phone and switch smoothing exactly backwards.
        const alongSourceW = l.rot ? l.dispH : l.dispW;
        const sampling = (alongSourceW * smoothDpr) / drawableSize(f).w;
        ctx.imageSmoothingEnabled = sampling < 1.5;
        ctx.imageSmoothingQuality = "high";
        if (l.rot) {
          // A quarter turn ANTICLOCKWISE about the centre of the box, so that tilting the phone
          // clockwise — the instinctive direction, and the one that yields landscape-primary on
          // essentially every handset — brings the desktop upright. Drawn with the source's own
          // dimensions in the rotated frame, where the box's width and height are swapped.
          ctx.save();
          ctx.translate(l.ox + l.dispW / 2, l.oy + l.dispH / 2);
          ctx.rotate(-Math.PI / 2);
          ctx.drawImage(f, -l.dispH / 2, -l.dispW / 2, l.dispH, l.dispW);
          ctx.restore();
        } else {
          ctx.drawImage(f, l.ox, l.oy, l.dispW, l.dispH);
        }
        const dot = cursorRef.current;
        if (dot) {
          // The cursor is a DOM element over the canvas, so it is placed in screen space through
          // the same projection the hit-test inverts — never by multiplying out the box directly,
          // which is right in one orientation and silently wrong in the other.
          const p = projectPoint(cursorNorm.current.x, cursorNorm.current.y,
            { left: l.ox, top: l.oy, width: l.dispW, height: l.dispH }, l.rot);
          // Turn the arrow with the picture as well: an upright pointer over a turned desktop
          // points at nothing the desktop recognises as "up and left".
          dot.style.transform = `translate(${p.x}px, ${p.y}px)` + (l.rot ? " rotate(-90deg)" : "");
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
      drawEpochRef.current++;   // a new picture is the whole point of repainting
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

      // AND THEN TRY AGAIN, because "fell back" used to mean "for ever".
      //
      // This was a one-way door: one decode error and the flag stayed false for the whole session,
      // so the room ran at whole-picture JPEG — measured at 79 Mbit/s against H.264's 4.3 at 1080p —
      // until someone thought to reload the page. The trigger does not have to be a broken device:
      // a VideoDecoder can error transiently on a reload that lands mid-GOP, on a phone that
      // thermally throttled for a moment, on a tab that was backgrounded at the wrong instant. A
      // permanent penalty for a temporary condition is exactly the shape of "it was fine and then it
      // got worse and never recovered".
      //
      // Backed off and bounded: the first retry is generous enough that a device in real trouble has
      // stopped being in trouble, each subsequent one waits longer, and after three we accept that
      // this browser genuinely cannot decode H.264 and stop asking. A retry costs one keyframe.
      if (h264RetriesRef.current < 3) {
        const wait = 15000 * Math.pow(2, h264RetriesRef.current);
        h264RetriesRef.current++;
        if (h264RetryTimer.current) window.clearTimeout(h264RetryTimer.current);
        h264RetryTimer.current = window.setTimeout(() => {
          if (disposed || !canDecodeH264()) return;
          h264Ref.current?.reset();
          connRef.current?.setH264(true);
        }, wait);
      }
    }, () => connRef.current?.requestKeyframe());
    h264Ref.current = h264;

    const conn = new RemoteConnection(token, {
      onHello: (h) => {
        connectionEstablishedRef.current = true;
        connectionAlertedRef.current = false;
        setStatus(h.paused ? "paused" : "live");
        if (h.screen?.w && h.screen?.h) screenSizeRef.current = { w: h.screen.w, h: h.screen.h };
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
      onClose: (willReconnect) => {
        lastVal.current = ""; setMods(new Set());
        setStatus((s) => (s === "stopped" || s === "idle" ? s : "reconnecting"));
        if (willReconnect && connectionEstablishedRef.current && !disposed &&
            backgroundAlertsRef.current && !connectionAlertedRef.current) {
          connectionAlertedRef.current = true;
          void showRemoteAlert("connection-interrupted");
        }
      },
      onPong: (rtt) => { const v = Math.round(rtt); setLatency(v); latRef.current = v; },
      onIdle: () => setStatus("idle"),
      onScreen: (avail) => setScreenOk(avail),
      onInputState: (ready,error) => { setInputOk(ready); if(error)showToast(`Input: ${error}`); },
    }, () => {
      // Geometry for every input event. Returning {} here is not harmless: the agent's
      // ValidateEnvelope REQUIRES content and source on every absolute event and silently rejects
      // the ones without them — the live log has "Rejected input 'click': invalid remote content
      // geometry" to prove it. So a tap before the first frame lands was thrown away, and while the
      // video was broken there WAS no first frame, which is how "the screen does not respond to
      // touch" and "there is no picture" turned out to be the same outage twice.
      //
      // There is no reason to be frameless-blind: the agent tells us the desktop size in `hello`, so
      // the source dimensions are known before any pixel arrives, and the canvas rect is always
      // measurable. Fall back to those and the click lands where the user aimed it.
      const c = canvasRef.current;
      if (!c) return {};
      const r = c.getBoundingClientRect();
      const f = frameRef.current;
      const l = computeLayout();
      if (f && l) {
        return { content:{left:l.ox,top:l.oy,width:l.dispW,height:l.dispH},
          canvas:{left:r.left,top:r.top,width:r.width,height:r.height}, source:drawableSize(f) };
      }
      const src = screenSizeRef.current;
      if (!src.w || !src.h || r.width <= 0 || r.height <= 0) return {};
      // No frame yet: the whole canvas IS the content, letterboxed to the desktop's aspect ratio the
      // same way computeLayout would do it once a frame exists — including the quarter turn, so the
      // very first taps of a session land where they were aimed rather than transposed.
      const rot = shouldRotate(src.w, src.h);
      const sw = rot ? src.h : src.w, sh = rot ? src.w : src.h;
      const base = Math.min(r.width / sw, r.height / sh);
      const dispW = sw * base, dispH = sh * base;
      return { content:{left:(r.width-dispW)/2, top:(r.height-dispH)/2, width:dispW, height:dispH},
        canvas:{left:r.left,top:r.top,width:r.width,height:r.height}, source:src };
    });
    connRef.current = conn;
    conn.connect();

    const gest = new GestureController(canvas, toNorm, () => view.current.zoom, {
      click: (b, x, y) => {
        conn.click(b, x, y);
        // Tapping a DIFFERENT field while the keyboard is up should bring that field into view, not
        // leave the viewer looking at the last one. Deferred a frame so the click lands first and
        // the cursor position this reads is the one the user just chose.
        if (kbOpenRef.current) requestAnimationFrame(() => focusCursor());
      },
      dblclick: (x, y) => conn.dblclick(x, y),
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
          // Keep the pixel that was under the fingers under the fingers. Projected rather than
          // multiplied out, so the anchor holds in a rotated view too.
          const r = c.getBoundingClientRect();
          const p = projectPoint(before.x, before.y,
            { left: l.ox, top: l.oy, width: l.dispW, height: l.dispH }, l.rot);
          view.current.panX += (fx - r.left) - p.x;
          view.current.panY += (fy - r.top) - p.y;
        }
        clampPan();
        drawEpochRef.current++;
      },
      panBy: (dx, dy) => { view.current.panX += dx; view.current.panY += dy; clampPan(); drawEpochRef.current++; },
      cursorAt: (x, y) => { cursorNorm.current = { x, y }; drawEpochRef.current++; },
      haptic: () => {if(hapticsRef.current)navigator.vibrate?.(8);},
      zoomToggleAt: (fx, fy) => zoomToggleAt(fx, fy),
    }, () => mouseSensitivityRef.current, inContent, canPan,
       () => computeLayout()?.rot ?? false);
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
      cursorAt: (x, y) => { cursorNorm.current = { x, y }; drawEpochRef.current++; },
      pasteIntent: () => { pasteIntentAt.current = performance.now(); armPasteFallback(); },
    }, () => scrollSensitivityRef.current, () => pointerLockRef.current);
    desktopRef.current = desk;
    if (modeRef.current === "desktop") desk.attach();

    const fpsTimer = window.setInterval(() => { setFps(fpsCount.current); fpsCount.current = 0; }, 1000);
    bumpToolbar();
    // No "Turn your phone sideways for a full-size desktop" nag on every portrait launch: nagging
    // the user about how to hold their phone is exactly the kind of pushiness the owner asked to be
    // rid of. The picture follows the phone (see shouldRotate); if they want it bigger they turn the
    // phone or pick 🔒 Sideways, on their own terms.
    //
    // What replaces it is said once, ever, and is about the thing that is genuinely not guessable:
    // the gesture. Two fingers do three different jobs here and none of them is discoverable by
    // looking, so the one hint that earns its space is the one naming them.
    let gestureHintTimer: number | null = null;
    if (!localStorage.getItem("moremote.seenGestureHint")) {
      try { localStorage.setItem("moremote.seenGestureHint", "1"); } catch { /* private mode */ }
      gestureHintTimer = window.setTimeout(
        () => showToast("Two fingers: scroll · pinch to zoom · double-tap to magnify"), 1400);
    }

    return () => {
      disposed = true;
      if (h264RetryTimer.current) window.clearTimeout(h264RetryTimer.current);
      h264RetryTimer.current = null;
      h264Ref.current?.reset();
      h264Ref.current = null;
      cancelAnimationFrame(raf);
      window.clearInterval(fpsTimer);
      if (gestureHintTimer) window.clearTimeout(gestureHintTimer);
      if (refreshTimerRef.current) window.clearTimeout(refreshTimerRef.current);
      refreshTimerRef.current = null;
      if (toastTimer.current) window.clearTimeout(toastTimer.current);
      toastTimer.current = null;
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

  /**
   * Stop the stream while nobody is looking, and pick it back up cleanly.
   *
   * A hidden tab does not close its socket: the browser throttles rAF and timers to almost nothing
   * while the WebSocket keeps delivering at full rate, so frames pile up in a receive buffer the
   * page is not draining. Caught on the live machine on a tab that had merely been switched away
   * from — `ss -tn` reported Recv-Q 7301038, seven megabytes of desktop nobody watched. Returning to
   * that tab means several seconds of the past playing out before the present arrives, which is
   * precisely the "it freezes and then everything happens at once" report. On a phone the same thing
   * is battery and mobile data spent on a screen that is in a pocket, and it is why the remote makes
   * a phone hot.
   *
   * Three things happen on hide, and each is doing different work:
   *   - the agent is told nobody is watching, which (once every viewer agrees) tears the encode
   *     pipeline down and stops the compositor copying frames at all;
   *   - the H.264 decoder is reset, because whatever it holds will be stale by the time anyone
   *     looks again and a half-decoded GOP is not worth carrying;
   *   - nothing else. In particular the socket stays open, so the session, the token and the input
   *     path all survive a glance at another app.
   *
   * On show, the reverse plus a keyframe request: the pipeline has to start from an IDR, and asking
   * is far cheaper than waiting up to a full GOP staring at a frozen picture.
   */
  useEffect(() => {
    const onVis = () => {
      const conn = connRef.current;
      if (!conn) return;
      if (document.hidden) {
        conn.setWatching(false);
        h264Ref.current?.reset();
        pendingRef.current = null;
      } else {
        conn.setWatching(true);
        conn.requestKeyframe();
        // The canvas still holds the last frame from before, and the first new one may be a moment
        // away; repaint so the letterboxing is right for whatever size we came back at.
        drawEpochRef.current++;
      }
    };
    // iOS fires pagehide rather than visibilitychange when Safari is backgrounded from the app
    // switcher. Same intent, different name; both are wired, and both are removed.
    const onHide = () => connRef.current?.setWatching(false);
    const onShow = () => { connRef.current?.setWatching(true); connRef.current?.requestKeyframe(); };
    document.addEventListener("visibilitychange", onVis);
    window.addEventListener("pagehide", onHide);
    window.addEventListener("pageshow", onShow);
    return () => {
      document.removeEventListener("visibilitychange", onVis);
      window.removeEventListener("pagehide", onHide);
      window.removeEventListener("pageshow", onShow);
    };
  }, []);

  /**
   * COPY ON YOUR COMPUTER, PASTE INTO THE REMOTE — with the keys you already use.
   *
   * Ctrl+V is not forwarded as a chord (see DesktopInput.onKeyDown). Instead the browser's own
   * `paste` event delivers what is on the LOCAL clipboard, that text is pushed to the remote's
   * clipboard, and only then is Ctrl+V pressed over there. The result is what the user expected the
   * first time: the thing they copied here appears in the window they are looking at.
   *
   * The fallback is what makes it safe to intercept a key at all. A browser may decline to fire
   * `paste` — nothing on the clipboard, an image rather than text, a policy that requires a user
   * gesture the page did not get. If nothing has arrived within PASTE_WAIT_MS the chord is forwarded
   * exactly as it always was, so the worst case is the previous behaviour rather than a dead key.
   */
  const PASTE_WAIT_MS = 140;
  const pasteIntentAt = useRef(0);
  const pasteTimer = useRef<number | null>(null);

  const armPasteFallback = useCallback(() => {
    if (pasteTimer.current) window.clearTimeout(pasteTimer.current);
    pasteTimer.current = window.setTimeout(() => {
      pasteTimer.current = null;
      if (!pasteIntentAt.current) return;
      pasteIntentAt.current = 0;
      connRef.current?.combo(["Control", "V"]);   // the old behaviour, unchanged
    }, PASTE_WAIT_MS);
  }, []);

  useEffect(() => {
    if (mode !== "desktop") return;
    const onPaste = async (e: ClipboardEvent) => {
      // Only when the viewer actually asked for a paste on the REMOTE. A paste into the app's own
      // "Send text" box, or into the PIN field, is that field's business and must not be hijacked.
      if (!pasteIntentAt.current || performance.now() - pasteIntentAt.current > 1500) return;
      const text = e.clipboardData?.getData("text") ?? "";
      if (!text) return;                          // let the fallback forward the chord
      e.preventDefault();
      pasteIntentAt.current = 0;
      if (pasteTimer.current) { window.clearTimeout(pasteTimer.current); pasteTimer.current = null; }
      try {
        await setClipboard(token, text);
        connRef.current?.combo(["Control", "V"]);
      } catch {
        // The clipboard endpoint refused. Pressing Ctrl+V anyway is strictly better than nothing:
        // whatever is on the remote's own clipboard is at least something the user can see and undo.
        connRef.current?.combo(["Control", "V"]);
        showToast("Couldn't send the clipboard to the PC");
      }
    };
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, token]);

  /**
   * On a computer, reach for the toolbar the way you reach for a dock: put the pointer at the
   * bottom edge.
   *
   * The bar hides itself after a few seconds — correctly, because on a phone it sits over the part
   * of the desktop you are trying to touch. But the way BACK is a 44px handle at the side of the
   * screen, and a handle is a touch affordance: on a phone it is a thumb's width away from wherever
   * the thumb already is, and on a computer it is a deliberate trip across the window with a mouse,
   * to hit a target smaller than most buttons, every single time you want Files or the keyboard.
   *
   * A mouse has something a finger does not: it can hover. So in desktop mode the bottom strip of
   * the window summons the bar, which is the gesture every dock and every full-screen video player
   * already trained everyone to make. The handle stays for anyone who wants it.
   *
   * Deliberately not wired in the touch modes: there is no hover there, and a pointermove from a
   * finger already means something else entirely.
   */
  useEffect(() => {
    if (mode !== "desktop") return;
    const EDGE = 76;
    let armed = true;
    const onMove = (e: PointerEvent) => {
      const near = e.clientY > window.innerHeight - EDGE;
      // Re-arm only after the pointer has LEFT the strip, so sitting still down there does not
      // restart the hide timer on every jitter — and so the bar can still time out while the
      // pointer rests over the dock the user is actually aiming at.
      if (near && armed) { armed = false; bumpToolbar(); }
      else if (!near) armed = true;
    };
    window.addEventListener("pointermove", onMove, { passive: true });
    return () => window.removeEventListener("pointermove", onMove);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  useEffect(() => {
    gestureRef.current?.setMode(mode);
    connRef.current?.setInputMode(mode);
    // Exactly one of the two input layers is live at a time. Detaching also releases whatever the
    // remote currently thinks is held, so switching modes mid-drag cannot leave a button down.
    const desk = desktopRef.current;
    if (!desk) return;
    if (mode === "desktop") desk.attach(); else desk.detach();
  }, [mode]);

  // The bar stays painted while a sheet is open, so its hide timer must not keep running behind
  // it — otherwise reading the quality presets or dragging a sensitivity slider always outlives
  // the 4.5s, and the toolbar vanishes the instant the sheet is dismissed, for no visible reason.
  useEffect(() => {
    if (sheet) { if (hideTimer.current) window.clearTimeout(hideTimer.current); }
    else bumpToolbar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sheet]);

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

  /**
   * TYPING ON A PHONE, AND WHY THIS IS NOT A LAYOUT PROBLEM.
   *
   * WHAT IT USED TO DO. When the keyboard came up, the canvas was shrunk to the band left above it
   * (`canvas.style.height = vv.height - barH`) so that nothing was hidden. That sounds right and it
   * is the source of both complaints:
   *
   *   - THE PICTURE CHOKES. A 390x844 phone with a 336px keyboard leaves a 390x416 band, and a 16:9
   *     desktop fitted into that is a 390x219 stamp — or, turned, a 234x416 sliver. The desktop's
   *     text was already 4x too small to read at full height; in a third of the height it is not
   *     text, it is texture. You cannot type into something you cannot read.
   *   - IT FLIPS. That band is often WIDER THAN IT IS TALL (on a 375x667 phone: 375x315), and the
   *     automatic rotation rule reads "wider than tall" as "landscape, stop turning the picture". So
   *     tapping a text box rotated the whole desktop a quarter turn, and dismissing the keyboard
   *     rotated it back.
   *
   * WHAT IT DOES NOW. The canvas keeps its full size and the PICTURE moves instead:
   *
   *   1. the rotation is latched, so nothing flips while you are mid-sentence;
   *   2. `kbInsetRef` records how much of the bottom is covered, which is what buys clampPan the
   *      extra upward travel to lift a fitted picture clear of the keyboard;
   *   3. the view zooms to a readable magnification and centres on the cursor — the one place on
   *      the desktop that matters while typing is where the caret is;
   *   4. all of it is put back exactly as it was when the keyboard closes.
   *
   * The whole screen stays the whole screen; the part you are working on comes to meet you.
   */
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
      // The canvas is deliberately NOT resized here any more; see the note above. What the rest of
      // the layout needs is not a smaller surface but an honest number for how much of it is buried.
      kbInsetRef.current = kbOpen ? Math.min(kb + barH, canvas.clientHeight * 0.75) : 0;

      // ASSIGNING canvas.width WIPES THE CANVAS — WHICH IS WHY THIS USED TO GO BLACK.
      //
      // Two bugs sat in the four lines this replaces, and together they made the picture disappear.
      //
      // First, the backing store was re-assigned on EVERY call, and this handler is wired to
      // visualViewport's `scroll` as well as its `resize` — so on iOS it fires while the address bar
      // slides, while the page rubber-bands, and on every keystroke that moves the keyboard. Writing
      // canvas.width is a full reallocate-and-clear even when the value is identical, so the picture
      // was being erased dozens of times a second for no reason at all.
      //
      // Second, and this is what made the erase permanent: the draw loop only repaints when
      // drawEpoch has moved, and nothing here moved it. So after the wipe the loop looked at an
      // unchanged epoch and returned immediately, leaving the cleared surface on screen until the
      // next FRAME arrived from the server. On a still desktop — which is most of the time, because
      // the capture is damage-driven and a screen nobody is changing produces no frames at all —
      // "the next frame" can be a long time coming. Open the keyboard on a quiet desktop and the
      // screen went black and stayed black.
      //
      // So: resize only when the pixel size genuinely changed, and invalidate unconditionally, since
      // even a pure CSS height change means the letterboxing has to be recomputed.
      const dpr = Math.min(window.devicePixelRatio || 1, 2.5);
      const w = Math.round(canvas.clientWidth * dpr);
      const h = Math.round(canvas.clientHeight * dpr);
      if (w > 0 && h > 0 && (canvas.width !== w || canvas.height !== h)) {
        canvas.width = w;
        canvas.height = h;
        canvas.getContext("2d")?.setTransform(dpr, 0, 0, dpr, 0, 0);
      }
      // Keep the caret above the keyboard as the keyboard's own height changes — it does, on both
      // platforms, when a suggestion strip appears or an emoji panel opens.
      if (kbOpen) focusCursor();
      clampPan();   // the visible area just changed; see the note in resize()
      drawEpochRef.current++;
    };
    vv.addEventListener("resize", update);
    vv.addEventListener("scroll", update);
    update();
    return () => { vv.removeEventListener("resize", update); vv.removeEventListener("scroll", update); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kbOpen]);

  /**
   * Bring the remote cursor into the band the keyboard has not covered, at a size you can read.
   *
   * ZOOM. At "fit" on a phone the desktop is reduced about four times, which is fine for finding a
   * window and useless for reading the line you are typing. ZOOM_SNAP (2.2x) is the same
   * magnification the two-finger double-tap uses, so "readable" means one thing in this app rather
   * than two. It only ever zooms IN — a viewer who had already pinched closer keeps their zoom.
   *
   * PLACEMENT. 0.42 of the free band, not 0.5: text sits ABOVE the caret, so leaving a little more
   * room below it puts the line you are writing and the two lines you just wrote all on screen.
   */
  const KB_FOCUS_Y = 0.42;
  const focusCursor = () => {
    const c = canvasRef.current;
    if (!c) return;
    const band = Math.max(80, c.clientHeight - kbInsetRef.current);
    if (typingZoomRef.current) {
      view.current.zoom = Math.min(5, Math.max(view.current.zoom, minZoom() * ZOOM_SNAP));
    }
    const l = computeLayout();
    if (!l) return;
    const p = projectPoint(cursorNorm.current.x, cursorNorm.current.y,
      { left: l.ox, top: l.oy, width: l.dispW, height: l.dispH }, l.rot);
    view.current.panX += c.clientWidth / 2 - p.x;
    view.current.panY += band * KB_FOCUS_Y - p.y;
    clampPan();
    drawEpochRef.current++;
  };

  /**
   * Enter and leave the typing mode. Called from the two buttons, NOT from an effect on `kbOpen`.
   *
   * WHY NOT AN EFFECT, WHICH IS WHERE THIS WAS AND WHY THE RESTORE SILENTLY DID NOTHING
   *
   * Both this and the visualViewport handler above key off `kbOpen`, and React runs effects in the
   * order they are declared. The viewport one is declared first, so on open it ran first, called
   * focusCursor(), and zoomed — and only THEN did this one run and save "the view to put back",
   * which by that point was the zoomed view. Closing the keyboard restored the magnification it was
   * supposed to undo, and the viewer was left at 2.2x on a random part of the desktop with no way
   * back but a manual reset.
   *
   * The user's press is the only moment that unambiguously precedes every consequence of it. Saving
   * and restoring there removes the ordering question rather than answering it.
   */
  const enterTyping = () => {
    if (!kbSavedView.current) kbSavedView.current = { ...view.current };
    // Latch the rotation while the viewport still has the shape the user can see; see kbRotLatch.
    const f = frameRef.current;
    if (f) { const s = drawableSize(f); kbRotLatch.current = shouldRotate(s.w, s.h); }
  };

  const leaveTyping = () => {
    kbRotLatch.current = null;
    kbInsetRef.current = 0;
    const saved = kbSavedView.current;
    kbSavedView.current = null;
    if (saved) view.current = saved;
    clampPan();
    drawEpochRef.current++;
  };

  // ---------- settings (quality + view) ----------
  // Read the preset through a ref: onHello is wired once, so closing over presetIdx directly
  // would make every reconnect re-send the preset that was selected on first render.
  /**
   * How many encoded pixels this viewer can actually SHOW.
   *
   * WHY THE PRESET ALONE WAS THE WRONG ANSWER IN BOTH DIRECTIONS
   *
   * The request was the preset's width and nothing else — the same 1366 or 1920 whether the picture
   * was being drawn into a 390px-wide phone or a 2560px-wide browser window. That is wrong twice
   * over, and each way is one of the two complaints this change exists to answer:
   *
   *   ON A PHONE it asks for pixels that are thrown away before they are ever seen. Measured here:
   *   a 390x844 phone showing the desktop fitted upright draws it 390 CSS px wide; at DPR 3 that is
   *   1170 real pixels, and "Balanced" was asking the encoder for 1366 while "Sharp" asked for
   *   1920 — 64% more bits than the display can resolve. Those bits are not free: they are encode
   *   time, bitrate on a cellular link, and decode work on a phone that is already the slowest thing
   *   in the chain. Paying them buys literally nothing visible.
   *
   *   ON A COMPUTER it asks for FEWER pixels than the window shows, and there is no way to get them
   *   back. A 2560-wide browser window on the default preset was being sent 1366 and upscaling it by
   *   1.9x — which is exactly the "the picture is not sharp when I open it on the computer" report,
   *   and no bitrate could have fixed it, because the detail was discarded before the encoder.
   *
   * So ask for what is on screen. The preset stays in charge of BANDWIDTH — it owns quality (bits
   * per pixel) and fps, and its width remains the ceiling — but it can no longer demand more pixels
   * than exist, and see autoMaxPreset() for how a genuinely large display is allowed past 1920.
   *
   * Zoom is included deliberately: pinching in to read something asks the encoder for the detail
   * that makes it readable, which is the one moment resolution is worth spending on.
   */
  const displayWidthPx = () => {
    const c = canvasRef.current;
    if (!c) return 0;
    const dpr = Math.min(window.devicePixelRatio || 1, 2.5);
    const l = computeLayout();
    // Before the first frame there is no layout; fit the known desktop size into the canvas the same
    // way, so the very first settings push is already the right size instead of a guess to be undone.
    let alongSourceWidth: number;
    if (l) alongSourceWidth = l.rot ? l.dispH : l.dispW;
    else {
      // ...and the estimate has to account for the quarter turn too, or the first request and the
      // one that replaces it a second later disagree — and every disagreement is a pipeline rebuild
      // the user watches as a blank screen. Measured before this branch knew about rotation, one
      // connection produced "Video stream: 974x548" immediately followed by "1366x768": two builds,
      // for one viewer, whose size never actually changed. `hello` carries the desktop's dimensions,
      // so there is nothing here that has to be guessed.
      const src = screenSizeRef.current;
      const cw = c.clientWidth, ch = c.clientHeight;
      if (!src.w || !src.h || cw <= 0 || ch <= 0) return 0;
      const rot = shouldRotate(src.w, src.h);
      const sw = rot ? src.h : src.w, sh = rot ? src.w : src.h;
      const base = Math.min(cw / sw, ch / sh);
      alongSourceWidth = rot ? sh * base : sw * base;
    }
    return Math.ceil(alongSourceWidth * dpr);
  };

  /**
   * How far the automatic ladder may climb, given what this viewer can actually show.
   *
   * AUTO_MAX_PRESET stops at 1920 because RTT is not bandwidth and Ultra's 2560 is a real cost to
   * impose on a link that merely pings well. That reasoning holds for a phone and inverts for a big
   * monitor: there, 1920 is not caution, it is a picture that is permanently soft on a machine whose
   * owner is sitting in front of a screen that can show more. The bitrate is derived from the actual
   * size now (bits-per-pixel x w x h x fps in the helper), so asking for the pixels the display has
   * is an honest request rather than an open-ended one.
   */
  const autoMaxPreset = () => (displayWidthPx() > 1920 ? QUALITY_PRESETS.length - 1 : AUTO_MAX_PRESET);

  /** The last width we asked for, and when — the dead band and the floor that protect the helper. */
  const lastPushedWidth = useRef(0);
  const lastWidthPushAt = useRef(0);

  const pushSettings = () => {
    const p = QUALITY_PRESETS[presetIdxRef.current] ?? QUALITY_PRESETS[1];
    // "100%" means the viewer wants real device pixels rather than a fitted picture, so the preset's
    // width stops being a ceiling; everywhere else it still is.
    // Zooming in is an explicit request to inspect detail: the preset ceiling
    // (tuned for the fitted view) must not pin a 2x zoom to upscaled mush, so a
    // zoomed viewer may ask up to the hard 2560 cap just like "100%".
    const zoomed = view.current.zoom > 1.05;
    const ceiling = viewModeRef.current === "actual" || zoomed ? 2560 : Math.min(p.width, 2560);
    const shown = displayWidthPx();
    // A zero means we could not measure yet (no canvas, no size): fall back to the preset rather
    // than to a floor, or the first seconds of every session would be a deliberately small picture.
    // The floor is 720: below that, text on a 1080p desktop is unreadable on ANY
    // phone, and the encode cost of 720 vs 480 is noise even on llvmpipe.
    const width = shown > 0 ? Math.max(720, Math.min(ceiling, shown)) : ceiling;
    lastPushedWidth.current = width;
    connRef.current?.settings(p.quality, p.fps, width, Math.min(1, width / 2560));
  };
  // `orient` belongs here: turning the picture swaps which of the source's axes runs across the
  // screen, so the number of encoded pixels this viewer can show changes with it.
  useEffect(() => { pushSettings(); /* eslint-disable-next-line */ }, [presetIdx, viewMode, orient]);

  /**
   * Re-ask when the size the picture is drawn at has genuinely moved.
   *
   * Every settings push that changes the width costs the helper a full GStreamer teardown and
   * rebuild (~200ms with no picture, then a fresh IDR), so this must never chase a pinch frame by
   * frame. Two guards: a 12% dead band, which is well inside "you would not notice the difference"
   * and well outside ordinary rounding; and a 1.5s floor, which is longer than any burst of resize
   * events a rotation or an address bar can produce.
   */
  useEffect(() => {
    const id = window.setInterval(() => {
      if (!connRef.current?.open) return;
      const want = displayWidthPx();
      if (want <= 0) return;
      const prev = lastPushedWidth.current;
      if (prev > 0 && Math.abs(want - prev) / prev < 0.12) return;
      if (Date.now() - lastWidthPushAt.current < 1500) return;
      lastWidthPushAt.current = Date.now();
      pushSettings();
    }, 700);
    return () => window.clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Auto quality: adapt to the network using round-trip latency (RTT). We deliberately do NOT
  // use fps — with identical-frame skipping, a still screen sends few frames, which is not lag.
  //
  // WHY THIS IS NOT A ONE-LINE THRESHOLD ANY MORE
  //
  // It was, and the loop it made was self-sustaining. Climbing to a richer preset raises the encode
  // cost and the bitrate, which raises the RTT, which trips the drop threshold, which lowers the RTT,
  // which trips the climb threshold — for ever. A preset change costs the server a full pipeline
  // rebuild, so the oscillation was not a cosmetic wobble: it was a stream that never held a keyframe.
  //
  // Three things make a control loop like this stable, and it had none of them:
  //   * a DEAD BAND wide enough that one step cannot carry the measurement across it (120..250 was
  //     narrower than the latency change a step itself causes);
  //   * CONSECUTIVE agreeing samples, so a single jittery ping cannot move anything — and on a
  //     Tailscale DERP relay the jitter is routinely 33..93ms all by itself;
  //   * a COOLDOWN after acting, so the loop observes the consequence of its last move before making
  //     another. Climbing needs a longer one than dropping: being slow to give someone more quality
  //     costs them nothing, being slow to relieve a struggling link costs them the session.
  const inputBurstAtRef = useRef(0);
  const autoStateRef = useRef({ up: 0, down: 0, last: 0 });
  useEffect(() => {
    if (!auto) return;
    autoStateRef.current = { up: 0, down: 0, last: Date.now() };
    const SAMPLE_MS = 2000;
    const AGREE_UP = 4;        // ~8s of consistently good latency before asking for more
    const AGREE_DOWN = 2;      // ~4s of bad latency is enough to back off
    const COOLDOWN_UP = 20000;
    const COOLDOWN_DOWN = 6000;
    const id = window.setInterval(() => {
      const lat = latRef.current;
      if (!lat) return;                        // no measurement yet — never act on a zero
      // Injection bursts (typing, drags) load the compositor and briefly inflate
      // RTT. That is the session working, not the network failing — stepping the
      // picture down on it is why quality cratered exactly while typing.
      if (Date.now() - inputBurstAtRef.current < 1500) return;
      const st = autoStateRef.current;
      const since = Date.now() - st.last;
      if (lat > 400) { st.down++; st.up = 0; }
      else if (lat < 90) { st.up++; st.down = 0; }
      else { st.up = 0; st.down = 0; }         // inside the dead band: forget, do not drift
      if (st.down >= AGREE_DOWN && since > COOLDOWN_DOWN) {
        // Auto backs off to Balanced at worst. Data saver's 540p exists for an
        // explicit human choice (metered data); a latency spike must never park
        // the session on an unreadable picture ("always blurry, can't see").
        setPresetIdx((idx) => { if (idx <= 1) return idx; st.last = Date.now(); st.down = 0; return idx - 1; });
      } else if (st.up >= AGREE_UP && since > COOLDOWN_UP) {
        const cap = autoMaxPreset();
        setPresetIdx((idx) => { if (idx >= cap) return idx; st.last = Date.now(); st.up = 0; return idx + 1; });
      }
    }, SAMPLE_MS);
    return () => window.clearInterval(id);
  }, [auto]);

  const selectPreset = (i: number) => { setPresetIdx(i); showToast(`Quality: ${QUALITY_PRESETS[i].label} · ${QUALITY_PRESETS[i].detail}`); };
  /**
   * Turning the picture changes which way is "wide", so a pan and a zoom from the old orientation
   * mean nothing in the new one — reset them rather than clamp them into something arbitrary. The
   * settings push is what re-asks the encoder for the size the NEW layout will actually show.
   */
  const ORIENT_LABEL: Record<Orient, string> = {
    auto: "Follows your phone — upright",
    on: "Turned sideways — fills the screen",
    off: "Locked upright",
  };
  const chooseOrient = (m: Orient) => {
    setOrient(m);
    orientRef.current = m;                    // the draw loop and the hit-test read the ref, now
    kbRotLatch.current = null;                // an explicit choice outranks a frozen one
    view.current = { zoom: 1, panX: 0, panY: 0 };
    // NONE of these three settings rotates the PHONE — they only decide how the picture is
    // drawn inside whatever the phone is doing. So every one of them also releases a
    // physical orientation lock, which gives the user a one-tap way out of a lock a
    // previously-installed version pinned at install time (see the unlock on startup).
    try {
      const so = (screen as any)?.orientation;
      if (so?.unlock) { so.unlock(); }
    } catch { /* nothing locked, or not permitted here */ }
    invalidate();
    showToast(ORIENT_LABEL[m]);
  };

  const chooseView = (m: ViewMode) => {
    setViewMode(m);
    view.current = { zoom: m === "actual" ? 1 : 1, panX: 0, panY: 0 };
    invalidate();
    showToast(m === "fit" ? "Fit to screen" : "Original size (100%)");
  };
  const zoomBy = (f: number) => { view.current.zoom = Math.min(5, Math.max(minZoom(), view.current.zoom * f)); clampPan(); invalidate(); };
  const resetZoom = () => { view.current = { zoom: 1, panX: 0, panY: 0 }; invalidate(); };

  /**
   * Snap between "the whole desktop" and "close enough to read", centred where the fingers were.
   *
   * There are only two magnifications anyone on a phone actually wants, and pinching between them is
   * a two-handed operation on a device usually held in one. 2.2x is the point at which 1080p-class
   * text on a 6" screen becomes readable rather than merely legible; going back is a single gesture
   * rather than the several pinches it takes to unwind one.
   *
   * Reads only refs, so the copy captured by the gesture controller on mount stays correct.
   */
  const ZOOM_SNAP = 2.2;
  const zoomToggleAt = (fx: number, fy: number) => {
    const c = canvasRef.current;
    const zoomedIn = view.current.zoom > minZoom() * 1.2;
    if (zoomedIn) {
      view.current = { zoom: minZoom(), panX: 0, panY: 0 };
    } else {
      const before = toNorm(fx, fy);
      view.current.zoom = Math.min(5, minZoom() * ZOOM_SNAP);
      const l = computeLayout();
      if (l && c) {
        const r = c.getBoundingClientRect();
        const p = projectPoint(before.x, before.y,
          { left: l.ox, top: l.oy, width: l.dispW, height: l.dispH }, l.rot);
        view.current.panX += (fx - r.left) - p.x;
        view.current.panY += (fy - r.top) - p.y;
      }
    }
    clampPan();
    invalidate();
  };

  // ---------- keyboard ----------
  // A real visible input. Tapping it raises the iOS keyboard; we diff its value so typing
  // AND Backspace both work (the field must hold text for iOS to fire delete events).
  const openKeyboard = () => {
    enterTyping();          // before setKbOpen, so nothing has moved the view yet
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
    leaveTyping();
  };
  /**
   * Keep the phone's keyboard OPEN when one of these buttons is pressed.
   *
   * THE BUG, WHICH IS MOST OF "I CANNOT TYPE ON THE PHONE". Every control in the keyboard bar is a
   * <button>, and on Android Chrome pressing a button moves focus away from the text field — which
   * closes the soft keyboard. So tapping Ctrl, or Esc, or an arrow key, or Backspace dismissed the
   * keyboard, and the user had to tap the field again for every single one. Sending Ctrl+C to the
   * remote desktop should not cost you your keyboard.
   *
   * It was guarded with `onMouseDown`, and that is the part that looks right and is not: on a touch
   * screen the compatibility mouse events are synthesised AFTER the touch has already moved focus,
   * so the handler runs too late to prevent anything. `pointerdown` is the first event in the
   * sequence and is the only one early enough. Preventing its default suppresses the focus change
   * (and the synthetic mouse events) while still delivering `click`, which is what these buttons
   * actually listen for.
   *
   * Spread onto every button in the bar rather than onto the bar itself: the shortcut row scrolls
   * sideways, and preventing the default on the scroll container would be preventing the scroll.
   */
  const keepFocus = { onPointerDown: (e: React.PointerEvent) => e.preventDefault() };

  const sendKey = (key: string) => {
    const c = connRef.current; if (!c) return;
    inputBurstAtRef.current = Date.now();
    if (mods.size > 0) { c.combo([...mods, key]); setMods(new Set()); } else c.keyTap(key);
  };
  const toggleMod = (m: string) => setMods((s) => { const n = new Set(s); n.has(m) ? n.delete(m) : n.add(m); return n; });

  // Diff the field value into keystrokes (handles text, Backspace, Arabic, autocorrect).
  const onInput = () => {
    const el = inputRef.current!, v = el.value, last = lastVal.current, c = connRef.current;
    if (!c) { lastVal.current = v; return; }
    inputBurstAtRef.current = Date.now();
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
      // Replaced (autocorrect/IME rewrite). Deleting the WHOLE line and retyping
      // it turned one autocorrect into a Backspace storm — up to 300 taps — that
      // visibly stalled the session. Autocorrect rewrites one word: keep the
      // common prefix AND suffix, delete only the differing middle, retype it.
      let p = 0;
      const max = Math.min(last.length, v.length);
      while (p < max && last[p] === v[p]) p++;
      let sf = 0;
      while (sf < max - p && last[last.length - 1 - sf] === v[v.length - 1 - sf]) sf++;
      const removed = last.length - p - sf;
      // The remote caret sits at the end of what we sent; step over the shared
      // suffix, delete the middle, type the replacement, then walk back.
      for (let i = 0; i < sf; i++) c.keyTap("ArrowLeft");
      for (let i = 0; i < removed; i++) c.keyTap("Backspace");
      const middle = v.slice(p, v.length - sf);
      if (middle) c.text(middle);
      for (let i = 0; i < sf; i++) c.keyTap("ArrowRight");
    }
    lastVal.current = v;
    // Resync while the line is still short: the worst replace burst above is
    // bounded by this cap, and Backspace-on-empty is handled in onKeyDown.
    if (v.length > 48) { el.value = ""; lastVal.current = ""; }
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
  const downloadFile = async (en: FileEntry) => {
    const a = document.createElement("a");
    try { a.href = await fileDownloadUrl(token, en.path); }
    catch { showToast("Download authorization failed"); return; }
    a.download = en.name;
    document.body.appendChild(a); a.click(); a.remove();
    showToast("Downloading " + en.name);
  };
  const onUploadFiles = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files; const dir = fileList?.path;
    if (!files || !dir) { e.target.value = ""; return; }
    setFileBusy(true);
    try {
      for (const f of Array.from(files)) {
        await uploadFile(token, dir, f, (sent, total) =>
          setUploadProgress(`${f.name} · ${Math.floor(sent * 100 / total)}%`));
      }
      if (backgroundAlertsRef.current) {
        void showRemoteAlert("upload-complete");
      }
      showToast(`Uploaded ${files.length} to PC`); await navFiles(dir);
    }
    catch { showToast("Upload paused — select the same file to resume"); }
    setUploadProgress("");
    setFileBusy(false);
    e.target.value = "";
  };

  // ---------- toolbar actions ----------
  const c = () => connRef.current;
  const cycleMode = () => {
    // Walks the three real models. "direct" is a variant of touch (the one-finger-drag
    // switch in the Controls sheet), so cycling into it here would step through a state
    // the toolbar has no way to explain.
    const order: GestureMode[] = ["touch", "trackpad", "desktop"];
    const cur = mode === "direct" ? "touch" : mode;
    const next = order[(order.indexOf(cur) + 1) % order.length];
    setMode(next); showToast(`Mouse: ${MODE_LABEL[next]}`);
  };
  const taskMgr = () => { c()?.combo(["Control", "Shift", "Escape"]); showToast("Task Manager (safe Ctrl+Alt+Del)"); };

  // ---------- sound ----------
  //
  // The desktop stream carries no audio and never has (the agent has no capture and no encoder).
  // The machine's sound is a SEPARATE service — moos-cloud-audio, the default sink's monitor as
  // Opus-in-WebM — and this URL is how the phone reaches it.
  //
  // It used to be a bare `audio/stream.webm`, published beside this app by
  // `tailscale serve --set-path=/audio`. That service has no authentication of any kind, so the
  // result was an unauthenticated live stream of the machine's sound on the same host, port and
  // certificate as a desktop that demands a 6-digit PIN — measured at 200 while POST /api/login
  // returned 401. Every device on the tailnet could listen, silently.
  //
  // It now goes through the agent, which is the only thing here that owns authentication. Since an
  // <audio> element cannot send an Authorization header, the client asks for a short-lived,
  // single-use ticket. The reusable session bearer never enters browser or proxy URL history.

  const stopSound = useCallback(() => {
    audioGenerationRef.current++;
    if (audioRetryRef.current !== null) {
      window.clearTimeout(audioRetryRef.current);
      audioRetryRef.current = null;
    }
    const a = audioRef.current;
    if (a) { a.pause(); a.removeAttribute("src"); a.load(); }
    setSound("off");
  }, []);

  const startSound = useCallback(async () => {
    const a = audioRef.current;
    if (!a) return;
    const generation = ++audioGenerationRef.current;
    setSound("connecting");
    // Cache-busting is load-bearing, not superstition: the service spawns one encoder per listener
    // and kills it on disconnect, so the previous response is a DEAD stream. Safari will happily
    // re-use it from cache and play nothing at all, reporting no error.
    //
    try {
      const url = await audioStreamUrl(token);
      if (generation !== audioGenerationRef.current || audioRef.current !== a) return;
      a.src = `${url}&t=${Date.now()}`;
    }
    catch {
      if (generation !== audioGenerationRef.current) return;
      setSound("unavailable"); showToast("Sound authorization failed"); return;
    }
    a.play().then(() => {
      if (generation === audioGenerationRef.current) setSound("on");
    }).catch(() => {
      if (generation !== audioGenerationRef.current) return;
      // Autoplay policy needs a gesture; this IS one (a click), so a rejection here means the
      // endpoint did not deliver: either the session token was rejected (401) or moos-cloud-audio
      // is not running (502).
      setSound("unavailable");
      showToast("Sound is unavailable right now");
    });
  }, [token]);

  const toggleSound = () => { if (sound === "off" || sound === "unavailable") startSound(); else stopSound(); };

  // A live WebM stream never "ends" cleanly and has no duration, so the ordinary media events do not
  // mean what they usually mean. `error`/`stalled`/`ended` here mean the encoder went away — which
  // it does by design whenever a listener drops — and the only fix is a fresh URL.
  useEffect(() => {
    const a = audioRef.current;
    if (!a) return;
    const onPlaying = () => {
      if (!a.src) return;
      audioFailsRef.current = 0;
      setSound("on");
    };
    const onBroken = () => {
      if (!a.src) return;
      // One dead media response commonly raises `stalled`, `error` and `ended` as a burst.
      // Treat that burst as ONE failure. Without this guard every event scheduled its own
      // ticket request; the timers then raced, opened several Opus encoders and could resurrect
      // sound after Stop because only the most recently stored timer id was cancellable.
      if (audioRetryRef.current !== null) return;
      // Bounded, and the bound is the point. Retrying for ever is right for the case this was
      // written for — the encoder is respawned per listener, so a reconnect genuinely does fix it —
      // and wrong for the case that actually happens first: no /audio mount at all, because the
      // server has not been updated yet. Verified against the live server: that returns a clean 404
      // for the stream, so the element errors immediately and an unbounded loop would sit there
      // re-requesting a 404 twice a second for as long as the tab is open, showing "connecting…"
      // and never saying what is wrong.
      if (++audioFailsRef.current > 3) {
        audioFailsRef.current = 0;
        audioGenerationRef.current++;
        a.pause(); a.removeAttribute("src"); a.load();
        setSound("unavailable");
        showToast("No sound endpoint — run: moos-cloud-desktop doctor");
        return;
      }
      const generation = audioGenerationRef.current;
      audioRetryRef.current = window.setTimeout(async () => {
        // Keep the slot occupied while the ticket request is in flight: the OLD source can emit
        // more broken events during a slow fetch, and none of them may create a second request.
        if (!a.src || generation !== audioGenerationRef.current) return;
        try {
          const url = await audioStreamUrl(token);
          if (generation !== audioGenerationRef.current || audioRef.current !== a || !a.src) return;
          // Reopen immediately before activating the NEW source. Any failure after this point
          // belongs to the new attempt and may schedule exactly one successor.
          audioRetryRef.current = null;
          a.src = `${url}&t=${Date.now()}`;
          await a.play();
        }
        catch {
          if (generation === audioGenerationRef.current && a.src) {
            audioRetryRef.current = null;
            setSound("unavailable");
          }
        }
      }, 1200);
    };
    a.addEventListener("playing", onPlaying);
    for (const ev of ["error", "ended", "stalled"] as const) a.addEventListener(ev, onBroken);
    return () => {
      audioGenerationRef.current++;
      a.removeEventListener("playing", onPlaying);
      for (const ev of ["error", "ended", "stalled"] as const) a.removeEventListener(ev, onBroken);
      if (audioRetryRef.current !== null) window.clearTimeout(audioRetryRef.current);
      audioRetryRef.current = null;
      a.pause();
      a.removeAttribute("src");
      a.load();
    };
  }, [token]);

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
          // Deliberately NOT locking the phone to landscape here. It used to call
          // screen.orientation.lock("landscape"), so tapping Fullscreen spun the phone sideways on
          // its own — the "الشاشة عم تعمل عرضي على الجوال" the owner reported, and the opposite of
          // the "let me control rotation" they asked for. Fullscreen now just goes fullscreen; the
          // user turns the phone (or picks 🔒 Sideways) if and when they want the wide view.
        })
        .catch(() => showToast("Add to Home Screen for fullscreen"));
    } else {
      // iOS has no Fullscreen API at all. Installing it is the only route, and it is the better
      // one anyway: standalone means no address bar and no Safari toolbar to reclaim the screen.
      showToast("Safari ▸ Share ▸ Add to Home Screen");
    }
  };
  const refreshStream = () => {
    setStatus("connecting");
    connRef.current?.disconnect();
    if (refreshTimerRef.current) window.clearTimeout(refreshTimerRef.current);
    refreshTimerRef.current = window.setTimeout(() => {
      refreshTimerRef.current = null;
      connRef.current?.connect();
    }, 120);
    showToast("Refreshing…");
  };
  const reconnect = () => {
    if (refreshTimerRef.current) window.clearTimeout(refreshTimerRef.current);
    refreshTimerRef.current = null;
    setStatus("connecting");
    connRef.current?.connect();
  };
  const disconnect = () => {
    if (refreshTimerRef.current) window.clearTimeout(refreshTimerRef.current);
    refreshTimerRef.current = null;
    stopSound();
    connRef.current?.disconnect();
    onExit();
  };

  const chooseMonitor = (i: number) => {
    if (i === selMonitor) return;
    setSelMonitor(i);
    connRef.current?.selectMonitor(i);
    view.current = { zoom: 1, panX: 0, panY: 0 }; // reset zoom/pan; the new screen may differ in size
    showToast(`Screen ${i + 1}`);
  };

  const runPower = async ({ action, label }: PendingPower) => {
    if (powerInFlightRef.current) return;
    powerInFlightRef.current = true;
    setPowerBusy(true);
    try {
      const ok = await powerAction(token, action);
      setPowerConfirm(null);
      showToast(ok ? `${label}…` : `${label} failed`);
    } finally {
      powerInFlightRef.current = false;
      setPowerBusy(false);
    }
  };
  const doPower = (action: PowerAction, label: string, needConfirm = false) => {
    const pending = { action, label };
    if (needConfirm) {
      setSheet(null);
      setPowerConfirm(pending);
      return;
    }
    setSheet(null);
    void runPower(pending);
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
    // No onPointerDown={bumpToolbar} here, and its absence is the feature.
    //
    // It used to be on this div, which covers the whole remote screen, so EVERY touch anywhere on the
    // desktop re-armed the 4.5s timer and brought the seven-button bar back over the bottom of the
    // picture. The one thing guaranteed to keep it on screen was using the remote desktop — and the
    // bottom of a desktop is where the dock and the taskbar live, so the controls sat on top of
    // exactly what the user was reaching for. That is the "something is always covering it" complaint.
    //
    // The bar now hides on its timer and is summoned deliberately, by the .show-tab handle below —
    // 50x30px instead of the full bar, and rendered only while the bar is hidden.
    <div className={"remote" + (mode === "desktop" ? " mouse-mode" : "")}>
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
      <button
        type="button"
        className={
          "topbar"
          + (compactBar ? " mini" : "")
          + (compactBar && !toolbar ? " gone" : "")
        }
        onClick={() => { if (healthy) setStatsOpen((v) => !v); }}
        aria-expanded={!compactBar}
        aria-label={healthy
          ? (compactBar ? "Connection healthy. Show connection details" : "Connection healthy. Hide connection details")
          : `${statusInfo.text}. Connection details are shown`}
        aria-live="polite"
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
      </button>

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
          <IconPause className="" />
          <b style={{ color: "var(--text)", fontSize: 16 }}>Paused on the PC</b>
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
        {/* THE SCROLL CONTAINER MUST NOT PREVENT ITS OWN DEFAULT — the row scrolls sideways, and
            that scroll IS a default action. Focus is defended on the BUTTONS instead; see keepFocus. */}
        <div className="keyrow">
          {(["Control", "Alt", "Shift"] as const).map((m) => (
            <button key={m} {...keepFocus} className={"kkey" + (mods.has(m) ? " on" : "")} onClick={() => toggleMod(m)}>
              {m === "Control" ? "Ctrl" : m}
            </button>
          ))}
          <button {...keepFocus} className="kkey" onClick={() => c()?.keyTap("Win")}>Win</button>
          <span className="kdiv" />
          <button {...keepFocus} className="kkey" onClick={() => c()?.combo(["Control", "A"])}>⌃A</button>
          <button {...keepFocus} className="kkey" onClick={() => c()?.combo(["Control", "C"])}>⌃C</button>
          <button {...keepFocus} className="kkey" onClick={() => c()?.combo(["Control", "X"])}>⌃X</button>
          <button {...keepFocus} className="kkey" onClick={() => c()?.combo(["Control", "V"])}>⌃V</button>
          <button {...keepFocus} className="kkey" onClick={() => c()?.combo(["Control", "Z"])}>⌃Z</button>
          <button {...keepFocus} className="kkey" onClick={() => c()?.combo(["Alt", "Tab"])}>Alt·Tab</button>
          <span className="kdiv" />
          <button {...keepFocus} className="kkey" onClick={() => sendKey("Escape")}>Esc</button>
          <button {...keepFocus} className="kkey" onClick={() => sendKey("Tab")}>Tab</button>
          <button {...keepFocus} className="kkey" onClick={() => sendKey("ArrowLeft")}>←</button>
          <button {...keepFocus} className="kkey" onClick={() => sendKey("ArrowUp")}>↑</button>
          <button {...keepFocus} className="kkey" onClick={() => sendKey("ArrowDown")}>↓</button>
          <button {...keepFocus} className="kkey" onClick={() => sendKey("ArrowRight")}>→</button>
        </div>
        <div className="kbinput-row">
          <input
            ref={inputRef} className="kbinput" type="text" inputMode="text"
            autoCapitalize="off" autoCorrect="off" autoComplete="off" spellCheck={false}
            placeholder="اكتب هنا ← يصل للكمبيوتر · type here"
            onInput={onInput} onKeyDown={onInputKeyDown}
            onCompositionStart={onCompositionStart} onCompositionEnd={onCompositionEnd}
          />
          <button {...keepFocus} className="kbicon" onClick={() => sendKey("Backspace")} aria-label="Backspace"><IconBackspace /></button>
          <button {...keepFocus} className="kbicon" onClick={() => sendKey("Enter")} aria-label="Enter"><IconEnter /></button>
          <button {...keepFocus} className="kbdone" onClick={closeKeyboard}>Done</button>
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
          <button
            className="tbtn"
            onClick={() => {
              const c = canvasRef.current;
              if (!c) return;
              const r = c.getBoundingClientRect();
              zoomToggleAt(r.left + r.width / 2, r.top + r.height / 2);
              bumpToolbar();
            }}
            aria-label="Zoom in on the centre, or back to fit"
          >
            <IconActual /><span>Zoom</span>
          </button>
          <button className={"tbtn" + (sound === "on" ? " on" : "")} onClick={toggleSound}>
            {sound === "on" ? <IconSpeaker /> : <IconSpeakerOff />}
            <span>{sound === "connecting" ? "…" : "Sound"}</span>
          </button>
          <button className="tbtn" onClick={fullscreen}><IconFullscreen /><span>Full</span></button>
          <button className="tbtn accent" onClick={() => setSheet("more")}><IconSettings /><span>Settings</span></button>
        </div>
      )}

      {/* sheets */}
      {(sheet || powerConfirm) && (
        <div className="sheet-backdrop" aria-hidden="true"
             onClick={powerConfirm ? (powerBusy ? undefined : cancelPowerConfirm) : closeSheet} />
      )}

      {powerConfirm && (
        <SheetPanel
          label={`Confirm ${powerConfirm.label}`}
          role="alertdialog"
          descriptionId="power-confirm-description"
          initialFocusSelector="#power-confirm-cancel"
          onClose={cancelPowerConfirm}
          dismissible={!powerBusy}
        >
          <div className="grip" />
          <div className="confirm-panel">
            <div className="confirm-icon"><IconPower /></div>
            <h3>{powerConfirm.label} this PC?</h3>
            <p id="power-confirm-description">
              {powerConfirm.action === "shutdown"
                ? "The remote session will end and this computer will power off. Unsaved work may be lost."
                : powerConfirm.action === "restart"
                  ? "The remote session will end while this computer restarts. Unsaved work may be lost."
                  : "The current desktop session will end. Unsaved work may be lost."}
            </p>
            <div className="confirm-actions">
              <button id="power-confirm-cancel" type="button" className="btn ghost"
                      disabled={powerBusy} onClick={cancelPowerConfirm}>Cancel</button>
              <button type="button" className="btn danger"
                      disabled={powerBusy} onClick={() => void runPower(powerConfirm)}>
                {powerBusy ? "Working…" : powerConfirm.label}
              </button>
            </div>
          </div>
        </SheetPanel>
      )}

      {sheet === "view" && (
        <SheetPanel label="Display" onClose={closeSheet}>
          <div className="grip" /><h3>Display</h3>
          <div className="row-label">Screen</div>
          <div className="seg">
            <button className={viewMode === "fit" ? "on" : ""} onClick={() => chooseView("fit")}><IconFit /> Fit</button>
            <button className={viewMode === "actual" ? "on" : ""} onClick={() => chooseView("actual")}><IconActual /> 100%</button>
          </div>
          {/* THE LOCK. Offered on every device, including the ones where it currently changes
              nothing — because the request is not "turn it for me", it is "let me decide, and then
              stop changing your mind". A control that appears and disappears with the viewport
              cannot deliver that promise: the moment you want the lock is the moment the picture
              just moved, and on a phone that is exactly when a portrait-only control is gone. */}
          <div className="row-label">Rotation</div>
          <div className="seg">
            <button className={orient === "auto" ? "on" : ""} onClick={() => chooseOrient("auto")}>Fit phone</button>
            <button className={orient === "on" ? "on" : ""} onClick={() => chooseOrient("on")}><IconRotate /> Sideways</button>
            <button className={orient === "off" ? "on" : ""} onClick={() => chooseOrient("off")}><IconLock /> Upright</button>
          </div>
          <p className="hint">
            Fit phone follows your phone: the desktop stays upright and fits however you hold it.
            Nothing rotates on its own. Sideways turns the desktop a quarter turn so it fills an
            upright phone — tilt your head, not the phone. Upright never turns it. Whichever you
            pick is held: not when you open the keyboard, and not when the address bar slides.
          </p>
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
              <button key={p.label} className={!auto && presetIdx === i ? "on" : ""} onClick={() => { setAuto(false); selectPreset(i); }}
                title={p.detail}>{p.label}<small>{p.detail}</small></button>
            ))}
          </div>
        </SheetPanel>
      )}

      {sheet === "more" && (
        <SheetPanel label="Settings" onClose={closeSheet}>
          {/* Rebuilt as grouped cards. See styles.css "Settings sheet" for why this shape:
              a small uppercase label, then a card holding related rows. The card edge is
              what lets you find a row without reading every line — which the previous flat
              column of sliders and buttons did not give you. */}
          <div className="grip" /><h3><IconSettings /> Settings</h3>

          <div className="sec-label">Pointer</div>
          <div className="card">
            <div className="card-pad">
              {/* Three buttons, not four. "Touch" and "Direct" were never two models — they
                  differ in one branch of the gesture recogniser, what a one-finger swipe
                  does — so that difference is the switch below, not a mode of its own. */}
              <div className="seg">
                <button className={mode === "touch" || mode === "direct" ? "on" : ""}
                        onClick={() => setMode("touch")}><IconMouse /> Touch</button>
                <button className={mode === "trackpad" ? "on" : ""}
                        onClick={() => setMode("trackpad")}><IconTrackpad /> Trackpad</button>
                <button className={mode === "desktop" ? "on" : ""}
                        onClick={() => setMode("desktop")}><IconMouse /> Mouse + keys</button>
              </div>
              <p className="hint" style={{ margin: "10px 0 0" }}>{MODE_HINT[mode]}</p>
            </div>
            {(mode === "touch" || mode === "direct") && (
              <Row title="One-finger drag" sub="Drag with one finger instead of scrolling.">
                <Switch on={mode === "direct"}
                        onToggle={() => setMode(mode === "direct" ? "touch" : "direct")} />
              </Row>
            )}
            {mode === "desktop" && (
              <Row title="Capture pointer"
                   sub="Raw movement for 3D and games. Esc releases it. Fullscreen also captures Esc, Tab and Ctrl+W.">
                <Switch on={pointerLock} onToggle={() => setPointerLock(v => !v)} />
              </Row>
            )}
          </div>

          <div className="sec-label">Feel</div>
          <div className="card">
            <div className="slider-row">
              <div className="row"><div className="row-main"><div className="row-title">Mouse speed</div></div>
                <div className="row-value">{mouseSensitivity.toFixed(1)}</div></div>
              <input type="range" min="0.4" max="2.5" step="0.1" value={mouseSensitivity}
                     onChange={e => setMouseSensitivity(Number(e.target.value))} />
            </div>
            <div className="slider-row">
              <div className="row"><div className="row-main"><div className="row-title">Scroll speed</div></div>
                <div className="row-value">{scrollSensitivity.toFixed(1)}</div></div>
              <input type="range" min="0.4" max="2.5" step="0.1" value={scrollSensitivity}
                     onChange={e => setScrollSensitivity(Number(e.target.value))} />
            </div>
            <Row title="Natural scroll" sub="Content follows your finger.">
              <Switch on={naturalScroll} onToggle={() => setNaturalScroll(v => !v)} />
            </Row>
            <Row title="Haptics" sub="A short buzz on tap and click.">
              <Switch on={haptics} onToggle={() => setHaptics(v => !v)} />
            </Row>
            <Row title="Magnify while typing"
                 sub="When the keyboard opens, the desktop lifts clear of it and zooms to the cursor so you can read the line you are writing.">
              <Switch on={typingZoom} onToggle={() => setTypingZoom(v => !v)} />
            </Row>
          </div>

          <div className="sec-label">Alerts</div>
          <div className="card">
            <Row title="Background alerts"
                 sub="Generic connection and transfer alerts only. Desktop notifications, filenames and clipboard content never leave the PC.">
              <Switch on={backgroundAlerts && remoteAlertPermission() === "granted"}
                      onToggle={() => void toggleBackgroundAlerts()} />
            </Row>
          </div>

          <div className="sec-label">Security</div>
          <div className="card trusted-list" aria-busy={trustedDevices === null}>
            {trustedDevices === null && <div className="card-pad muted" role="status">Loading trusted devices…</div>}
            {trustedDevices?.length === 0 && <div className="card-pad muted">No remembered devices.</div>}
            {trustedDevices?.map(device => (
              <div className="trusted-row" key={device.id}>
                <div className="row-main">
                  <div className="row-title">{device.name}{device.current ? " · This device" : ""}</div>
                  <div className="row-sub">Last used {new Date(device.lastUsedUnix * 1000).toLocaleDateString()}</div>
                </div>
                <button className="device-revoke" disabled={!!deviceBusy}
                        onClick={() => void revokeDevice(device)}
                        aria-label={`Remove trusted device ${device.name}`}>
                  {deviceBusy === device.id ? "Removing…" : "Remove"}
                </button>
              </div>
            ))}
          </div>

          <div className="sec-label">Actions</div>
          <div className="card">
            <div className="card-pad">
              <div className="grid">
                <button className="cell" onClick={openFiles}><IconFolder /> Files</button>
                <button className="cell" onClick={() => { taskMgr(); setSheet(null); }}><IconShield /> Ctrl+Alt+Del</button>
                <button className="cell" onClick={() => c()?.combo(["Control", "C"])}><IconCopy /> Copy</button>
                <button className="cell" onClick={() => c()?.combo(["Control", "V"])}><IconPaste /> Paste</button>
                <button className="cell" onClick={() => { refreshStream(); setSheet(null); }}><IconRefresh /> Refresh</button>
                <button className="cell" onClick={() => { fullscreen(); setSheet(null); }}><IconFullscreen /> Fullscreen</button>
                <button className="cell danger" onClick={disconnect}><IconPower /> Disconnect</button>
              </div>
            </div>
          </div>

          {/* Power is SHUT. These change the state of the computer you are looking at, and
              "Shut down" sitting one tap below "Copy" is how a phone in a pocket ends a
              session. Opening the section is the deliberate act that earns the buttons. */}
          <div className="sec-label">Power</div>
          <div className="card">
            <details className="fold">
              <summary><span>{hostPowerAllowed ? "Lock, sleep, restart, shut down" : "Managed by the Cloud administrator"}</span><IconChevronDown /></summary>
              <div className="card-pad">
                {hostPowerAllowed ? <div className="grid">
                  <button className="cell" onClick={() => doPower("lock", "Lock")}><IconLock /> Lock</button>
                  <button className="cell" onClick={() => doPower("sleep", "Sleep")}><IconPower /> Sleep</button>
                  <button className="cell" onClick={() => doPower("signout", "Sign out", true)}><IconLock /> Sign out</button>
                  <button className="cell" onClick={() => doPower("restart", "Restart", true)}><IconRefresh /> Restart</button>
                  <button className="cell danger" onClick={() => doPower("shutdown", "Shut down", true)}><IconPower /> Shut down</button>
                </div> : <p className="muted" style={{ margin: 0 }}>
                  This is a shared, passwordless Cloud session. Use the server console to restart or end it safely.
                </p>}
              </div>
            </details>
          </div>

          {/* About answers "which build is my phone running?" WHERE YOU CAN ASK IT. The
              version used to appear only on the connect screen — the one screen you stop
              seeing the moment you connect. */}
          <div className="sec-label">About</div>
          <div className="card">
            <details className="fold">
              <summary><span>Version and connection</span><IconChevronDown /></summary>
              <div>
                <div className="kv"><span>App version</span><b>{BUILD}</b></div>
                <div className="kv"><span>Connection</span><b>{status}</b></div>
                <div className="kv"><span>This device</span><b>{describeHints(deviceHints)}</b></div>
                <div className="kv"><span>Video</span>
                  <b>{status === "live"
                       ? `${codec === "h264" ? "H.264" : "JPEG"} · ${fps} fps · ${latency} ms`
                       : "—"}</b>
                </div>
                <p className="hint" style={{ padding: "0 14px 12px", margin: 0 }}>
                  If the version is not the newest, close the app and open it again — the
                  offline cache serves the previous build until a new one takes over.
                </p>
              </div>
            </details>
          </div>

          <div className="credit">Mo Remote Personal · by Moalfarras</div>
        </SheetPanel>
      )}

      {sheet === "files" && (
        <SheetPanel label="Files" onClose={closeSheet}>
          <div className="grip" />
          <h3>Files · {fileList?.title ?? "…"}</h3>
          <div className="file-actions">
            {fileList?.path && <button className="cell" onClick={() => navFiles(fileList.parent)}><IconArrowUp /> Up</button>}
            {fileList?.path && <button className="cell" onClick={() => fileUpRef.current?.click()}><IconUpload /> Upload here</button>}
            <button className="cell" onClick={() => navFiles(fileList?.path ?? null)}><IconRefresh /> Refresh</button>
          </div>
          <input ref={fileUpRef} type="file" multiple hidden onChange={onUploadFiles} />
          <div className="file-list">
            {fileBusy && <div className="hintline" role="status">{uploadProgress || "Loading…"}</div>}
            {!fileBusy && fileList?.truncated &&
              <div className="hintline" role="status">Showing the first 500 items. Open a smaller folder to continue.</div>}
            {!fileBusy && fileList && fileList.entries.length === 0 && <div className="hintline">Empty folder</div>}
            {!fileBusy && fileList?.entries.map((en) => (
              <button key={en.path} className="file-row" onClick={() => (en.isDir ? navFiles(en.path) : downloadFile(en))}>
                <span className="file-ic">{en.isDir ? <IconFolder /> : <IconFile />}</span>
                <span className="file-name">{en.name}</span>
                <span className="file-meta">{en.isDir ? "›" : fmtSize(en.size)}</span>
              </button>
            ))}
          </div>
        </SheetPanel>
      )}

      {sheet === "clip" && (
        <SheetPanel label="Clipboard sync" onClose={closeSheet}>
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
        </SheetPanel>
      )}

      {!toolbar && !kbOpen && !sheet && !overlay && (
        <button className="show-tab" onClick={bumpToolbar}><IconChevronDown /></button>
      )}

      {toast && <div className="toast" role="status" aria-live="polite">{toast}</div>}
    </div>
  );
}
