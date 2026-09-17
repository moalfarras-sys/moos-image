# The MoOS agent guide — runtime ownership and delivery

`AGENTS.md` is the **rules**. `PROJECT_STATE.md` is the **terrain**. This file is
the map of which files can affect boot or desktop state. Open product work is
tracked only in `docs/DEVELOPMENT_PLAN.md`.

Read `AGENTS.md` first; it is binding. Then read this. For visual work, read
`artwork/MOOS_UI2_DESIGN.md` and the active task in
`docs/DEVELOPMENT_PLAN.md`.

---

## 0. The one habit that matters

**Never write "done" for something you did not watch happen.**

Every claim in this repository is supposed to be backed by a command that ran and
returned output. `PROJECT_STATE.md` records measured state; `AGENTS.md`
preserves occasions where green gates missed a shipped defect.
The gates check what someone thought to check; they cannot see the screen.

The honest loop, in order:

```bash
just check              # every slice; maintained CI gate, failures propagate
just build              # Tier 1 changes and milestone end (build-nvidia/build-cloud)
```

Then **look at it**. A screenshot, a live readback, a pixel. See §4.

Work is batched: several plan tasks per cycle, `just check` and live review as you
go, the full image build and the release proofs once per milestone. See
**How MoOS work is scheduled** in `AGENTS.md` and the task protocol in
`docs/DEVELOPMENT_PLAN.md`.

---

## 1. The sensitive files — ranked by what breaks

### Tier 1 — get this wrong and the machine does not boot

| file | why it is dangerous |
|---|---|
| `build_files/build.sh` | builds the whole image; a bad line fails at minute 20 of CI, or ships a broken `/usr` |
| `Containerfile` / `Containerfile.arm` | shared x86 / native ARM base inputs; current tags are mutable, see P6.1 |
| `system_files/usr/lib/dracut/**`, anything initramfs | a bad initramfs is an unbootable machine, and the failure is at boot, not at build |
| `/etc/pki/containers/moos.pub` + the signature policy | break it and `bootc` refuses every update, including the one that would fix it |
| `.github/workflows/build*.yml`, `promote-x86.yml` | candidate signing, artifact proof and promotion; ARM also signs in its own pipeline |

Rule: for anything in Tier 1, the previous deployment must stay bootable
(`bootc rollback` / the second GRUB entry). Check before you reboot:

```bash
rpm-ostree status --json
```

Inspect the booted and rollback deployments' `container-image-reference` and
resolved digests. An official `ostree-image-signed:docker://ghcr.io/…` reference
is signed-origin evidence; an entry count or missing `unverified` substring is
not. Follow `RELEASE.md` for the full pre-update procedure.

### Tier 2 — the desktop breaks, the machine still boots

| file | why it is dangerous |
|---|---|
| `system_files/usr/bin/moos-apply-theme` | runs at every login and rewrites the user's desktop config. A bug here is applied to every machine on next login. It holds `THEME_REV`. |
| `system_files/usr/bin/moos-bar-apply` | the ONE writer of the bar. It does **file surgery on the appletsrc**. A bug here can leave a user with no panel. |
| `system_files/usr/share/moos/moos-bar.conf` | single source of truth for the dock. `layout.js`, `moos-bar-apply`, `moos-selfcheck` and the gates all mirror it. |
| `.../layout-templates/.../layout.js` | the seed for a NEW profile. A throw anywhere in it leaves the session with **no panel at all** — which is why every call in it is wrapped in `try`. |
| `system_files/usr/bin/moos-visual-tier` | writes KWin + Kirigami motion settings on every login |
| `artwork/generate_moos_*.py` | regenerate 16 theme packages; never hand-edit a generated SVG, edit the generator |

### Tier 3 — cosmetic, but visible to every user

`system_files/usr/share/plasma/plasmoids/org.moos.*`, the generated
`desktoptheme/MoOSUI2*` trees, `aurorae/themes/*`.

---

## 2. The five mechanisms you must understand before touching the desktop

These mechanisms have caused real regressions and need runtime readback.

### 2.1 A running plasmashell overwrites your config edits

plasmashell holds the panel config in memory and **flushes it over the file when
it exits**. Edit `plasma-org.kde.plasma.desktop-appletsrc` while it runs and your
change is silently reverted.

Determine the actual lifecycle owner first with `systemctl --user status
plasma-plasmashell.service` and the process cgroup. On the current station it
is an active systemd user service. Use that service for lifecycle changes.
Only for a verified legacy session-managed instance, use this sequence:

```bash
kquitapp6 plasmashell                        # stop FIRST
for i in $(seq 1 25); do pgrep -x plasmashell >/dev/null || break; sleep 1; done
# ... now edit the file ...
setsid plasmashell >/dev/null 2>&1 &         # then start
```

Verify one live process and re-read the panel afterward.

### 2.2 The tray has three lists and they do not mean the same thing

In `[Containments][N][Applets][M][General]` (note: **not** under
`[Configuration]` — there is a decoy `shownItems` in the `[Configuration][General]`
group that nothing reads):

- `shownItems` — **FORCED** visible, whatever the item's own status says
- `extraItems` — items the tray KNOWS about; each one's `Plasmoid.status` decides
- `hiddenItems` — always behind the arrow

An applet that should appear only sometimes belongs in `extraItems` and **never**
in `shownItems`. Putting `org.moos.island` in `shownItems` made it permanent and
defeated its whole design; `verify_user_experience.py` now refuses that by name.

### 2.3 An applet that wants to disappear must be a tray item

Plasma does **not instantiate a representation for a zero-width applet**. So a
panel applet whose width comes from its own content can never grow out of zero —
the content that would give it width never exists. Measured: the compact
representation's `Component.onCompleted` never fired once.

The mechanism that works is the one the shell already ships:

```qml
// metadata.json: "X-Plasma-NotificationArea": "true"
Plasmoid.status: hasSomethingToSay ? PlasmaCore.Types.ActiveStatus
                                   : PlasmaCore.Types.PassiveStatus
```

`org.kde.kdeconnect` and `org.kde.plasma.vault` do exactly this on disk today.
And remember **a tray cell is square** — a wide chip gets clipped and renders
blank. Icon in the tray, rich content in the popup.

### 2.4 OSTree freezes mtimes, so caches outlive content

`/usr` mtimes are pinned to the epoch. Plasma's `~/.cache/plasma_theme_*.kcache`
and Qt's `qmlcache` are keyed on mtime, so **new art and new QML do not reach the
screen after an update** — the cache serves the old bytes and every gate stays
green.

`moos-apply-theme` purges those caches, but only inside its once-per-revision
migration. **Therefore: any change to shipped theme SVGs or plasmoid QML requires
bumping `THEME_REV`.** Two gates pin the literal (`tests/test_moos_ui2.py` and
`tests/verify_user_experience.py`); move them with it, then run
`python3 tests/test_theme_rev_fingerprint.py --record`.

`tests/test_theme_rev_fingerprint.py` enforces the rule: it compares the revision
with a recorded digest of every package a frozen-mtime cache can serve stale
(plasmoids, wallpapers, look-and-feel, shells, layout templates, `org.moos.ui`,
Plasma Style and Aurorae SVGs), fails when bytes moved and the number did not, and
`--record` refuses to hide that. W5 changed the island and search at rev 60 with
every check green; ARM promotes each green `main` push, so its machines kept the
cached W3 widgets. First-party apps are exempt because their launchers export
`QML_DISABLE_DISK_CACHE=1` — keep that line when you add an app.

### 2.5 The motion gate floors at 1, not 0

`Kirigami.Units.longDuration` never reaches 0, so `longDuration > 0` is **true
even with animations fully disabled** and the gate never fires. Use `> 1`.
`verify_user_experience.py` refuses `> 0` in a motion gate by name, and it also
refuses an *alias*: an `Animation.Infinite`'s `running:` must name the gate
itself, not a derived property, because the checker cannot follow an alias.

---

## 3. How a change reaches every edition

`Containerfile` produces `moos`, `moos-nvidia` and `moos-cloud` from the same
x86 base. `Containerfile.arm` uses the native ARM base. Both consume the common
`system_files/` overlay; architecture-specific paths and service wiring still
need built-image verification on each architecture.

The release path:

```
fixed branch SHA -> signed candidate -> exact QCOW2 + offline ISO boot proofs
       -> reviewed merge preserving ancestry/tree -> promotion of proven digests
       -> moai-do update (stages the promoted signed digest)
       -> reboot -> moos-apply-theme runs the THEME_REV migration at login
```

Verify a release rather than assuming it:

```bash
skopeo inspect docker://ghcr.io/moalfarras-sys/moos-nvidia:latest \
  | jq -r '.Labels["org.opencontainers.image.version"], .Labels["org.opencontainers.image.revision"]'
# Compare with the promoted candidate revision, not the newest branch commit.
```

### Delivery checks

**A dispatch is not proof of completion.** Record the workflow run ID, head SHA,
attempt, individual job outcomes and candidate/boot manifests. An advisory
review can fail inside a green job; inspect its outcome and findings.

**One edition can finish while another fails.** Matrix builds publish candidate
tags only. A partial build must not move production tags; promotion requires
all edition proofs from the same revision.

**Never read the run's top-level conclusion alone.** Check per-edition, at the
registry, which is the only thing users pull from:

```bash
for i in moos moos-nvidia moos-cloud; do
  printf '%-12s ' "$i"
  skopeo inspect docker://ghcr.io/moalfarras-sys/$i:latest \
    | jq -r '"\(.Labels["org.opencontainers.image.version"])  rev=\(.Labels["org.opencontainers.image.revision"][0:8])"'
done
# Every revision must equal the accepted release candidate.
```

**GHCR can rate-limit uploads.** Inspect the actual error before changing
credentials. A previously observed response was:

```
denied: permission_denied ... HTTP status code 403 "Forbidden"
  "You have exceeded a secondary rate limit."
```

That response describes throttling, not a broken token. Respect the cooldown
and inspect the failed step before attempting another candidate.

So: **batch your work into one push.** A commit is cheap; a push costs three
image builds and three registry uploads. Committing five times and pushing once
is the same history and a fifth of the load.

Inspect individual failed jobs:

```bash
gh run view <run-id> --json jobs \
  --jq '.jobs[] | select(.conclusion!="success") | "\(.databaseId) \(.name)"'
```

For release evidence, launch a fresh workflow dispatch after fixing the cause;
`RELEASE.md` requires `run_attempt == 1`, so **Re-run jobs** cannot repair a
release candidate. Keep the previous completed release available.

Before promising "it will apply after reboot", resolve the staged deployment
from status, then inspect its files. Directory mtimes cannot identify it:

```bash
rpm-ostree status --json | jq '.deployments[] | select(.staged) | {checksum, serial, osname, "container-image-reference": .["container-image-reference"]}'
```

---

## 4. How to actually see the desktop

Use the actual logged-in user's environment and `moai-open` for detached app
launches. Read [`live-development.md`](../skills/moos-engineering/references/live-development.md)
for host/Flatpak access, private evidence and the Settings review harness. Do
not hard-code the UID or Wayland socket from a previous session.

- Read panel state live:
  `gdbus call --session -d org.kde.plasmashell -o /PlasmaShell -m org.kde.PlasmaShell.evaluateScript '<js>'`
- Preview a branch's theme without building: copy
  `system_files/usr/share/plasma/desktoptheme/<ActiveTheme>` into
  `~/.local/share/plasma/desktoptheme/`, clear `~/.cache/plasma_theme_*.kcache`
  and `ksvg-elements`, toggle `plasma-apply-desktoptheme`. **Override the ACTIVE
  variant** (read it: `kreadconfig6 --file plasmarc --group Theme --key name`) —
  it is usually a family member, not the base.
- **Remove every home override before you finish.** A package under
  `~/.local/share/plasma/` outranks `/usr` forever and masks all future updates.

Two traps that have eaten whole sessions:

- `pkill -f <pattern>` matches the invoking shell's own command line and **kills
  your shell** (exit 144). Kill by PID, always.
- Qt logs nothing without `QT_FORCE_STDERR_LOGGING=1`, and `console.log` needs
  `QT_LOGGING_RULES='qml=true'` on top of it.

---

## 5. Constraints for the active plan

The task queue and missing acceptance evidence live in
[`DEVELOPMENT_PLAN.md`](DEVELOPMENT_PLAN.md), not in a second backlog here.

- **P2.4/P2.5:** launcher source tests cover search/content focus transitions;
  real-key and scale-specific proof must come from the current artifact. Do not
  generalize one clock or Settings capture into whole-desktop qualification.
- **P3.2:** context-island activity needs observable state transitions. A same-name
  mtime touch may not notify a directory model; `FolderListModel` does not list
  Unix sockets. Prefer lifecycle-bound regular-file presence or a typed signal.
- **P2:** the dock remains one capsule as specified in `moos-bar.conf`. Preserve
  Plasma task-manager behavior (pinning, grouping, drag/reorder and previews)
  when evaluating motion. A hover effect alone does not justify replacing it.
- **P2.5:** derive actual outputs/scales from KScreen. Review each responsive/RTL
  class and restore any session state changed by the review.

---

## 6. Before you push

- `just check` green (§0); a full local build for Tier 1 changes (§1) and at the
  end of a milestone, not after every edit.
- `THEME_REV` bumped if any shipped SVG or shell QML changed, with both pinned
  gates moved and the fingerprint re-recorded (§2.4) — `just check` refuses otherwise.
- Every home override under `~/.local/share/plasma/` removed.
- `PROJECT_STATE.md` and `docs/DEVELOPMENT_PLAN.md` updated concisely —
  **including what you did NOT finish**. Git history replaces per-session
  continuation journals.
- Branches: work on a branch, then merge to `main`. After merging, retire it.
  Verify a branch is safe to delete rather than guessing:
  `git merge-base --is-ancestor <branch> origin/main`. If ancestry does not hold,
  review unique commits and patch equivalence before retiring it.
