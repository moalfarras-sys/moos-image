# Continuation — design campaign, post-reboot (written seconds before the 2nd reboot, 2026-08-02 ~14:20Z)

The host is rebooting into `44.20260802.512` (`23254c54…`, cosign-verified) which
carries ALL design slices (7aaa5625 power island, b43dcea1 lock/login, 718b231b
theme reconcile). The Stop-hook goal is NOT met yet. Remaining, in order:

1. `post-update-check.sh` on the new deployment (expect 49/0; the check is
   edition-aware now).
2. LIVE captures from the INSTALLED image (not the repo tree):
   - lock: `kscreenlocker_greet --testing` (+ ydotool key to wake the island),
     Light(Scholar) + a dark palette, LTR + RTL if reachable.
   - power doorway: `artwork/moos-ui2/preview-harness/make-preview.sh
     /usr/share/plasma/look-and-feel/<pkg> <sdtype> <out> 4 <scheme> [rtl]`.
   - splash already captured (splash-current.png, untracked — commit it).
3. Judge the live result AS CDO against the "wow" bar; iterate if any surface
   reads cheap (the hook demands first-glance difference).
4. The PROJECT_STATE entry for the theme-reconcile commit 718b231b was NEVER
   written (a failed string match) — write it with the final evidence batch.
5. Final docs commit + push (one CI run), final bilingual report + WhatsApp.
6. Still pending elsewhere: owner must re-enter the Telegram bot token
   (task #7); desktop machine updates itself to the new image (owner reboots).

Preview harness knows: scheme arg (MoOSUI2Dark/MoOSUI2ScholarLight/…), rtl arg,
needs XDG_RUNTIME_DIR/WAYLAND_DISPLAY/DBUS_SESSION_BUS_ADDRESS of the session.
