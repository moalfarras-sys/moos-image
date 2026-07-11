// Lightweight stroke icons (no icon-font dependency). 24x24 viewBox.
import type { ReactNode } from "react";
type P = { className?: string };
const S = (props: { children: ReactNode } & P) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={props.className}>
    {props.children}
  </svg>
);

export const IconKeyboard = (p: P) => (
  <S {...p}>
    <rect x="2" y="6" width="20" height="12" rx="2" />
    <path d="M6 10h.01M10 10h.01M14 10h.01M18 10h.01M8 14h8" />
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
    <path d="M12 3v9" />
    <path d="M6.4 6.4a8 8 0 1 0 11.2 0" />
  </S>
);
export const IconShield = (p: P) => (
  <S {...p}>
    <path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z" />
    <path d="M9 12l2 2 4-4" />
  </S>
);
export const IconMouse = (p: P) => (
  <S {...p}>
    <rect x="6" y="3" width="12" height="18" rx="6" />
    <path d="M12 7v4" />
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
export const IconPause = (p: P) => (
  <S {...p}>
    <rect x="6" y="5" width="4" height="14" rx="1" />
    <rect x="14" y="5" width="4" height="14" rx="1" />
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
    <rect x="5" y="11" width="14" height="9" rx="2" />
    <path d="M8 11V8a4 4 0 0 1 8 0v3" />
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
    <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
  </S>
);
export const IconUpload = (p: P) => (
  <S {...p}>
    <path d="M12 16V4M7 9l5-5 5 5" />
    <path d="M4 17v2a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-2" />
  </S>
);
