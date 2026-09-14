# Developing on the installed MoOS workstation

Read this for live diagnostics, editor/SDK setup or desktop review. This computer
is the engineering station for the OS it runs. Keep the checkout and the running
deployment independently identifiable throughout the task.

## Establish the environment

Inside VS Code Flatpak, `/usr` belongs to its SDK runtime. Inspect the actual
machine through `flatpak-spawn --host`; run Git authentication and Podman there.
Use the shared checkout path as an argument, never interpolate untrusted text
into a shell command. From a host terminal, omit the Flatpak wrapper.

The visual/image suite imports Pillow and other host development dependencies.
From VS Code Flatpak, run `flatpak-spawn --host just check` (not the editor
runtime's `just check`); a missing module is a workstation-environment defect,
not a reason to skip the image test.

```bash
git status --short --branch
git log -1 --format='%h %s'
bash scripts/setup-development-machine.sh --check
flatpak-spawn --host rpm-ostree status --json
flatpak-spawn --host systemctl --failed --no-pager
flatpak-spawn --host systemctl --user --failed --no-pager
flatpak-spawn --host df -h /var
flatpak-spawn --host kscreen-doctor -o
```

Record booted version, exact digest, signed transport, rollback and any staged
deployment. Do not dump the whole environment, private provider configuration,
Git credentials or command histories. Capability-check output can contain local
tool paths; it is not a shareable anonymized support bundle.

Record the target edition/architecture for every check. This workstation's
NVIDIA x86 evidence says nothing about an Oracle ARM instance, a cloud VM or a
new ISO until those targets are actually accessed and tested. A plan mentioning
Oracle is not evidence of a connected or working Oracle deployment.

## Observe before changing

- Resolve a service's actual unit and process cgroup. Stopping an inactive unit
  can succeed while an unmanaged daemon survives; prove ownership before cache
  deletion or starting another instance.
- A process, open port or `/healthz` response proves liveness only. For Mo AI,
  separately verify configured provider, key presence, model policy and one
  synthetic reply. Distinguish missing/invalid key, billing/quota, network and
  provider outage. Never transfer one provider's key to another or test a paid
  route without an explicit paid choice.
- `/var` measures writable storage; composefs `/` does not. RPM installed-size
  metadata may include already-scrubbed files. Check actual bytes and reverse
  dependencies before proposing package removal.
- Attribute crashes using executable, time, command line and cgroup. A rootless
  image-build scriptlet crash is not a desktop app crash. Do not suppress host
  crash reporting merely to make the audit quiet.
- Measure boot and idle separately from active builds, browsers and editors.
  State sampling duration and workload. Lifetime CPU averages are not idle CPU.

## Review visible behavior

Use the active user's session, not a root shell with a borrowed runtime path.
`moai-open` resolves Wayland/XWayland state and launches an app in a detached
user unit. Record that unit and inspect its journal for exit/runtime errors.
Do not guess `wayland-0`, a UID or that an old session socket still exists.

Capture evidence into a uniquely named directory on real disk under the user's
cache or ignored `test-results/`. Keep private desktop captures local. Select
only necessary redacted images for a CI/review artifact; do not add a screenshot
archive to Git.

For Settings, `tests/qml/settings-review.qml` loads source QML without installing
an override. Read it first: it can exercise navigation and has an optional route
launch. The installed `/usr/libexec/moos-settings-status` publishes a private
read-only status snapshot. Pass that file with `--status=file://…`, an existing
`--out=…` directory, the intended width/height and expected `--rtl=true|false`.
Refresh the snapshot immediately before each run or keep its existing bounded
watcher alive. The UI rejects stale status; keyboard tests alone must not count
disabled real actions as a healthy review. The harness now fails without fresh
status or when a capture cannot be saved.
Set locale only on the review process; never change the user's session language
for a fixture. The harness types into its own window, so avoid concurrent input.

Check screenshots for clipping, focus, contrast, missing icons and RTL order.
Read the interaction assertions and runtime log as well. Distinguish:

1. Source harness: proves that source surface against the installed Qt stack.
2. Installed app: proves the current deployment's surface and live backend.
3. Booted candidate: proves the deliverable users will receive.

Do not count one as another. Never change a theme or replace artwork simply
because the task asks for polish; identify a failed frame or missing flow first.

When reviewing a shared QML component, set `QML_IMPORT_PATH` on the review
process to the source module root. A source app importing the installed module
does not test changes to that module. `tests/qml/motion-review.qml` exercises
real spring settling, reversal, interruption, hidden state and button input;
`build_files/verify_moos_motion.py` isolates its bus/display/home for image tests.
Use a detached Wayland review separately for rendered evidence. Never export
the review import path globally into the desktop's user manager.

## Leave a usable workstation

SDKs and editor extensions belong to the development profile, not automatically
to the shipped OS. Prefer upstream versioned artifacts, verify their published
hashes, install in user space or a development container, and execute the real
component check. An editor runtime is not a compiler SDK. Avoid duplicate AI
extensions, unrelated extension packs and global compilers in the base image.

Before finishing, re-read live health/theme state, close only review units you
started, remove your temporary runtime overrides if any, and verify Git status.
Update the existing state and plan with what changed, what ran, what is still
unproven, and the next task. A pushed PR is source publication; a promoted digest
and a reboot/readback are separate release and machine outcomes.
