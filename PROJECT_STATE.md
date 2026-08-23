# MoOS — current project state

This file is current state, not session history. Git history owns the history.
When documentation disagrees with a running machine, a freshly booted artifact,
or current source, those stronger forms of evidence win.

Last reconciled: **2026-08-23** after merge of PR #60 into `main`.
Full session narrative: [`docs/CHECKPOINT-2026-08-23-UTM-INSTALLER-SESSION.md`](docs/CHECKPOINT-2026-08-23-UTM-INSTALLER-SESSION.md)

---

## Where we are (one paragraph)

Work pivoted from Oracle (paused) to a **UTM iPhone net installer**
(`MoOS-UTM-Installer.utm.zip`). The branch was **merged to `main`** at owner
request to stabilize the repo. A CI-built zip (1.5 GB) was delivered to the
owner's Desktop. **Real iPhone test FAILED:** boot showed **Fedora** branding —
an identity violation. The recovery installer is **fedora-bootc-based** with
minimal `os-release` patching only; it does **not** pass full MoOS identity
scrub. Net-install E2E and iPhone PASS remain **open**.

---

## UTM iPhone net installer

| Item | Status |
|---|---|
| Slim recovery (`Containerfile.arm-recovery`) | **In `main`** — Fedora bootc base + installer tools |
| Menu + cosign + `bootc install` scripts | **In `main`** |
| Old full-QCOW2-in-zip bundle | **SUPERSEDED / FAILED** (real iPhone + fstab flood) |
| `MoOS-UTM-Installer.utm.zip` (CI `32655458877`) | **Old zip on Desktop** — rebuild required after identity fix |
| Recovery identity (MoOS plymouth, no Fedora splash) | **FIXED in code** (`build-arm-recovery.sh`) — pending CI rebuild |
| iPhone physical test | **FAIL** (old zip showed Fedora); **retest after new zip** |
| Net install → target disk → MoOS greeter | **NOT PROVEN** |

Install source (manifest): `ghcr.io/moalfarras-sys/moos-arm@sha256:e1ace22c3a6a207f2bcd3507fe98f2071bdb9a9d6bd3bfbf7de03e1d0de28601`
(`release/arm-latest.json`, product `196f8679`).

Owner deliverable path: `/var/home/moos/Desktop/MoOS-Release/MoOS-UTM-Installer.utm.zip`

---

## Oracle (paused)

Frankfurt A1 `OUT_OF_HOST_CAPACITY`. Watcher stopped. Not a MoOS quota issue.
See Desktop `ORACLE-BLOCKER.txt` if present.

---

## PR #60 — merged

Branch `fix/release-trust-boot-20260820` merged into `main` on **2026-08-23**
(owner directive: stop work, merge, document, push).

Includes: release-trust fixes, ARM boot proof gates, UTM net installer pipeline,
`Containerfile.arm-recovery`, CI reorder (UTM zip before visual gate).

**Merge does not mean:** iPhone PASS, recovery identity clean, tag promotion, or
host update to a new digest.

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
| UTM net install | `moos-utm-installer-menu` + `moos-utm-net-install` | recovery disk only | cosign + bootc; **identity scrub missing on recovery** |
| Disk installation | `moos-install-to-disk` / bootc | target disk | ARM net install path unproven E2E |

---

## Load-bearing release contracts

- Never weaken identity gates; repair the image scrub.
- **`/etc/os-release` patch alone is not MoOS identity** — recovery must be fixed.
- Published tags move only after boot-proven artifacts.
- `/var` empty in image; `bootc container lint` is a gate.

---

## Still unproven

- Recovery installer without foreign branding (Fedora on boot = blocker).
- iPhone UTM net install full path (download → install → boot target → greeter).
- ARM greeter visual frame in CI (stddev gate often skipped for delivery).
- x86 QCOW2/ISO proofs for freeze digests (parallel track on PR #60 scope).
- Real-host update, rollback exercise, clean-VM visual matrix.

---

## Next safe order

1. **Recovery identity scrub** — Plymouth, logos, os-release, foreign sweep; gate it.
2. Rebuild `MoOS-UTM-Installer.utm.zip` from CI; owner re-tests iPhone.
3. Prove net install E2E (target disk boot, no fstab flood, greeter).
4. Only then: promote ARM tags / host update if applicable.
