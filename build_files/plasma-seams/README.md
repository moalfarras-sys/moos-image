# MoOS seams in Plasma

MoOS replaces eleven files that live inside Plasma's own packages: the shell package's lock screen
(`LockScreenUi.qml`, `MainBlock.qml`, `MediaControls.qml`), widget explorer, edit mode,
`defaults` and panel template, plus the breeze components `ActionButton`, `Clock` and
`UserDelegate` that the login, lock and logout screens draw. Each one is a fork of the upstream
file at one Plasma version. `seams.json` lists them, and `rpm -V` in the build proves the list
is complete.

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

2. Resolve every conflict by taking upstream's authentication logic **verbatim**:
   authenticator connections, the password path, the StackView and the footer. MoOS's part is
   visual only. The file's header says so, and it must stay true.

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

## Live material, 2026-09-26

Panel.qml is a reviewed seam for 6.7.5 and the 6.7.90 package. MoOS imports its
shared material policy and changes frame opacity and mask selection only. KDE
continues to own panel geometry, applets and input; MoOS clarity owns material density,
including beside maximized windows. The 6.8
variant retains the upstream ContainmentItem and panel-enum changes.
