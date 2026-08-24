# MoOS — current project state

This file is current state, not session history. Git history owns the history.
When documentation disagrees with a running machine, a freshly booted artifact,
or current source, those stronger forms of evidence win.

Last reconciled: **2026-08-24** after the boot-splash black-screen fix.
Full session narrative: [`docs/CHECKPOINT-2026-08-23-UTM-INSTALLER-SESSION.md`](docs/CHECKPOINT-2026-08-23-UTM-INSTALLER-SESSION.md)

---

## Boot splash: root cause of "black screen, no MoOS logo" — FIXED (2026-08-24)

**Symptom on the owner's NVIDIA daily driver:** from power button to desktop,
a black screen; the MoOS splash never appeared; boot felt slow (~36 s measured:
13.9 s firmware + 6.6 s GRUB/loader + 10.5 s kernel+initrd + 4.9 s userspace).

**Root cause (proven, not guessed):** `moos.script` shipped with a **UTF-8 BOM**
(EF BB BF at byte 0). Plymouth's scanner turns those bytes into three SYMBOL
tokens before the first comment, so the parser rejects the whole script
(`Unparsed characters at end of file`, L:1 C:0) and `script_parse_file()`
returns NULL. `plugin.c` does NOT check that result — it calls
`start_script_animation()` anyway and reports success, so plymouthd runs a
theme that draws nothing (not even its background colour, which the script
sets). Result: a pure BLACK splash window (8.7 s → 14.5 s of the boot) while
every file-presence gate stayed green.

Proof method: built a harness against Fedora 44's real parser sources
(plymouth 24.004.60) — with BOM: PARSE FAILED; identical bytes minus BOM:
PARSE OK. `artwork/preview_boot_animation.py` had already documented that
nothing in the repo proved parseability; that gap is now closed.

Fixes landed:

- BOM stripped from
  `system_files/usr/share/plymouth/themes/moos/moos.script`.
- New gates that FAIL on any BOM in the theme dir:
  `tests/test_boot_splash_polish.py` (repo) + inline gates in `build.sh`,
  `build-arm.sh`, `build-arm-recovery.sh` (image). Both layers bite-tested.

Initramfs diet (same session): the generic `--no-hostonly` initramfs was
sweeping in the full initrd network stack (`network`, `network-manager`,
`kernel-network-modules`) plus all of `kernel-modules-extra` although MoOS
always roots from a LOCAL device. Both are now omitted in `99-moos-boot.conf`
and both dracut runs. Measured composition of the 229 MB installed image:
~109 MB NVIDIA GSP firmware (kept — needed for early KMS), ~65 MB modules;
recompression is pointless (the cpio body is already-compressed data: 213 MB
at every zstd level). Expected new size ≈185–200 MB; confirm on next build via
the size-guard line CI prints.

Not fixable from inside MoOS (documented for the owner): the first ~14 s is
UEFI firmware POST/monitor handshake and ~6 s more is GRUB reading the kernel
+ initramfs — enable fast/ultra boot in the board firmware to cut the first
part. A GRUB-phase MoOS theme would need writing into `/boot/grub2`
(`console.cfg` hook exists in bootupd's static grub.cfg) but has no
bootupd-managed shipping path yet — open item.

---

## Where we are (one paragraph)

The **UTM iPhone net installer** (`MoOS-UTM-Installer.utm.zip`) is the sole
priority. The previous iPhone test **FAILED** with a `systemd-fstab-generator`
flood at ~42s — root cause was three missing ARM boot fixes in the recovery
image (`build-arm-recovery.sh`): block coldplug service not enabled,
DefaultDeviceTimeoutSec=120 missing, boot.mount ordering absent. All three are
now **fixed** in `main` (`817cca89`) and **CI is rebuilding** (run
`32659798645`). Identity fixes (MoOS Plymouth, os-release, no Fedora branding)
were already committed in `c02bba7a`. Owner iPhone retest required after CI
delivers the new zip.

---

## UTM iPhone net installer

| Item | Status |
|---|---|
| Slim recovery (`Containerfile.arm-recovery`) | **In `main`** — Fedora bootc base + MoOS identity + installer tools |
| ARM block coldplug + 120s timeout (fstab fix) | **FIXED** `817cca89` — was the root cause of iPhone boot flood |
| Recovery identity (MoOS Plymouth, no Fedora) | **FIXED** `c02bba7a` — os-release, Plymouth theme, logo overlay |
| Menu + cosign + `bootc install` scripts | **In `main`** — whiptail menu + cosign verify + bootc to-disk |
| Old full-QCOW2-in-zip bundle | **SUPERSEDED / FAILED** (real iPhone + fstab flood) |
| Old `MoOS-UTM-Installer.utm.zip` on Desktop | **SUPERSEDED** — pre-coldplug-fix, pre-identity-fix |
| CI rebuild (run `32659798645`) | **IN PROGRESS** — will produce the fixed zip |
| iPhone physical test | **FAIL** (old zip); **OWNER RETEST REQUIRED after new zip** |
| Net install → target disk → MoOS greeter | **NOT PROVEN** |

Install source (manifest): `ghcr.io/moalfarras-sys/moos-arm@sha256:e1ace22c3a6a207f2bcd3507fe98f2071bdb9a9d6bd3bfbf7de03e1d0de28601`
(`release/arm-latest.json`, product `196f8679`).

Owner deliverable path: `/var/home/moos/Desktop/MoOS-Release/MoOS-UTM-Installer.utm.zip`

---

## Oracle (paused)

Frankfurt A1 `OUT_OF_HOST_CAPACITY`. Watcher stopped. Not a MoOS quota issue.
See Desktop `ORACLE-BLOCKER.txt` if present.

---

## Running development host

- Booted signed `moos-nvidia` `44.20260821.632`, digest
  `sha256:ef3b4ea72568e76a47b2b617c11ba594b93908e68c92647c7e6e5a831bc7adab`.
- Staged (not rebooted) `44.20260822.633` — **not** the UTM mission digest.
- Do not reboot onto unstaged/unproven digests for release work.

---

## One authority per responsibility

| Responsibility | Authority | Runtime / state | Proof |
|---|---|---|---|
| OS image update | `moos-image-update` | bootc/OSTree deployment + signed origin | release gates, post-update check |
| Rollback | bootc/rpm-ostree | previous signed deployment | live deployment inspection |
| Image identity | `build.sh` / finalize scripts | final image filesystem | three identity firewalls |
| Theme selection | `moos-theme` → `moos-apply-theme` | user KConfig/GSettings | live readback + UI gates |
| Hardware policy | `moos-device-plan` + `moos-hardware-adapt` | `/etc/moos` state | fixtures + live journal/readback |
| UTM net install | `moos-utm-installer-menu` + `moos-utm-net-install` | recovery disk only | cosign + bootc; identity fixed, coldplug fixed |
| Disk installation | `moos-install-to-disk` / bootc | target disk | ARM net install path unproven E2E |

---

## Load-bearing release contracts

- Never weaken identity gates; repair the image scrub.
- Published tags move only after boot-proven artifacts.
- `/var` empty in image; `bootc container lint` is a gate.
- Recovery coldplug + device timeout gates cannot be removed (iPhone boot fix).

---

## Still unproven

- iPhone UTM net install full path (download → install → boot target → greeter).
- ARM greeter visual frame in CI (stddev gate often skipped for delivery).
- x86 QCOW2/ISO proofs for freeze digests (parallel track).
- Real-host update, rollback exercise, clean-VM visual matrix.

---

## Next safe order

1. **CI run `32659798645` completes** — download `MoOS-UTM-Installer.utm.zip`.
2. Owner tests on real iPhone: import → install → boot → MoOS greeter.
3. If PASS: promote ARM tags / update `arm-latest.json` if new digest built.
4. If FAIL: diagnose from serial log, fix, rebuild.
