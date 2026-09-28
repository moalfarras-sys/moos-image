# Mira Neural OS v4 — ميرا

Mira is the owner's voice assistant: the Echo Dot 2 in the room is her ears and voice, the MoOS
computer runs her mind and her window, and Home Assistant and Mo AI are her hands. This directory
is the whole source of the desktop app and of the Echo's on-device client. It is a per-user app
(`~/.local/share/mira/app`), **not** part of a signed MoOS image.

Both original faces — the rose one and the holographic one — are kept exactly as drawn
(`mira-*.png`), with every expression.

## What changed in v4 (2026-09-28/29)

| Area | v3 | v4 |
|---|---|---|
| Interface | QWidget + QPainter, repainting in Python | **Qt Quick on the GPU**: shaders for the aura, the face portal and the background (`shaders/*.frag`, compiled `.qsb`) |
| Face | whole sprites cross-faded; head jumped between sheets | every frame **aligned** (`faces.json`, `devtools/align_faces.py`); blink blends only the eye band, speech only the mouth band, driven by the playback level |
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
  executor (`confirmed=false`; the executor decides what needs confirmation).
- A result is "done" only when read back (Home Assistant state, Mo AI status). Otherwise the card
  says "sent, not verified" or "failed".
- Credentials stay in `~/.config/mo-dot/` (0600) and `/data/mira` on the Echo; they are never
  shown, logged or committed. Owner recordings are not in this repository.
- The Echo's wake configuration (Beamformer, `[alexa, mira_ar_experimental]`) is never changed by
  the app.

## Status, measured — see the bottom of this file for the latest evidence

Earlier measured history (v1–v3) is kept in `HISTORY.md`; the device client in `device/README.md`.

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
