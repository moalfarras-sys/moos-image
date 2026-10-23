# Native session continuity — 2026-10-23

The owner requests one coherent MoOS interface across the launcher, login,
lock and power screens. This batch improves those existing native surfaces;
the owner's rejection of earlier small changes as a complete UI remains valid.
The accepted Island-caption fix is separate from whole-interface acceptance.

The physical V3 still boots signed1097, retaining1090 and pinned1078. Its DP-12
output remains3840×2160 at250%,1536×864 logical. KWin, Remote, PipeWire and the
portal remain the same owners. Private captures stay local.

## Native destination and common appearance

The actual6.8.1 power greeter loads the shell's `contents/logout/LogoutControls.qml`.
The former look-and-feel implementation was not that destination: the installed
baseline displayed stock black power controls. The native file hash is
`6ed15b0ea18d118e8862ad0fd01038ab62afc41d96946fff2075dfd8f656d201`, matching
the [exact upstream file](https://invent.kde.org/plasma/plasma-desktop/-/blob/v6.8.1/desktoppackage/contents/logout/LogoutControls.qml).
The [C++ owner](https://invent.kde.org/plasma/plasma-workspace/-/blob/Plasma/6.8/logout-greeter/main.cpp)
loads a Plasma/Shell package. Only the visual controls are adapted. Its native
root, timer module, single shared output owner, capability context and C++ action
signals remain authoritative. The registry adds this seam only to the reviewed
6.8.1 set; older sets keep12 seams and unknown versions/digests still refuse.

One generator derives the native view and all18 legacy theme siblings from
the canonical power design. The card uses the same GlassSurface as login/lock.
All known desktop/login/power wallpaper packages use one profile map. This
fixes Bloom login resolving a nonexistent3840×2160 JPEG instead of its actual
1672×941 PNG. The active look is read through QtCore Settings.location, without
writing settings. The first fileName attempt's errors/fallback are preserved.

Captions include complete update/restart/shutdown words and a clear return to
desktop.44px targets, inner caption ink, card bounds and confirmation text are
checked independently. Native navigation cancels the countdown; held Enter
cannot confirm a sensitive action twice. Hidden/reduced motion settles.

## Launcher and installed-session evidence

The existing launcher has corrected Arabic favourites text, clearer session
labels, readable secondary ink and a finite page transition. Unmeasured privacy
and trust badges are removed. The existing Kicker and session executors remain.
Four native source popup cases exercise mouse, keyboard, Qt touch, categories,
rapid page transitions and reduced/hidden settling, with broken controls.

One exact owned user-local LauncherView.qml changes from
`ae6f6dcff8614224882aa6cf224ec48430fe5be04cc0bc6e1eb085548679050b` to
`209b95b104afb3c3ef33bb4a84b069e26823bf9fecf3780a8161841b0d9e485d`.
Only Plasma reloads897244→1039530. A guarded actual Home-page click renders
the corrected favourites screen. The backup and exact retirement manifest
remain private; this file is a compatibility preview, not signed delivery.

Actual installed `ksmserver-logout-greeter --windowed` uses a scoped source
module/private complete shell. Final positive1042367 and restored1043178 load
the correct BloomLight image with zero scoped QML errors; broken1043149 refuses
the missing type. A guarded real Cancel pointer closes1042367 with exit0.
The final view hash is
`34583fe4e677469e22b5b4705fb560c5af71227b7ce2e6474f2876f78ddd570b`.
No shutdown, reboot, logout or suspend action is fired on the owner's session.
Private native Qt tests cover24 positive profile/size/language/motion cases and
wrong-setting/wrong-forwarded-destination negatives, including actual loaded
wallpaper pixels, caption ink,44px controls and production input callbacks.
The initial34/41px Cancel failures are preserved before the44px correction.

The real login KCM's synchronization dialog confirms palette, fonts, cursor,
Plasma style and display/locale/input settings are native shared settings.
It is cancelled without applying: the currently selected Bloom package must
exist globally in the signed image before the greeter account can use it.
Wallpaper selection remains its separate native appearance destination.

## Qualification and remaining acceptance

The131 checkpoint passes native `just check`0/817.171s and the complete generic
image0/770.130s, with unchanged source snapshots. Independent470-file,
106-embedded-source/7-module readback has zero mismatches on
`sha256:8742621243356db2b6a81ec0b46b8a9897c0587b0b55ef29ec9bf84fca5948c6`.
Its actual in-image power gate passes both Bloom halves at motion0/1 and refuses
the deliberate missing-type adapter. This qualifies131, not the later changes.

The owner still asks for more colour and specifically requires that colour to
follow the selected theme.132 therefore shares SessionActionGlyph across actual
login/lock controls and power tiles: opaque selected-theme accent/paired ink and
the scheme's negative-role shutdown. It preserves native button input owners.
One24px Qt scene-blur token retains more wallpaper colour/contours; KWin's
distinct15 ceiling stays intact. Extra hard halo plates are removed from both
login/lock variants so the shared GlassSurface owns the card depth.

The native test matrix now executes42 positives:24 power/profile/size cases
and18 actual native login/lock button cases, including AR/EN/DE captions,
44px targets, production pointer/keyboard callbacks and actual glyph ink/fill
contrast at least4.5. Four completed negatives cover wrong theme property,
wrong native destination and wrong glyph ink in both control owners.
Actual vivid power1131267 renders and closes0 through guarded Cancel.
Actual native lock test client1137371 renders the matched BloomLight scene,
clean card and source glyph at1536×864; import traces verify the exact private
SessionManagementScreen/ActionButton and source SessionActionGlyph paths, with
zero scoped QML errors. No credentials or actual owner-session lock are used.

Actual native login test client1133473 resolves the same source components and
paints its password card/coloured action after guarded cover activation. Its
standalone test scene is gray without the separate compositor-owned wallpaper,
and qrc GreeterState reports an undefined LoginState. A matched installed-module
baseline reproduces that warning with no missing style/icons; it is preserved,
not assigned to the new visual code or patched in authentication. Full login
appearance/authentication remains unaccepted. The first mixed data-path baseline
is retained separately. An initial lock probe also discards caller QML_IMPORT_PATH
and loads/usr: its green result is explicitly rejected as source acceptance.
The later explicit native test-client trace/pixels, not that marker, qualify the
scoped lock component. The13-file573901-byte initial private module manifest
records every installed/review hash and its later clean-card revision.

THEME_REV132 freezes the owner-directed assets;130 was private preparation.
Both image
builders load the actual native power greeter under private HOME/XDG and absent
session/system buses, including the broken-adapter negative. Authentication,
identity, image-state, signature and boot gates are retained.

Final full-check/image/readback and exact-head remote results are recorded in
the companion qualification receipt when complete. Cold login/lock/theme sync,
actual power operations, physical touch/scale, screen reader, phone and endurance
remain open. The existing greeter screenRemoved crash and Android window defects
are separate unresolved work. The66-file user-local native shell preview must
retire only after exact signed delivery: it can otherwise shadow the new power
adapter. No new immutable host files, display settings or authentication policies
are changed during this preview.

The final132 native check completes0/824.844s and the full generic image
completes0/612.123s on identical unchanged75-file source snapshots. Independent
473-file/106-resource/7-module readback has zero mismatches on image
`sha256:61eff6075a6298815dc9ef67e2d66f357e46bef3173f8e932fbe04936ecb9fe5`.
See the [qualification receipt](2026-10-23-session-qualified-proof.json).

After the owner reboots, the source75-file snapshot still matches exactly and
both complete gate receipts remain intact. The workstation still boots1097,
not132, with signed1090/pinned1078 recovery, no staged deployment or failed units.
Its actual display is now eDP-1,2560×1600@145%,1766×1104 logical. Login logs
explicitly quarantine brand/Island source shadows at23:24:03UTC and repair
Graphite. The native132 shared module is absent from immutable/usr. The visual
reversion is retained as failed delivery continuity; it is not erased source.
Restore only manifested compatibility bytes for current review, then retire
them after exact signed global delivery. Do not disable that safety reconciler.
