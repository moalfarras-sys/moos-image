# The MoOS agent guide — the map, the mines, and the backlog

`AGENTS.md` is the **rules**. `PROJECT_STATE.md` is the **terrain**. This file is
the thing neither of them is: a map of *which files can hurt you*, and an honest
list of *what is still not done and how to do it*.

Read `AGENTS.md` first. It is short and it is binding. Then read this.
For **visual** work read `docs/MOOS_DESIGN_PLAN.md` before either — it
carries the measured design findings and the ordered plan.

---

## 0. The one habit that matters

**Never write "done" for something you did not watch happen.**

Every claim in this repository is supposed to be backed by a command that ran and
returned output. That is not a style preference — `PROJECT_STATE.md` documents
five separate occasions where a gate was green and the shipped thing was broken.
The gates check what someone thought to check; they cannot see the screen.

The honest loop, in order:

```bash
bash -n build_files/build.sh                  # syntax first, it is free
python3 tests/verify_user_experience.py       # the big one, ~3 s
# ... the full CI list — extract it rather than retyping it:
python3 - <<'EOF' > /tmp/gates.sh
import pathlib
y = pathlib.Path(".github/workflows/build.yml").read_text()
step = y.split("- name: Repo gates")[1].split("- name: Resolve registry")[0]
cmds = [l.strip() for l in step.splitlines()
        if l.strip() and not l.strip().startswith("#") and l.strip() != "run: |"]
print("set -o pipefail")
for c in cmds:
    print(f'echo "### {c}"; {c} || echo "!!!FAILED: {c}"')
EOF
bash /tmp/gates.sh 2>&1 | grep -c '!!!FAILED'   # must print 0
just build                                     # ~20 min, runs every IMAGE gate
```

Then **look at it**. A screenshot, a live readback, a pixel. See §4.

---

## 1. The sensitive files — ranked by what breaks

### Tier 1 — get this wrong and the machine does not boot

| file | why it is dangerous |
|---|---|
| `build_files/build.sh` | builds the whole image; a bad line fails at minute 20 of CI, or ships a broken `/usr` |
| `Containerfile` | the pinned base; changing it changes every edition at once |
| `system_files/usr/lib/dracut/**`, anything initramfs | a bad initramfs is an unbootable machine, and the failure is at boot, not at build |
| `/etc/pki/containers/moos.pub` + the signature policy | break it and `bootc` refuses every update, including the one that would fix it |
| `.github/workflows/build.yml` | the only thing that signs images; a broken matrix means no signed update reaches anyone |

Rule: for anything in Tier 1, the previous deployment must stay bootable
(`bootc rollback` / the second GRUB entry). Check before you reboot:

```bash
rpm-ostree status | grep -c 'ostree-image-signed'   # expect >= 2
ls /boot/loader/entries/*.conf | wc -l              # expect >= 2
```

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

These are not documented anywhere else and each one has cost a session.

### 2.1 A running plasmashell overwrites your config edits

plasmashell holds the panel config in memory and **flushes it over the file when
it exits**. Edit `plasma-org.kde.plasma.desktop-appletsrc` while it runs and your
change is silently reverted.

```bash
kquitapp6 plasmashell                        # stop FIRST
for i in $(seq 1 25); do pgrep -x plasmashell >/dev/null || break; sleep 1; done
# ... now edit the file ...
setsid plasmashell >/dev/null 2>&1 &         # then start
```

`plasmashell` on this system is **session-launched, not a systemd unit** —
`systemctl --user restart plasma-plasmashell.service` is a silent no-op.

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
`tests/verify_user_experience.py`); move them with it.

### 2.5 The motion gate floors at 1, not 0

`Kirigami.Units.longDuration` never reaches 0, so `longDuration > 0` is **true
even with animations fully disabled** and the gate never fires. Use `> 1`.
`verify_user_experience.py` refuses `> 0` in a motion gate by name, and it also
refuses an *alias*: an `Animation.Infinite`'s `running:` must name the gate
itself, not a derived property, because the checker cannot follow an alias.

---

## 3. How a change reaches every edition

One tree, one `Containerfile`, three matrix variants — `moos`, `moos-nvidia`,
`moos-cloud`. **Anything under `system_files/` ships to all three automatically.**
There is nothing per-edition to remember; a new edition added to the matrix picks
up everything by construction.

The release path:

```
commit -> push to main -> CI builds + cosign-signs all three
       -> moai-do update (stages the signed digest)
       -> reboot -> moos-apply-theme runs the THEME_REV migration at login
```

Verify a release rather than assuming it:

```bash
skopeo inspect docker://ghcr.io/moalfarras-sys/moos-nvidia:latest \
  | jq -r '.Labels["org.opencontainers.image.version"], .Labels["org.opencontainers.image.revision"]'
# the revision MUST be the commit you pushed, or the registry is serving a rebuild
```

### Two ways delivery fails silently — check for both

**1. A push to `main` does not always create a workflow run.** It has silently
failed to trigger; if no run appears within a few minutes,
`gh workflow run "Build MoOS image" --ref main` produces one, and the
`concurrency` group makes that safe.

**2. One edition can be left behind.** The three editions build as independent
matrix jobs, so a run whose overall conclusion is `cancelled` or `failure` may
still have SIGNED two of them. `moos-nvidia` is the one that fails: it layers
the NVIDIA driver, and the GitHub runner is disk-constrained — it has been
killed mid-`buildah` with every repo gate already green. The result is the
dangerous state: `moos` and `moos-cloud` publishing the new commit while
`moos-nvidia` still serves the previous one, which is the edition the
maintainer's own machine tracks.

**Never read the run's top-level conclusion alone.** Check per-edition, at the
registry, which is the only thing users pull from:

```bash
for i in moos moos-nvidia moos-cloud; do
  printf '%-12s ' "$i"
  skopeo inspect docker://ghcr.io/moalfarras-sys/$i:latest \
    | jq -r '"\(.Labels["org.opencontainers.image.version"])  rev=\(.Labels["org.opencontainers.image.revision"][0:8])"'
done
# every revision MUST equal the commit you pushed
```

**3. GHCR rate-limits you, and it looks like a permissions error.** Every push
to `main` builds AND pushes three images. Do that six times in an afternoon and
the registry answers:

```
denied: permission_denied ... HTTP status code 403 "Forbidden"
  "You have exceeded a secondary rate limit."
```

It reads like a broken token. It is not — it is throttling, and it hits ONE
edition while the other two finish, leaving exactly the split state above. The
only fix is to wait and re-run the losing job.

So: **batch your work into one push.** A commit is cheap; a push costs three
image builds and three registry uploads. Committing five times and pushing once
is the same history and a fifth of the load.

To repair just the edition that lost, rather than rebuilding all three:

```bash
gh run view <run-id> --json jobs \
  --jq '.jobs[] | select(.conclusion!="success") | "\(.databaseId) \(.name)"'
gh run rerun --job <job-id>
```

Before promising "it will apply after reboot", read it out of the deployment the
machine will actually boot:

```bash
STAGED=$(ls -1dt /ostree/deploy/default/deploy/*.0 | head -1)
grep -o "THEME_REV=[0-9]*" "$STAGED/usr/bin/moos-apply-theme"
test -e ~/.local/state/moos-ui2-theme-applied.v<REV> && echo "migration would SKIP" || echo "migration WILL run"
```

---

## 4. How to actually see the desktop

```bash
export XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-0 \
       DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus
spectacle -b -n -f -o /var/home/moos/.cache/shot.png
```

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

## 5. What is NOT done — the honest backlog

Ordered by value. Each entry says what it is, why it is not done, and how.

### 5.1 Launcher keyboard flow and final clock scale proof

**State:** the launcher now owns its card hierarchy and staggered reveal. The
panel clock now owns a responsive full day/calendar surface and has live Arabic
evidence at 100/125/150%. The remaining claims are narrower: keyboard-first
launcher navigation and final 200/225% clock frames on 4K.

**How:** audit arrow-key movement through launcher favourites/results and the
focus return path after launch. For the clock, boot the signed artifact at 4K
200/225%, capture dark/light and Arabic/English, and prove the popup stays inside
the available work area. Do not redesign the popup again without a failed frame.

### 5.2 Mo AI "thinking" is missing from the context island

**State:** the island reads MPRIS only. Mo AI's sole signal today is the **mtime**
of `/run/$UID/moai-activity`, and a directory watcher does not reliably see a
touch that changes no listing. Shipping it would have been a state that lies.

**How:** have `moai-gateway` write a real state file (a word: `idle`/`busy`) and
watch it with `FolderListModel`. Note **`FolderListModel` cannot see unix
sockets** — proved by measurement: three matching names in a directory, two
sockets and one regular file, and the model reported `count=1`. So the Mo PC
Remote session state needs a regular marker file too; the frame socket is
invisible to it.

### 5.3 The task area is off geometric centre

**State:** accepted and documented in `moos-bar.conf`. The system zone outweighs
the launcher, so the tasks sit slightly right of centre. Rev 30 fixed this by
splitting the bar into two capsules; **the owner rejected that on sight and it
was reverted in rev 33.** Do not re-split the bar — a gate now prevents it.

**How, if it is ever addressed:** inside ONE surface only — a balancing spacer
applet, or a launcher and system zone of matched width.

### 5.4 Dock icon hover/active motion is not reachable

**State:** the task icons are Plasma's stock `icontasks`, and its `Task.qml` is
compiled inside `org.kde.plasma.taskmanager.so`. Hover/active motion on the
dock icons cannot be added without replacing the whole task manager.

**How:** a MoOS task manager applet is a large piece of work (drag-reorder,
grouping, window previews, launcher pinning). Do not start it casually.

### 5.5 Visual sweep at other scales

**State:** everything visual is verified at 4K@225% only. 100/125/150/200% has
never been swept.

**How:** `kscreen-doctor output.HDMI-A-1.scale.1.5` then screenshot the dock,
launcher and a popup at each step.

---

## 6. Before you push

- All CI gates green (§0), and `just build` exit 0.
- `THEME_REV` bumped if any shipped SVG or plasmoid QML changed, with both pinned
  gates moved.
- Every home override under `~/.local/share/plasma/` removed.
- `PROJECT_STATE.md` and `MOOS_ROADMAP.md` updated concisely — **including what
  you did NOT finish**. Git history replaces per-session continuation journals.
- Branches: work on a branch, then merge to `main`. After merging, retire it.
  Verify a branch is safe to delete rather than guessing:
  `git cherry main <branch>` — every line starting `-` is already upstream.
