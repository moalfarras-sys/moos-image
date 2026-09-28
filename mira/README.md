# Mira Neural OS — MoOS source

This directory contains the owner's current desktop Mira application and its two
existing faces (`rose` and `holo`). The source was imported from the live user
installation without replacing MoOS's desktop or Mo AI. It is **not yet** an
OS-image package or a signed release.

## Measured on the owner's station, 2026-09-28

- The installed app starts, pairs to the Echo, and reaches voice `ready`.
- The microphone **button** previously produced a spoken Echo reply. Hands-free
  activation by saying Mira is **not proven**. The local PC-microphone listener
  captures frames and a wake request appeared in logs, but the owner did not see
  the ring respond to the latest test. Do not describe it as working until an
  owner-spoken test passes without a button.
- Home Assistant returned current devices. A real available lamp was turned on,
  changed to pink, then returned to its original off state; all three state
  readbacks were `ok`. Two TVs were `unavailable`, so their controls stay disabled.
- Mo AI's pinned Hermes runtime was installed for this user, and the `MoOS`
  project was registered with the owner's explicit consent to cloud project
  analysis. The `projects` tool was observed in the agent event log; Mira's text
  route returned `MoOS` through the `hermes` gateway. Mutating agent tools still
  require Mo AI's one-time approval.
- Chat/profile data remain in private files under `~/.config/mo-dot/`.

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
QT_QPA_PLATFORM=offscreen python -m unittest \
  test_ui_routes test_group_lights test_mira_memory test_moai_agent_link -q
```

These checks exercise routes with mocked services; they do not qualify the
microphone, Echo, Home Assistant or a signed OS image.
