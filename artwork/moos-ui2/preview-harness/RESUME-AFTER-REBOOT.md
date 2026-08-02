# Continuation — design campaign, after the THIRD reboot (2026-08-02 ~14:58Z)

Booting into `44.20260802.513` (`ee4a24e2…`, cosign-verified) = head `b260174b`,
which carries THE root fix: Complementary is now the dark session surface on
every palette (light schemes borrow the dark sibling wholesale), plus the
on_negative extraction fix in moos_ui2.py. This is the build where the Glass
Islands finally RENDER as designed on light themes.

The Stop-hook goal remains open until, in order:

1. Confirm booted digest == ee4a24e2; `post-update-check.sh` (expect 49/0).
2. LIVE captures from the real session (env: XDG_RUNTIME_DIR=/run/user/1000,
   WAYLAND_DISPLAY=wayland-0, DBUS session bus, YDOTOOL_SOCKET):
   - Lock (Scholar Light active): `timeout 16 /usr/libexec/kscreenlocker_greet
     --testing` + `ydotool key 42:1 42:0` after 6s + spectacle capture.
     EXPECT: dark warm island with amber accents; tiles with captions inside.
   - Power doorway from INSTALLED /usr packages via
     `artwork/moos-ui2/preview-harness/make-preview.sh /usr/share/plasma/
     look-and-feel/org.moos.ui2.study.light 1 <out> 4` — NOTE the harness
     scheme arg does NOT actually apply schemes (qml-qt6 limitation, documented
     in PROJECT_STATE); colour truth for the doorway comes from the LIVE
     ksmserver path or from scheme-file values + the lock render (same
     Complementary set). Geometry/material still verifiable via harness.
   - RTL variant (add `rtl` arg), a dark-palette lock if quick (switch scheme
     back after!). Do NOT open the real logout prompt unattended (countdown
     fires real shutdown).
3. Judge as CDO vs the WOW bar; iterate immediately if any surface reads pale.
4. Final PROJECT_STATE entry (513 boot + evidence) — commit + push docs batch
   (includes any new captures).
5. Final bilingual report + WhatsApp summary to owner: what changed, evidence
   paths, and that the DESKTOP (moos-nvidia) gets the same at its next update
   (`moos-update` or automatic staging + reboot).
6. Still pending: owner re-enters Telegram bot token (task #7).
