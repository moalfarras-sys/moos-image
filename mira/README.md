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

`device/agent.py` is a temporary on-device Gemini client. A real cloud text-to-audio
turn completed on Echo and the daemon logged streamed playback with zero underruns.
This does not prove an owner-spoken wake/question/answer or operation after reboot.
The desktop sends authenticated heartbeats: stopping its actual unit made Echo
change from `desktop` to `ready` within five seconds; reopening returned it to
`desktop`. Handoff now drains the old audio producer before releasing the channel.

A console sample contains `hey_mira` detection at score 0.879 (cutoff 0.50), then
a listening timeout. That proves one detection, not a successful conversation.
The model still recognizes English; UI Arabic aliases do not retrain it.

Deployment is experimental: Python packages are installed in the current root,
the client is manually launched, and its LAN firewall rule is temporary.
The initial dependency mismatch was corrected with aioesphomeapi 45.0.0 and
zeroconf 0.151.5; device `pip check` now reports no broken requirements.
The older client requires explicit `password=None`, now supplied alongside Noise.
Full voice qualification still remains before persistent startup, preserving
the signed A/B firmware path. Credentials/history are private in `/data/mira`;
the LAN endpoint exposes only state and accepts paired HMAC heartbeats.

The on-device client has no house/PC tools yet. Home Assistant remains on this PC;
computer-off house control needs an always-on HA host. The phone setup page is
configuration, not a complete mobile assistant. PC-off endurance, restart recovery,
dependency qualification and owner-spoken hands-free proof remain open.

Latest owner test still failed to activate. Live state confirmed all microphones,
mic mute false, leveling enabled and gain 24 dB. Wake threshold was subsequently
changed from 0.50 to 0.30 with state readback; this tuning is not evidence of
successful recognition and can increase false activations. No new face/UI was
introduced. The on-device standby client now releases the encrypted API entirely
while the desktop heartbeat is present, avoiding concurrent configuration.

### Direct microphone investigation, 2026-09-28 evening

The owner continued to report no wake response. The active detector was changed
to the built-in `alexa` model for diagnosis (Mira's identity/faces are unchanged).
`live_voice.py` now preserves an existing device-selected wake configuration across
reconnection rather than forcibly restoring `hey_mira`; the installed app was
backed up and updated. 24 UI/voice tests passed. The device log measured Alexa
at 50 frames/s, 5.7 ms/frame and 28% processing budget, versus Mira's roughly
15.4 ms and 77%. This measures processing, not spoken recall.

A five-second direct ALSA diagnostic, with daemon hold and automatic cleanup,
measured all seven microphone channels: peaks -37.9 to -33.6 dBFS and RMS -56.8
to -53.9 dBFS. Both playback reference channels were silent as expected. No raw
audio file was saved. The daemon resumed as PID 7648. These are ambient levels,
not a calibrated speech test and not proof of good intelligibility.

The microphone mixing mode was changed from `All microphones` to `Beamformer`,
with state readback, to test directional capture. Active wake remained `alexa`.
Owner-spoken outcome is pending; revert mixing to `All microphones` if it worsens
capture. Firmware remains v0.5.39; no bootloader or signed firmware change was
made in this investigation. The device advertises v0.5.41, whose migration and
preservation of the experimental client are not yet reviewed.

The owner subsequently confirmed the ring lit after saying Alexa. The matching
device log recorded `wake detected id=alexa`, peak 0.602, zero dropped frames.
Desktop state advanced activating → listening and received 463872 microphone
bytes (peak 6943). The turn timed out after 15 seconds with no recognized text
or reply audio. The prompt had requested only the wake word, so this proves
owner-spoken wake and transport, not a complete question/answer. Keep Alexa and
Beamformer in place while testing a spoken question; do not restore the failed
Mira model on reconnect.

The owner then confirmed Alexa both replies and controls devices normally. This
is the first explicit successful owner-spoken end-to-end report for the current
Beamformer configuration. To evaluate Mira without removing that working path,
active models are now `[alexa, hey_mira]`; slot 2 has threshold 0.30, streamed
reply delivery and 20-second follow-up, all read back through the device API.
The existing model targets the complete English phrase `Hey Mira`, not bare
Arabic `ميرا`. Its owner-spoken test under the new microphone mode is pending.

## Arabic Mira wake breakthrough (2026-09-28 evening)

The old model failed the owner's dual-wake test and was deselected. A private
15-second Echo sample was captured with permission and analyzed locally only.
The old classifier peaked at .0023. A new synthetic Arabic model, trained without
the owner recording, peaked at .9357 on that held-out clip. See `wake_training/`
for reproducible source, limitations and public dataset licensing.

The new model is installed as `mira_ar_experimental` alongside Alexa. The owner
confirmed saying Mira lights the ring and gets a reply. Device logs independently
show two new-model detections followed by 6.28s and 4.85s streamed replies, zero
underruns. Live readback: Beamformer, slot-2 configured threshold .70, streamed
delivery, active `[alexa, mira_ar_experimental]`. Detector logs used cutoff .60
for those turns; configured and effective thresholds must not be conflated.
This is real end-to-end wake evidence, not all-pronunciation or false-wake proof.
No firmware upgrade, boot persistence proof or PC-off home-control proof is implied.

## Voice agent and taught memory (2026-09-28)

Desktop Gemini voice now exposes `moai_project_task`, delegating the owner's
request to the existing Hermes gateway/session, with Mo AI remaining the approval
and execution authority. It does not add a root shell or treat an agent's prose
as verified execution. A real read-only gateway request returned registered
project MoOS; system status returned ok. Home summary measured 4 available and
4 unavailable individual lights, with two groups counted separately.

`remember_owner_fact` appends explicit owner-taught information to the existing
private editable profile without replacing it; duplicate lines are ignored and
length is bounded. Existing conversation persistence is retained. This is stored
knowledge, not autonomous model training or automatic source self-modification.
34 UI/voice/memory tests passed; both changed files were backed up and installed,
and the desktop returned to ready. End-to-end spoken project-tool invocation and
YouTube playback have not yet been verified. The on-device standalone client does
not inherit these desktop tools.

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
