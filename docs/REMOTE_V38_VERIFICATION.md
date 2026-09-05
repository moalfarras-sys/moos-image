# Mo PC Remote v38 — verification report

This is the report `PROJECT_STATE.md` points to for the v38 connection/input revision
(`fix/remote-control-audit-20260904`). It records exactly what was run, what passed, and
what remains unverified — no claim below is made without a command or a screenshot behind it.

## What this revision changes

Reconnect/session robustness on both ends of the WebSocket, so a phone entering/leaving Wi-Fi,
switching tabs, or losing the network mid-session recovers instead of hanging or dropping input:

- **Controller (`moremote/controller/src/lib/ws.ts`)**: a monotonic connection generation plus
  `finishConnection()` retire path replaces the old ad-hoc close handling, so a stuck
  `CONNECTING` socket (a network change can leave that open-ended) is force-retired by a
  10s connect timeout instead of hanging forever. `authenticated` gates `.open` so input
  cannot queue against a socket that is merely TCP-connected but not yet authenticated.
  The stall watchdog and the ping probe both route through the same retire path.
- **Agent (`moremote/agent/Web/StreamSession.cs`)**: a hidden/backgrounded viewer no longer
  drains frames just because another viewer keeps the shared H.264 encoder alive; resume
  after `watching` toggles waits for a fresh IDR instead of decoding into a stale GOP;
  pause serializes with in-flight input execution so a queued key-down cannot land after
  `ReleaseAll()`; fragmented UTF-8 control messages are decoded statefully instead of
  risking a split multi-byte character.
- **Linux input (`moremote/agent-linux/InputInjector.cs`)**: the pressed-key/button state
  change and its wire write now happen under the same lock, so a concurrent
  pause/disconnect `ReleaseAll()` cannot race a key-down and leave a stuck key on the real
  desktop; `Dispose()` is idempotent and drains pending text before releasing state.
- **Gestures/desktop input** (`gestures.ts`, `desktop.ts`): cancelled gestures, lost pointer
  capture, backgrounded tabs and pointer-lock exit all release held input through one path;
  letterbox hit-testing stops a drag from starting outside the mapped picture; AltGr and
  dead/composition keys no longer inject a phantom physical chord.

See [`moremote/docs/MOOS_REMOTE_ARCHITECTURE.md`](../moremote/docs/MOOS_REMOTE_ARCHITECTURE.md#v38-input-and-recovery-refinements)
for the mechanism-level write-up.

## What was actually run for this report (2026-09-05)

All of the following were executed against the current tree, not asserted from memory:

| Gate | Command | Result |
|---|---|---|
| Controller typecheck | `npm run typecheck` (tsc 7.0.2) | pass, 0 errors |
| Controller unit tests | `npm test` (Node native test runner) | 66/66 pass, incl. `ws-lifecycle.test.ts`, `decode-renegotiate.test.ts`, `desktop.test.ts` |
| Bundle freshness | `node tests/bundle-freshness.test.ts` | pass |
| Bundle matches source | `npm ci && npm run build`, diffed against committed `agent/wwwroot` | byte-identical |
| npm audit | `npm audit --audit-level=high` | 0 vulnerabilities |
| Shipped bundle tracked | `python3 tests/test_shipped_bundle_is_tracked.py` | **failed on first run** — see Findings |
| Linux agent build | `dotnet build agent-linux/MoRemoteLinux.csproj -c Release` | succeeds, 0 warnings |
| Stream session tests | `dotnet run --project moremote/tests/MoRemote.Stream.Tests -c Release` | pass — Unicode fragmentation, hidden-viewer suspension, IDR resume, input-loop teardown |
| Linux input tests | `dotnet run --project moremote/tests/MoRemote.Linux.Input.Tests -c Release` | pass — 13 assertions, ordering/recovery/disposal against a fake portal |
| Remote Python gates | full `just check` list (86 gates) | pass, except one pre-existing environment gap — see Findings |

## Findings from this pass, and what was done about them

1. **The committed bundle was stale relative to the branch's own source changes.** `vite build`
   emptied the output directory and wrote new hashed asset names
   (`index-BrcvjXxa.css`, `index-D48dB6DW.js`); `moremote/.gitignore` hides `agent/wwwroot/assets/`,
   so the new files were untracked and the old hashed files were still staged as tracked-but-deleted.
   Had this shipped, the agent would have served `index.html` for the missing script/style
   requests via its SPA fallback — a 200 status and a blank page, not a 404. Fixed with
   `git add -f` on the two new assets and `git rm --cached` on the two stale ones; the gate
   (`tests/test_shipped_bundle_is_tracked.py`) now passes.
2. **The two new .NET test executables had no fast CI feedback.** `MoRemote.Stream.Tests` and
   `MoRemote.Linux.Input.Tests` are already gated correctly: `Containerfile` and
   `Containerfile.arm` both `RUN dotnet run` them during the image build, so a regression fails
   that build before anything ships. But that build takes up to 180 minutes and needs a full
   buildah run, so the earliest a regression would surface was very late. Added a
   `remote-dotnet-tests` job to `.github/workflows/build.yml` (mirrors `remote-windows-build`'s
   pattern — its own `actions/setup-dotnet` step, unaffected by the image-build job's disk-space
   reclamation) that runs both executables on every push in about a minute.
3. **This report itself did not exist.** `PROJECT_STATE.md` linked to it before it was written.
   This file closes that gap.
4. One pre-existing, unrelated gate — `tests/test_boot_path_authorities.py` — fails in this
   sandbox because `systemctl` is not installed here; that is an environment limitation of the
   review sandbox, not a regression, and is unchanged by anything in this revision.

## Evidence

- `docs/evidence/remote-v38-desktop-en.png` — the native control center on the desktop session
  in English, showing live health rows (firewall, PipeWire, portal, input backend), the QR/secure
  URL, and the quick-mode toggle.
- `docs/evidence/remote-v38-phone-ar.png` — the phone PWA in Arabic (RTL), bottom nav
  (الإعدادات / الشاشة / لوحة لمس / الحافظة / كتابة) and the same control-center sheet reachable
  from a narrow viewport without overlap.
- `docs/evidence/remote-v38-settings-ar.png` — the Arabic settings sheet: cursor mode (فأرة
  ومفاتيح / لوحة لمس / لمس), mouse/scroll sensitivity, natural scrolling, haptics and the
  typing-zoom toggle, laid out without clipping at phone width.

Before local activation, a separate loopback instance (documented in `PROJECT_STATE.md`,
2026-09-05 entry) produced 111 real H.264/OpenH264 frame messages in seven seconds and reported
ready portal input; a focused GTK text field read back `MoOS العربية 😀` exactly through a remote
click, relative pointer movement and Backspace. That proof used a live portal session, not
intercepted transport — the browser-level tests above are separate and use a mocked WebSocket.

## Scope and known limits (unchanged by this report)

These are not run anywhere in CI or in this pass and remain open acceptance items in
`MOOS_ROADMAP.md`:

- Physical Android/iOS keyboards, Safari's IME/selection/autocorrect behavior, and
  background/resume on a real phone browser.
- Real Internet loss/latency matrices (only the local-loopback and unit-test-simulated
  reconnect paths are exercised here).
- Windows runtime input. The Windows agent compiles cleanly
  (`dotnet build moremote/agent/MoRemoteAgent.csproj -c Release`, run in the separate
  `remote-windows-build` CI job on `windows-latest`), but nothing runs it against real Windows
  input APIs.
- Per-controller held-key ownership: two simultaneously authenticated controllers still share
  one `InputInjector`; only the view-only-vs-active teardown distinction is fixed in this
  revision.

This is a local Remote deployment audit, not a new signed OS release; it does not by itself
change what ships in `moos`/`moos-nvidia`/`moos-cloud`.
