# Mira Neural OS — MoOS source

This directory contains the owner's current desktop Mira application and its two
existing faces (`rose` and `holo`). The source was imported from the live user
installation without replacing MoOS's desktop or Mo AI. It is **not yet** an
OS-image package or a signed release.

## Measured on the owner's station, 2026-09-28

- The installed app starts, pairs to the Echo, and reaches voice `ready`.
- The user journal shows a local-computer wake at 09:54 followed by an Echo
  voice turn with `heard=True` and reply audio. This is the earlier single
  success, not proof that Echo's on-device wake model recognized the owner.
- The microphone **button** previously produced a spoken Echo reply. The local
  PC microphone matched spoken wake phrases and Echo entered `listening` in the
  live log. Those turns produced no recognized question or audio answer. The
  latest source uses the same PC microphone for the question and falls back to
  Echo's microphone if it is too slow; it separates capture from recognition.
  The USB gadget microphone delivered only 10% of real-time audio in a measured
  four-second capture, and a later live health sample fell to 0.9 frames/s.
  An analog input delivered 95% in a capture test, but its physical port reports
  disconnected and the owner's spoken test did not activate Mira. That selection
  was reverted to the USB source; neither PC input currently proves reliable
  hands-free operation. Echo remains the speaker. The device's on-device wake
  cutoff had drifted to `0.99`; it was restored to `0.50` with state readback.
  Its room sensitivity was lowered from 6 to 4 dB (the supported minimum) for
  an owner-spoken test; the ring still did not respond. The previous 6 dB
  setting was restored with device readback.
- The microphone picker now excludes a source whose active physical port is
  reported as unplugged. The tested change is installed in the user app.
- The active on-device `hey_mira.tflite` is an English openWakeWord model.
  Arabic aliases in `local_wake.py` apply only to a working computer audio
  source; they do not change what the Echo model recognizes. Improving Arabic
  and the owner's pronunciation requires a measured replacement wake model,
  tested against actual Echo microphone samples, rather than another UI alias.
- A direct, read-only Echo console audit confirmed its seven-microphone capture
  device is `RUNNING` at 16 kHz, nine channels (seven microphones plus two
  loopback channels). Its installed `hey_mira.tflite` SHA-256 matches the app's
  model (`45d825aa…6729b1`). The voice daemon remains active. This rules out
  a stopped capture device or damaged model file; it does not measure the
  model's recall for the owner's voice. A temporary console text-echo loop was
  stopped by opening the serial port in raw mode; no device file was changed.
- Home Assistant returned current devices. A real available lamp was turned on,
  changed to pink, then returned to its original off state; all three state
  readbacks were `ok`. Two TVs were `unavailable`, so their controls stay disabled.
- Mo AI's pinned Hermes runtime was installed for this user, and the `MoOS`
  project was registered with the owner's explicit consent to cloud project
  analysis. The `projects` tool was observed in the agent event log; Mira's text
  route returned `MoOS` through the `hermes` gateway. Mutating agent tools still
  require Mo AI's one-time approval.
- Chat/profile data remain in private files under `~/.config/mo-dot/`.
- The Echo itself answers on the local Wi-Fi at `192.168.3.83:6053` without a USB
  cable. Its own `http://192.168.3.83:8181/setup` page was opened and returned
  HTTP 200 after the Setup Page switch was turned on; a press on the device
  authorizes a browser. The page closes itself after seven idle minutes.
  Mira's Settings now opens it, and offers the device's actual microphone-mute
  and Bluetooth-pairing switches. The mute switch was exercised on the Echo
  (off → on → off with state readbacks); pairing was not triggered without a
  target speaker. The installed desktop process restarted and
  returned to `ready`; 34 mocked UI/voice tests pass. These are network and
  control proofs, not a hands-free or computer-off voice proof.

## Independent operation boundary

The current TECHO5 Dot daemon owns all seven microphones and plays audio locally,
but `conversation.go` explicitly ignores wake events when no ESPHome voice
pipeline is subscribed. Mira's Gemini Live client and Home Assistant currently
run on this computer. If it is off, neither answers; the device's setup page,
Bluetooth speaker and Wi-Fi remain device-local. A mobile browser can configure
the Dot through its setup page, but it is not a remote AI conversation app.

For computer-off voice, the device needs a supported on-device cloud conversation
client that takes the daemon's microphone/audio stream, or a separate always-on
home hub running the voice pipeline. For computer-off Hue/Tuya/TCL control through
Home Assistant, that Home Assistant instance must run on an always-on host. The
Dot's 481 MiB RAM and 32-bit ARM system are not an appropriate substitute for
the full Home Assistant hub. No on-device client or hub migration is deployed yet.
Any such firmware extension must preserve the Dot's signed A/B update and rollback
path and be tested with the owner-spoken wake model. Do not describe the desktop
client's current Wi-Fi connection as standalone operation.

## Current deployment boundary

The running app is in `~/.local/share/mira/app/` with user-local Python
environments. `MIRA_ECHO_HOST` can select the paired device; the encryption key
remains in `~/.config/mo-dot/device.key`. Do not commit either credentials or
private conversation/profile data. Packaging the app, dependencies, and wake
model into all MoOS editions needs an image build and boot proof before any menu
entry is shipped. The repo's Mo AI capability broker remains the authority for
project files, web access and host controls. Mira must not add a raw host shell.

Targeted source checks on the station:

```sh
QT_QPA_PLATFORM=offscreen ~/.local/share/mira/venv/bin/python -m unittest \
  test_ui_routes test_group_lights test_mira_memory test_moai_agent_link \
  test_live_voice_local -q
# Run with the separate wake recognizer environment:
~/.local/share/mira/wake-venv/bin/python -m unittest test_local_wake -q
```

These checks exercise routes with mocked services; they do not qualify the
microphone, Echo, Home Assistant or a signed OS image.
