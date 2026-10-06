import type { RefObject, FormEvent, KeyboardEvent, CompositionEvent, ChangeEvent, ClipboardEvent,
  PointerEvent as ReactPointerEvent } from "react";
import type { Lang, StringId } from "../../lib/i18n";
import type { GestureMode, ViewMode, MonitorInfo } from "../../types";
import type { ClipResult, FileEntry, FileListing, PowerAction, TrustedDeviceInfo } from "../../lib/api";
import type { DeviceHints, HostEncode } from "../../lib/quality";
import type { HostAction, HostKind } from "../../lib/hostActions";

export type Conn = "connecting" | "live" | "paused" | "stopped" | "reconnecting" | "idle";
export type SettingsTab = "picture" | "control" | "general";
export type TransferTab = "clipboard" | "files";
export type Orient = "auto" | "on" | "off";
/** The three ways to drive the desktop the owner chooses between; Touch covers touch and drag. */
export type ControlMode = "touch" | "trackpad" | "desktop";

/**
 * Everything the Glass Console's pieces read from the session, and every action they may take.
 *
 * RemoteScreen owns the connection, the decoders, the gesture engines and every piece of state;
 * the dock, the keyboard and the sheets only draw it and call back. One explicit interface rather
 * than a context, so a component can never reach a ref or a setter it was not handed.
 */
export interface RemoteModel {
  tr: (id: StringId) => string;
  lang: Lang;
  onLangSwitch: (next: Lang) => void;

  // connection and stream
  status: Conn;
  statusText: string;
  /** "ok" when nothing needs saying, "warn" while it recovers, "bad" when something is missing. */
  health: "ok" | "warn" | "bad";
  /** The one problem worth naming, or "" when there is none. */
  issue: string;
  fps: number;
  latency: number;
  codec: "jpeg" | "h264";
  weak: boolean;
  clipboardOk: boolean;
  stream: { width: number; fps: number; quality: number };
  hostEncode: HostEncode | null;
  deviceHints: DeviceHints;

  // layout and control
  rail: boolean;
  mode: GestureMode;
  controlMode: ControlMode;
  chooseMode: (mode: ControlMode) => void;
  padOnly: boolean;
  setPadOnly: (on: boolean) => void;
  touchDrag: boolean;
  setOneFingerDrag: (on: boolean) => void;
  kbOpen: boolean;
  openKeyboard: () => void;
  closeKeyboard: () => void;
  openSettings: (tab: SettingsTab) => void;
  openActions: () => void;
  openTransfer: (tab: TransferTab) => void;
  closeSheet: () => void;
  settingsTab: SettingsTab;
  setSettingsTab: (tab: SettingsTab) => void;
  transferTab: TransferTab;
  setTransferTab: (tab: TransferTab) => void;
  fullscreen: () => void;

  // picture
  auto: boolean;
  chooseAuto: () => void;
  presetIdx: number;
  choosePreset: (index: number) => void;
  qualityLabel: (index: number) => string;
  fpsPref: number;
  setFpsPref: (fps: number) => void;
  viewMode: ViewMode;
  chooseView: (mode: ViewMode) => void;
  zoomBy: (factor: number) => void;
  resetZoom: () => void;
  orient: Orient;
  chooseOrient: (orient: Orient) => void;
  monitors: MonitorInfo[];
  selMonitor: number;
  chooseMonitor: (index: number) => void;
  sound: "off" | "connecting" | "on" | "unavailable";
  toggleSound: () => void;

  // feel
  pointerLock: boolean;
  togglePointerLock: () => void;
  mouseSensitivity: number;
  setMouseSensitivity: (value: number) => void;
  scrollSensitivity: number;
  setScrollSensitivity: (value: number) => void;
  naturalScroll: boolean;
  toggleNaturalScroll: () => void;
  haptics: boolean;
  toggleHaptics: () => void;
  typingZoom: boolean;
  toggleTypingZoom: () => void;

  // general
  backgroundAlerts: boolean;
  backgroundAlertsGranted: boolean;
  toggleBackgroundAlerts: () => Promise<void>;
  trustedDevices: TrustedDeviceInfo[] | null;
  trustedDevicesFailed: boolean;
  retryTrustedDevices: () => void;
  deviceBusy: string;
  revokeDevice: (device: TrustedDeviceInfo) => Promise<void>;
  refreshStream: () => void;
  disconnect: () => void;
  build: string;

  // keyboard panel
  kbbarRef: RefObject<HTMLDivElement | null>;
  inputRef: RefObject<HTMLInputElement | null>;
  secureTyping: boolean;
  hostLocked: boolean | null;
  secureKeyboardAvailable: boolean;
  toggleSecureTyping: () => void;
  mods: Set<string>;
  toggleMod: (modifier: string) => void;
  sendKey: (key: string) => void;
  sendShortcut: (keys: string[]) => void;
  keepFocus: { onPointerDown: (event: ReactPointerEvent) => void };
  onInput: (event: FormEvent<HTMLInputElement>) => void;
  onInputKeyDown: (event: KeyboardEvent) => void;
  onCompositionStart: () => void;
  onCompositionEnd: (event: CompositionEvent<HTMLInputElement>) => void;
  onInputBlur: () => void;

  // quick actions
  hostKind: HostKind;
  /** keepOpen: leave the sheet up (volume and media keys are pressed several times in a row). */
  runAction: (action: HostAction, keepOpen?: boolean) => void;
  hostPowerAllowed: boolean;
  doPower: (action: PowerAction, label: string, needConfirm?: boolean) => void;

  // clipboard
  copyFromPc: () => Promise<void>;
  pasteFromDevice: () => Promise<void>;
  pcClip: ClipResult;
  getPcClip: () => Promise<void>;
  copyToPhone: () => Promise<void>;
  sendText: string;
  setSendText: (text: string) => void;
  readPhoneClip: () => Promise<void>;
  sendToPc: (paste?: boolean) => Promise<void>;
  clipboardBusy: string;
  phoneClipRef: RefObject<HTMLTextAreaElement | null>;
  pickImage: (paste: boolean) => void;
  onPasteBox: (event: ClipboardEvent<HTMLDivElement>) => Promise<void>;
  onPasteBoxInput: (event: FormEvent<HTMLDivElement>) => void;

  // files
  fileList: FileListing | null;
  fileBusy: boolean;
  uploadProgress: string;
  navFiles: (path: string | null) => Promise<void>;
  downloadFile: (entry: FileEntry) => Promise<void>;
  pickUpload: () => void;
  fmtSize: (bytes: number) => string;
}

export type { ChangeEvent };
