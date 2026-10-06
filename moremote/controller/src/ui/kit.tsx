import { useEffect, useRef, type ReactNode } from "react";
import { IconClose } from "./icons";

/**
 * The Glass Console's building blocks. Each exists once so every sheet, row and control in the
 * remote has the same height, edge and keyboard behaviour — the previous screen grew a slightly
 * different variant of each per sheet, which is a large part of why it read as cluttered.
 */

/**
 * A settings row: title (and optional explanation) on the start side, its control on the end.
 */
export function Row({ title, sub, children, icon }: {
  title: string; sub?: string; children?: ReactNode; icon?: ReactNode;
}) {
  return (
    <div className="row">
      {icon && <span className="row-icon" aria-hidden="true">{icon}</span>}
      <div className="row-main">
        <div className="row-title">{title}</div>
        {sub && <div className="row-sub">{sub}</div>}
      </div>
      {children}
    </div>
  );
}

/**
 * A real switch, not a tinted button. role/aria-checked rather than a styled <input>: the sheet
 * scrolls and a native checkbox drags oddly inside one on iOS, and the accessible state is
 * explicit rather than inferred from a class name. The knob moves, so on/off reads at a glance.
 */
export function Switch({ on, onToggle, label, disabled }: {
  on: boolean; onToggle: () => void; label?: string; disabled?: boolean;
}) {
  return (
    <button type="button" role="switch" aria-checked={on} aria-label={label}
            className="switch" onClick={onToggle} disabled={disabled} />
  );
}

/**
 * One choice out of a few, with a thumb that slides to the chosen one. Buttons with
 * aria-pressed, so each option keeps its own accessible name ("Sharp 1080p · 30 fps").
 */
export function Segmented<T extends string | number>({ value, options, onChange, label, className = "" }: {
  value: T;
  options: { value: T; label: ReactNode; aria?: string; icon?: ReactNode }[];
  onChange: (value: T) => void;
  label: string;
  className?: string;
}) {
  const index = Math.max(0, options.findIndex((o) => o.value === value));
  return (
    <div className={"segmented " + className} role="group" aria-label={label}
         style={{ ["--seg-count" as string]: options.length, ["--seg-index" as string]: index }}>
      <span className="segmented-thumb" aria-hidden="true" />
      {options.map((o) => (
        <button key={String(o.value)} type="button" aria-pressed={o.value === value}
                aria-label={o.aria} onClick={() => onChange(o.value)}>
          {o.icon}<span>{o.label}</span>
        </button>
      ))}
    </div>
  );
}

/** A tab strip for a sheet with sections. role=tablist so screen readers announce "tab 2 of 3". */
export function Tabs<T extends string>({ value, tabs, onChange, label, idPrefix }: {
  value: T;
  tabs: { value: T; label: string; icon?: ReactNode }[];
  onChange: (value: T) => void;
  label: string;
  idPrefix: string;
}) {
  const index = Math.max(0, tabs.findIndex((t) => t.value === value));
  const move = (event: React.KeyboardEvent, delta: number) => {
    event.preventDefault();
    const next = tabs[(index + delta + tabs.length) % tabs.length];
    onChange(next.value);
    requestAnimationFrame(() => document.getElementById(`${idPrefix}-tab-${next.value}`)?.focus());
  };
  return (
    <div className="tabs" role="tablist" aria-label={label}
         style={{ ["--seg-count" as string]: tabs.length, ["--seg-index" as string]: index }}>
      <span className="segmented-thumb" aria-hidden="true" />
      {tabs.map((t) => (
        <button key={t.value} id={`${idPrefix}-tab-${t.value}`} type="button" role="tab"
                aria-selected={t.value === value} aria-controls={`${idPrefix}-panel`}
                tabIndex={t.value === value ? 0 : -1}
                onClick={() => onChange(t.value)}
                onKeyDown={(e) => {
                  const rtl = document.documentElement.dir === "rtl";
                  if (e.key === "ArrowRight") move(e, rtl ? -1 : 1);
                  else if (e.key === "ArrowLeft") move(e, rtl ? 1 : -1);
                }}>
          {t.icon}<span>{t.label}</span>
        </button>
      ))}
    </div>
  );
}

/** A labelled slider with its value shown, because a slider with no number is a guess. */
export function SliderRow({ title, value, min, max, step, onChange, format }: {
  title: string; value: number; min: number; max: number; step: number;
  onChange: (value: number) => void; format?: (value: number) => string;
}) {
  return (
    <label className="slider-row">
      <span className="row">
        <span className="row-main"><span className="row-title">{title}</span></span>
        <span className="row-value" dir="ltr">{format ? format(value) : value.toFixed(1)}</span>
      </span>
      <input type="range" min={min} max={max} step={step} value={value}
             onChange={(e) => onChange(Number(e.target.value))} />
    </label>
  );
}

/** A small section heading above a card. */
export function Section({ title, children, aside }: { title: string; children: ReactNode; aside?: ReactNode }) {
  return (
    <section className="section">
      <div className="section-head"><h4>{title}</h4>{aside}</div>
      <div className="card">{children}</div>
    </section>
  );
}

/**
 * A bottom sheet is a modal dialog, not merely a card drawn above a scrim.
 * Own focus while it is open, close on Escape, wrap Tab inside it, and restore
 * the invoking control afterwards. This keeps phone screen-readers and desktop
 * keyboard users on the same interaction path as touch users.
 *
 * It also follows the phone's keyboard: visualViewport says how much of the window the keyboard
 * covers, and the sheet's bottom and height track it so a text field inside is never underneath.
 */
export function SheetPanel({ label, closeLabel, onClose, children, role = "dialog", descriptionId,
  initialFocusSelector = ".sheet-close", dismissible = true, title, icon, className = "" }: {
  label: string;
  /** Fully composed, already-translated "Close <sheet name>" text for the close button. */
  closeLabel: string;
  onClose: () => void;
  children: ReactNode;
  role?: "dialog" | "alertdialog";
  descriptionId?: string;
  initialFocusSelector?: string;
  dismissible?: boolean;
  /** The visible heading; omitted for a sheet that draws its own. */
  title?: string;
  icon?: ReactNode;
  className?: string;
}) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const viewport = window.visualViewport;
    const panel = panelRef.current;
    if (!viewport || !panel) return;
    const resize = () => {
      panel.style.bottom = `${Math.max(0, window.innerHeight - viewport.height - viewport.offsetTop)}px`;
      panel.style.maxHeight = `${Math.max(0, Math.min(window.innerHeight * .86, viewport.height - 16))}px`;
    };
    viewport.addEventListener("resize", resize);
    viewport.addEventListener("scroll", resize);
    resize();
    return () => {
      viewport.removeEventListener("resize", resize);
      viewport.removeEventListener("scroll", resize);
    };
  }, []);

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
    <div ref={panelRef} className={"sheet " + className} role={role} aria-modal="true" aria-label={label}
         aria-describedby={descriptionId} tabIndex={-1}>
      <div className="sheet-head">
        <span className="grip" aria-hidden="true" />
        {title && <h3>{icon}<span>{title}</span></h3>}
        <button type="button" className="sheet-close" onClick={onClose} disabled={!dismissible}
                aria-label={closeLabel}><IconClose /></button>
      </div>
      <div className="sheet-body">{children}</div>
    </div>
  );
}
