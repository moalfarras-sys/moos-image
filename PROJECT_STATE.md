# MoOS current state — measured 2026-10-06

**Oracle A1, 2026-10-06:** booted signed `.710` (`a2ee890d…`, source `66653f76`), `.696` rollback. Installed selfcheck 51/0 and post-update 55/0; no failed units/kernel errors. Private FileBrowser/code-server/rootless Immich 3.2.4 and SMB3 provide files/code/photos; original upload/download, thumbnails/video and encrypted configuration/catalog restore pass.
Packaged Tailscale 1.102.5 now owns the daemon; its stale `/etc` executable shadow was retired. Phone background upload and off-host originals backup remain unproven; `oomd` still monitors nothing. Host profile/evidence: [Oracle cloud workstation](docs/ORACLE_CLOUD_WORKSTATION.md), P5.5/P5.7.

**Session-return audit, 2026-10-06:** station boots signed NVIDIA `.999` (`b5c4d84f…`, source `a803a075`); signed `.989` rollback verified. All 100 refs reviewed before the new correction are integrated; the 21 worktrees were clean and a verified 577 MiB Git bundle is retained. The owner confirmed full logout then login with the same account. The September development autologin drop-in was retired with native administrator authentication into `/etc/moos/development-backups/session-return-20261006/`, outside PLM's parsed directories; the active owner session is untouched and the setting takes effect after reboot. Physical logout/return acceptance remains open. After the owner reported no update dialog, the native Polkit agent was restarted with no pending privilege requests (screen connected; earlier no-output logs); it runs with zero automatic restarts, but new prompt visibility is unproven.

PR #209 merged at `66653f76`; signed NVIDIA `.1003` (`33a4cc91…`) is promoted: x86 build `37436965002`, generic/NVIDIA/cloud QCOW2 `37441298335`/`37441303180`/`37441307859`, ISO `37441312322`, promotion `37445784220`, ARM build/boot/promotion `37436934386`, all first-attempt success. Production revision/version/signature were independently read back. The unstarted `.1003` authentication prompt was cancelled before its update worker ran because the native correction needs a newer release; `.1003` is not staged or booted. Source diagnostic **54/0**, installed post-update **55/0**, full `just check`, .NET, controller and local NVIDIA image gates passed for #209. The source-map-js lock-only 1.2.2 correction has zero audit findings and identical shipped frontend bytes.

**Open native logout correction:** a SHA-256-verified exact `.999` artifact passed three settled ordinary password-login/logout cycles without reboot. Two early full-logout attempts stayed active: upstream `plasma-shutdown` discarded `TransactionIsDestructive` when stopping the graphical target in `fail` mode conflicted with a pending MoOS theme-sync start. A private real-systemd negative control reproduces rejection with `fail` and stops both units with `replace`. The compiled source worker, temporarily bound only in the guest, passed three early cycles with observer UID1001; restoring the original worker reproduced the same failure. KWrite’s actual save prompt preserved its exact UTF-8 file and completed logout; cancelling the power prompt kept the unsaved editor. Native old/fixed/error/cancellation worker cases and 18 package fixtures pass; full maintained repo gates pass. Final local NVIDIA `e9518537c5d0` passes every image gate and lint (13 pass, one skip, existing nonempty-boot warning); readback confirms fixed core NVR/worker `44a00a19…`, MoOS picker and activation. PR #211 merged as `ef8ec7ea`; final-head repo `37487257957`, x86 `37487257903` and ARM `37487257919` image gates pass. PR boot/promotion jobs were skipped, and both advisory heads failed internally despite green. Signed candidate `37496769111` failed before image build on newly published Sharp GHSA-wq5f-xc86-pv6w; its early ARM build was cancelled before boot proof. Sharp 0.35.5 / prebuilt librsvg 2.63.2 now has zero audit findings; controller type/unit/production-browser and every .NET project pass, with byte-identical shipped frontend; final full maintained repo gates pass. This patch is source evidence pending CI, a new signed cycle and physical acceptance. The identity gate caught vendor workspace-common replacing the session name: x86 installation now precedes the MoOS overlay; kernel exclusions stay explicit. ARM SDK proof lacked dbus-run-session; both proof stages now install dbus-daemon explicitly. Health fixtures now isolate statvfs (20 cases, including 90/97% warnings), after builds exposed live-disk leakage; production checks are unchanged. The topic retains the full vendor spec/patches and corrects only the final transaction/error recovery. No authentication or theme redesign. Three retired Remote selectors now resolve to signed image bytes, zero restarts; Store/system app and firmware checks completed (no firmware update available). Inaccessible Claude link supplied no specification/approval. Private evidence: audit worktree `test-results/session-audit-20261006/`.

**Session design released, 2026-10-06 (P2.16):** PR #207 merged at `a803a075` on the owner's explicit decision; `scripts/release-candidate.sh --promote` from the station signed `moos` `57aca4e3…`, `moos-nvidia` `b5c4d84f…`, `moos-cloud` `09b47b00…`, passed the generic, NVIDIA and cloud QCOW2 boots, the ISO proof and the ARM pipeline (first attempt), and promotion run 37394260892 succeeded. The station resolved `moai-do update` to the NVIDIA digest; staging was waiting on the administrator prompt when this was written, so the booted system was still `.989` with `.997` staged. Apps were up to date (`moai-do update-apps`). Earlier history of this work, written before the merge: the owner sent three screenshots — the lock clock drawn under the password card, the brand mark on the card's rim, a bare login screen. Reproduced from the tree at 640×480 and, for the rim, at the station's own 1536×864. Cause: the lock screen was a fork of `LockScreenUi.qml`/`MainBlock.qml` with a card sized from outside and a second, corner-pinned clock; the login screen, compiled, could have neither. Now the lock, login and power screens share one clock, one face, one signature and one island drawn by the breeze components (`SessionManagementScreen`, `WallpaperFader`, `Clock`, `UserList`, `UserDelegate`); MoOS forks no file that authenticates, the two lock-screen forks and their three 6.8 variants are deleted, and `build.sh`/`build-arm.sh` refuse a MoOS copy at either path. `THEME_REV` 101 purges the cached compile of the retired fork; the greeter account's QML cache, which no purge ever reached, is cleared at boot. **Measured:** the three real greeter binaries rendered from the tree under Xvfb (software GL) on Plasma 6.7.5 at 640×480, 1024×600, 1280×720, 1536×864 and 3840×2160@2.5, Arabic/English/German, idle/active/typed/refused, all sixteen families; `probe-lockscreen` passes and its negative control fails on 6.7.5 and on a real Plasma 6.7.91 stack with the 6.8 variants; full `just check` passes. **Local image, same day:** the generic x86 image built from `8b57a788` (`localhost/moos:session-design-20261005`, the later commits on the branch touch only the review harness and documents) with every in-image gate: seam set 6.7, twelve seams matching their reviewed upstream bytes, the real greeter loading the lock screen, the image-experience, motion, identity and image-state gates, seven Settings modules loaded, lint with the one existing `nonempty-boot` warning. Read back from the image, not the source: `LockScreenUi.qml` and `MainBlock.qml` carry upstream's digests (`32850178…`, `ca4116aa…`), the six components are MoOS's, the greeter tmpfiles file has the cache rule, `THEME_REV` is 101; and the image's own files, with an X server added, render the same lock, login and power screens. **Not measured:** the installed lock screen on the NVIDIA GPU with KWin blur, a real login (this station autologs in), the power screen with a power backend (the harness has none, so it shows two of the six tiles), the two new Appearance rows as pixels (the module loads), Orca, the NVIDIA/cloud/ARM editions, a boot. Nothing is installed: the station still runs the old lock screen. **Second pass, same day, after the owner called the first one ordinary:** one `Tokens.sessionScale` sizes the whole family from the window (0.6–1.6; 1.0 at 1536×864, 1.25 at 1080p); the clock has a cover pose and a working pose and moves between them; the island arrives as a wave; the selected face stands in a two-tone ring a hair's width off the picture; a light orbits the island's rim and the frame a counted number of turns (twice on arrival, once per typed character) and docks; the key is glass until its field holds something. **Measured live on the station's session and GPU** (`kscreenlocker_greet --testing` from the worktree through a private import path, the owner's real account photo, media strip and Sleep/Switch User keys): 0.3% of a core as a cover, 6.5% while the orbit turns, 0.0% docked and back as a cover; no QML error in the journal. The real greeter probe passes and its negative control fails on 6.7.5 and 6.7.91 with this pass. The image was NOT rebuilt for the second pass (no Tier 1 file changed); PR CI builds it.

**One Remote review, 2026-10-05:** v55 keeps the real picture visible while typing and permits bounded Auto detail trials on a healthy direct or relay link. Native KWin EIS input is independent of PipeWire capture; a production browser drove private KWin click/text during capture failure. Tight sensitive key batches lost uppercase in the real greeter; prompt preparation and 40 ms sensitive key edges passed five consecutive ordinary password unlocks beyond the grace interval in a disposable signed-base guest, while a wrong password stayed locked. Real GTK typing and decoded video were proven. Only `org.moos.remote` was granted for the owner's unattended-access request. The backed-up station review is app-level over signed `.989`; owner iPhone acceptance, WAN endurance, display/portal loss cause and final signed delivery remain open. See `moremote/ONE_REMOTE.md`.

**Phone control follow-up, 2026-10-05:** the owner's 12:46–12:48 v51 iPhone trial still failed. Direct commands through the live approved portal moved KWin's actual pointer to 384/216 and 1151/518 and restored 1254/577; this proves that channel, not phone control. Source v52 accepts finger taps/drags even in saved desktop mode while preserving real mouse input and suppressing compatibility duplicates. Production-bundle Chromium, controller checks and full `just check` pass; old gesture/bundle controls fail. A 0×0 GDK placeholder now waits for valid geometry instead of scheduling an extra renewal; old helper fails its private control. DDC was already disabled by the installed hardware-adaptation drop-in; the redundant temporary flag was removed. Three HDMI disconnects still occurred in 65 s. Physical HDMI cause, a new phone trial and signed delivery remain open.

**Remote + Island correction, 2026-10-05:** the owner's v51 phone trials still show output loss and failed control. HDMI loss remains measured; HTTP and zero service restarts do not prove phone control. New source uses KScreen's logical fallback extent (1536×864, not assumed 1920×1080), reacquires the fallback pointer after portal motion/resizing and before a tap after external mouse motion, and gives fallback capture the same embedded-cursor choice as the portal. Unknown extent never clicks a guessed point. Private input/core/.NET suites and full `just check` pass; the old injector fails the portal→fallback position control.
The owner's vertically broken Island tabs reproduce on native Qt: invisible tabs still reserve default width and Arabic wraps. `THEME_REV` 100 sizes tabs by their single-line text, gives hidden tabs zero width and bounds the strip to 44 px. Eight native AR/EN light/dark two/five-domain renders and real tab clicks pass; old code fails at 140–192 px. This is component evidence, not a whole signed-desktop proof.
Local `v51-pointer4` review activated at 09:37 CEST, via the backed-up `55-mobile-recovery-review.conf`; only managed DLL/PDB and v51 frontend differ from signed `.989` runtime. A new home Island package has exact reviewed bytes; plasmashell restarted successfully. Remove that package and restore the saved selector to return to the preceding review. No OS origin/update/reboot change. Fresh native consent was accepted; KWin witnessed the consent pointer moving exactly −492/+136 logical pixels. New phone interaction/soak and signed delivery remain open.

**Oracle A1, 2026-10-05, after the owner's reboot:** booted signed `44.20261004.694` (`sha256:09878407…`, source `3b00e90b`), kernel `7.2.8`, `.638` kept for rollback; graphical target 9.1 s. The one-time acceptance capture (`~/.local/state/moos/release-acceptance-20261005/post-reboot.txt`) and a session read: 0 failed system/user units, `moos-selfcheck` 51 passed, `post-update-check.sh` 55/0, no core dumps or errors this boot. The desktop is 1280×720 and Auto sends it 1:1; the screenshot shows the MoOS dock whole. Installed-byte proofs: the installed helper equals the tested source, and in the compositor rig it encodes 29.8 frames/s at 27% of a core for fps=30 and 15.0/s at 14% for fps=15 (the old limiter: 47/s, 42%); `pipewire` is 16 MiB with no orphaned clients; the privacy monitor runs one feed and used 0.2 s of CPU in its first minutes; the installed Mira, offscreen against a copy of the chat that reached 8.9 GiB, held 207 MiB at 0% for 30 s. The EFI partition had carried a FAT dirty flag on every boot since at least 2026-09-28 (no other damage in a read-only check); it was cleared after a full raw backup, and all 9 boot files are byte-identical. Not fixed, measured: `kded6` ignores SIGTERM at every shutdown and is aborted after Plasma's own 5 s stop timeout (3 of 3 boots); Plasma's GTK bridge paints the GTK window buttons into empty images because it reads Aurorae themes only from `~/.local/share` (not imported by MoOS's `gtk.css`, so nothing on screen; ~230 log lines a login). Open on the phone: H.264 give-ups, below.
**Download readiness audit, 2026-10-05 (latest release readback; supersedes the older production snapshot):** all 86 pre-existing local/remote refs were ancestors of `origin/main` (`3b00e90b`), all 18 pre-existing worktrees clean; no unique branch work was lost or discarded. A verified Git bundle preserves every ref. Exact-SHA x86 `44.20261004.989` passed signed build `37237691599`, generic/NVIDIA/cloud QCOW2 `37241864883`/`37241867108`/`37241869276`, offline ISO/install `37241871439`, and promotion `37244560572`; ARM `.694` passed build/boot/promotion `37237676136`. All four OCI signatures and revisions were independently verified. The 5,786,763,264-byte final ISO is archived under `/var/home/moos/moos-releases/44.20261004.989/x86-iso/`; its detached signature and SHA-256 match the CI's final installed-system proof. Streaming verification peaked at 24 MiB, without loading the ISO into RAM. The ARM QCOW2 archive and decompressed hash match its boot proof. `just check` passes all 231 suites, including 15 delivery/crypto cases. Native Arabic design-reference frames were inspected in light/dark; these are not whole installed-desktop acceptance. Station remains signed NVIDIA `.977` with signed `.975` rollback: the owner-authorized `.989` update reached `pkexec`, but no staged deployment was observed; authentication/reboot and corrective home-shadow retirement remain owed. Retain the home overrides meanwhile (baseline selfcheck: 51 passed, 3 notes, 2 broken). Public ISO endpoint remains HTTP 503; shell installers returning HTTP 200 are not ISO downloads. Website files remain with its agent. Exact artifacts, edition digests, proofs and unresolved hosting: `docs/releases/2026-10-05-download-handoff.md`, P0.12.

**Physical station update, 2026-10-05, before reboot:** owner explicitly authorized full update and reboot. Native `moai-do update` completed successfully; signed NVIDIA `.989` (`025ea94d…`, source `3b00e90b`) is staged over booted `.977`, with `.975` also retained. The exact staged and current rollback signatures were reverified. User and system Flatpak update/repair completed with exit 0; system app `cn.navclub.ldbfx` and its GNOME 42 runtime are publisher-declared EOL, not repaired by an update, and were retained with owner data. Firmware metadata refreshed; the successful JSON query offered zero device updates. Fresh `just check` passed all 231 suites. Five documented corrective home shadows are snapshotted in private `~/.local/state/moos/release-acceptance-20261005/`; the one-time `owner-moos-989-migrate.service` may retire only their exact saved bytes after matching the booted signed `.989` digest/version/key, before the graphical session. Its old-image negative guard and systemd unit validation pass. A two-minute post-login timer captures maintained selfcheck/post-update, GPU/audio/network/Bluetooth/kernel evidence and disables itself. These are local acceptance helpers, not OS-image changes; autostart choices and provider settings are untouched. Post-reboot results, visual boot, physical audio/lamps, pairing and suspend remain unproven until observed. Baseline failed units are historical drkonqi processors; preserve their evidence, never reset them to make the audit green.

**Home/control corrective audit, 2026-10-03:** branch
`fix/mira-lighting-control-20261003` fixes lost Hue Entertainment regions,
Echo effects overriding screen colour, black frames leaving lamps orange, stale
PC streaming state and failed portals reporting running. Adds explicit screen
selection and available/total counts; Tuya sync is limited to one update per 2 s.
Real installed-executor volume 100→99→100 passed. Tuya wall light, Hue Büro and
Echo blue/45% read back; four PC headers acknowledged commands (physical colour
still needs observation). Owner pressed Hue's button: pairing succeeded and a
real DTLS Entertainment session sent frames alongside PC/Echo. Of 13 light
endpoints, 10 available; RGB, Ta5it and Tv Links remain unavailable after reloading
Hue/Tuya; direct Hue Zigbee readback also marks Ta5it/Tv Links unreachable.
HDMI-A-1 captures at 17–20 fps (>10000 frames); red/blue/green HDMI test colours
matched all outputs and Tuya/Echo readback; Hue remained active. Hue starts on the first
picture and falls back to house control on stream loss; saved Tuya targets persist.
Owner reported no response after reboot removed fixes; a backed-up local app now replaces them.
Persistent Lumen `40-local-mira-control.conf` selects it; login sync survived service restart.
Group «إضاءة البيت والكيس» spans all 13.
281 checks and full `just check` pass (6 skips); physical proof remains open.
Mouse clicks recovered after ydotoold restart (owner/test window); fixed station helper's button-down release and failed-drag cleanup.
**Readiness source repair, 2026-10-04:** `fix/os-readiness-20261004` extends
pending Mira corrective source. Kernel socket-UID checks isolate all three Mo AI
HTTP APIs; Android/firmware errors no longer report readiness/no updates; boot
accounting no longer adds graphical time twice, and interpreted MoOS services
count by systemd ownership. Remote releases held input through the backend that
accepted its press. Targeted tests pass, including 45 input assertions using a
private socket recorder; the regression fails the old injector and passes the fix.
Full `just check`, real owner/second-UID HTTP checks and Linux publish passed;
these repairs are not signed installed bytes. A private Remote bundle at source
`9ffdf92f` is selected by `45-readiness-review.conf`; the owner confirmed clicking
works. HTTP 200, exact executable path and zero restarts passed; phone/soak remain open.
PR #194 repo/.NET/controller/x86/ARM image checks passed; boot/promotion skipped.
Its advisory reviewer failed internally despite the green job; no review acceptance claimed.
Native Update Settings reads nine firmware states with private atomic records,
concurrent-action guard and dead-process detection, including unreaped exits.
41 Settings/31 action fixtures, native KCM contract and `just check` pass;
36 AR/EN light/dark native frames cover all states without flashing hardware.
Installed firmware/timer acceptance remains open. Plymouth SIGABRT resolves to
`head != NULL` after quit; exact vendor source confirms the undisarmed callback.
Boot correction is being integrated on `fix/boot-journey-20261004`: pinned vendor
RPM rebuild cancels the freed frame callback; native ASan 3 old/20 fixed and actual
RPM-library controls pass on x86/ARM. Parser fixed to load rebuilt graphics, not base SDK.
Real renderer: 640×480/1080p/4K and changing password prompt; final native 1080p sample peak RSS 169→93 MiB, CPU 1.177→0.370 s. Slow redraw control fails.
Language guard builds 50 dictionaries without crashes; converter restored; spool uses tmpfiles.
Approved resting hero replaces 32 frames (58.1→1.82 MiB decode), finite 360 ms
entrance and shared login ground. Final local NVIDIA `ce5d668913df` passes all image gates;
actual archive/library/theme readback and tamper rejection pass; signed boots open.
Owner's Mira autostart disabled; stopped foreground cgroup charged ~914 MiB;
Backup `~/.local/lib/moos-review/20261004-095219/mira-login`; voice on demand. Current boot: 33.225 s (15.447 firmware/loader), not a stopwatch. Echo repair open; 76 old converter crash handlers timed out, preserved; user failed units 0.
**Remote:** signed `59e97672` corrected empty GDK snapshots; no Xid or memory pressure
was observed and KWin stayed running. HDMI and physical mouse/phone endurance remain open.
**MoPlayer, merged and delivered on `.964`:** the "freeze" was a 278 MB Hive catalogue decoded on the UI isolate each launch (~6 s, 1.4 GB) plus a 4.9 GB idle GPU reservation from Impeller gradient shaders and window-sized layers. The merged source moves catalogue work to isolates (~1.3 s, 0.5 GB), reduces idle GPU use to ~0.6 GB, reads get.php links as Xtream accounts, sorts playlists, supports MAC portals and ships Horizon UI. A 4K HEVC live stream and 1080p VOD played on the station from the source bundle; 255 Flutter tests passed. The local launcher that shadowed `.964` is now backed up, and the signed launcher is selected. Open: a real MAC portal, ~1 GB kept after Stop and installed playback readback (plan P2.13).
**Mira, 2026-10-02:** PRs #177–#180 integrate her six pages, approvals inbox, chat history, KDE entry, new Mo AI actions and ARM packaging. Signed x86/ARM builds include her; the station's earlier user install proved Arabic voice, a live approval and the page renders. Installed `.967` face was captured. A topic-source live Gemini voice turn on 2026-10-02 proved mouth energy returning to zero in pauses and at idle; 89 controller/QML/voice tests pass. Registered patches preserve original portraits. A corrective single-mouth UV rig replaces lip cross-fades after the owner showed doubled lips; both GPU waveform renders and a native voice reply (28 captures, pause/idle zero) were reviewed. The station now boots `.975`, which delivers the single-mouth correction; owner-spoken endurance remains open. See `mira/README.md`. **Mira home centre + Lumen, 2026-10-03 (merged and signed in `.977`; station readback below is from temporary source):** Home Assistant's registries drive a room-by-room Home page where names, rooms and voice aliases are written back into HA (rename and area round-trips read back and restored); Mira's instruction carries the same device inventory with real capabilities. Lumen, the lighting engine (`/usr/bin/mira-lumen`, user service), unifies HA lamps, the Hue bridge directly and the PC's Gigabyte RGB Fusion 2 controller (IT5701 v3.0.27.0 on this B660 GAMING X DDR4, hidraw, nothing written to flash). Measured live: a Hue lamp set violet 60 % read back in 0.43 s and was restored to its exact xy; a living scene streamed to the four PC headers at 30 fps for 1.8 % of one core; the owner approved the ScreenCast portal once and Screen Sync ran at ~14–16 fps (static desktop) with the restore token sparing a second dialog — Lumen 7 % and KWin +7.5 % of one core while syncing, Lumen 0.1 % idle; the Hue bridge was discovered (mDNS/Avahi) and a DTLS-PSK round trip through GnuTLS was proven against `openssl s_server`; Mira's text brain answered a device-capability question from the inventory and ran `light_scene`/`lights` on the PC. The station uses the documented backed-up per-user Mira app/launcher/autostart and persistent Lumen MIRA_APP drop-in until a signed image carries the corrections. Hue pairing and actual HDMI Entertainment streaming are now proven in the corrective audit above. Open: which physical fans hang on which header (needs the owner), installed Home/Lumen acceptance after reboot.
## Source and release truth

- Production/source `66653f76`, NVIDIA `44.20261006.1003` (`33a4cc91…`), is promoted with the proof IDs above; the station still boots signed `.999` and retains signed `.989`. The native early-logout correction is a separate topic and is not in `.1003`.
- Plymouth's pinned-vendor native old/fixed controls and exact final initramfs/library proof are retained; the local image passes these gates. Photographed hardware boot and physical session endurance remain open.
- Remote now runs signed image bytes; phone/WAN endurance, HDMI disconnect, Home/Lumen physical observation and the two-icon design approval remain open. Post-update checks currently pass 55/0.

## App engines — what this machine can actually run

**Corrective source work, 2026-09-27:** THEME_REV 90 adds a reviewed 6.7/6.8 dock material seam and shared Hub material; isolated clear/solid Hub renders and local image gates passed.
Windows setup folder access is temporary, confirmed and read-only. Generals Zero Hour
ran a real Alpine Assault Skirmish at 1080p fullscreen on the 4K station: Dozer selection,
movement and saving worked. Its local MoOS menu entry launches directly, but some reopen
attempts stay on the introductory background, also with the builtin renderer. The tested
DXVK configuration and save remain; all owned probes are closed. Repeated-launch/universal
Windows qualification and this corrective batch's physical-station proof remain open.

**All three app engines ran on the station (2026-09-20).** Windows Notepad, Minesweeper
and PuTTY PE32+ used `moos-run-foreign` with MoOS decoration and taskbar presence; Linux
apps completed install → launch → remove through `moos-storectl`. Correct Waydroid OTA
channels let 2.3 GB download, the container run, and F-Droid open after App Drop install.
VLC's real window is captured in `test-results/android-vlc-source-live.png`. The 4K Windows
UI density is measured. PE32 remains blocked by an SELinux `execmod` denial for an i386 PE
DLL from composefs; do not weaken SELinux globally.
## Physical development station

| Area | Measured state |
| --- | --- |
| Install | Offline USB install completed; target-only write was observed |
| Target storage | `/dev/sdb`: 512 MiB ESP + 476.4 GiB Btrfs; `/var` 244/477 GiB used, 230 GiB free (2026-09-27) |
| CPU / RAM | Intel Core i5-14400F / 15.4 GiB |
| GPU | NVIDIA RTX 2080 SUPER, driver 615.71.09 |
| Desktop | Plasma/KWin 6.7.5, Wayland, 3840×2160@60, scale 250% (1536×864 logical) on 2026-10-01 |
| Kernel | `7.2.7-200.fc44.x86_64` (2026-10-01) |
| Network | Intel AX210 Wi-Fi/Bluetooth + RTL8125 Ethernet |
| Health | Baloo recovered; post-update 55/0; powersave changed to balanced, turbo read back enabled |
| Freeze audit (2026-10-01) | 3.7 GiB in zram, no OOM this boot. Mo PC Remote renewed its portal grant ~2,600 times in the previous boot; `.964` logged repeated `1536x864+0+0@3 -> no outputs`. Live monitoring found the HDMI connector itself disconnecting for about one second, and KDE closed its portal session when that happened. The signed `.967` fix suppresses an extra geometry-triggered restart during the dropout; live cellular endurance proof is pending. `moai-control` woke rpm-ostreed 59× in 2 h 50 min, now once per boot. The Echo gadget's USB microphone floods the kernel log (~60 xHCI "buffer overrun" warnings/s, journald ~3% CPU): the 500 MB journal spans only ~5 h, so the previous boot's user logs were already gone. The fix is the gadget's packet size (Mira) |

**Remote control:** signed `.989` serves private v55 web/native core through `55-mobile-recovery-review.conf`, pointing to `~/.local/lib/moos-review/20261005-one-remote-v53`. Signed apphost/runtime/dependencies remain; reviewed DLL/helpers and controller changed. Native EIS and the named capture scope report ready; NRestarts remained zero on 2026-10-05. Only the Mo PC Remote permission was granted, with prior consent, v52 drop-in and previous web assets backed up. The home Island review remains active. Actual typing/video was proven in the disposable signed VM; five ordinary password unlock cycles were proven on the disposable guest; owner phone acceptance, display loss cause, WAN endurance and signed delivery remain open (P2.14).
## Proven source/image behavior

- **W9.10 — Mo AI's desktop hands (source, `THEME_REV` 96, 2026-09-28).** `moos-control` gains
  14 fixed verbs so the brain runs the whole desktop: a window BY NAME (focus/min/max/full/
  keep-above/close), move/go/add/remove desktop, media, lock, reminders, open a page or folder,
  animation speed, auto-lock, click. Each read back through KDE's own interfaces (KWin window
  search + `getWindowInfo`, `VirtualDesktop`, MPRIS, ScreenSaver, `systemd-run --user`, KConfig);
  free text is only a search term/reminder/http(s), free-text verbs stay OFF `moos://`; close and
  auto-lock-off ask first. Exercised live on the A1 KDE session, read back from KWin; `just check`
  green. Owed: installed-image + new-case action measurement. **P3.9 `run_command` still NOT
  built** (owner re-asked 2026-09-28).
- A signed build passes every image gate for all three x86 editions; every disk boots
  twice under QEMU/KVM; each final ISO installs offline, logs in, opens every first-party
  app twice, reboots and powers off. `pr-image-gates.yml` builds the generic image on a
  pull request and pushes nothing (16m54s on PR #141).
- Horizon motion gates cover finite settling, reversal, hidden state, reduced motion and
  pointer/key paths on a real Qt runtime.
- **W8 material arrival is in source (`THEME_REV` 85):** one finite glint/1.5% settle on shared
  glass, still under Reduced Motion; real Qt changed at 60 ms and rested by 900 ms. **W9 source:**
  Settings deep-links Update, Recovery and Remote to their transaction owners, with owner-read
  busy/superseded update, queued rollback and failed Remote rows (Arabic/English light/dark Qt
  captures passed). Installed routes and real transactions remain unproven; neither is installed.
- **The Island's job feed no longer depends on one event (source, `THEME_REV` 98, 2026-10-04):** `FolderListModel` loses a directory event that arrives while it is re-reading, so a job's last rename could leave the chip on "Installing…" (2 of 60 probe runs on the A1 with one busy core; with the guarded re-read 0 of 60). The Store and Mira job folders are read again while a job is shown as running, and `moos-privacy-monitor` publishes each change twice, a second apart (seen live: one capture, two writes). Owed: the installed Island; Mo PC Remote's own presence tokens still ring once.

## Development environment

- On the station: VS Code is a Flatpak; host work uses `flatpak-spawn --host`. There is
  **no C++ toolchain**, so any gate needing one skips here. `just workstation-check` is a
  read-only inventory; .NET `10.0.401` and Flutter 3.47.4 are installed. Pointer review
  goes through `scripts/station/pointer.py` — KWin confirms every position before a click.
- Off the station: Windows 11 + WSL2 `FedoraLinux-44`. `scripts/review/` holds the toolchain
  installer, the gate mirror and the from-source renderers; `release-candidate.sh` needs `TMPDIR`.
## ARM station `moos-arm-oracle` (Oracle A1, measured 2026-10-04)

The only ARM MoOS machine: 2 vCPU / 11.6 GiB, no GPU, `kwin_wayland --virtual 1920x1080` at 60 Hz on llvmpipe, essential tier; the owner's screen is Mo PC Remote (loopback behind Tailscale Serve). **Read back 2026-10-04, 61 h after boot:** booted signed `44.20260930.638`, `44.20261003.669` staged, `.632` kept; kernel `7.2.7-200.fc44.aarch64`; graphical target 8.5 s; `/var` 199 GiB, 103 GiB free; no failed system unit; Plasma 6.7.5, Qt 6.11.2. 5.8 GiB available; 2.6 GiB of cold pages in zram cost 0.6 GiB; memory pressure 0.01. The editor and agent scopes hold 3.2 GiB + 1.7 GiB swap and 166 of the machine's 404 core-minutes. Idle `kwin_wayland` **2.1%**, `plasmashell` **0.6%** of one core (2026-09-21).

**Three defects measured there, fixed in source with gates (branch `test/oracle-cloud-workstation-20261003`; not signed, not installed):**
- **Mira's chat ran away to 8.9 GiB (OOM, 2026-10-02).** An entry's height passed through 1208 px, then 452, while it was made; bound into the ListView that remade entries 2–7 about 27 times in 8 s. Reproduced from source (98% of a core, 386→759 MiB in 30 s); with a settled, content-driven height: 172 MiB, 0%. Both launch paths also stop at 1.5 GiB; a template drop-in was read back on a transient unit.
- **Mo PC Remote leaked one PipeWire remote per rebuilt pipeline** (`pipewiresrc` closes only its duplicate): 67 orphaned clients, `pipewire` 464 MiB + 104 MiB swap, growing 11.6 MiB/h idle. The station's helper keeps them until Remote restarts or a fixed image boots.
- **`moos-privacy-monitor`'s 1.5 s poll had used 52.1 CPU-minutes**, more than KWin's 50.1. One `pw-dump --monitor` feed with a one-minute resync: 2.51% → 0.05% of a core; a real capture gave the same token 0.04 s after it began instead of 0.64 s.

**Cloud desktop, measured in an isolated second compositor (`scripts/station/compositor-rig`, 2026-10-04; source and gates, not signed):** the compositor is the cost: OpenGL on llvmpipe drew a busy window for 71.8% of a core with no stream and 77–81% with one; QPainter drew it for 12.1% and offers no ScreenCast. `max-framerate=30` is a loss (25.2 frames delivered a second, 15.5 encoded) and is not shipped. Two fixes: the frame-rate setting did not limit (`videorate max-rate` passes a variable-rate source; asked for 30, 35.6 encoded) and `FramePacer` now does, by waiting, never dropping (28.9/s, encode path 71.0% → 57.7%); and `moos-cloud-desktop display phone|desk|WxH` chooses the desktop's size, because Auto sends 1280 px here and 1080p reached the phone through a 1.5:1 scaler: 37.7 frames/s for 64.6% scaled, 47.3 for 41.5% at a native 1280×720. Default unchanged; applies at the next sign-in. `systemd-oomd` monitors nothing on ARM and upstream's 80% limit did not act on a zram thrash at 67–70%: plan P5.5 and P5.7.

**Seen on the live A1 on 2026-09-24, and fixed in source with a gate:** the MoOS Bar and Dolphin read LTR in Arabic, GTK windows drew Adwaita light, App Drop's `ask()` returned False (no kdialog), the privacy monitor ran blind (no pw-dump). All eight capabilities come from x86's base; `build-arm.sh` now names them and `verify_desktop_parity.py` passes on the published x86 image and a full local ARM build. Mo AI's chat texture drew stray logos on the software scene graph (fixed, runtime-gated); it answered in 0.65 s on the free route, APIs loopback-only. Three readings look like defects and are not (`cost_policy: "paid"`, `"gateway": false`, sandboxed `systemd-tmpfiles`): see the plan.

## Plasma 6.8 readiness (measured 2026-09-24; detail in plan row P6.7)

On KDE SIG's 6.8 beta (`6.7.90`) MoOS's 6.7 lock screen falls back to the emergency locker (6.8
removed `VirtualKeyboardLoader`). **Canary run `35980381601` built the whole generic image on
6.7.90 with every in-image gate green:** the seam gate picked set 6.8, matched ten digests and
loaded the merged lock screen in the real greeter; PR #161's 6.7.5 builds pass it too. CI also
fixed Breeze Global Themes hidden on x86 (one shared step) and flagged a libplasma soname bump
that removes `kcm-fcitx5` until Fedora rebuilds it. No 6.8 candidate yet.
## Open evidence gaps

- **W9.9 source, live from the worktree (2026-09-25):** the seven System Settings modules on the
  station — MoOS group first; "Linux 7.2.7", "MoOS for NVIDIA graphics"; Update's three rows; Mo
  AI GET-only; MoOS Themes marks the Arena look. `moai-measure-actions` (65 cases, ar+en):
  **126/130 = 96.9%** on `nex-n2.5-pro:free` (3 timeouts, 1 wrong tool). The installed one-module
  `.929` KCM (packager kernel tag, English Input Method, wrong window class) is fixed in W9.9
  source. Owed: installed image, THEME_REV 86 migration, Meta+Space after login, update/rollback.
- **Testing side effects, now gated (2026-09-24/25):** repo tests wrote fake `moai-do`/`moos-update`
  audit lines and dumped `bluetoothctl` core; tests now stub `logger` under a meta-gate and skip
  Bluetooth without a system bus.
- M1 visual/accessibility matrix: English/German, light/dark, reduced motion, 1080p–4K,
  100–250%, island Remote/Media (Arabic only so far).
- Hardware: suspend/resume, multi-monitor, audio/network recovery, deliberate rollback,
  photographed boot/login, laptop and touch hardware, ARM on a physical seat.
- Versioned, failure-tested Mo AI/Store/core contracts and one lifecycle across every
  adapter. APK installation now has the Store authority; shared cancel/remove/retry and
  stable cross-engine app IDs remain P4.1 work.
- Owner decision P3.9: a Mo AI tool that runs a command the model wrote. Re-asked
  2026-09-28; not built. W9.10's 14 fixed desktop hands cover the control it wanted safely.
## Other measured facts

**The free brain is measured where it runs (2026-09-18):** the catalogue carried **21**
tool-capable zero-price models. `moai-measure-free` asks each two fixed questions through the
real gateway and writes `~/.local/state/moai/free-ranking.json`, which `moai_cloud_policy`
prefers for 30 days without adding a model, a price or a billed route. P0.5 owes the key
entered through Settings, a reboot and the provider-failure surface.

**A second desktop server:** `moos-health scan` found `krdpserver` on `tcp *:3389` beside Mo PC
Remote; the finding carries `moos://privacy/stop-sharing`, and `moos-remote-guard off` stops and
un-autostarts both with no administrator rights.
