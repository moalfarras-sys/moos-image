import type { ReactNode } from "react";
import type { RemoteModel } from "./model";
import { SheetPanel } from "../kit";
import { actionGroups, type ActionIcon } from "../../lib/hostActions";
import type { StringId } from "../../lib/i18n";
import {
  IconCamera, IconClipboard, IconClose, IconDeskNext, IconDeskPrev, IconDesktop, IconEmoji, IconFolder,
  IconGauge, IconLauncher, IconLock, IconMaximize, IconMinimize, IconMoos, IconNextTrack, IconOverview,
  IconPlayPause, IconPower, IconPrevTrack, IconPulse, IconRefresh, IconRegion, IconSearch, IconSettings,
  IconSparkle, IconSpeakerOff, IconTerminal, IconTileLeft, IconTileRight, IconVolumeDown, IconVolumeUp,
  IconWindows2,
} from "../icons";

const ICONS: Record<ActionIcon, ReactNode> = {
  launcher: <IconLauncher />, assistant: <IconSparkle />, search: <IconSearch />, files: <IconFolder />,
  terminal: <IconTerminal />, settings: <IconSettings />, monitor: <IconPulse />, clipboard: <IconClipboard />,
  emoji: <IconEmoji />, overview: <IconOverview />, desktop: <IconDesktop />, switch: <IconWindows2 />,
  maximize: <IconMaximize />, minimize: <IconMinimize />, tileLeft: <IconTileLeft />, tileRight: <IconTileRight />,
  deskPrev: <IconDeskPrev />, deskNext: <IconDeskNext />, close: <IconClose />, volDown: <IconVolumeDown />,
  mute: <IconSpeakerOff />, volUp: <IconVolumeUp />, prev: <IconPrevTrack />, play: <IconPlayPause />,
  next: <IconNextTrack />, shot: <IconCamera />, region: <IconRegion />, taskmgr: <IconGauge />,
};

/**
 * The desktop's own commands, one tap each: open the launcher, ask Mira, search, see every window,
 * snap a window, change desktop, turn the volume, take a screenshot — and, behind a confirmation,
 * the power actions. Every tile is a shortcut the host already has (lib/hostActions.ts), checked
 * against the agents' key tables by tests/host-actions.test.ts so none of them can be a dead tile.
 */
export function ActionsSheet({ m }: { m: RemoteModel }) {
  const { tr, hostPowerAllowed, doPower } = m;
  const title = m.hostKind === "windows" ? tr("windowsActionsTitle") : tr("moosActionsTitle");
  return (
    <SheetPanel label={title} closeLabel={`${tr("closePrefix")} ${title}`} onClose={m.closeSheet}
                title={title} icon={m.hostKind === "windows" ? <IconLauncher /> : <IconMoos />} className="actions-sheet">
      <p className="sheet-lead">{tr("actionsHint")}</p>
      {actionGroups(m.hostKind).map((group) => (
        <section key={group.id} className="section">
          <div className="section-head"><h4>{tr(group.title as StringId)}</h4></div>
          <div className={"tile-grid" + (group.id === "media" ? " media" : "")}>
            {group.actions.map((action) => (
              <button key={action.id} type="button" className="tile" onClick={() => m.runAction(action, group.id === "media" && action.send.kind === "code" && action.icon !== "shot")}>
                <span className="tile-icon" aria-hidden="true">{ICONS[action.icon]}</span>
                <span className="tile-label">{tr(action.label as StringId)}</span>
                <small className="tile-hint" dir="ltr" aria-hidden="true">{action.hint}</small>
              </button>
            ))}
          </div>
        </section>
      ))}

      {/* Power is grouped last and the three that end the session ask first: "Shut down" one tap
          below "Volume up" is how a phone in a pocket ends a session. */}
      <section className="section">
        <div className="section-head"><h4>{tr("power")}</h4></div>
        {hostPowerAllowed ? <div className="grid">
          <button type="button" className="tile" onClick={() => doPower("lock", tr("lock"))}>
            <span className="tile-icon" aria-hidden="true"><IconLock /></span><span className="tile-label">{tr("lock")}</span></button>
          <button type="button" className="tile" onClick={() => doPower("sleep", tr("sleep"))}>
            <span className="tile-icon" aria-hidden="true"><IconPower /></span><span className="tile-label">{tr("sleep")}</span></button>
          <button type="button" className="tile" onClick={() => doPower("signout", tr("signOutPower"), true)}>
            <span className="tile-icon" aria-hidden="true"><IconLock /></span><span className="tile-label">{tr("signOutPower")}</span></button>
          <button type="button" className="tile" onClick={() => doPower("restart", tr("restart"), true)}>
            <span className="tile-icon" aria-hidden="true"><IconRefresh /></span><span className="tile-label">{tr("restart")}</span></button>
          <button type="button" className="tile danger" onClick={() => doPower("shutdown", tr("shutDown"), true)}>
            <span className="tile-icon" aria-hidden="true"><IconPower /></span><span className="tile-label">{tr("shutDown")}</span></button>
        </div> : <p className="muted card card-pad">
          {tr("powerCloudManagedBody")}
        </p>}
      </section>
    </SheetPanel>
  );
}
