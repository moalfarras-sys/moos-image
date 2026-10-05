import { useEffect, useRef } from "react";
import { GestureController } from "../lib/gestures";
import type { RemoteConnection } from "../lib/ws";
import { IconMouse, IconTrackpad } from "./icons";
import type { makeT } from "../lib/i18n";

export function Touchpad({ connection, enabled, sensitivity, scrollSensitivity, naturalScroll, tr }: {
  connection: () => RemoteConnection | null; enabled: boolean; sensitivity: number;
  scrollSensitivity: number;
  naturalScroll: boolean;
  tr: ReturnType<typeof makeT>;
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
  return <section className="input-workspace" aria-label={tr("touchpadWorkspace")}>
    <div className="workspace-heading"><IconTrackpad /><h1>{tr("touchpadWorkspace")}</h1>
      <p>{tr("touchpadInstructions")}</p></div>
    <div ref={surface} className={"touchpad-surface" + (enabled ? "" : " disabled")}
      data-testid="remote-touchpad" aria-label={tr("touchpadSurface")}>
      <div className="touchpad-horizon" aria-hidden="true" />
      <span>{enabled ? tr("touchpadSurface") : tr("noInput")}</span>
    </div>
    <div className="touchpad-buttons">
      <button className="cell" disabled={!enabled} onClick={() => connection()?.clickCurrent("left")}>
        <IconMouse />{tr("leftClick")}</button>
      <button className="cell" disabled={!enabled} onClick={() => connection()?.clickCurrent("right")}>
        <IconMouse />{tr("rightClick")}</button>
    </div>
  </section>;
}
