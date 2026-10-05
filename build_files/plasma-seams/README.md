# MoOS seams in Plasma

MoOS replaces twelve files that live inside Plasma's own packages: the shell package's widget
explorer, edit mode, panel, lock-screen media strip (`MediaControls.qml`), `defaults` and panel
template, plus six breeze components the login, lock and power screens draw (`ActionButton`,
`Clock`, `UserDelegate`, `UserList`, `SessionManagementScreen` and `WallpaperFader`). Each one is a fork of the
upstream file at one Plasma version. `seams.json` lists them, and `rpm -V` in the build proves the
list is complete.

**No seam carries authentication.** Until 2026-10-05 two of them did: MoOS forked the lock screen's
own `LockScreenUi.qml` and `MainBlock.qml` to draw a card, a clock and a brand mark around the
password row. Those are the files that hold the authenticator wiring, upstream rewrites them every
release, and by 6.8 beta 2 MoOS was carrying three hand-derived variants of one and two of the other
(beta 1 is the release whose missing `VirtualKeyboardLoader` this whole gate exists for). The MoOS
session design now lives in what those two files *instantiate*. `SessionManagementScreen` is the
layout both the lock screen's `MainBlock` and the login greeter's compiled `Login` are built from, so
the island it draws is on both screens; `WallpaperFader` is the lock screen's backdrop, so it carries
the session veil and signature. Neither ever sees a password or an authenticator. The lock screen
runs the two files `plasma-desktop` ships, on every Plasma, and `build.sh` refuses a MoOS copy at
either path. Do not make an authentication file a seam again: restyle what it draws.

`build_files/plasma_seams.py build` runs in `build.sh` and `build-arm.sh` after the last package
transaction. It selects the set whose Plasma range holds the image's `plasma-workspace`,
installs that set's variant files, and fails the build when:

- no set covers this Plasma;
- a replaced file's upstream bytes (rpm's own digest) are not the bytes the set was reviewed
  against;
- a Plasma file is modified in the image but is neither a seam nor a registered edit;
- kscreenlocker's real greeter, started in testing mode offscreen with no session bus, cannot
  load the lock screen.

A red build here means a new Plasma reached the base image. The mutable `kinoite-main:44` tag
moves by itself, so this fires without any change in this repository. It is the truth: the
lock screen MoOS would ship was written for another Plasma.

## Reviewing a new Plasma

The weekly `plasma-next-canary.yml` workflow builds MoOS on KDE's beta packages, so a new
Plasma usually shows up there weeks before it reaches the base.

1. Fetch both upstream versions and merge MoOS's changes onto the new file:

   ```bash
   python3 scripts/plasma-next/rederive_seams.py 6.7.5 6.7.90   # old reviewed, new upstream
   ```

   It downloads the two `plasma-desktop` and `plasma-workspace` RPMs, lists the seams whose
   upstream bytes changed, and writes a three-way merge (`git merge-file`) of each one into
   `~/.cache/moos-plasma-next/rederive/`, with the upstream diff beside it.

2. Resolve every conflict by taking upstream's side **verbatim**: its public properties,
   aliases and signals, its anchor lines and its states. MoOS's part is visual only. The file's
   header says so, and it must stay true. (A conflict in authentication logic cannot happen any
   more — no seam contains any — and if one ever does, the seam is the mistake.)

3. Put the result under `build_files/plasma-seams/<set>/<image path>` and give the set a
   `sources` entry for it. A seam whose upstream change does not touch what MoOS replaced
   keeps the MoOS copy, and the set records why in `reviewed_on`.

4. Load it before recording anything:

   ```bash
   python3 build_files/plasma_seams.py probe-lockscreen --shell-dir <shell package with the new files>
   ```

   The probe must pass on the new Plasma. It must also fail when the file is broken on purpose,
   for example by renaming one type it instantiates.

5. Only then record the new upstream digests in the set's `reviewed` map, and run
   `python3 tests/test_plasma_seams.py`.

Never widen a range or add a digest to make a build pass. A digest in `reviewed` is a claim that
a person merged that upstream version into MoOS's copy and watched the real greeter load it.
That is why the beta-1-only set (6.7.90) was removed on 2026-10-05 instead of being given digests
for the two new seams: no 6.7.90 stack exists any more to load the greeter on.

## Seeing the session surfaces from a worktree

`scripts/station/session-review/review.sh shots.txt` renders the lock, login and power screens
from the tree with the real greeter binaries (`kscreenlocker_greet --testing`,
`plasma-login-greeter --test`, `ksmserver-logout-greeter --windowed`) in a throwaway container,
at any logical size, scale, language and MoOS family, idle or with the password row active,
typed into, or refused. `MOOS_REVIEW_IMAGE=<a Plasma-next image> SEAM_SET=6.8` lays a variant
set over a newer Plasma, and a `probe <name>` line runs `probe-lockscreen` there with its
negative control. It never touches the owner's desktop.

## Live material, 2026-09-26

Panel.qml is a reviewed seam for 6.7.5 and the 6.7.90 package. MoOS imports its
shared material policy and changes frame opacity and mask selection only. KDE
continues to own panel geometry, applets and input; MoOS clarity owns material density,
including beside maximized windows. The 6.8
variant retains the upstream ContainmentItem and panel-enum changes.
