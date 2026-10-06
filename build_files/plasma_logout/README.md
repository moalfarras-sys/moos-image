# Native logout transaction correction

The signed NVIDIA `.999` guest on Plasma 6.7.5 reproduced an ordinary logout
failure immediately after login. Three ordinary logout/login cycles after the
appearance migration settled passed. During the early failure the user manager
reported `TransactionIsDestructive`: stopping `graphical-session.target` with
job mode `fail` conflicted with the pending start of `moos-theme-sync.service`.
The upstream shutdown worker ignored that error and exited while KSMServer
remained in Quitting. The desktop session stayed active for over 120 seconds.

`logout-transaction.patch` changes only the final systemd stop transaction,
after upstream's session saving, application close prompts and KWin window
closing have completed. Job mode `replace` supersedes overlapping startup jobs,
as a normal `systemctl stop` does. If the call still fails, the worker logs the
actual error and uses upstream's `resetLogout` and cancellation path so that
the user can retry. It does not change authentication, inhibitors, application
prompts, login policy, branding or any QML seam.

Both architectures rebuild the exact vendor `plasma-workspace-6.7.5-1.fc44`
source RPM with its original spec, flags and vendor patches. The one added patch
and higher release `1.1.moos1` stay visible to RPM. The installer refuses every
unreviewed base NVR and replaces only subpackages the edition already owns;
`libkworkspace6` and `plasma-workspace-common` move with the main package and its libraries. The vendor's
theme/doc outputs stay in the SDK manifest; an already-owned theme is replaced
before the existing final identity scrub, never added implicitly or named in
the runtime receipt.
The final gate compares the worker with both the install receipt and the RPM
database's payload digest. No compiler or devel package enters the runtime.
The x86 package transaction precedes the authoritative `system_files` copy;
ARM already reapplies that overlay after package installation. Both exclude
kernel packages and preserve the base-kernel/initramfs gates. A local image's
identity gate caught the incorrect original order when workspace-common
restored the upstream session-picker name; the gate was preserved.
Review a new upstream NVR explicitly. When upstream fixes the transaction,
remove this rebuild and its package helper after proving the ordinary journeys
on that exact upstream package; never force a later upstream back to this NVR.

Primary sources: [upstream shutdown worker, v6.7.5](https://github.com/KDE/plasma-workspace/blob/v6.7.5/startkde/plasma-shutdown/shutdown.cpp),
[systemd manager job modes](https://www.freedesktop.org/software/systemd/man/latest/org.freedesktop.systemd1.html).
Private native evidence is in the session audit worktree's ignored
`test-results/session-audit-20261006/`: early-failure journal, settled three-cycle
acceptance and a real systemd transaction negative control. The source-bound worker passed three early guest cycles; restoring the vendor
worker reproduced the failure. The exact rebuilt RPM worker passes native
old/fixed/rejected-stop/window-cancel cases on private D-Bus instances. The
proof stage installs dbus-daemon explicitly on both architectures; ARM exposed
its absence from the bootc SDK. Signed delivery and physical logout remain open.
