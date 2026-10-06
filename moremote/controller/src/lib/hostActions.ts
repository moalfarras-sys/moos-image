/**
 * The desktop's own commands, reachable from the phone in one tap.
 *
 * Every entry is a keystroke the HOST already understands — a KDE global shortcut, a KWin window
 * action or a hardware media key — so nothing here is a new privilege or a new command channel.
 * The phone presses keys; the desktop decides what they mean, exactly as if the owner were sitting
 * in front of it. That is also why a shortcut the owner rebinds in System Settings stops working
 * here: the table names the shortcut MoOS ships, not the action behind it.
 *
 * The MoOS table was read back from a running MoOS session (`~/.config/kglobalshortcutsrc` and
 * `/usr/share/kglobalaccel/*.desktop`, 2026-10-06): Mira is Meta+Space, KRunner Alt+Space, Overview
 * Meta+W, Files Meta+E, System Settings Meta+I, System Monitor Meta+Esc, clipboard history Meta+V,
 * emoji Meta+., Spectacle Print / Meta+Shift+S, Konsole Ctrl+Alt+T, lock Meta+L. A Windows host
 * gets the Windows equivalents, because the same phone may drive either agent.
 *
 * The wire has three shapes and each action uses exactly one:
 *   combo — modifiers plus one key, through the agent's Combo() (letters resolve on the live keymap)
 *   tap   — one named key, through KeyTap() ("Meta" alone opens the launcher on KDE)
 *   code  — one PHYSICAL key position, through KeyTapCode(); media keys and Print live only there
 */

export type HostKind = "moos" | "windows";

export type KeyAction =
  | { kind: "combo"; keys: string[] }
  | { kind: "tap"; key: string }
  | { kind: "code"; code: string };

export type ActionIcon =
  | "launcher" | "assistant" | "search" | "files" | "terminal" | "settings" | "monitor"
  | "clipboard" | "emoji" | "overview" | "desktop" | "switch" | "maximize" | "minimize"
  | "tileLeft" | "tileRight" | "deskPrev" | "deskNext" | "close" | "volDown" | "mute" | "volUp"
  | "prev" | "play" | "next" | "shot" | "region" | "taskmgr";

export interface HostAction {
  id: string;
  icon: ActionIcon;
  /** i18n id of the label; resolved by the UI so this file stays language-free. */
  label: string;
  /** The keys as a person would read them, for the tile's second line. */
  hint: string;
  send: KeyAction;
}

export interface ActionGroup {
  id: "apps" | "windows" | "media";
  /** i18n id of the group title. */
  title: string;
  actions: HostAction[];
}

const combo = (...keys: string[]): KeyAction => ({ kind: "combo", keys });
const tap = (key: string): KeyAction => ({ kind: "tap", key });
const code = (c: string): KeyAction => ({ kind: "code", code: c });

const MEDIA: HostAction[] = [
  { id: "vol-down", icon: "volDown", label: "actVolDown", hint: "−", send: code("AudioVolumeDown") },
  { id: "mute", icon: "mute", label: "actMute", hint: "⊘", send: code("AudioVolumeMute") },
  { id: "vol-up", icon: "volUp", label: "actVolUp", hint: "+", send: code("AudioVolumeUp") },
  { id: "prev", icon: "prev", label: "actPrev", hint: "⏮", send: code("MediaTrackPrevious") },
  { id: "play", icon: "play", label: "actPlay", hint: "⏯", send: code("MediaPlayPause") },
  { id: "next", icon: "next", label: "actNext", hint: "⏭", send: code("MediaTrackNext") },
];

const MOOS: ActionGroup[] = [
  {
    id: "apps", title: "groupApps", actions: [
      { id: "launcher", icon: "launcher", label: "actLauncher", hint: "Meta", send: tap("Meta") },
      { id: "mira", icon: "assistant", label: "actMira", hint: "Meta+Space", send: combo("Meta", "Space") },
      { id: "search", icon: "search", label: "actSearch", hint: "Alt+Space", send: combo("Alt", "Space") },
      { id: "files", icon: "files", label: "actFiles", hint: "Meta+E", send: combo("Meta", "e") },
      { id: "terminal", icon: "terminal", label: "actTerminal", hint: "Ctrl+Alt+T", send: combo("Control", "Alt", "t") },
      { id: "settings", icon: "settings", label: "actSettings", hint: "Meta+I", send: combo("Meta", "i") },
      { id: "monitor", icon: "monitor", label: "actMonitor", hint: "Meta+Esc", send: combo("Meta", "Escape") },
      { id: "clipboard", icon: "clipboard", label: "actClipboard", hint: "Meta+V", send: combo("Meta", "v") },
      { id: "emoji", icon: "emoji", label: "actEmoji", hint: "Meta+.", send: combo("Meta", ".") },
    ],
  },
  {
    id: "windows", title: "groupWindows", actions: [
      { id: "overview", icon: "overview", label: "actOverview", hint: "Meta+W", send: combo("Meta", "w") },
      { id: "show-desktop", icon: "desktop", label: "actShowDesktop", hint: "Meta+D", send: combo("Meta", "d") },
      { id: "switch", icon: "switch", label: "actSwitch", hint: "Alt+Tab", send: combo("Alt", "Tab") },
      { id: "maximize", icon: "maximize", label: "actMaximize", hint: "Meta+PgUp", send: combo("Meta", "PageUp") },
      { id: "minimize", icon: "minimize", label: "actMinimize", hint: "Meta+PgDn", send: combo("Meta", "PageDown") },
      { id: "tile-left", icon: "tileLeft", label: "actTileLeft", hint: "Meta+←", send: combo("Meta", "ArrowLeft") },
      { id: "tile-right", icon: "tileRight", label: "actTileRight", hint: "Meta+→", send: combo("Meta", "ArrowRight") },
      { id: "desk-prev", icon: "deskPrev", label: "actDeskPrev", hint: "Ctrl+Meta+←", send: combo("Control", "Meta", "ArrowLeft") },
      { id: "desk-next", icon: "deskNext", label: "actDeskNext", hint: "Ctrl+Meta+→", send: combo("Control", "Meta", "ArrowRight") },
      { id: "close", icon: "close", label: "actClose", hint: "Alt+F4", send: combo("Alt", "F4") },
    ],
  },
  {
    id: "media", title: "groupMedia", actions: [
      ...MEDIA,
      { id: "shot", icon: "shot", label: "actScreenshot", hint: "Print", send: code("PrintScreen") },
      { id: "region", icon: "region", label: "actRegion", hint: "Meta+Shift+S", send: combo("Meta", "Shift", "s") },
    ],
  },
];

const WINDOWS: ActionGroup[] = [
  {
    id: "apps", title: "groupApps", actions: [
      { id: "launcher", icon: "launcher", label: "actStart", hint: "Win", send: tap("Meta") },
      { id: "search", icon: "search", label: "actSearch", hint: "Win+S", send: combo("Meta", "s") },
      { id: "files", icon: "files", label: "actFiles", hint: "Win+E", send: combo("Meta", "e") },
      { id: "settings", icon: "settings", label: "actSettings", hint: "Win+I", send: combo("Meta", "i") },
      { id: "taskmgr", icon: "taskmgr", label: "actTaskManager", hint: "Ctrl+Shift+Esc", send: combo("Control", "Shift", "Escape") },
      { id: "clipboard", icon: "clipboard", label: "actClipboard", hint: "Win+V", send: combo("Meta", "v") },
      // No Win+. emoji tile: the Windows agent's KeyMap has letters, digits and named keys but no
      // OEM punctuation, so the combo would arrive as a bare Win press and open Start instead.
    ],
  },
  {
    id: "windows", title: "groupWindows", actions: [
      { id: "overview", icon: "overview", label: "actTaskView", hint: "Win+Tab", send: combo("Meta", "Tab") },
      { id: "show-desktop", icon: "desktop", label: "actShowDesktop", hint: "Win+D", send: combo("Meta", "d") },
      { id: "switch", icon: "switch", label: "actSwitch", hint: "Alt+Tab", send: combo("Alt", "Tab") },
      { id: "maximize", icon: "maximize", label: "actMaximize", hint: "Win+↑", send: combo("Meta", "ArrowUp") },
      { id: "minimize", icon: "minimize", label: "actMinimize", hint: "Win+↓", send: combo("Meta", "ArrowDown") },
      { id: "tile-left", icon: "tileLeft", label: "actTileLeft", hint: "Win+←", send: combo("Meta", "ArrowLeft") },
      { id: "tile-right", icon: "tileRight", label: "actTileRight", hint: "Win+→", send: combo("Meta", "ArrowRight") },
      { id: "close", icon: "close", label: "actClose", hint: "Alt+F4", send: combo("Alt", "F4") },
    ],
  },
  {
    id: "media", title: "groupMedia", actions: [
      ...MEDIA,
      { id: "region", icon: "region", label: "actRegion", hint: "Win+Shift+S", send: combo("Meta", "Shift", "s") },
    ],
  },
];

/**
 * Which desktop the agent is driving. The Windows agent names its injector "Win32 SendInput";
 * every Linux backend (native EIS, portal, ydotool fallback) is a MoOS desktop. An unknown or
 * missing name is MoOS, because that is the only Linux desktop this controller ships with.
 */
export function hostKindFrom(backend: string | undefined | null): HostKind {
  return typeof backend === "string" && /^win32\b/i.test(backend.trim()) ? "windows" : "moos";
}

export function actionGroups(kind: HostKind): ActionGroup[] {
  return kind === "windows" ? WINDOWS : MOOS;
}

/** Every modifier name the agents' Combo() accepts. Anything else in a combo must be one key. */
export const COMBO_MODIFIERS = ["Control", "Alt", "Shift", "Meta"] as const;
