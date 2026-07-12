# Mo PC Remote integration with MoOS

## Shipped paths

- `/usr/bin/mo-pc-remote` — native GTK control center.
- `/usr/share/applications/org.moos.remote.desktop` — system launcher.
- `/usr/lib/mo-remote/` — legacy diagnostic agent built reproducibly from `moremote/`.
- `/usr/lib/systemd/user/mo-remote-personal.service` — opt-in user service.
- `/usr/lib/systemd/user/ydotoold-moremote.service` and `70-mo-remote-uinput.rules` — active-user-only fallback input.

`Containerfile` builds the legacy .NET source in a dedicated SDK stage. `build_files/build.sh` installs runtime dependencies, makes the native UI executable, and explicitly disables legacy auto-start. The launcher and `moos://app/remote` both open the native UI.

## Remaining production integration

Package Sunshine from a pinned, verifiable source in the image build; do not curl an unversioned binary. Add a dedicated firewalld service, KWin capture configuration, Moonlight QR/deep link, paired-client management and notification integration. Then build both generic and NVIDIA image variants and execute the ISO/disk test matrix.
