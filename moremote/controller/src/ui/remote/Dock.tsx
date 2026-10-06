import type { RemoteModel, ControlMode } from "./model";
import { Segmented } from "../kit";
import {
  IconFullscreen, IconKeyboard, IconMoos, IconMouse, IconSettings, IconTouch, IconTrackpad, IconTransfer,
} from "../icons";

/**
 * The Glass Console dock: the one strip of controls, always in the same place.
 *
 *   row 1  ●  connection orb  ·  [ Touch | Trackpad | Mouse & keys ]   — HOW you drive the desktop
 *   row 2  Keyboard · MoOS · Transfer · Settings                        — WHAT you can do
 *
 * On a portrait phone the two rows sit under the picture, in the band a 16:9 desktop leaves empty
 * anyway. On a computer or a phone on its side the same pieces stand in a narrow rail beside the
 * picture. Either way it is a sibling grid track of the stage (styles.css), never drawn over the
 * desktop, so the remote MoOS Horizon Bar stays visible and clickable.
 */
export function Dock({ m }: { m: RemoteModel }) {
  const { tr } = m;
  // The dock says "Mouse"; its accessible name and the Settings card say "Mouse & keys" in full.
  const modes: { value: ControlMode; label: string; aria: string; icon: React.ReactNode }[] = [
    { value: "touch", label: tr("modeTouch"), aria: tr("modeTouch"), icon: <IconTouch /> },
    { value: "trackpad", label: tr("modeTrackpad"), aria: tr("modeTrackpad"), icon: <IconTrackpad /> },
    { value: "desktop", label: tr("modeMouseShort"), aria: tr("modeMouse"), icon: <IconMouse /> },
  ];
  return (
    <div className={"toolbar" + (m.kbOpen ? " under-keyboard" : "")} inert={m.kbOpen} aria-hidden={m.kbOpen}>
      <div className="toolbar-primary" role="toolbar" aria-label={tr("remoteControlsAria")}
           aria-orientation={m.rail ? "vertical" : "horizontal"}>
        <div className="dock-row dock-modes">
          <StatusOrb m={m} />
          <Segmented className="mode-switch" label={tr("controlMode")} value={m.controlMode}
                     onChange={m.chooseMode}
                     options={modes.map((o) => ({ value: o.value, label: o.label, aria: o.aria, icon: o.icon }))} />
        </div>
        <div className="dock-row dock-actions">
          <button type="button" className="dock-btn" onClick={m.openKeyboard}>
            <IconKeyboard /><span>{tr("keyboardWorkspace")}</span>
          </button>
          <button type="button" className="dock-btn moos" onClick={m.openActions}
                  aria-label={m.hostKind === "windows" ? tr("windowsActionsTitle") : tr("moosActionsTitle")}>
            <IconMoos /><span>{tr("dockMoos")}</span>
          </button>
          <button type="button" className="dock-btn" onClick={() => m.openTransfer("clipboard")}
                  aria-label={tr("transferTitle")}>
            <IconTransfer /><span>{tr("dockTransfer")}</span>
          </button>
          {m.rail && m.controlMode === "desktop" && (
            <button type="button" className="dock-btn" onClick={m.fullscreen} aria-label={tr("fullscreen")}>
              <IconFullscreen /><span>{tr("dockFullscreen")}</span>
            </button>
          )}
          <button type="button" className="dock-btn" onClick={() => m.openSettings(m.settingsTab)}>
            <IconSettings /><span>{tr("settings")}</span>
          </button>
        </div>
      </div>
    </div>
  );
}

/**
 * The connection in one glance: a coloured dot and the round trip. It names a problem only when
 * there is one ("No video", "Weak connection"), and it is the door to resolution and speed.
 */
function StatusOrb({ m }: { m: RemoteModel }) {
  const { tr } = m;
  const text = m.issue
    || (m.status === "live" ? (m.weak ? tr("weakLinkShort") : m.latency > 0 ? `${m.latency} ms` : tr("connectedStatus"))
      : m.statusText);
  return (
    <button type="button" className={"status-orb " + m.health} aria-haspopup="dialog"
            aria-label={`${m.statusText}${m.issue ? ` · ${m.issue}` : ""}${m.latency > 0 ? ` · ${m.latency} ms` : ""}. ${tr("statusOpenAria")}`}
            onClick={() => m.openSettings("picture")}>
      <span className="orb-dot" aria-hidden="true" />
      <span className="orb-text" dir="auto">{text}</span>
    </button>
  );
}
