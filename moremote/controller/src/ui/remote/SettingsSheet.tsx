import type { RemoteModel, ControlMode, Orient } from "./model";
import { Row, Section, Segmented, SheetPanel, SliderRow, Switch, Tabs } from "../kit";
import { QUALITY_PRESETS } from "../../types";
import { describeHints, estimateMbps } from "../../lib/quality";
import {
  IconActual, IconBell, IconGauge, IconDesktop, IconFit, IconFullscreen, IconGlobe, IconInfo, IconLock, IconMouse,
  IconPower, IconRefresh, IconRotate, IconSettings, IconShield, IconSpeaker, IconTouch, IconTrackpad,
  IconZoomIn, IconZoomOut,
} from "../icons";

/**
 * Settings, in three tabs instead of one long scroll:
 *
 *   Picture  — resolution & speed (with what each costs), frame rate, view, rotation, sound
 *   Control  — the three modes explained, each mode's own option, pointer and scroll feel
 *   General  — language, alerts, trusted devices, session, version
 *
 * The connection orb opens Picture directly, because "it is blurry / it is slow" is the question
 * people open settings with most often.
 */
export function SettingsSheet({ m }: { m: RemoteModel }) {
  const { tr } = m;
  return (
    <SheetPanel label={tr("settingsTitle")} closeLabel={`${tr("closePrefix")} ${tr("settingsTitle")}`}
                onClose={m.closeSheet} title={tr("settingsTitle")} icon={<IconSettings />} className="settings-sheet">
      <Tabs idPrefix="settings" label={tr("settingsSections")} value={m.settingsTab} onChange={m.setSettingsTab}
            tabs={[
              { value: "picture", label: tr("tabPicture"), icon: <IconDesktop /> },
              { value: "control", label: tr("tabControl"), icon: <IconTouch /> },
              { value: "general", label: tr("tabGeneral"), icon: <IconSettings /> },
            ]} />
      <div id="settings-panel" role="tabpanel" aria-labelledby={`settings-tab-${m.settingsTab}`} className="tab-panel">
        {m.settingsTab === "picture" && <PictureTab m={m} />}
        {m.settingsTab === "control" && <ControlTab m={m} />}
        {m.settingsTab === "general" && <GeneralTab m={m} />}
      </div>
    </SheetPanel>
  );
}

function LiveReadout({ m }: { m: RemoteModel }) {
  const { tr, stream } = m;
  const live = m.status === "live" && stream.width > 0;
  const height = Math.round(stream.width * 9 / 16);
  return (
    <div className={"live-readout " + m.health} role="status" aria-live="polite">
      <span className="orb-dot" aria-hidden="true" />
      <div className="live-main">
        <b>{live ? tr("streamingNow") : m.statusText}</b>
        <span dir="ltr">
          {live
            ? `${stream.width}×${height} · ${stream.fps} fps · ${m.codec === "h264" ? "H.264" : "JPEG"}`
            : "—"}
        </span>
      </div>
      <div className="live-side" dir="ltr">
        <b>{m.latency > 0 ? `${m.latency} ms` : "—"}</b>
        {/* The budget is the H.264 encoder's; a JPEG stream has no such ceiling, so no number. */}
        <span>{live && m.codec === "h264" ? `≤ ${estimateMbps(stream.quality, stream.width, stream.fps)} Mbit/s` : ""}</span>
      </div>
    </div>
  );
}

function PictureTab({ m }: { m: RemoteModel }) {
  const { tr } = m;
  const orientOptions: { value: Orient; label: string; icon?: React.ReactNode }[] = [
    { value: "auto", label: tr("fitPhone") },
    { value: "on", label: tr("sideways"), icon: <IconRotate /> },
    { value: "off", label: tr("upright"), icon: <IconLock /> },
  ];
  return (
    <>
      <LiveReadout m={m} />

      <Section title={tr("qualitySpeed")}>
        <div className="card-pad">
          <button type="button" className={"quality-auto" + (m.auto ? " on" : "")} aria-pressed={m.auto}
                  aria-label={tr("auto")} aria-describedby="quality-auto-desc" onClick={m.chooseAuto}>
            <span className="qa-mark" aria-hidden="true"><IconGauge /></span>
            <span className="qa-text">
              <b>{tr("auto")}{m.auto && m.weak && <em> · {tr("weakLinkShort")}</em>}</b>
              <small id="quality-auto-desc">{tr("autoQualityDesc")}</small>
            </span>
          </button>
          <div className="quality-grid">
            {QUALITY_PRESETS.map((p, i) => {
              const fps = m.fpsPref === 30 || m.fpsPref === 60 ? m.fpsPref : p.fps;
              const cost = estimateMbps(p.quality, p.width, fps);
              const detail = `${p.detail.split("·")[0].trim()} · ${fps} fps`;
              return (
                <button key={p.label} type="button" className={"quality-card" + (!m.auto && m.presetIdx === i ? " on" : "")}
                        aria-pressed={!m.auto && m.presetIdx === i}
                        aria-label={`${m.qualityLabel(i)} ${detail} · ${tr("upTo")} ${cost} ${tr("mbps")}`}
                        onClick={() => m.choosePreset(i)}>
                  <b>{m.qualityLabel(i)}</b>
                  <span dir="ltr">{detail}</span>
                  <small>{tr("upTo")} <span dir="ltr">{cost}</span> {tr("mbps")}</small>
                  <i className="q-bars" aria-hidden="true" data-level={i} />
                </button>
              );
            })}
          </div>
          {m.codec === "jpeg" && m.status === "live" && <p className="hint warn">{tr("jpegCostNote")}</p>}
          {/* Say the limit out loud. A limit that acts without explaining itself is indistinguishable
              from the app being bad at its job. */}
          {m.hostEncode && (
            <p className="hint">
              {tr("hostCapPrefix")}{" "}
              <b dir="ltr">{m.hostEncode.maxWidth}×{m.hostEncode.maxHeight}@{m.hostEncode.maxFps}</b>.{" "}
              {tr("hostCapSuffix")}
            </p>
          )}
        </div>
      </Section>

      <Section title={tr("frameRate")}>
        <div className="card-pad">
          <Segmented label={tr("frameRate")} value={m.fpsPref === 30 || m.fpsPref === 60 ? m.fpsPref : 0}
                     onChange={(v) => m.setFpsPref(v)}
                     options={[
                       { value: 0, label: tr("fpsFromQuality") },
                       { value: 30, label: "30 fps" },
                       { value: 60, label: "60 fps" },
                     ]} />
          <p className="hint">{tr("fpsHint")}</p>
        </div>
      </Section>

      <Section title={tr("viewSection")}>
        <div className="card-pad stack">
          <Segmented label={tr("screen")} value={m.viewMode} onChange={m.chooseView}
                     options={[
                       { value: "fit", label: tr("fitScreen"), icon: <IconFit /> },
                       { value: "actual", label: "100%", icon: <IconActual /> },
                     ]} />
          <div className="zoom-row" role="group" aria-label={tr("zoom")}>
            <button type="button" className="chip" onClick={() => m.zoomBy(0.77)}><IconZoomOut />{tr("zoomOut")}</button>
            <button type="button" className="chip" onClick={m.resetZoom}>{tr("reset")}</button>
            <button type="button" className="chip" onClick={() => m.zoomBy(1.3)}><IconZoomIn />{tr("zoomIn")}</button>
          </div>
          <div className="field-label">{tr("rotation")}</div>
          {/* THE LOCK. Offered on every device, including the ones where it currently changes
              nothing — because the request is "let me decide, and then stop changing your mind". */}
          <Segmented label={tr("rotation")} value={m.orient} onChange={m.chooseOrient} options={orientOptions} />
          <p className="hint">{tr("rotationHelp")}</p>
          {m.monitors.length > 1 && (
            <>
              <div className="field-label">{tr("monitor")}</div>
              <Segmented label={tr("monitor")} value={m.selMonitor} onChange={m.chooseMonitor}
                         options={m.monitors.map((mon, i) => ({
                           value: i, label: mon.primary ? tr("mainScreen") : `${tr("screenNumberPrefix")} ${i + 1}`,
                         }))} />
            </>
          )}
        </div>
      </Section>

      <Section title={tr("actions")}>
        <Row title={tr("computerSound")} sub={m.sound === "connecting" ? tr("connecting") : tr("computerSoundSub")}
             icon={<IconSpeaker />}>
          <Switch on={m.sound === "on" || m.sound === "connecting"} onToggle={m.toggleSound} label={tr("computerSound")} />
        </Row>
        <Row title={tr("fullscreen")} sub={tr("fullscreenSub")} icon={<IconFullscreen />}>
          <button type="button" className="chip" onClick={() => { m.fullscreen(); m.closeSheet(); }}>{tr("fullscreen")}</button>
        </Row>
      </Section>
    </>
  );
}

function ControlTab({ m }: { m: RemoteModel }) {
  const { tr } = m;
  const cards: { value: ControlMode; title: string; desc: string; icon: React.ReactNode }[] = [
    { value: "touch", title: tr("modeTouch"), desc: tr("modeTouchDesc"), icon: <IconTouch /> },
    { value: "trackpad", title: tr("modeTrackpad"), desc: tr("modeTrackpadDesc"), icon: <IconTrackpad /> },
    { value: "desktop", title: tr("modeMouse"), desc: tr("modeMouseDesc"), icon: <IconMouse /> },
  ];
  return (
    <>
      <div className="mode-cards" role="group" aria-label={tr("controlMode")}>
        {cards.map((c) => (
          <button key={c.value} type="button" className={"mode-card" + (m.controlMode === c.value ? " on" : "")}
                  aria-pressed={m.controlMode === c.value} onClick={() => m.chooseMode(c.value)}>
            <span className="mode-card-icon" aria-hidden="true">{c.icon}</span>
            <span className="mode-card-text"><b>{c.title}</b><small>{c.desc}</small></span>
          </button>
        ))}
      </div>

      <Section title={tr("pointer")}>
        {m.controlMode === "touch" && (
          <Row title={tr("oneFingerDrag")} sub={tr("oneFingerDragSub")}>
            <Switch on={m.touchDrag} onToggle={() => m.setOneFingerDrag(!m.touchDrag)} label={tr("oneFingerDrag")} />
          </Row>
        )}
        {m.controlMode === "trackpad" && (
          <Row title={tr("padOnly")} sub={tr("padOnlySub")}>
            <Switch on={m.padOnly} onToggle={() => m.setPadOnly(!m.padOnly)} label={tr("padOnly")} />
          </Row>
        )}
        {m.controlMode === "desktop" && (
          <Row title={tr("capturePointer")} sub={tr("capturePointerSub")}>
            <Switch on={m.pointerLock} onToggle={m.togglePointerLock} label={tr("capturePointer")} />
          </Row>
        )}
        <SliderRow title={tr("mouseSpeed")} value={m.mouseSensitivity} min={0.4} max={2.5} step={0.1}
                   onChange={m.setMouseSensitivity} />
        <SliderRow title={tr("scrollSpeed")} value={m.scrollSensitivity} min={0.4} max={2.5} step={0.1}
                   onChange={m.setScrollSensitivity} />
        <Row title={tr("naturalScroll")} sub={tr("naturalScrollSub")}>
          <Switch on={m.naturalScroll} onToggle={m.toggleNaturalScroll} label={tr("naturalScroll")} />
        </Row>
        <Row title={tr("haptics")} sub={tr("hapticsSub")}>
          <Switch on={m.haptics} onToggle={m.toggleHaptics} label={tr("haptics")} />
        </Row>
        <Row title={tr("magnifyTyping")} sub={tr("magnifyTypingSub")}>
          <Switch on={m.typingZoom} onToggle={m.toggleTypingZoom} label={tr("magnifyTyping")} />
        </Row>
      </Section>
    </>
  );
}

function GeneralTab({ m }: { m: RemoteModel }) {
  const { tr, lang, trustedDevices, toggleBackgroundAlerts, deviceBusy, revokeDevice } = m;
  return (
    <>
      <Section title={tr("language")}>
        <div className="card-pad">
          <Segmented label={tr("language")} value={lang} onChange={(next) => m.onLangSwitch(next)}
                     options={[
                       { value: "ar", label: "العربية", icon: <IconGlobe /> },
                       { value: "en", label: "English", icon: <IconGlobe /> },
                     ]} />
        </div>
      </Section>

      <Section title={tr("alerts")}>
        <Row title={tr("backgroundAlerts")}
             sub={tr("backgroundAlertsSub")} icon={<IconBell />}>
          <Switch on={m.backgroundAlerts && m.backgroundAlertsGranted}
                  onToggle={() => void toggleBackgroundAlerts()} label={tr("backgroundAlerts")} />
        </Row>
      </Section>

      <Section title={tr("trustedDevicesTitle")}>
        <div className="trusted-list" aria-busy={trustedDevices === null && !m.trustedDevicesFailed}>
          {m.trustedDevicesFailed && <div className="card-pad">
            <div role="alert">{tr("trustedDevicesLoadFailed")}</div>
            <button type="button" className="btn" onClick={m.retryTrustedDevices}>{tr("retry")}</button>
          </div>}
          {trustedDevices === null && !m.trustedDevicesFailed && <div className="card-pad muted" role="status">{tr("loadingTrustedDevices")}</div>}
          {trustedDevices?.length === 0 && <div className="card-pad muted">{tr("noRememberedDevices")}</div>}
          {trustedDevices?.map(device => (
            <div className="trusted-row" key={device.id}>
              <span className="row-icon" aria-hidden="true"><IconShield /></span>
              <div className="row-main">
                <div className="row-title">{device.name}{device.current ? tr("thisDeviceSuffix") : ""}</div>
                <div className="row-sub">{tr("lastUsedPrefix")} {new Date(device.lastUsedUnix * 1000).toLocaleDateString()}</div>
              </div>
              <button type="button" className="device-revoke" disabled={!!deviceBusy}
                      onClick={() => void revokeDevice(device)}
                      aria-label={`${tr("removeTrustedDeviceAria")} ${device.name}`}>
                {deviceBusy === device.id ? tr("removingDevice") : tr("removeDevice")}
              </button>
            </div>
          ))}
        </div>
      </Section>

      <Section title={tr("sessionSection")}>
        <Row title={tr("refresh")} sub={tr("refreshStreamSub")} icon={<IconRefresh />}>
          <button type="button" className="chip" onClick={() => { m.refreshStream(); m.closeSheet(); }}>{tr("refresh")}</button>
        </Row>
        <Row title={tr("disconnect")} icon={<IconPower />}>
          <button type="button" className="chip danger" onClick={m.disconnect}>{tr("disconnect")}</button>
        </Row>
      </Section>

      {/* About answers "which build is my phone running?" WHERE YOU CAN ASK IT. */}
      <Section title={tr("about")}>
        <div className="kv"><span><IconInfo />{tr("appVersion")}</span><b>{m.build}</b></div>
        <div className="kv"><span>{tr("connection")}</span><b>{m.statusText}</b></div>
        <div className="kv"><span>{tr("quality")}</span>
          <b>{m.auto ? `${tr("autoMode")} · ` : ""}{m.qualityLabel(m.presetIdx)}</b>
        </div>
        <div className="kv"><span>{tr("thisDevice")}</span><b dir="ltr">{describeHints(m.deviceHints)}</b></div>
      </Section>
      <div className="credit">Mo PC Remote · by Moalfarras</div>
    </>
  );
}
