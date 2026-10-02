# Mira Neural OS v4 — ميرا

Mira is the owner's assistant and, since 2026-09-29, the MoOS assistant: Mo AI's app became Mira.
The Echo Dot 2 in the room is her ears and voice, the MoOS computer runs her mind and her window,
Home Assistant is her hands in the house, and every Mo AI tool — through Mo AI's own executor — is
her hands on the computer. This directory is the whole source of the desktop app and of the Echo's
on-device client. It ships in signed MoOS images at `/usr/lib/mira/app`; the installed station boots `.967`.
A user source install can shadow that package and must be reported separately.

Both original faces — the rose one and the holographic one — are kept exactly as drawn
(`mira-*.png`), with every expression.

## What changed in v4 (2026-09-28/29)

| Area | v3 | v4 |
|---|---|---|
| Interface | QWidget + QPainter, repainting in Python | **Qt Quick on the GPU**: shaders for the aura, the face portal and the background (`shaders/*.frag`, compiled `.qsb`) |
| Face | whole sprites cross-faded; head jumped between sheets | every frame **aligned** (`faces.json`, `devtools/align_faces.py`); blink blends only the eye band, speech deforms one registered lip patch with playback RMS |
| States | colour changes | six distinct states: calm breathing ring, listening (mint, mic-reactive), thinking (violet comets, eyes up), speaking (rose, voice-reactive mouth), executing (amber orbit), error (dim red pulse) |
| Layout | five tabbed pages | one stage: context rail · Mira · conversation, a single command dock, and Home / Computer / Settings as slide-in workspaces; RTL/LTR mirrored; 4K → phone width |
| Typed chat | keyword router → free Mo AI model | **same brain as voice**: Gemini with Mira's 13 tools (`tools.py`, `brain.py`), fast model with a fallback chain, then the local router, then Mo AI |
| Voice | new session per turn; 24→16 kHz by averaging | one session across follow-ups, resumption, live captions, barge-in, stateful polyphase resampler, 8 s stall guard (`live_voice.py`) |
| Echo alone | client started by hand from the console | init-supervised service with backoff, firewall, tools for PC-off use, profile sync from the desktop (`device/`) |
| Background | closing the window stopped Mira | tray icon; closing hides the window and Mira keeps listening |

## How it fits together

```
Echo Dot (TECHO5 Linux) ── encrypted ESPHome API ──► mira_bridge.Bridge ──► live_voice.LiveVoice ──► Gemini Live
      │  wake word on device (Alexa + Arabic «ميرا»)          │ heartbeat/sync (HMAC, port 8765)          │
      │                                                       ▼                                          ▼
      └─ device/agent.py takes over when the PC is off   controller.Controller ◄── brain.TextBrain ── tools.py
                                                             │  (one state machine)        (typed)     │ home_link → Home Assistant
                                                             ▼                                         │ moai_link → Mo AI executor
                                                        qml/Main.qml (GPU)                             │ weather_link → Open-Meteo
                                                                                                       └ mira_memory → owner profile
```

- `app.py` — entry: single instance, tray, Echo model server, QML engine, face image provider.
- `controller.py` — the only object QML talks to; every button is a slot that reaches a real
  backend, and every result shown is the backend's read-back (`test_qml.py` fails a dead button).
- `faces.py` + `faces.json` — the original sheets cropped to one aligned portrait per expression.
- `qml/Mira/*` — the design system (`Theme.qml`, own line icons in `icons.js`) and surfaces.
- `i18n.py` — Arabic and English interface text.
- `review_fakes.py` — stand-ins used only with `MIRA_TEST_MODE=1`.

## Run, review, test, install

```sh
# normal launch (the menu entry and login autostart do this)
~/.local/share/mira/venv/bin/python ~/.local/share/mira/app/app.py

# render the source UI on the live session with stand-in data, without touching the Echo:
MIRA_TEST_MODE=1 MIRA_INSTANCE=review XDG_CONFIG_HOME=$(mktemp -d) \
  ~/.local/share/mira/venv/bin/python app.py --capture=/tmp/mira.png --scene=speaking --face=holo

# tests (UI routes/strings/QML load, controller, brain, tools, voice, device client)
QT_QPA_PLATFORM=offscreen ~/.local/share/mira/venv/bin/python -m unittest \
  test_controller test_qml test_brain test_tools test_live_voice_local test_device_agent \
  test_group_lights test_mira_memory test_moai_agent_link
~/.local/share/mira/wake-venv/bin/python -m unittest test_local_wake

# install into the user app (keeps the previous install whole in app.before-<time>) and restart
sh devtools/install_user.sh
```

The running window can save its own pixels (never the rest of the desktop) for review:
send `snapshot:~/.cache/mira/<name>.png` to the local socket `mo-dot-desktop-<uid>`.

Keyboard: Ctrl+Space talk/stop · Ctrl+K type · Ctrl+1 Home · Ctrl+2 Computer · Ctrl+3 Settings ·
Ctrl+Shift+F switch face · Esc close a workspace or stop Mira.

Shaders are compiled with `/usr/lib64/qt6/bin/qsb --glsl "100es,120,150" --hlsl 50 --msl 12 -o x.frag.qsb x.frag`.

## Boundaries that stay

- No free shell, terminal or model-written command. Computer actions go only through Mo AI's fixed
  executor. The model always calls it with `confirmed=false`; the executor decides what needs
  confirmation, and only the OWNER confirms: the card's button, the notification's button, or his
  own short «نعم» from a later turn (`pending.py`). A card expires after 3 minutes and runs nothing.
- A result is "done" only when read back (Home Assistant state, Mo AI status). Otherwise the card
  says "sent, not verified" or "failed".
- Credentials stay in `~/.config/mo-dot/` (0600) and `/data/mira` on the Echo; they are never
  shown, logged or committed. Owner recordings are not in this repository.
- The Echo's wake configuration (Beamformer, `[mira_ar_experimental]`) changes only through the
  owner's own buttons (Settings → Voice), with read-back; a model that fails to load is rolled back
  to the exact previous selection.

## Status, measured — see the bottom of this file for the latest evidence

Earlier measured history (v1–v3) is kept in `HISTORY.md`; the device client in `device/README.md`.

## Added 2026-09-29 (second batch)

- **Mira only.** Echo's active wake words are `[mira_ar_experimental]`, read back from the device. «Alexa»
  no longer wakes it, which is what the owner asked for. Every default and repair path is Mira-only.
- **Research.** The `research` tool thinks the question through and searches Google with grounding
  (gemini-2.5-flash, free up to 1,500 requests a day), then returns the source names. Voice, typed
  chat and the Echo's own client all use it. Current Plasma and Bitcoin answers came back with sources
  in 2.6–4.3 s. The Echo client answered a live question through research in 2.9 s.
- **Looking at the screen** (`look_at_screen`). Opt-in and off by default. One capture is taken only
  when asked, described, deleted, and announced with a notification.
- **Teach Mira your voice** (Settings → Voice). The Echo itself records the owner, the model trains
  locally, and it is installed over the Echo API with SHA-256 and selection read-back, with rollback.
- **Mira Companion** (Settings → Phone). A phone web app reachable only on this PC's Tailscale address,
  with QR pairing: chat, talk and home controls, and no computer tools. Off until enabled.
- A udev rule (`/etc/udev/rules.d/70-mira-echo.rules`, installed by the owner) keeps the Echo's USB
  console usable after Echo reboots.

## Mira is the MoOS assistant — Mo AI merged in (third batch, 2026-09-29)

- **One app.** For this user, `~/.local/bin/mira`, a `moai` shim that is first on the session PATH, and an
  `org.moos.moai.desktop` override named Mira with Mo AI's icon and Meta+Space all open Mira. The window's
  Wayland app id is `org.moos.moai`, read from KWin, so the dock shows one icon, Mo AI's. The system Mo AI
  launcher's pages still work: `--panel device|apps|compat|dev` → System, `remote|settings` → Settings,
  `--ask TEXT` fills the composer (a `moos://` link never sends for the owner). Mo AI's services keep
  running as the executor. `devtools/install_user.sh --restore-moai` gives the launcher back.
- **Every Mo AI tool, by name** (`moai_tools.py`). The 50 tools the installed image declares in
  `/usr/lib/moai/moai_tool_schemas.py` are the model's own tools, with no enum wrapper. `open_app` stays
  `computer_open_application`, which resolves Arabic names. Reads and instant controls run at once, and
  volume/brightness are read back. `find_app` searches Mo Store's catalogue for a real Flatpak id.
- **Owner approval** (`pending.py`, `ActionCards.qml`). A system change parks as a live card: install,
  update MoOS, repair sound, firmware, NVIDIA, Waydroid or closing a window. It carries a KDE notification
  with Approve/Cancel and runs only on the owner's answer. The job is then followed to its real end
  (`/tool/job`), with its output on the card. A privileged job still asks for the password through Polkit.
  A job longer than 20 s is announced when it ends.
- **System centre** (`SystemSheet.qml`, Ctrl+4) replaces Mo AI's device panel. It shows the booted
  deployment (version, signed origin, edition, rollback), store search with Install/Open/Remove, and every
  check, repair, update and set-up tile with its real output.
- **Desktop and time tools** (`desktop_tools.py`, `reminders.py`, `routines.py`, `announce.py`):
  - media via MPRIS, the clipboard, file search (Baloo), and opening files and links;
  - windows through KWin scripting: list and focus, with close behind approval;
  - per-app volume;
  - reminders and timers that fire on time as a desktop notification and on the Echo through Gemini TTS;
  - named routines built from Mira's own tools, where each step keeps its tool's rules.

  Opening a launcher, script or program by path is refused.
- **Improved wake model** `mira_ar_v2` (`wake_training/`, report `mira_ar_v2-report.md`). It was trained on
  26 synthetic voices with real room sound. At an equal false-accept budget it beats the committed model on
  unseen voices: 0.80 vs 0.65. Confusables fire 0.5% vs 8.8%. It is offered from Settings → Voice to run
  beside the proven model.
- **Measured:**
  - 169 unit tests pass, plus 19 device tests.
  - Real Gemini Live with all 74 declarations read memory and found VLC. It parked `install_app` as a card,
    asked for «نعم», and answered «تمام» without claiming the install had started.
  - A real round trip through `moai-control` passed: `set_do_not_disturb=on` was refused unconfirmed, then
    parked, approved, and the job ran with state read back `dnd=true`. It was turned off again.
  - `moai --panel device` opened the System centre with the booted signed deployment.
- **Any MoOS user, not only this station:**
  - The Echo connects only when one is paired (`echo.json` or `device.key`); otherwise Mira is typed chat
    with every tool.
  - Settings → Voice keeps the user's own Gemini key (0600) and proves it with a real request.
  - Without a key, the same 74 tools run on **Mo AI's free cloud brain** through moai-gateway (OpenAI tool
    calling). This was measured live: memory was read back; a VLC install became a card with «نعم»;
    the audio settings opened.
- **The paired phone** shows the same approval cards and can Approve or Cancel them. A privileged step
  still asks for the password at the computer.
- **The Echo is reached without an inbound port.** Wake models and spoken lines go to the Dot's
  own client over the signed channel (`POST /asset/<name>`), and echod fetches them from its
  loopback. Measured:
  - `mira_ar_v2` runs in slot 1 at its measured cutoff 0.65, beside `mira_ar_experimental` at 0.60;
  - a reminder was spoken on the Echo as a 16 kHz announcement;
  - without TTS quota, Mira says the line herself in Live.
- **Not done:** a model-authored command tool (P3.9 — not built; needs the owner's explicit go-ahead
  in a session), a signed image with Mira, and Mira on ARM.

## In the MoOS image (branch `mira/neural-os-v4`, x86 editions)

- The Containerfile's `mira-build` stage starts FROM the image's own base. It installs the base's RPM
  `python3-pyside6`/`python3-numpy` and adds only `packaging/requirements.lock` (22 sha256-pinned
  wheels: google-genai 2.25, aioesphomeapi 46.6, protobuf 7, …; no dependency resolution, no
  bytecode). It then runs Mira's suites, stages the runtime tree (`packaging/stage.sh`) and opens
  her window offscreen.
- The image gets `/usr/lib/mira/app`, `/usr/lib/mira/site` and `/usr/bin/mira`. `/usr/bin/moai`
  hands every launch to her, so Meta+Space, the dock, moos:// routes, KRunner, moos-hardware and
  moos-compat reach Mira. An edition without the stage (ARM, whose Containerfile belongs to the
  Oracle agent) keeps the QML app.
- `build.sh` installs her RPMs and gates the tree, the pinned packages, the launcher hand-off, her
  app id, the imports, an offscreen frame and the absence of bytecode.
- System Settings → MoOS → Mira is her page: her settings and the System centre (`moos://ai/settings`,
  `moos://ai/system`), and how to reach her.
- `moos-ui-migrate` (Mo AI rev 4) removes this folder's per-user takeover once the image carries
  her, and never touches her data.

## Measured on the owner's station, 2026-09-28/29

- **Installed** with `devtools/install_user.sh` (previous install kept whole in
  `~/.local/share/mira/app.before-20260928T235825`). The app connected to the Echo and reached
  `ready`; its tray item is registered with Plasma (`StatusNotifierItem`, title "Mira"). The
  window grabbed its own pixels showing real data: Berlin 17 °C from Open-Meteo, 3/3 lights on,
  the TCL TV on, and the restored conversation.
- **Hands-free Arabic conversation, owner-spoken (00:34–00:35).** Echo detected «ميرا» with the
  Arabic model (peak 0.83). Then there were three turns in one conversation:
  1. Time: the session resumed and the reply started 0.71 s after the owner stopped speaking (4.8 s answer).
  2. A follow-up without the wake word, on the reused session (32 ms): the reply started at the end of speech.
  3. Weather: the tool took 0.81 s and the reply started 1.42 s after the end of speech.

  echod logged each turn as `turn ended was=replying … why=spoken`. Earlier, an «Alexa» turn with
  a question also answered 0.65 s after the end of speech.
- **Wake detection.** Before the Echo reboot, the owner's «ميرا» scored 0.56–0.91 at cutoff 0.70.
  After the reboot, bare «ميرا» stayed below 0.5, so the slot-2 threshold was set back to 0.60 (the
  value the earlier successes ran at; read back 0.6). echod lowers it by its own slack to 0.50
  while echo cancellation runs. The owner then reported that «هاي ميرا» wakes reliably, and the
  log shows 0.91, 0.82 and 0.83. The model is still the synthetic-voice experiment; see
  `wake_training/`.
- **Typed chat through the brain, real services (read-only prompts).** «كم ضوء مضاء الآن؟»,
  weather, time, a computer check, «مين إنتِ؟» and an English weather question were each answered by
  `gemini-flash-lite-latest` with the right tool in 1.2–4.4 s, in the language of the message. An
  earlier run on `gemini-flash-latest` hit its quota within a few calls and took 12 s, so text now
  uses flash-lite first and falls back to 2.5-flash, then flash-latest, before any local route.
- **Echo client**: see `device/README.md`. The reboot recovered in 43 s end to end. With the PC app
  closed, the Echo took the voice in 5 s and handed it back in 2 s, after the loopback fix.
- **Energy.** The live app used about 11 % of one core in its first minute and 3 % at rest (blinks
  only). RSS is about 520 MB.
- **Tests**: 107 unit/integration tests plus 7 wake tests pass. The QML route and string gate was
  shown to fail when a dead button or an undefined name was added.

Not done, and not claimed:
- Power-cut recovery. It uses the same init path as the reboot, but has not been measured.
- A long false-wake measurement.
- A wake model trained on the owner's own voice.
- Home control while the PC is off. This needs an always-on Home Assistant host.
- Screen understanding.
- A phone interface.
- Packaging into a signed MoOS image.


## Face motion correction — 2026-10-02

The original neutral/mood/blink portraits and their calibration are preserved.
`mira-rose-motion-v1.png` and `mira-holo-motion-v1.png` are derived motion patches
(half eyelid, small/medium opening, rounded mouth), generated against the original
face. `devtools/align_faces.py --motion` registers only these new frames against
the stable nose bridge; the portal samples the eyelids/lips only. Rounded mouth
is available artwork, not guessed from quiet audio.

Speech uses PCM RMS on the playback clock, distinct from the aura's peak energy.
Pending silence survives the level notification floor. Equal-level packets refresh
a 240 ms watchdog; missing audio, hidden state and reduced motion close the mouth.
Speaking uses the neutral registration and removes voice-driven whole-head zoom.
The mouth now samples **one** medium-opening patch and compresses its inner gap
in UV space. Each lip moves without shrinking its thickness; deformation fades
out before the nose/chin. Mouth patches are never cross-faded: their different
outlines produced duplicate lips at intermediate amplitude. At rest the original
portrait is used. No original image, blink, face identity or provider changed.
This improves the opening envelope; it does not recognize speech phonemes.

`just check` and 89 controller/QML/voice tests passed; the silence regression
rejects the old scheduler. Both GPU faces were rendered to 600×600
H.264/AAC MP4s using a real synthesized Arabic WAV. A source live Gemini voice
turn delivered mouth packets, reached zero during pauses and at idle, and yielded
28 face-only captures in the corrective single-mouth review. The first Echo wake-button diagnostic did not start a turn;
the live test invoked the native voice-start callback with an explicit text request,
so it proves conversation output, not owner-spoken wake/microphone capture.

Temporary live process: `mira-face-motion-live.service` runs
`fix/mira-single-mouth-20261002` through the cache-only review runner
`~/.cache/mira/live-single-mouth-review.py`; its one text-triggered voice diagnostic
ends after capture, leaving the normal application running. It runs this source
with the installed dependencies. It replaced the autostart process for review;
no launcher, credential or permission file changed. After signed delivery, stop
this unit and launch the installed `mira` again. Reboot naturally selects the
installed package. Signed motion delivery and owner-spoken endurance are open.

Reproduce a waveform review (keep recordings/output local):

```sh
PYTHONPATH=/usr/lib/mira/site python3 -s devtools/review_face_motion.py \
  --audio /path/to/16k-mono.wav --face rose --output /path/to/review.mp4
```

Research: [MuseTalk](https://github.com/TMElyralab/MuseTalk) performs audio-driven
face-region synthesis; [LivePortrait](https://github.com/KwaiVGI/LivePortrait)
provides portrait retargeting; [Rhubarb](https://github.com/DanielSWolf/rhubarb-lip-sync)
produces timed 2D mouth shapes. None was installed or measured on this station.
The correction keeps the existing Qt renderer and both selected identities.


## Home centre and Lumen — 2026-10-03 (branch `feat/mira-home-lumen-20261002`)

The owner asked for the house to be Mira's most important skill: rename every device so she
understands it, a control centre for the house, lights as groups and scenes with every effect,
lights that follow the screen, and the PC's own case RGB.

**Home** (`pages/home.py`, `HomePage.qml`, `homehub.py`). Every device by room, read from Home
Assistant's own registries (one WebSocket session: areas, devices, entities, voice aliases) and
states. A name, a room or a voice name set on the page — or by asking Mira (`home_rename`) — is
written IN Home Assistant and read back, so every later conversation and every app uses it. Each
device carries what it can really do (`homehub.capabilities`: colour modes, white range, effects,
media feature bits, remote keys …), in one Arabic and one English line; Mira's instruction carries
the same inventory (`tools.home_block`), so she never offers a TV a volume level it does not have.
Without a link the page probes `127.0.0.1:8123` and asks for a token; devices Home Assistant has
discovered on the network are listed with a way to add them.

**Lumen** (`lumen/`, `LumenPage.qml`, `/usr/bin/mira-lumen`, `mira-lumen.service`). The MoOS
lighting engine, its own small user service (17–30 MB) so living scenes and Screen Sync keep
running while Mira's window is closed. One id scheme for every light: `ha:<entity>` (Hue, Tuya,
ESPHome … through Home Assistant), `hue:<uuid>` (the Hue bridge directly, when no Home Assistant
covers it — a fresh install), `pc:<header>` (the motherboard's lighting controller). Targets are
words — all, a room, a group, a name or alias, `pc` — resolved the same way for the page, the voice
brain and the text brain.

- *Colour and white*: names in Arabic/Levantine and English, hex, kelvin (`lumen/colors.py`);
  a white goes to a lamp's colour-temperature channel where it has one.
- *Scenes* (`lumen/scenes.py`): fourteen moods; each lamp takes its own stop of the palette, living
  ones drift at a rate the bridge accepts (≤ 8 commands/s for the whole house), Hue's candle and
  fire run inside the bulb, the PC joins at 30 fps. A living scene on the PC resumes at sign-in;
  the house's lamps are never changed because the computer started.
- *Read-back*: ok only when Home Assistant (or the bridge) reads the asked state back; a lamp that
  stays as it was is `pending`, an unreachable one is named and never counted.
- *The PC* (`lumen/fusion2.py`): Gigabyte RGB Fusion 2 (ITE IT5701/5702/8297), found by its USB id,
  driven through hidraw (the image's openrgb udev rules give the seat's user access). Nothing is
  written to the controller's flash. Its LEDs cannot be read back: "ok" there means the controller
  acknowledged every report. Headers can be renamed, identified (flash) and sized.
- *Screen Sync* (`lumen/capture.py`, `lumen/sync.py`, `lumen/syncsession.py`): the ScreenCast portal
  (approved once, restore token kept), a tiny downscaled frame, colour per light by position; the
  PC every frame, a Hue Entertainment stream every frame once Lumen holds its own bridge pairing
  (DTLS-PSK through GnuTLS, `lumen/dtls.py`), other lamps a few times a second with transitions.
  Cloud-polled lamps (Tuya) follow the screen only when named on purpose.
- *Hue pairing* (`lumen/hue.py`): the bridge is discovered (mDNS/Avahi), the owner presses its round
  button, the keys go to `~/.config/mo-dot/lumen-hue.json` (0600) with the certificate fingerprint.

Mira's tools: `lights`, `light_scene`, `screen_sync`, `home_rename`, `tv_control` (beside the
existing `home_*` tools). Reached from her NavRail (الإضاءة, Ctrl+8), `mira --panel lumen|home`,
the Mira launcher's Lights/Home actions, `moos://ai/lumen|home`, and System Settings → Mira.
