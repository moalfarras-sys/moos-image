# Shared application-update unit bases

The native ARM bootc base does not supply the two service/timer pairs that the
x86 base supplies. Drop-ins alone do not create units. The shared overlay now
owns both complete service/timer pairs under `system_files/usr/lib/systemd`,
and both builders enable the same system and global-user timers. Shared drop-ins own
the delayed schedule, idle CPU/I/O priority and resilient updater. There is no
second updater or package installation path.

The allowed NetworkManager metered states (2 and 4) and initial timer policy
follow the reviewed [upstream update units](https://github.com/ublue-os/packages/tree/e8141a5a883da1705adb70f8487ff7560077353f/packages/ublue-os-update-services/src/usr/lib/systemd).
The MoOS condition bounds its read to five seconds and refuses failed or
malformed replies. Mo Store's existing automatic-update choice and job lock
remain in the shared user updater. OS-image updates retain their separate
signature-enforcing authority.

`verify_app_updates.py` checks the finished units, providers, effective drop-ins
and actual enablement links in both image builds. Portable tests execute real
private-root `systemctl enable` commands and reject the old missing-unit tree,
missing/wrong wants, missing providers, lost calendar/idle policy and boot
catch-up. Native timer firing and installed-machine repair have separate audit
receipts; they do not qualify a signed image.
