// Lightweight stroke icons (no icon-font dependency). 24x24 viewBox.
import type { ReactNode } from "react";
type P = { className?: string };
// width/height are PRESENTATION ATTRIBUTES, and that is the whole point of putting them here.
//
// An <svg> with a viewBox and no dimensions has no intrinsic size, so the browser falls back to
// the default object size — about 300px — and the icon arrives the size of a photograph. The
// settings gear shipped that way once already, at roughly 600px, filling the phone screen above
// a barely visible title. The fix then was a CSS rule for that one container, which left every
// FUTURE use site one forgotten rule away from the same bug: `className=""` at three sites here
// (the idle-timeout overlay, the PC-locked overlay, and the auth lockout hint) had no rule that
// could ever match them, and each rendered a ~300px glyph.
//
// A presentation attribute loses to ANY css declaration, so every existing `.tbtn svg { width }`,
// `.cell svg { width }`, `.sheet h3 svg { width }` still wins exactly as before and nothing
// resizes. What changes is only the case nobody wrote a rule for: it lands at 24px — the size of
// the viewBox — instead of at the browser's fallback.
const S = (props: { children: ReactNode } & P) => (
  <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false" className={props.className}>
    {props.children}
  </svg>
);

export const IconKeyboard = (p: P) => (
  <S {...p}>
    <rect x="2.5" y="5" width="19" height="14" rx="2" />
    <path d="M5.5 8.5h2M9.5 8.5h2M13.5 8.5h2M17.5 8.5h2M5.5 12h2M9.5 12h2M13.5 12h2M17.5 12h2M7.5 15.5h9" />
  </S>
);
export const IconSpeaker = (p: P) => (
  <S {...p}>
    <path d="M7 8.5L11 8.5 17 3.5v17l-6-5H7z" />
    <path d="M19.5 7.8a5.5 5.5 0 0 1 0 8.4M22.4 5.6a9 9 0 0 1 0 12.8" />
  </S>
);
export const IconSpeakerOff = (p: P) => (
  <S {...p}>
    <path d="M7 8.5L11 8.5 17 3.5v17l-6-5H7z" />
    <path d="M15.2 9.7l5.6 5.6M20.8 9.7l-5.6 5.6" />
  </S>
);
export const IconEsc = (p: P) => (
  <S {...p}>
    <path d="M9 6 4 12l5 6M20 12H4" />
  </S>
);
export const IconEnter = (p: P) => (
  <S {...p}>
    <path d="M9 10 4 15l5 5" />
    <path d="M20 4v7a4 4 0 0 1-4 4H4" />
  </S>
);
export const IconWindows = (p: P) => (
  <S {...p}>
    <rect x="3" y="3" width="8" height="8" rx="1" />
    <rect x="13" y="3" width="8" height="8" rx="1" />
    <rect x="3" y="13" width="8" height="8" rx="1" />
    <rect x="13" y="13" width="8" height="8" rx="1" />
  </S>
);
export const IconAltTab = (p: P) => (
  <S {...p}>
    <path d="M3 9h13l-3-3M21 15H8l3 3" />
  </S>
);
export const IconMore = (p: P) => (
  <S {...p}>
    <circle cx="5" cy="12" r="1.6" />
    <circle cx="12" cy="12" r="1.6" />
    <circle cx="19" cy="12" r="1.6" />
  </S>
);
export const IconSettings = (p: P) => (
  <S {...p}>
    <circle cx="12" cy="12" r="3.2" />
    <path d="M19.4 15a1.7 1.7 0 0 0 .33 1.87l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.7 1.7 0 0 0-1.87-.33 1.7 1.7 0 0 0-1 1.55V21a2 2 0 1 1-4 0v-.09A1.7 1.7 0 0 0 8.9 19.3a1.7 1.7 0 0 0-1.87.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-1.55-1H3a2 2 0 1 1 0-4h.09A1.7 1.7 0 0 0 4.7 8.9a1.7 1.7 0 0 0-.33-1.87l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-1.55V3a2 2 0 1 1 4 0v.09a1.7 1.7 0 0 0 1 1.55 1.7 1.7 0 0 0 1.87-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.7 1.7 0 0 0 19.4 9v0a1.7 1.7 0 0 0 1.55 1H21a2 2 0 1 1 0 4h-.09a1.7 1.7 0 0 0-1.55 1z" />
  </S>
);
export const IconCopy = (p: P) => (
  <S {...p}>
    <rect x="9" y="9" width="11" height="11" rx="2" />
    <path d="M5 15V5a2 2 0 0 1 2-2h8" />
  </S>
);
export const IconPaste = (p: P) => (
  <S {...p}>
    <path d="M9 4h6v3H9z" />
    <path d="M7 5H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-2" />
    <rect x="13" y="11" width="8" height="10" rx="2" />
  </S>
);
export const IconFullscreen = (p: P) => (
  <S {...p}>
    <path d="M4 9V5a1 1 0 0 1 1-1h4M20 9V5a1 1 0 0 0-1-1h-4M4 15v4a1 1 0 0 0 1 1h4M20 15v4a1 1 0 0 1-1 1h-4" />
  </S>
);
export const IconPower = (p: P) => (
  <S {...p}>
    <path d="M12 3v10" />
    <path d="M6.4 6.4a8 8 0 1 0 11.2 0" />
  </S>
);
export const IconShield = (p: P) => (
  <S {...p}>
    <path d="M12 2.5l7.5 3.5v7c0 5-3.5 8.5-7.5 10-4-1.5-7.5-5-7.5-10V6z" />
    <path d="M9 12l2.5 2.5 4.5-5" />
  </S>
);
export const IconMouse = (p: P) => (
  <S {...p}>
    <rect x="6" y="3" width="12" height="18" rx="6" />
    <path d="M12 3.5v5.5" />
    <path d="M9.5 6.5a2.5 2.5 0 0 1 5 0v2" />
  </S>
);
export const IconTrackpad = (p: P) => (
  <S {...p}>
    <rect x="3" y="4" width="18" height="16" rx="2" />
    <path d="M12 15v.01" />
  </S>
);
export const IconGauge = (p: P) => (
  <S {...p}>
    <path d="M12 13l4-3" />
    <path d="M4 18a8 8 0 1 1 16 0" />
  </S>
);
export const IconBackspace = (p: P) => (
  <S {...p}>
    <path d="M21 5H8L2 12l6 7h13a1 1 0 0 0 1-1V6a1 1 0 0 0-1-1z" />
    <path d="M14 9l-4 6M10 9l4 6" />
  </S>
);
export const IconClose = (p: P) => (
  <S {...p}>
    <path d="M6 6l12 12M18 6 6 18" />
  </S>
);
export const IconPause = (p: P) => (
  <S {...p}>
    <rect x="7" y="4" width="3.5" height="16" rx="1" />
    <rect x="13.5" y="4" width="3.5" height="16" rx="1" />
  </S>
);
export const IconStop = (p: P) => (
  <S {...p}>
    <rect x="5" y="5" width="14" height="14" rx="2" />
  </S>
);
export const IconRefresh = (p: P) => (
  <S {...p}>
    <path d="M21 12a9 9 0 1 1-3-6.7L21 8" />
    <path d="M21 4v4h-4" />
  </S>
);
export const IconLock = (p: P) => (
  <S {...p}>
    <rect x="5" y="11" width="14" height="10" rx="2" />
    <path d="M8.5 11V8a3.5 3.5 0 0 1 7 0v3" />
  </S>
);
export const IconClipboard = (p: P) => (
  <S {...p}>
    <rect x="6" y="4" width="12" height="17" rx="2" />
    <path d="M9 4a3 3 0 0 1 6 0" />
    <path d="M9 11h6M9 15h4" />
  </S>
);
export const IconZoomIn = (p: P) => (
  <S {...p}>
    <circle cx="11" cy="11" r="7" />
    <path d="M11 8v6M8 11h6M20 20l-3.5-3.5" />
  </S>
);
export const IconZoomOut = (p: P) => (
  <S {...p}>
    <circle cx="11" cy="11" r="7" />
    <path d="M8 11h6M20 20l-3.5-3.5" />
  </S>
);
export const IconFit = (p: P) => (
  <S {...p}>
    <rect x="3" y="5" width="18" height="14" rx="2" />
    <path d="M8 9l-2 2 2 2M16 9l2 2-2 2" />
  </S>
);
export const IconActual = (p: P) => (
  <S {...p}>
    <rect x="3" y="5" width="18" height="14" rx="2" />
    <path d="M9 9v6M9 9h.01M15 9v6M13 12h4" />
  </S>
);
export const IconChevronDown = (p: P) => (
  <S {...p}>
    <path d="M6 9l6 6 6-6" />
  </S>
);
export const IconSend = (p: P) => (
  <S {...p}>
    <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
  </S>
);
export const IconFolder = (p: P) => (
  <S {...p}>
    <path d="M3 7.5a2 2 0 0 1 2-2h4.5l2 2H19a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
    <path d="M5.5 10.5h13" />
  </S>
);
export const IconUpload = (p: P) => (
  <S {...p}>
    <path d="M12 16V4M7 9l5-5 5 5" />
    <path d="M4 17.5v2.5a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-2.5" />
  </S>
);
export const IconFile = (p: P) => (
  <S {...p}>
    <path d="M6 2.75h7l5 5V21.25H6z" />
    <path d="M13 2.75v5h5M9 12h6M9 16h6" />
  </S>
);
export const IconArrowUp = (p: P) => (
  <S {...p}>
    <path d="M12 20V4M6.5 9.5 12 4l5.5 5.5" />
  </S>
);
export const IconRotate = (p: P) => (
  <S {...p}>
    <path d="M20 8V3.5L16.5 7" />
    <path d="M20 4a9 9 0 1 0 1 12" />
  </S>
);
export const IconPlug = (p: P) => (
  <S {...p}>
    <path d="M8 3v5M16 3v5M6 8h12v2a6 6 0 0 1-6 6v0a6 6 0 0 1-6-6z" />
    <path d="M12 16v5M8.5 21h7" />
  </S>
);
