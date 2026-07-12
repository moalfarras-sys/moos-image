# Mo PC Remote architecture

```text
Native GTK control center
  ├─ systemd user lifecycle and diagnostics
  ├─ trusted-device/pairing status (Sunshine API, planned)
  ├─ QR for Moonlight endpoint (planned)
  └─ firewall/PipeWire/input health

Sunshine user process (selected production stream)
  ├─ KWin Wayland capture → PipeWire/KPipeWire path
  ├─ H.264 / HEVC / AV1 encoder selection
  ├─ encrypted Moonlight pairing and session
  └─ uinput access only for active local user

Moonlight Android/iOS
  └─ video, audio, touch/mouse, keyboard, gamepad

KDE Connect (optional companion)
  └─ media, volume, commands and remote-input fallback
```

The management UI never embeds the remote desktop and never launches a browser. Streaming is opt-in and user-session scoped. Service activation must not block boot.
