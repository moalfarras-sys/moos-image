import { useEffect, useRef } from "react";
import { GestureController } from "../lib/gestures";
import type { RemoteConnection } from "../lib/ws";
import { IconDesktop, IconMouse, IconTrackpad } from "./icons";
import type { makeT } from "../lib/i18n";

/**
 * Pad only: the phone becomes a trackpad and the picture stops.
 *
 * For when the computer's own screen is in front of you — a PC on the TV, a desk across the room.
 * Video is suspended (the agent is told nobody is watching), so the phone neither decodes nor
 * downloads a picture it would only duplicate. The pad is relative and needs no frame at all.
 */
export function Touchpad({ connection, enabled, sensitivity, scrollSensitivity, naturalScroll, tr, onShowPicture }: {
  connection: () => RemoteConnection | null; enabled: boolean; sensitivity: number;
  scrollSensitivity: number;
  naturalScroll: boolean;
  tr: ReturnType<typeof makeT>;
  onShowPicture: () => void;
}) {
  const surface = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!surface.current || !enabled) return;
    const c = () => connection();
    const gesture = new GestureController(surface.current, () => ({ x: .5, y: .5 }), () => 1, {
      click: b => c()?.clickCurrent(b), dblclick: () => c()?.dblclickCurrent(),
      moveCursor: () => {}, moveRelative: (x, y) => c()?.moveRelative(x, y),
      dragStart: () => c()?.downCurrent("left"), dragMove: () => {},
      dragEnd: () => c()?.upCurrent("left"),
      scroll: (x, y) => c()?.scroll(x * scrollSensitivity * (naturalScroll ? -1 : 1),
                                  y * scrollSensitivity * (naturalScroll ? -1 : 1)),
      zoomAt: () => {}, panBy: () => {}, cursorAt: () => {},
    }, () => sensitivity, () => true, () => ({ x: false, y: false }), () => false, () => true);
    gesture.setMode("trackpad");
    return () => gesture.destroy();
  }, [enabled, sensitivity, scrollSensitivity, naturalScroll]);
  return <section className="input-workspace" aria-label={tr("padOnly")}>
    <div className="workspace-heading">
      <span className="workspace-badge" aria-hidden="true"><IconTrackpad /></span>
      <div><h1>{tr("padOnly")}</h1><p>{tr("touchpadInstructions")}</p></div>
      <button type="button" className="chip" onClick={onShowPicture}><IconDesktop />{tr("screen")}</button>
    </div>
    <div ref={surface} className={"touchpad-surface" + (enabled ? "" : " disabled")}
      data-testid="remote-touchpad" aria-label={tr("touchpadSurface")}>
      <div className="touchpad-glow" aria-hidden="true" />
      <span>{enabled ? tr("touchpadSurface") : tr("noInput")}</span>
    </div>
    <div className="touchpad-buttons">
      <button type="button" className="pad-btn" disabled={!enabled} onClick={() => connection()?.clickCurrent("left")}>
        <IconMouse />{tr("leftClick")}</button>
      <button type="button" className="pad-btn" disabled={!enabled} onClick={() => connection()?.clickCurrent("right")}>
        <IconMouse />{tr("rightClick")}</button>
    </div>
  </section>;
}
