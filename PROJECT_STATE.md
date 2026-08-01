# MoOS — where the project actually is

**Read this before touching anything.** It is the map an agent needs on day one:
what exists, what is load-bearing, and which of the "obvious" things to do next
are traps that have already cost this project a day.

Last updated: 2026-08-01 — the Mo AI Workspace rebuild is merged on `main`,
published and booted. GitHub Actions run `30704582346` built, pushed, cosign-
signed and verified `moos`, `moos-cloud` and `moos-nvidia` from merge
`77707fd1461774b931518df14a418e9286251ba4`. The maintainer machine is booted
from signed NVIDIA digest
`sha256:c73d9002efb3db9ffc2c6c2d4a7141b17d8af5e283172adb3c2790dccc0731e7`
with kernel `7.1.5-201.fc44.x86_64`; the previous deployment remains available.

Working-tree correction, later on 2026-08-01 (`push-temp`): the unpublished
`0a6a05d3` glass pass replaced the reviewed Tidal Cut doorway with a full-frame
`Qt5Compat.GraphicalEffects` DropShadow (65 samples plus an offscreen layer) in
Splash, Login, Lock, Logout and first-party apps, then changed three regression
gates to require that implementation. This was an identity and GPU-cost
regression, not accepted polish. Commits `2811e138`, `b2ddb444` and `c0154aa0`
restore the code-native Qt Quick Shapes horizon and make the gates require its
cut/gradient geometry again across all 38 synchronised copies. The Cloud-hosted
repo gate suite passes by executing the complete `just check` recipe directly
(`just` itself is absent). Minimal Cloud Python also exposed two real portability
defects: DOCX/ODT MIME detection depended on a host MIME database (`a7dc930b`
now recognises the three supported document suffixes deterministically), and two
runtime gates crashed on a partial non-PyGObject `gi` namespace (`41c40bf4`,
`b2ddb444` now retain their pure contracts and skip only unavailable GTK/KDE
runtime checks). Mo PC Remote's available source gates pass for capture rebuild
coalescing, non-blocking input, resolution negotiation, H.264 fallback/restart,
authenticated sound, private Cloud desktop, PIN ownership, subids and per-user
ports. This Cloud environment has no Node/npm, .NET, systemd, Qt/KDE runtime or
display, so controller compilation, image compose, live phone control and new
Light/Dark × RTL/LTR × 4K captures remain explicitly unverified in this round.
The same round later gained a real isolated Node build environment verified
against Node's published SHA256 for the current LTS `v24.18.0`. Mo PC Remote's
controller now cancels generation-bound reconnect timers on logout/unmount
(`1ac17902`), closing a ghost-socket path that could restart streaming after the
screen had exited. Its committed PWA was rebuilt deterministically after moving
to React 19.2.8, Vite 8.2.0, TypeScript 7.0.2 and vite-plugin-pwa 1.3.0
(`d66a3ff6`); `npm ci`, controller tests, `tsc --noEmit`, two byte-identical
builds and `npm audit` (0 vulnerabilities) passed. CI now enforces typecheck and
audit before comparing the shipped bundle. `@vitejs/plugin-react` remains on
5.2.0, the newest cleanly resolving line that supports Vite 8; 6.0.5 currently
has an unsatisfied Babel 8 peer graph and was not forced with legacy resolution.
Cloud audio cleanup is bounded after both TERM and KILL, and Mo AI activity
stamps use unique atomic temporaries under concurrent requests (`9f120c27`).
Two duplicated troubleshooting reports that exposed an owner phone number and
an unsafe allow-all example were removed; `tests/test_docs_privacy.py` now gates
the repository and CI (`2877c228`). The complete repo `just check` recipe passes
after these changes. Image compose, installed-service proof and a real phone
session remain open.

Session/login/power accessibility correction, later in the same unpublished
Cloud audit (`4073365e`, `e5c18d9b`, `2c298613`, `d51a1252`): the shared logout action had a visible keyboard focus ring,
four-direction navigation, a name and a description, but relied on
`AbstractButton` to infer its assistive role while running in ksmserver's
out-of-process greeter. All 16 theme copies now explicitly expose
`Accessible.Button` and their transient pressed state. A repository gate holds
the role, name, description, pressed state, strong focus policy and arrow-key
contract. The complete `just check` recipe passes. This is source/gate evidence,
not a live screen-reader claim; Qt/KDE runtime and live Light/Dark × RTL/LTR ×
4K verification remain open on an installed image. The lock screen now follows
the same explicit contract: Password has a stable accessible name and Unlock
exposes Button role plus pressed state, while preserving its real PAM path. The
actual Plasma Login Manager components now expose the same complete contract.
Most importantly, UserDelegate's inert `function accessiblePressAction()` was
replaced by the Qt-supported `Accessible.onPressAction`, so assistive activation
selects a user through the same real click signal; Enter and Return now match
Space. The compiled greeter's shared action button also routes assistive presses
through its existing `animateClick()` path.
The greeter's four button transitions and three user-selection transitions now
also resolve to a literal zero duration when `AnimationDurationFactor=0`; both
components are registered in the real Qt motion-gate test. The Cloud source gate
passes, while the runtime branch remains explicitly pending an image environment
with Qt/KDE and `kwriteconfig6`.
The same audit then closed the lock surface (`ebcebc57`): all eight auth-card
transitions and six scene transitions are explicitly duration-zero when motion
is disabled, and a repeated authentication notice no longer starts its bounce.
PAM, grace timers, password bindings and unlock signals remain unchanged. Both
lock files are now held by the real Qt motion-gate test; the complete repository
check recipe passes on Cloud, with its Qt runtime branch honestly skipped.

Mo PC Remote server proof, later in the same Cloud audit: Microsoft’s temporary
.NET 10.0.302 SDK ran the exact Containerfile test (`21` mapping, validation and
Unicode checks) and published the Linux agent self-contained in Release with no
compiler warnings. The resulting 109 MB distribution was launched on isolated
loopback port `18765`; a real HTTP sequence proved fresh status, PIN setup,
token revoke/logout, rejection of a wrong PIN, successful login, and delivery
of the committed React PWA. Its config landed mode `0600`. `MOREMOTE_DATA_DIR`
is now an explicit absolute-only service/container boundary with a deterministic
per-directory mutex, so an isolated validation instance cannot read the owner's
live configuration or be suppressed by the live agent (`65ac6d71`). A relative
override was actually run and rejected nonzero. NuGet reports no known
vulnerabilities for the Linux project. ImageSharp 4.0 was tested but its build
requires a separate Six Labors commercial license; the project therefore stays
intentionally on the newest license-compatible 3.1.11 line, with a gate that
prevents an automated major bump from breaking the image build. The complete
repo gate recipe passes after this server proof. Screen capture through the real
KDE portal, phone input over a real tailnet, image compose and installed-service
behavior remain separate open proofs.

Mo PC Remote power/session audit, later on 2026-08-01: the Linux agent's five
buttons were not real. It sent `lock-session` and `terminate-user` to
`systemctl` (both belong to other session interfaces), and treated
`Process.Start` as success even when the command immediately failed. Commit
`59600e7d` now uses fixed-argument Plasma D-Bus calls for the exact user
session, non-blocking logind operations for suspend/reboot/poweroff, and checks
timeout plus exit status. The .NET suite now has 32 tests including accepted,
rejected and hung-process execution; Linux publish succeeded. The next audit
found a multi-user Cloud boundary: an authenticated developer PIN could expose
sleep/reboot/poweroff for the shared server. Commit `c489d10c` bakes an
authoritative edition marker and initially rejected the three host operations.
A follow-up lifecycle audit found that Cloud accounts are passwordless by design
(Lock is therefore unrecoverable) and that clean Sign out stops their private
desktop because its supervisor correctly uses `Restart=on-failure`. The Cloud
API and phone now withhold all five session/power operations and explain that
the server console owns them; desktop MoOS retains all five controls.
The committed PWA is v16; Linux and Windows agents build with zero warnings,
controller tests/typecheck/build pass, and the complete repo check recipe is
green. No destructive power command was run on the audit host. Image compose,
installed Cloud service behavior and a real tailnet/phone session remain open.

Mo PC Remote transfer/authentication audit, later on 2026-08-01 (`67e58e6a`):
native downloads and the HTML audio element embedded the reusable session bearer
in their query strings, exposing it to browser/proxy history and copied URLs.
Both now exchange the Authorization header for a cryptographically random
256-bit, purpose-bound, single-use ticket that expires after 45 seconds. An
isolated real HTTP run proved download `200`, replay `401`, missing ticket `401`;
an audio ticket reached the absent upstream (`502`) and replay was still `401`.
Uploads no longer stream directly into the visible destination: each file is
limited to 1 GiB at Kestrel and application boundaries, written to an isolated
partial, removed on disconnect/error, moved atomically only after completion,
and stops before consuming the final 512 MiB of its actual longest-matching
filesystem. Space checks are paced at 64 MiB rather than per 128 KiB network
chunk. Ticket storage is capped at 1024 entries with amortised O(1) FIFO
eviction (`a5d9e954`); it no longer scans the entire dictionary on every issue,
which made an authenticated issuance burst quadratic. The .NET suite now passes
48 tests including pressure bounds, ticket replay/purpose
confusion and interrupted-upload cleanup; Linux publish, Windows build (zero
warnings), TypeScript typecheck, controller tests, committed PWA v17 and the
complete repo check recipe all pass. A real phone/tailnet transfer and full
image compose remain open release evidence.

Mo PC Remote asynchronous lifecycle audit (`44ab6880`): Refresh owned a raw
120 ms `setTimeout(connect)` that could reopen a socket after Disconnect/Sign
out, and an audio-ticket request could finish after Stop and begin playback
behind the user's back. Refresh/Reconnect/Disconnect now retire one owned timer;
audio start and retry results are generation-bound, Stop/unmount invalidate the
generation, remove the media source and close the upstream encoder. Toast and
first-use hint timers are also cleared on unmount. The new
`test_remote_async_lifecycle.py` gate runs in local checks and CI, the committed
controller is PWA v18, TypeScript/controller tests pass, and the complete repo
check recipe is green.

Phone sign-out audit (`dcdb9c0c`): the UI's Sign out path only cleared
`localStorage`; it never called the already-existing `/api/logout`, so a copied
bearer remained valid server-side for up to the 60-minute session TTL after the
user saw the login screen. `App.exitToLogin` now awaits server revocation before
returning to authentication while retaining offline-safe local clearing. The
new relationship gate is wired into local checks and CI, PWA v19 is committed,
and the complete repo check recipe passes. The server revocation endpoint itself
was already proven in the isolated HTTP login/logout sequence earlier in this
audit; this change connects the real phone action to it.

Mo PC Remote phone interaction/accessibility audit (`aad4a25c`): Display,
Settings, Files and Clipboard were visual bottom sheets only. Focus stayed on
the desktop behind them, Tab could escape into hidden controls, Escape did not
close them and no dialog semantics reached a screen reader. All four now share
one modal SheetPanel that moves focus in, traps Tab/Shift+Tab, closes on Escape,
restores the invoking control and exposes a labelled close target. The clickable
connection pill is a real disclosure button with an accurate expanded state;
connection changes and transient confirmations are polite live announcements.
The content-editable image paste target remains inside the focus loop. A source
regression test is part of `npm test`; TypeScript, production build, two
byte-identical builds, zero-vulnerability npm audits, shipped-asset tracking and
the complete repository check recipe pass. The committed controller is PWA v20.
Touch/VoiceOver/TalkBack proof on a real phone remains open release evidence.

Remote PIN interaction follow-up (`32de7625`): the connect/setup screen was
touch-only despite using native buttons—physical number keys, Backspace/Delete
and Enter did nothing. It now gives hardware keyboards the exact keypad path,
announces only the entered digit count (never the secret), and disables the
entire keypad atomically during a login/setup request or server lockout instead
of leaving controls that visibly press but are ignored. The regression test,
TypeScript, zero-vulnerability audit, deterministic production rebuild, shipped
asset gate and complete repository check pass. The committed controller is PWA
v21; real mobile keyboard and screen-reader proof remains open.

Remote Reduced Motion follow-up (`d78ac6cc`): the PWA previously honoured the
system preference for only the settings switch and disclosure chevron while 18
other animations/transitions—including the perpetual connecting spinner,
sheets, toast, toolbar and keypad feedback—continued. One global policy now
stops animations and transitions for every element and pseudo-element and keeps
scroll state changes immediate; it does not use a near-zero-duration workaround.
The source gate, TypeScript, npm audit, deterministic production rebuild,
shipped-asset gate and complete repository check pass. The committed controller
is PWA v22; a real phone setting toggle remains open visual evidence.

Remote sensitive-power confirmation audit (`34a1f8b0`): Sign out, Restart and
Shut down used the browser's `window.confirm()`, producing an unthemed platform
dialog outside the Liquid Glass interaction and an untestable focus path. They
now use a MoOS `alertdialog` built on the same modal/focus contract as the phone
sheets, with Cancel focused first, explicit unsaved-work consequences and a
single shared API execution path. An atomic in-flight guard prevents a fast
double tap from issuing the action twice. Once submitted, the dialog becomes a
non-dismissible Working state because closing it cannot cancel a command already
delivered to the host. Cloud still exposes none of these host actions. The source
gate bans `window.confirm` and holds confirmation-before-API plus single-flight;
TypeScript, npm audit, deterministic production build, shipped assets and the
complete repository check pass. The committed controller is PWA v23. A safe
non-destructive live confirmation run on desktop MoOS remains open evidence.

Remote authentication-handoff audit (`b8ff5480`): a network drop during
`login()` or first-time `setupPin()` threw past the screen and left `busy=true`,
permanently disabling the keypad. A second race happened after the server issued
a token: if the immediate status read failed, `enterRemote()` leaked a rejected
Promise with no recovery UI. Both auth screens now catch network failure and
release busy through `finally`; successful handoff deliberately avoids updating
an unmounted screen. App stores the issued token, enters an accessible Loading
state, and on status failure shows a Retry path that reuses the token rather than
asking for the PIN again. Non-2xx `/api/status` is rejected instead of parsed as
a valid status. A Node behavior test proves HTTP 503 rejection and gates both
handoffs. TypeScript, npm audit, deterministic production build, shipped assets
and the complete repository check pass. The committed controller is PWA v24;
an actual mid-handoff network interruption on a phone remains open live proof.

Remote control-plane timeout audit (`99c66235`): rejection handling still did
not cover a black-holed mobile network, where `fetch()` could remain pending for
minutes and pin Login, Setup or a power action in its busy state. Short JSON
control requests now share a 15-second `AbortController` boundary, relay a
caller's own abort signal, and always remove the relay listener and timer. File
uploads and media streams intentionally remain outside this boundary because
they are valid long-running transfers. A Node behavior test proves that a
never-resolving request is aborted; TypeScript, npm audit, deterministic
production build, shipped-assets gate and the complete repository check pass.
The committed controller is PWA v25. A real tailnet black-hole test from a phone
remains open live proof.

Remote Linux network-boundary audit (`efaa3c98`): the Linux agent still used
Kestrel `ListenAnyIP`, leaving a raw cleartext port beside the intended
Tailscale-Serve HTTPS door. Its CGNAT-range middleware was not an interface
boundary, and the Cloud account manager had escaped the earlier audio fix: it
still created an unauthenticated `/audio` sibling mount for both the seat owner
and private desktops. Linux Kestrel now listens on loopback only; Desktop and
Cloud publish that single door through Tailscale Serve. Both Cloud setup paths
actively retract legacy audio mounts, and Doctor now treats such a mount as an
exposure instead of a requirement. Sound remains available through the agent's
authenticated, one-use-ticket proxy. A new regression gate covers the listener,
both publishers, the truthful startup log and the Cloud audio path, and is part
of `just check`. Runtime proof against the built .NET agent returned HTTP 200 on
loopback and refused both the host network and tailnet interfaces; .NET built
with zero warnings, all 48 behavior tests passed, and the complete repository
check passed. A real phone connection through Tailscale Serve remains open live
proof.

Remote trusted-device lifecycle (`d4364fe7`): “trusted device” previously meant
only an access bearer in browser `localStorage`; the server kept it in memory,
had no device identity or inventory, and every agent restart forced a PIN while
leaving the UI to try a dead token. Trust is now explicit on Setup/Login and
separate from the short-lived access session. The phone receives a 256-bit
device secret once; Linux stores only its SHA-256 hash in the mode-0600 config
and Windows keeps the same hash inside its existing DPAPI-protected config.
Credentials expire after 30 days, are capped at 16, carry a sanitized device
name and last-used time, and changing/resetting the PIN removes all of them.
The PWA validates an access token before entering Remote, resumes through the
device credential after an agent restart, and exposes an owner-visible Settings
inventory with individual removal. Sign out removes both the access session and
the current trusted credential. The server also closes the first-run setup race
inside the same authentication lock, rather than relying on the earlier HTTP
check. A new gate covers Linux/Windows persistence, hashing, bounds, API, PWA
handoff, consent, inventory and revocation. Live HTTP proof showed the old bearer
return 401 after restart, device resume/list/revoke return 200, and replay after
revocation return 401. Linux and Windows .NET builds completed with zero
warnings; 61 core behavior tests, PWA tests/typecheck, npm audit (zero findings),
deterministic PWA v26 build, shipped-assets gate and the complete repository
check pass. Touch/visual confirmation on a physical phone remains open evidence.

Remote transfer resource-bound audit (`21008908`): authenticated clipboard-image
upload copied the complete HTTP body into a `MemoryStream` before checking the
25 MB limit. Kestrel permits the file-transfer ceiling of 1 GiB, so one trusted
client could make the agent retain close to a gigabyte and be killed by memory
pressure. It now rejects declared oversize bodies before reading and uses a
shared streaming reader that asks for only one byte beyond the remaining cap;
the rejected byte is never followed by buffering the rest. Directory browsing
also stopped materializing and sorting an unbounded folder: enumeration is
materialized inside its exception boundary, capped at 500 entries, and reports
`truncated` visibly in the phone UI instead of pretending the response is
complete. Exact-limit, one-byte-over, 520-entry truncation and partial-upload
cleanup are behavior tested. Linux and Windows .NET builds have zero warnings,
65 core tests pass, PWA tests/typecheck and npm audit pass with zero findings,
the PWA v27 production build is deterministic, and the shipped-assets and full
repository gates pass. A real large transfer interrupted over a phone tailnet
remains open live evidence; automatic background folder sync is not claimed.

Remote resumable-download audit (`a8689686`): the download URL previously held
a one-use capability, so enabling HTTP Range alone would have made the first
partial request consume the ticket and every retry fail. Downloads now receive
a five-minute, resource-bound lease limited to 32 uses; wrong-purpose use burns
it, its FIFO shares the existing 1,024-capability memory ceiling, and audio
remains strictly single-use. The file response enables Range and supplies stable
Last-Modified plus length/mtime ETag validators so a browser does not splice two
versions of a changing file. Live HTTP proof against the built Linux agent used
one lease for two ranges: both returned 206, `bytes 5-9/37` and `bytes 10-15/37`,
with the requested payload and identical ETag. Linux and Windows builds have
zero warnings, 72 core behavior tests and the complete repository check pass.
This proves resumable downloads; bidirectional background folder sync remains a
separate, unimplemented protocol and is not claimed.

Remote resumable-upload audit (`e484249e`): the PWA formerly sent every selected
file as one request, so losing the final response forced a full restart and made
it unsafe to guess whether the server had accepted the bytes. Uploads now use an
owner-bound, 30-minute session and authoritative offset, with 4 MiB chunks, a
64-session ceiling and a 1 GiB file ceiling. Chunks are written to a hidden file
in the destination filesystem; only a complete commit atomically moves it into
place, incomplete/cancelled/expired sessions clean their temporary file, and a
name collision still uses the existing unique-name policy. The PWA fingerprints
the selected file from metadata plus its first and last 64 KiB before resuming,
shows byte progress, and queries status after a lost response instead of sending
the same bytes twice. Live HTTP proof against the built Linux agent wrote two
chunks around a deliberate duplicate-offset conflict: the conflict returned 409
with authoritative offset 3, no target existed before commit, commit returned
200 with exactly `abcdef`, and commit replay returned 404. Linux and Windows
builds completed with zero warnings; 84 core tests, PWA tests/typecheck, npm audit
(zero findings), shipped-bundle freshness and the complete repository check pass.
A follow-up audit found that the original expiry cleanup was request-driven: a
phone that vanished caused no later request, so its `.part` file could survive
for the lifetime of the agent. A five-minute timer now sweeps the bounded
64-entry table even while idle, is disposed with the agent services, and has a
clock-controlled regression test proving both session and file disappear after
expiry.
A service restart intentionally invalidates in-memory upload sessions, and a real
interrupted large transfer on a physical phone remains open evidence; automatic
background folder sync is not claimed.

Mo AI service lifecycle audit (`1cf194b3`, `017df8a6`): the ~386 MB OpenClaw
Node gateway used `Restart=always` with a heavy preflight but no start limit, so
a persistent binary/config failure could rebuild its stack every ten seconds
forever. It now permits eight attempts per five minutes—enough for intentional
clean reloads—then becomes visibly failed, and its stop is bounded at 30 seconds
instead of the systemd default 90-second logout/reboot stall. The on-demand
Ollama and ~1.5 GB Speaches Quadlets had the same unbounded five-second restart
shape; each now has a five-per-five-minute limit, and Ollama teardown is bounded
at 30 seconds. Explicit stop, wake-on-demand, clean OpenClaw reloads and
AutoUpdate behavior are unchanged. `test_moai_service_lifecycle.py` is in local
checks and CI; focused Mo AI tests and the complete repo check recipe pass.
This Cloud host has no systemd user runtime, so installed-unit restart-rate and
shutdown timing remain image/live evidence rather than claimed measurements.

Mo AI small-service lifecycle follow-up: the original gate covered only the
heavy OpenClaw/AI containers. `moai-control` could still restart every five
seconds forever, `moai-wake` had the same crash-loop shape, and the gateway's
30 attempts at a four-second cadence sat on the exact edge of its 120-second
window, so the limiter was not a reliable stop. Control now permits 6/120s,
gateway 12/120s, and wake 5/300s; Mo PC Remote receives the same 5/300s bound.
Control, gateway, wake, agent API, Remote and Cloud audio now have explicit
10–15 second stop bounds instead of the default 90 seconds. The regression gate
was also repaired: its section parser previously matched `[Service]` written in
a comment before the real header, so it could inspect dead text. It now matches
only actual systemd headers and verifies directive placement. Focused Mo AI
tests and the complete repository check pass. This off-image Cloud host lacks
`systemd-analyze`, so unit loading and shutdown latency still require the image
build/live system and are not claimed here.

OpenClaw deep health now proves Telegram `OK` and the owner's newly paired
WhatsApp account `LINKED`, both on the same gateway/session store. That live
pairing exposed a status bug: OpenClaw 2026.7 reports WhatsApp through
`connected`/`linked` rather than Telegram's `probe.ok`, so Mo AI rendered a
false disconnected state. The source API now consumes both contracts; a real
isolated source run returned both channels `connected:true`, WhatsApp account
with the owner's account redacted, mode `linked`. The bootstrap also pins the exact seven trusted
runtime plugins once WhatsApp exists, removing unrestricted extension discovery
without overwriting an owner-managed allowlist. `just check` passes with
regression tests. This post-pairing correction still needs its own signed
matrix/update before the installed UI contains it.

The pairing audit also found two lifecycle traps that would have made a linked
channel unreliable. OpenClaw exits successfully when a channel config reload
needs a full restart, so `Restart=on-failure` left both channels offline; the
signed unit now uses `Restart=always` (an explicit systemd stop still suppresses
restart). A legacy installer-created user unit also outranked that signed unit
forever and hard-required Ollama. The bootstrap now recognizes only its exact
old fingerprint, moves it to a private recoverable migration backup and reloads
the user manager; customised units and symlinks are untouched. Finally,
`openclaw-idle` no longer stops the sole WhatsApp Web receiver while WhatsApp is
enabled. The local model still unloads itself and frees VRAM after its keepalive;
machines without a persistent WhatsApp channel retain the lightweight Telegram
wake/sleep path. These contracts have behavioral/static gates and were applied
to the live account; their signed image update remains pending.

The first booted-image `post-update-check.sh` proved the published digest,
signature policy, MoOS identity/UI, Mo AI runtime, boot and zero failed units;
it returned 46/3 only because `$HOME` shadowed the image with an old `de,ara`
keyboard file and two hand-installed MoPlayer launchers. The MoPlayer shadows
were moved to recoverable
`~/.local/state/moos/post-update-backup-20260801-1810`; `/usr/bin/moplayer` now
wins. The keyboard file agrees with the image at `de,us,ara`, but the already-
running KWin process retains `de,ara` until the next login/reboot. A clean rerun
therefore remains open and must not be claimed yet.

Mo AI Workspace rebuild, first implementation slice
on `product/moai-workspace-rebuild-2026-08-01`. `MO_AI_ARCHITECTURE.md` is now
the durable architecture and completion ledger. The existing Qt/Kirigami and
Python stack is retained; no second Mo AI and no risky language rewrite was
introduced. `moai-agent-api` now owns separate atomic workspace metadata for
OpenClaw conversations (search/pin/rename/archive), canonical home-contained
projects and persistent task state. It also provides bounded user-owned PTYs:
the source UI was run on the live 4K RTL session and showed real shell output
from `printf 'Mo-AI-terminal-live\n'`, with tabs and process stop. Image/text
attachments now enter through a private non-executable store via picker or
drag/drop. PDF (first 50 pages), DOCX and ODT text extraction is real and capped
at 512 KiB; PDF uses fixed `pdftotext` argv and Office/ODF reads only an exact
bounded XML member, while unsupported binaries remain honestly metadata-only.
Vision routing now reads explicit model input metadata: Ollama's real
`/api/show` capability or provider-advertised `input`/`modalities`; it no longer
guesses from a model name, and uncertain routes remain text-only. A live PNG
request through the source Mo AI gateway and unified OpenClaw runtime reached
`qwen3-vl:4b` and returned `blue` in 17.6 seconds. Push-to-talk uses `pw-record`
→ the existing `moai-transcribe` path. A synthesized English speech proof was
auto-detected as `en` with 0.93 probability and returned `Hello, I am the MOAI
assistant.`; transcription now defaults to bilingual auto detection rather
than forcing every clip through Arabic. A real human Arabic microphone sample
is still not verified. The Speaches Quadlet now treats its known exit 137 after
clean ASGI shutdown as a successful idle stop, avoiding a false failed service.
`moai-gateway` gains
an explainable Hybrid route: sensitive data and attachments remain local by
default, complex work may use configured/reachable cloud, and routing/fallback
reasons are returned to the UI. The gateway now reads the same OpenClaw cloud provider/key written
by Settings, with the old Mo AI config retained only as an upgrade fallback;
this fixes a live contradiction where Settings reported Cloud linked but the
gateway returned `cloud brain not configured`. Source runtime proofs returned
the exact Cloud and Local markers, then routed Hybrid private to `local/privacy`
and Hybrid complex to `cloud/complex-task`, all HTTP 200 with
`X-MoAI-Agent: openclaw`. OpenClaw permissions are split into the four
real levels (read/project/system-with-approval/full). Tracked tasks now launch
the fixed OpenClaw agent command, persist real outcomes, expose pause/resume/
cancel, and ingest tool-call names from the OpenClaw session JSONL. The project
Workbench provides canonical-root file browsing, bounded UTF-8 preview and
fixed-argv Git status/diff; traversal and symlink escapes are tested, and a
bounded persistent audit ledger records task actions, project reads/diffs and
permission-policy changes. Agent process completion now adds a separate bounded
`task/finish` event for completed, failed, cancelled, timed-out or internal-error
outcomes with only exit status and observed tool names; model prompts and process
output are deliberately excluded from the audit record. OpenClaw tool outcomes
are now audited individually too: success/error and explicit
`missing-result`, bounded to the newest 8 MiB and 200 events, with only tool name
and a short call-id hash. Arguments and tool output never enter the ledger.
Tracked task cards consume OpenClaw's real
Gateway exec-approval queue and expose only its allowed decisions; a live
source-API proof listed an exact pending command, denied it through
`exec.approval.resolve`, verified removal from the queue and recorded the
decision plus command hash in the audit ledger. The shared Gateway token stays
inside the backend, and `python3-websockets` is now an explicit image
dependency. Live 4K RTL evidence exists for Tasks and the real
Git Workbench. The primary Chat canvas now uses OpenClaw's authenticated
loopback Chat Completions endpoint, so desktop, Telegram and WhatsApp share the
same agent runtime, sessions, memory, tools and policy while the existing QML
keeps streaming and multimodal payloads. A real local two-turn test preserved
the token `MOAI-LOCAL-UNIFIED-READY` in one OpenClaw session; the live UI proof
shows `qwen3-vl:4b · وكيل موحّد`. The central Chat now includes a searchable
conversation drawer and can load/continue the exact OpenClaw thread shared with
phone channels. A 4K RTL source run rendered all four messages from the proof
session; a subsequent request using its guarded session key returned the same
token with `X-MoAI-Agent: openclaw`. Replies retain Markdown/fenced-code
rendering, are selectable and have a one-click Qt clipboard action. Real
OpenClaw tool calls/results now render as bounded semantic status cards; a live
4K RTL run displayed the actual `exec` call and `opened (setsid): code` result.
Streaming can be stopped through the real active XHR, and Regenerate now removes
the prior turn then replays its exact stored payload—including image/document
parts—without duplicating conversation history.
Settings are now twelve distinct functional pages (Models, Providers, OpenClaw,
Telegram, WhatsApp, Voice, Permissions, Memory, Projects, Terminal, Privacy and
Appearance) rather than seven mixed buckets. Hybrid is a first-class privacy
choice, secrets remain write-only, and the retired unreachable Health duplicate
was removed. The fixed narrow rail is now a responsive workspace sidebar: it
keeps the 76 px compact form at 720×540 and expands to 188 px with readable
horizontal labels at 1120 px and above. Both compact and 1440×900 RTL source-QML
states were captured and visually inspected without clipping. Live 4K RTL evidence covered the section grid and real configured
OpenClaw status. Settings also passed English/LTR at the enforced compact
`720×540` minimum and Permissions passed Dark/RTL on the live 4K session; the
machine was restored to its exact prior `MoOS Scholar Light` theme afterward.
The visual matrix is now complete for the four primary workspaces. Source QML
and the source Agent backend were run together on the live 4K Wayland session;
Conversations, Projects, Tasks and Terminal were captured in Light/Dark ×
LTR/RTL at `720×540`, `1120×760` and native 4K scale: 48 real screenshots,
reviewed as three 4×4 contact sheets. The captures show the real MoOS project,
real OpenClaw sessions and a completed task. No binding/type/load errors appeared.
The accessibility surface is now live-proven rather than only grepped: Qt's
AT-SPI tree exposed the source app, every interactive node had a name or named
`labelledBy` relation after fixing six anonymous secret/switch controls, and
real Tab traversal reached named chat, composer and Settings actions. Reduced
motion remains enforced by the existing real-QML runtime gate.
The bilingual speech proof now covers Arabic too: an 11.96-second synthesized
Arabic WAV traversed the shipped `moai-transcribe` and live Speaches service
with `MOAI_STT_LANG=ar`, returned recognisable Arabic text and exit 0, after
which Speaches was stopped and reset to clean inactive state.
Visual review direction can now be selected per source run with the validated
`--layout-direction ltr|rtl` argument, avoiding global locale changes. Live
captures added Light/LTR compact Providers, Dark/LTR 1440×900 Chat and Dark/RTL
compact Terminal, then restored `org.moos.ui2.study.light` and
`MoOSUI2ScholarLight` exactly. The full primary-workspace cross-product is now
closed; the evidence contact sheets remain under `/var/tmp/moai-review-source-*`.
OpenClaw also gains a `moai/hybrid` loopback
provider so phone turns use the same smart routing policy. The installed OpenClaw
advertises WhatsApp Web support and Mo AI now exposes its fixed login route.
Channel settings now call a bounded, secret-free `/api/channels` probe instead
of implying connectivity: a live source-backend probe verified Telegram polling
connected as `@Moalfarras_bot`. The owner has now completed the real WhatsApp
QR pairing and OpenClaw deep health reports the account `LINKED`; the repaired
source projection returns both channels connected. A real inbound WhatsApp turn
is the remaining channel proof. The
endpoint wakes OpenClaw only for this explicit status request and leaves idle
sleep policy intact. `just check` passed after this slice. All of this is
unreleased working-branch state
until merge, signed CI matrix and live update pass. The final release image proof
was repeated after the last code change from branch head `622926a2`: generic
image `localhost/moos:latest` (`e3f83010083e…`). Its final 122 MB initramfs contains the OSTree boot path and
MoOS Plymouth assets; all shipped QML apps, Launcher, desktop scene, Store,
image-experience, identity and foreign-identity firewall gates passed, followed
by `bootc container lint` (9 checks passed, four pre-existing warning classes).
The same exact head produced Cloud image
`localhost/moos-cloud:latest` (`11eb2b525ba1…`) and NVIDIA image
`localhost/moos-nvidia:latest` (`7de9463dc16d…`); both passed edition-specific
gates and bootc lint. NVIDIA used kernel `7.1.5-201.fc44.x86_64`, matched
`kmod-nvidia` and `nvidia-driver` at `610.43.03`, and proved seven NVIDIA modules
inside its final 217 MB initramfs. This proves all three local composes—not
signed publication, the booted deployment or post-update behavior.
Telegram is now end-to-end proven: the live config restricts DMs to owner
`1142563280`, the real shared session records owner inbound turns plus explicit
`telegram-final` delivery mirrors to that same chat, and a new cold-start source
probe returned `@Moalfarras_bot` connected via polling. That cold proof exposed
and fixed a status race: the API now waits up to 12 seconds for the configured
loopback Gateway port before invoking OpenClaw, instead of treating systemd's
early active state as socket readiness. WhatsApp is now paired and linked;
inbound-turn proof remains open.

Previous update: 2026-08-01 — release pipeline recovery. The public, NVIDIA and
cloud images built and pushed in CI, but all three jobs were killed afterward by
an accidentally reintroduced in-job Syft SBOM scan. This is the exact failure
already recorded on 2026-07-29. Heavy SBOM work is removed again from
`build.yml`, while digest signing and verification against the installed MoOS
public key remain mandatory. `tests/test_release_workflow_safety.py` now prevents
the release-critical workflow from regressing. The locally callable `just check`
suite is also brought back in sync with CI's qdbus, gateway-streaming, cloud UID,
fail-closed ports, OpenClaw no-op, H.264 fallback and authenticated-audio gates.
The cloud build's stale status line claiming the retired unauthenticated
`tailscale serve /audio` mount is corrected to name the authenticated agent
proxy, and the audio regression test now holds the build-log contract too.
Publication, staging, reboot and
post-update verification remain open until the repaired CI run completes.

Previous update: 2026-07-31, early session — **Premium Liquid Glass application
marks** on branch `product/liquid-glass-app-icons-2026-07-30`. The machine
still boots signed `moos-nvidia` **44.20260730.486**; this round restores the
theme-baked SVG architecture (after a mid-flight PNG/hardcoded-RGB diversion
broke palette baking and the app-icon gates) and upgrades the plate material
to multi-layer Liquid Glass. Design system remains **MoOS UI — Liquid Glass**.

> **Mo AI phone-agent repair — 2026-08-01.** The gateway unit now uses the
> same `~/.local/node` runtime that `moai-do install-openclaw` provisions;
> the contradictory nvm-only drop-in was removed and the SQLite gate checks
> the installer/service contract. Bootstrap now reapplies mode `0700` to the
> OpenClaw credentials directory even when configuration content is unchanged.
> The local `just check` list was also brought back in line with CI's omitted
> runtime, cloud, recovery, streaming and remote-security gates.

> **Read [`skills/moos-engineering/SKILL.md`](skills/moos-engineering/SKILL.md) first —
> it is mandatory for every agent working here.**

> **Premium Liquid Glass app marks — 2026-07-31, branch
> `product/liquid-glass-app-icons-2026-07-30`.** A same-day diversion replaced
> the nine themeable SVG marks with static RGB PNG squircles (and stole
> Firefox/Dolphin/Konsole/Gwenview identity). That broke
> `generate_moos_themes.build_icon_theme`'s `recoloured()` bake,
> `tests/test_moos_app_icons.py`, and the "icons follow the theme" claim.
> This round restores SVG masters with KDE colour roles, upgrades the plate to
> a multi-layer Liquid Glass stack (sheen / depth / refraction / caustic /
> floor / rim — white+black opacity only, theme-safe), and redesigns Mo Store
> as a four-tile modern storefront (not a shopping bag). Mo AI stays the
> commissioned floating orb. Third-party overrides are removed. Live evidence:
> Daylight bake → blue store, Amethyst bake → purple store
> (`artwork/moos-ui2/live-tests/daylight-store-256.png`,
> `amethyst-store-256.png`); family sheet
> `artwork/moos-ui2/previews/moos-app-icons.png` + palette matrix
> `moos-app-icons-palettes.png`. `artwork/generate_3d_squircle.py` is retired.
> Release still needs commit/push, signed image, and THEME_REV=27's home purge
> on reboot so `/usr` wins over any leftover preview.

> **THEME_REV=27 — home icon override purge, 2026-07-30 evening.** The
> redrawn marks and per-palette bakes were already on `main`, but existing
> sessions never saw them: `~/.local/share/icons` outranks `/usr`, and a
> live-preview tree left the retired geometry (often still Breeze
> `#3daee9`) in place forever. `moos-apply-theme` now deletes
> `~/.local/share/icons/MoOSUI2*` and every `moos-*` / `moplayer.*` under
> home `hicolor` once per this revision, then rebuilds ksycoca. The UX
> gate asserts the purge. Until the signed image that carries THEME_REV=27
> is booted, this machine may still wear a *fresh* home preview of the new
> marks (MoOS teal / palette-baked) so the dock is honest during the wait;
> that preview is exactly what THEME_REV=27 clears after reboot.
>
> **Application-mark round — 2026-07-30, on `main` (baked per palette).** The symbolic overlays gave the *interface* a palette;
> the nine first-party **application marks** still did not have one. They are
> redrawn from scratch in `artwork/generate_moos_app_icons.py` (one 880 px
> squircle on the 1024 canvas, glyph inside a 640 px safe area, every load-
> bearing stroke ≥ 76 units so it survives the 16 px dock cell) and **every
> ink is a KDE colour role, never a literal colour**. Because MoOS pins
> `FollowsColorScheme=false` for the reason below, following the palette is
> not a runtime property — it is **baked**: `generate_moos_themes.build_icon_theme`
> writes one re-inked copy of all nine into each of the 14 palette icon themes
> (`moos/apps/scalable`, now declared in every overlay's `Directories=`), and
> `build.sh`'s new `recolor_moos_app_dir` does the same for the two broad
> bases it assembles from Colloid. Role pairing is not free choice: only
> `HighlightedText`-on-`Highlight`, `Background`-on-`Positive/Neutral/Negative`
> and the inverted `Background`-on-`Text` plate are used, because those are
> the pairs KDE guarantees — measured minimum contrast across all 16 shipped
> palettes is **4.4:1**, and `tests/test_moos_app_icons.py` re-derives it and
> fails under 4:1. What actually proves the claim is
> `tests/test_moos_symbolic_runtime.py::MoOSAppMarkThemeResolverTests`: it runs
> **`kiconfinder6`** under an isolated XDG profile once per palette and asserts
> KDE resolves `moos-store` (and three siblings) to *that* theme's baked file
> whose accent equals that palette's own `Colors:Selection`. Rendered evidence:
> `artwork/moos-ui2/previews/moos-app-icons-palettes.png` (six palettes × ten
> marks, each row on its own window colour).
>
> Three things this round found already broken and fixed:
> **(1)** `hicolor/scalable/apps/moos-moai.svg` on `main` had **lost the
> embedded commissioned master entirely** — it was a bare plate carrying
> Breeze's `#3daee9`/`#eff0f1`, i.e. a foreign identity on the assistant's
> icon, while the UX gate that requires the byte-exact master sat in a
> working-tree state that no longer checked it. **(2)** The same working tree
> had moved every app master from `scalable/apps` to `scalable/places` and
> pointed `verify_user_experience.py` at the new path — Plasma looks up
> application icons in `apps`, so that was a silent break with a green gate.
> **(3)** It had deleted the four `moos-logo.png` rasters the brand plasmoid
> resolves. All three are restored. Mo AI is now the one **tile-less** mark:
> its tile would be re-inked per palette like its siblings' and would fight
> the commissioned orb's own light, so the orb floats — scaled so its visible
> footprint is the family's 880 px span (`generate_moai_icon.py`), which is
> measured on the rendered 512 px raster by a gate, not asserted from markup.
> The stale `72x72` MoPlayer raster (a size the ladder does not produce, left
> over from MoPlayer's own packaging tree) is dropped rather than left showing
> the retired ember tile at one size.

> **Icon-bridge round — 2026-07-30, working tree on top of the shipped
> `.478` (THEME_REV=26).** Continued from the previous session, which stopped
> mid-flight on an external usage limit; its in-progress step (settling the
> Theme/Icon-bridge test contracts) is now complete. The round gives every one
> of the 14 family palettes its own first-party symbolic icon overlay
> (`/usr/share/icons/MoOSUI2<Family>[Light]`, 69 Tidal Cut symbols each,
> identical geometry, palette-matched inks) inheriting the broad `MoOSUI2` /
> `MoOSUI2Light` bases built from Colloid. The load-bearing decision is
> **`FollowsColorScheme=false`** on every MoOS icon theme: with `true`,
> QIcon recolouring reads the application `QPalette` rather than the Plasma
> surface colour set, which painted near-invisible dark symbols on the dark
> Launcher (evidence pair in `artwork/moos-ui2/live-tests/`,
> `tidal-cut-arena-followscolorscheme-before.png` →
> `tidal-cut-arena-baked-inks-after.png`, both captured through the real
> KIconLoader on the live session). Each overlay instead bakes its
> WCAG-checked palette inks; `_symbol_accent_ink` picks the nearest 1% step
> from primary toward text clearing 3:1 on every semantic surface, and
> `tests/test_moos_symbolic_icons.py` holds that math. The bridge is wired
> end-to-end: look-and-feel `defaults` select the palette overlay,
> `moos-theme`/`moos-apply-theme`/`moos-selfcheck` expect `icons == style`
> for every member, `build_files/build.sh` gates all 14 overlays in the image
> (index validity, inherits direction, full inventory, semantic roles) and
> recolours the two broad bases' baked inks, and
> `tests/post-update-check.sh` now proves `kiconfinder6` resolves the
> overlay from `/usr` after an update. The same round calms the Command
> Canvas (four columns on the 11px+ type ramp, 20px outer rhythm, 56px
> command field, quieter tiles/nav, scrollbars) — live-verified at 4K RTL
> (`launcher-four-column-live-4k.jpg`) — and gives the shared app Button
> semantic 44px states plus `isMask` symbol foregrounds; the native Plasma
> widget states (button/lineedit/listitem/menubaritem/viewitem across all 16
> desktoptheme variants) render through the real KSvg/FrameSvg path
> (`native-controls-arena-kframe.png`). The four previously-failing gate
> files were moved to the new contracts without weakening intent (density,
> type-ramp, target and destructive-pairing protections all kept). Release
> steps still open: local `just build`, commit/push + CI signed image, host
> staging, reboot, and the stricter post-update check on the booted image.

> **Tidal Horizon product-design pass — 2026-07-30, working tree
> `product/tidal-horizon-2026-07-30`.** This pass starts from the already
> accepted commercial audit; it is implementation, not another audit. It gives
> MoOS one spatial signature across the desktop: two low mineral-glass
> membranes meet at a precise concave **Tidal Cut**, while content keeps a calm
> upper field. The normal contract is `left/right=0.11/0.89W`,
> `horizon=0.82H`, `crest=0.12H`, `shoulder=0.22W` and
> `cutHalf=max(11px,0.013W)`; compact surfaces use
> `0.04/0.96W`, `0.78H`, `0.19H` and `0.18W`. It is physical geometry and
> therefore does not mirror in RTL.
>
> The accepted light/dark wallpaper masters are 1672×941 lossless PNGs:
> `moos-ui-tidal-horizon-master-v1.png`
> (`b09a5a71e68d…`) and
> `moos-ui-graphite-horizon-master-v1.png`
> (`4402f755df0c…`). They keep one silhouette and change only material/light;
> the family generator maps that geometry to all 16 semantic palettes. The
> MoOS and Mo AI logos keep their existing geometry. The accepted 69-symbol
> Tidal Cut family also remains the icon language; this pass does not restart
> icon design or import another project's artwork.
>
> The shell is now the **Command Canvas**, `828×630` logical px with a `24px`
> outer rhythm, `68px` command bar, ≥`40px` targets and the shared
> `8/12/16/24px` radius scale. It exposes Mo AI, Store and Settings once,
> then quiet context/session actions; its finite entrance is `240ms` and
> interaction feedback `120ms`. Hero Clock updates by the minute and has no
> perpetual seconds animation. Splash, login, lock and logout share the same
> horizon geometry; the application component uses one finite `320ms` reveal.
> Every duration becomes zero when
> `Kirigami.Units.longDuration <= 1`.
>
> Portal motion is deliberately surface-specific: Splash reveal **460ms** +
> progress **260ms**; Logout background **480ms** + sheet **420ms**; Lock has
> only finite transitions and a minute-event pulse; the Login wallpaper is
> static. The canonical portal component hash is
> `11a0ddbd40ae617a2ff7ac25204ceb9cf63fd42795fa373d531b5fb6caa82705`;
> the generator synchronises those exact bytes across all 16 family doorways.
> Store and Mo AI now seat their unchanged identities on the shared horizon
> instead of unrelated decorative glow layers. The new native MoOS Control
> Center unifies Overview, Appearance, Connectivity, Hardware, Privacy,
> Updates and Recovery in one bilingual/RTL shell. It uses ≥`48px` controls,
> a read-only status helper and **34 fixed allowlisted routes**; storage is
> measured on `/var`, not composefs `/`. MoPlayer was deliberately not
> reworked again in this pass: the accepted MoOS chrome and canonical
> `23799ad` / 176-test state remain the source of truth.
>
> Working-tree previews and before/after pairs are indexed at
> [`artwork/moos-ui2/live-tests/README.md`](artwork/moos-ui2/live-tests/README.md).
> The final wallpaper and Command Canvas were also captured from the running
> 3840×2160 Plasma session after a temporary source-package install; that user
> override was then removed so it cannot shadow the signed image. These are
> **not signed-deployment evidence**. Measured idle samples from the previews:
> Launcher **0 ticks / 0.000% over 20s**, Hero Clock **0 / 0.000% over 20s**,
> Store **0 / 0.000% over 20s**; Control Center held **55.8 MiB current /
> 58.8 MiB peak** and accumulated **0.427s CPU after minutes**. The full gates
> and local generic image build have passed. Release remains open until the
> branch is committed/pushed, CI publishes a signed image, that exact digest is
> staged and booted, and post-update verification plus final booted-image
> captures pass.

> **Working-tree visual/UX audit — 2026-07-30, branch
> `audit/commercial-visual-polish-2026-07-30`.** The measured audit and release
> checklist are in
> [`artwork/MOOS_VISUAL_POLISH_AUDIT_2026-07-30.md`](artwork/MOOS_VISUAL_POLISH_AUDIT_2026-07-30.md).
> The rejected 67/68-symbol monoline checkpoint was replaced wholesale by the
> original **69-symbol Tidal Cut** family: compound filled paths, one generated
> manifest/catalogue, live semantic theme roles and executable KDE, GTK and
> librsvg proofs at 16–128 px. The worktree also closes session-control and
> Installer contrast gaps across all 16 schemes; makes custom actions keyboard-
> and AT-reachable; binds finite motion to animations-off; maps first-party GTK
> windows to the active family palette; removes blocking Recovery and Mo PC
> Remote work from GTK's main loop; and fixes shell double-mirroring in RTL.
>
> Source acceptance is now green: the four QML apps share tokens, focus, buttons
> and symbols; Launcher is a 720×590 three-column MoOS composition; dock type
> uses the system font/11 pt floor; Splash is one reveal plus progress; Mo AI
> ambient loops and bilingual duplication are removed; and active-locale copy
> is enforced. MoPlayer uses palette-native MoOS chrome, passes analyze plus
> **176/176**, is committed/pushed at canonical `23799ad`, and is vendored from
> that exact clean revision. Final image-repository `just check` exits 0. The
> full generic `just build` also exits 0 from this exact worktree and produces
> `localhost/moos:latest` (`5e64dbf3373a…`): all in-image QML, Launcher,
> desktop-scene, identity, Store, initramfs/Plymouth and bootc gates pass;
> initramfs is 122 MB and contains the MoOS Plymouth assets plus
> `ostree-prepare-root`.
> **This is still not shipped evidence:** signed publication (including the
> NVIDIA matrix image), update staging, reboot and post-update check are the
> remaining release steps.

> **Session N — the practical full-system audit (2026-07-29), branch
> `fix/full-system-audit-and-completion`.** A live-first audit (bootc/rpm-ostree
> status, failed units, journal, coredumps, boot chain, sysctl-vs-live, ports)
> found the boot/update/rollback/kernel/signature foundation HEALTHY: all MoOS
> sysctls apply live (BBR, fq, swappiness 150, backlog, inotify), zram active,
> two deployments (rollback intact), signature policy enforced. No Critical/High.
> A read-only defect sweep across all subsystems then produced ten reproduced
> defects, each fixed with a regression proven to bite:
> - **boot** — `net.core.default_qdisc=fq` was rejected on the primary
>   systemd-sysctl pass because sch_fq (a module) was never preloaded; only
>   tcp_bbr was. Added sch_fq to modules-load.d and generalised
>   test_kernel_network_tuning to pair any module-backed sysctl value (95b0161).
> - **ui/motion** — the MoOS apps were the motion-gate blind spot: Mo AI ran 12
>   unguarded Animation.Infinite loops, Welcome/Installer/Store two each. Gated
>   all 18 on `Kirigami.Units.longDuration > 1` and added
>   `system_files/usr/share/moos/apps` to _MOTION_ROOTS (302a410).
> - **cloud** — moos-cloud-dev wrote an inverted subuid range (100000-65535);
>   fixed to a unique per-uid block + new gate test_cloud_subid_range (0c77163).
> - **remote** — the orphaned MoRemote.Tests crashed on a stale assertion
>   (removed wall-clock check); fixed and wired into the Containerfile build
>   stage so it runs every build (ba5bc81).
> - **moai** — test_moai_do now validates the UI's real extractRuns alternation
>   whitelist, not just literals (9569c6e).
> - **ci** — build-disk/iso now cosign-verify the image before building an
>   installer; all jobs got timeout-minutes; build-disk got concurrency
>   (8a13cff). Image build also gained an SPDX SBOM attestation (592e55f) —
>   **which was removed again on 2026-07-29 after it broke the build twice; see
>   the round-3 entry below. Do not re-add it to this workflow.**
> - **moplayer** — the bundled demo playlist could never load (undeclared in
>   pubspec, wrong asset path); shipped it correctly + regression (b25b158).
> - **store** — curated npm/AppImage tools could be installed but never removed;
>   added the symmetric removal path in storectl + the UI Remove button (cb4f981).
> All 30 repo gates pass locally verbatim; controller TS, MoRemote.Tests (.NET,
> 21), and MoPlayer flutter (164) all green. Live-verified where possible:
> Welcome rendered from edited source; `moos-storectl remove claude-code`
> returns success (was "Invalid Flatpak app ID"), the test install restored
> afterward. NOT yet verified (needs a boot / a main build): the sch_fq
> ordering on a clean single-pass boot, and the SBOM attestation step.
> **Update:** the SBOM step was never verifiable — it killed the runner on both
> attempts and was removed (round 3).
>
> **Session N, round 3 — shipped to main, booted, and verified on the machine
> (2026-07-29).** Everything below is running on `44.20260729.452` (rev d567c8b,
> digest ff45fe58), signature-verified against `/etc/pki/containers/moos.pub`.
> `tests/post-update-check.sh`: **48 passed, 0 failed** (was 45/3 before this
> boot), 0 failed system or user units, user `default.target` **1.444s**.
> - **ci (High)** — the SPDX SBOM step killed the GitHub runner twice; the second
>   time it took ALL THREE matrix jobs. syft spends ~8 min unpacking a multi-GB
>   image on a runner already squeezed by `Free disk space`, and the runner does
>   not come back. `continue-on-error: true` does NOT save it — that forgives a
>   step which EXITS non-zero, and nothing forgives a runner that is gone, so the
>   step showed "success" inside a red job. Removed (04b57bd). If it ever returns
>   it needs its own workflow, off the path that produces the image people boot.
> - **recovery (High)** — `deployments()` documents a 3-tuple and the call site
>   unpacks three names, but two failure paths still returned pairs, so Recovery
>   died with `ValueError: not enough values to unpack (expected 3, got 2)`.
>   Both paths mean "rpm-ostree is unwell" — the only reason anyone opens
>   Recovery. It worked on every healthy machine and crashed on the broken one
>   (db7fd10). Verified on this boot: with rpm-ostree PATH-shadowed by a stub
>   that exits 1, `/usr/bin/moos-rollback` still draws (timeout 6s -> exit 124,
>   no traceback); the installed file has 3 three-tuple returns and 0 pairs.
> - **remote/ui (High)** — the shared `<S>` icon set only a viewBox, so any use
>   site without a matching CSS rule fell back to the browser default object
>   size. Measured in Firefox: **290x270px vs 20x19px**, 14.5x too wide, at three
>   sites (idle-timeout overlay, PC-locked overlay, sign-in lockout hint) — the
>   same defect as the ~600px settings gear. Fixed on the component so no future
>   site can repeat it, then sized deliberately: `.center-msg svg` 44px,
>   `.hint svg` 1.05em (f6118e4, e391f79).
> - **remote/ui (Medium)** — `.seg button { min-width: 132px }` was tuned for a
>   FOUR-segment row; Pointer became three and Quality five, so phones wrapped
>   2+1 and 2+2+1. Re-measured inside the real `.card > .card-pad` nesting (a
>   first attempt measured the un-nested case, picked 108px and changed nothing):
>   320px fits three at no value tested, 360px needs <=84px, 390px+ fits all.
>   84px (d567c8b).
> - **theme (Medium)** — the UI2 cursor gate required the two halves to name
>   DIFFERENT themes, which the INVERTED assignment satisfies just as well, and
>   no file said which theme is the light-coloured one. Now two layers, neither
>   trusting the name: the repo gate covers all 16 look-and-feels, and
>   `verify_image_experience.py` decodes the shipped XCursor files and compares
>   mean opaque-pixel luminance (MoOS 155/255 light, MoOSDark 98/255 dark).
>   Both passed inside real CI image builds (5403739).
> - **moai (High)** — every privileged action now leaves a journal record with
>   four distinct verdicts. Verified on this boot against the INSTALLED binary:
>   `verdict=ok` (gpu-report), `verdict=declined` (a rollback declined via closed
>   stdin, deployments unchanged), `verdict=failed status=N`, and `verdict=refused`
>   for `rm -rf /`, `update; rm -rf /`, `$(reboot)`, `../../bin/sh`, `--exec`
>   (a5c2536).
> - **remote/ci (Medium)** — the image ships the vite OUTPUT, and that output is
>   committed at `moremote/agent/wwwroot`. Editing src/ without `npm run build`
>   left every test green and the shipped bundle unchanged. Two guards now:
>   `tests/bundle-freshness.test.ts` (BUILD marker must appear in the bundle, and
>   sw.js may only precache assets that exist) and a CI step running
>   `npm ci && npm run build` that fails on ANY diff. The CI step passed
>   byte-identical on GitHub's runner, so the build is reproducible from the
>   lockfile (8fe3695).
> - **security (HIGH, live) — the machine's sound was on the tailnet with no PIN.**
>   `mo-pc-remote` published moos-cloud-audio with
>   `tailscale serve --set-path=/audio`, and that service has NO authentication —
>   its own header says so. `tailscale serve` re-publishes a loopback socket to
>   the WHOLE tailnet, so on one hostname, one port, one certificate:
>       POST /api/login (wrong PIN)       -> 401
>       GET  /audio/stream.webm (no auth) -> 200 audio/webm, a live Opus stream
>   Four devices were enrolled. Any of them could listen to every call and video,
>   silently, with nothing on the desktop to say so. Tailnet-only
>   (`AllowFunnel: None`), all peers one account — bounded, not harmless.
>   The flaw was architectural: the audio was a SIBLING of the authenticated app
>   instead of part of it. Two doors, one with no lock. The sound now goes through
>   the agent at `/api/audio/stream.webm`, behind `UseNetworkGuard` and the session
>   token, with the token in the query string for the same reason
>   `/api/files/download` takes it that way — an `<audio>` element cannot send an
>   Authorization header. `mount_audio()` is replaced by `unmount_audio()`, which
>   the panel calls on every open, so a machine exposed once closes itself.
>   Verified end to end against a real agent on a spare port: no token -> 401,
>   bogus token -> 401, valid token -> 200 audio/webm decoding as WebM. The live
>   mount was retracted on this machine during the work (200 -> 404).
>   NOTE FOR THE NEXT AGENT: `tests/test_desktop_sound_reachable.py` used to
>   REQUIRE the vulnerable mount, and kept passing after the fix only because
>   `mount_audio` is a substring of `unmount_audio`. It now uses word boundaries
>   and asserts the opposite. New gate: `tests/test_remote_audio_is_authenticated.py`.
> Also recorded: the blanket `/etc/sudoers.d/moos-nopasswd` and
> `49-moos-wheel-nopasswd.rules` on the maintainer's machine are LOCAL dev
> artifacts, NOT shipped by the image — checked against `system_files/`. A
> five-agent adversarial audit refuted 6 of 8 candidate findings, including the
> theory that the 217MB initramfs costs meaningful boot time; do not re-chase it.
> Sweeps that found nothing, recorded so nobody repeats them: return-arity
> mismatches across 51 Python files and unbounded `subprocess` calls in 6 GTK
> apps produced 5 candidates, 4 false positives cleared by reading (the 5th was
> the Recovery bug above). Mo Store: 33/33 Flathub entries resolve against the
> Flathub API, and every curated `install.kind` (npm, web) has a handler.
>
> **Session N, round 2 — a deeper adversarial pass** on the same branch found
> and fixed eight more, each reproduced with a regression proven to bite:
> - **recovery (High)** — `moos-rollback` named a STAGED update as the rollback
>   target (rpm-ostree lists staged at index 0), telling the user "roll back to
>   <the newer version>". Skip staged deployments (7f9eefa).
> - **cloud/security (High)** — `60-moai-ports` failed OPEN for uid≥1010 (the
>   11th account), reverting to the base ports and reaching uid 1000's key-holding
>   gateway. Now folds into a unique non-base high band (f47f8f6).
> - **moai (High)** — the gateway left a chat reply hanging for ever on a
>   mid-stream drop (swallowed the error, never closed the socket) and dropped
>   Anthropic error/truncation events as blank "successful" replies (6266d7b).
> - **remote (High)** — the H.264→JPEG fallback latch was dead code (`if not
>   pick_h264()` on an always-truthy tuple) and the mid-stream blacklist keyed
>   the instance name 'enc' + called dict.add(); froze ~4s per rebuild (c0b9368).
> - **session (Med)** — `moos-open` session/logout|power hardcoded `qdbus6`
>   (absent on Plasma 6), so they confirmed then did nothing. Added a qdbus
>   resolver (5c58075).
> - **ui (Visual)** — the first-run theme picker previewed Nova/Aurora/Tidal in
>   the wrong accent and drew Midnight black-on-black (Qt.lighter on #000000).
>   Corrected accents to the palettes, elevate with Qt.tint (48dcd0b).
> - **perf** — `moai-openclaw-bootstrap` re-validated an unchanged config every
>   login (~1.7s / ~428 MB Node); short-circuit when nothing changed (fca4757).
> - **REJECTED** — a per-session gateway token (deep-pass proposal) was NOT
>   implemented: `moai-do:942` points codex/claude/opencode at the gateway as a
>   shared OpenAI endpoint, so requiring a token would break them. The gateway
>   being a shared local endpoint is by design.
>
> And the explicitly-requested Mo AI capability growth (60df793): three new
> `moai-do` actions — `rollback` (rescue), `net-doctor` and `gpu-report`
> (read-only diagnostics) — each a fixed case with confirm+pkexec, wired in
> moai-do + moos-open + the QML whitelist/prompt/menu, live-verified. Deferred
> by design: power lock/sleep/restart (overlaps moos://session/*), service-
> restart (validated-arg surface), backup-home (needs a destination story).

> **Session M — the audit-and-truth session (2026-07-28).** The live machine, the
> repo and GHCR were audited against each other before anything was edited.
> Verified live: the machine boots `moos-nvidia` **44.20260728.419** from the
> signed GHCR digest, zero failed system units, all Mo AI/Mo Remote/cloud-audio
> user services active, and `tests/post-update-check.sh` returned **44 passed /
> 0 MoOS failures** (the only failed units were third-party app scopes —
> Chrome/Chromium/Cursor/xwaylandvideobridge — cleared with `reset-failed`).
> All 26 gate commands of `build.yml`'s Repo-gates step pass locally, run verbatim. All
> three images (`moos`, `moos-nvidia`, `moos-cloud`) were published and
> cosign-signed the same day; `main` == `origin/main`; nothing local was
> unpushed (two stale merged branch pointers were deleted). The Mo PC Remote
> engineering of 2026-07-27/28 is on `main` and gated: input injection moved off
> the socket thread, the 1920×1080@30 resolution ceiling replaced by hardware
> probing, encoder rebuild debounce, kernel network tuning (BBR), codec resend,
> the desktop Sound button fix, and the phone UI layout fixes.
> Identity work this session: the design system is now consistently named
> **MoOS UI — Liquid Glass Design System** across README/AGENTS/ROADMAP/artwork
> docs ("Nova" survives only as the `MoOS UI · Nova` palette member and in
> historical logs; every load-bearing identifier — `MoOSUI2Nova*`,
> `org.moos.ui2.nova*`, `org.moos.nova.clock`, SVG `nova-*` ids, Dart
> `class Nova`, QML `nova*` properties — was deliberately left untouched).
> `skills/moos-engineering/SKILL.md` is the new mandatory agent skill, linked
> from README/AGENTS/this file and symlinked into `.claude/skills/` for
> auto-discovery. README.md was rewritten to describe the three-image reality.

> **Session L — MoPlayer 1.2 desktop playback overhaul (2026-07-26).** The
> canonical `~/MoPlayerMoOS` release is `e856461`, pushed on `main`, and the
> vendored source in this image is an exact sync of that commit. The KDE Wallet
> prompt is gone: MoPlayer no longer loads `flutter_secure_storage`/libsecret
> and stores IPTV credentials in its private XDG data file instead (directory
> `0700`, file `0600`, atomic replacement, and a non-fatal memory fallback).
> Existing wallet secrets cannot be migrated without reopening the wallet, so
> users enter the source once after this update. The NVIDIA-safe software
> presentation texture remains the default because the GL texture path has
> killed this app on the maintainer's RTX 2080 SUPER; hardware decoding remains
> enabled. Full-player presentation is bounded to 1280x720 and mini-player to
> 640x360, with a `videoParams` guard that reasserts the bound after media_kit
> silently resets it to the source size. Eight consecutive Wayland captures of
> the public 1080p Mux HLS stream were clean after the earlier 1920x1080 tearing
> was reproduced.
>
> Home, settings, player and catalogue browsing were modernised for mouse and
> keyboard use; direct URL launch on a clean profile works; live channel
> previous/next wraps through the queue from buttons, PageUp/PageDown, N/P and
> MPRIS; buffering/cache/reconnect settings are tuned for IPTV; catalogue caches
> are memoised and invalidated; and storage state is explained in all shipped
> languages. `flutter analyze` is clean, **114 tests** pass, release build and
> `~/.local` installation pass, desktop/AppStream validation pass, and the
> installed binary was exercised against the public HLS stream with MPRIS
> reporting `Playing`, system `libmpv.so.2`, NVDEC active, the safe texture
> resize visible in logs, and no KWallet/Secret Service call. Both local images
> then built successfully from the same source: generic `moos:latest`
> (`0328de17…`) and NVIDIA `moos-nvidia:latest` (`8929faea…`), including the
> app/identity/initramfs/bootc gates and NVIDIA 610.43.03 modules matched to
> kernel 7.1.4-204. Image commit `7308e57` was then published by CI run
> `30182998521`: generic, NVIDIA and cloud all built, pushed, cosign-signed, and
> verified against the OS-enforced public key. The machine has staged the exact
> signed NVIDIA digest `sha256:9608f65a…` as version `44.20260726.358`; the
> booted deployment remains `44.20260725.357` until the user reboots, after which
> `tests/post-update-check.sh` is still required before calling the boot proven.

> **Session K — MoPlayer 1.1 (2026-07-25).** The canonical
> `~/MoPlayerMoOS` repository, not only its image snapshot, now owns the rebuilt
> home and playback experience. The player has complete transport, seek,
> previous/next, volume, fullscreen, fit/fill/original sizing, speed and
> audio/subtitle controls; buffering is visible and recovery is bounded,
> generation-safe and manually retryable instead of silently wedging. The home
> hero is catalogue-driven and the always-running weather/live animations that
> kept an idle 4K window near one full core were removed (measured at ~1.6% CPU
> after the change). Linux single-instance activation now forwards a second
> file/URL to the existing window and was proven live while playback continued.
> Flutter is 3.44.8 / Dart 3.12.2 and the media stack is current.
>
> The “server disappears after restart” report exposed a system/app relationship
> bug: a shipped three-line `~/.config/kwalletrc` shadow disabled the encrypted
> wallet, while the compatibility provider was not active under
> `org.freedesktop.secrets`. `moos-secret-service.service` now provides that
> session service, and `moos-ui-migrate` repairs **only** the exact legacy
> disabled file; custom or later user choices are preserved. MoPlayer itself now
> treats the two encrypted writes as a transaction result and visibly refuses to
> claim success if either one fails — there is deliberately no plaintext
> credential fallback. The canonical app passed analyze + **102 tests**, built
> in release mode and was installed under `~/.local`; two full local image
> builds passed every image/identity/initramfs gate, with the second containing
> the final persistence service and exact existing-user migration.

> **Session J — the release pass (2026-07-25).** Session I's work is now ON
> `main`: `moos-ui-unify` merged as `1e7991b`, build-resilience as `5823f93`, and
> CI run `30152979451` published + cosign-signed `moos:latest` and
> `moos-nvidia:latest` (17m37s, green). Two defects the audit's evidence pointed
> at were fixed rather than noted: the wallpaper scene's `motionEnabled` now
> honours Plasma's "animations off" (it consulted only its own `AmbientMotion`
> key, so the largest surface on screen kept animating against the user's
> setting), and `uupd` — the most expensive unit of this machine's boot at
> 1min 16.195s, firing inside the first fifteen minutes of any desktop that was
> off at 04:00 — got the same idle CPU/IO drop-in `flatpak-system-update` already
> had. Both are gated (`test_moos_ui2.py`, `verify_user_experience.py`).
> **The release gate is now closed:** the machine staged
> `ostree-image-signed:docker://ghcr.io/moalfarras-sys/moos-nvidia:latest`
> (`sha256:12b44aba…`, `44.20260725.347`), rebooted, and
> `tests/post-update-check.sh` returned **48 passed / 0 failed** — the first boot
> on this machine from the signed published image rather than a local
> containers-storage deployment. `moos-selfcheck`: 46 passed.
> The live audit that followed found one real defect, now fixed: **Mo Store's rail
> status dot animated forever with no `running:` guard**, holding the QML render
> loop at full frame rate and repainting a 4K window for one 8 px dot — ~11% of a
> CPU core, paid by any session that merely had the Store window restored behind
> other windows. It was the ONLY unguarded infinite animation among the 30 MoOS
> ships, and the contract that would have caught it existed but covered the
> dashboard only; `verify_user_experience.py` now enforces it across `apps/`,
> `plasmoids/` and `wallpapers/`, broken-once to prove it bites. Everything else
> sampled was clean: no failed units, no MoOS QML errors in the journal,
> notifications deliver, the Mo AI stack answers, the Arabic locale resolves,
> firmware and Flatpaks have nothing pending.

> **Session I — unified visual-system work (2026-07-25, full audit in
> `artwork/MOOS_VISUAL_AUDIT_2026-07-25.md`).** The repository and live 4K/225%
> Plasma session were inventoried rather than judging metadata alone. The 16-theme
> family now shares one generated MoOS design system: complete high-visibility
> Plasma controls and blur masks, rebuilt Aurorae frames and functional button
> states, one safe KWin frost profile, crop-safe Graphite/Tidal wallpaper masters,
> low-duty ambient motion, RTL clock/picker corrections, exact Qt/GTK/GSettings
> readback, and an owned nine-application icon family. Existing-user revisions are
> `THEME_REV=22` and `MOOS_THEME_REV=10`. Both local images then built from the
> fresh `7.1.4-204.fc44.x86_64` base: generic and NVIDIA passed the identity,
> experience, initramfs/OSTree, Plymouth and bootc gates; NVIDIA carried the
> matching 610.43.03 open driver, and both produced 50 Qt WebEngine spell-check
> dictionaries including Arabic and English. The booted audit image was still
> `44.20260724.1` from a **local unverified containers-storage origin**, so it is
> diagnostic evidence only: signed CI publication, signed staging and
> post-reboot proof remain mandatory and must not be claimed until recorded.

> **Session H — the first-boot session (2026-07-17, full writeup in `docs/FIXES_2026-07-17b.md`).**
> ISO `44.20260717.190` was walked end-to-end in QEMU (all green: splash+ring, DE live
> keyboard, 9-page installer, moving progress bar, offline install, target first boot on
> Vienna time) and the walkthrough caught two shipped bugs no gate had seen: (1) the zram
> storm — moos-hardware-adapt's first-boot re-tier restarted systemd-zram-setup@zram0
> bare, tripping dev-zram0.swap into start-limit-hit and leaving a fresh install's first
> boot with two failed units and NO swap (fix: config-equality skip + stop → daemon-reload
> → reset-failed → one start); (2) the live session kept KDE's 5-minute autolock and
> LOCKED the screen over its own running installer (fix: moos-live-polish, gated on
> rd.live.image, writes liveuser's kscreenlockerrc/powerdevilrc — never /etc/xdg). Both
> gates broken-once and watched go red. Forensics trick that cracked it: power the VM off,
> guestfish the journal out of the target disk, read it with `journalctl --directory`.

> **Session G — the polish session (2026-07-17, full writeup in `docs/FIXES_2026-07-17.md`).**
> Wallpapers v2: the four family themes now carry LIT-SILK art (crest-lit bands, aurora
> veil, screen-blended neon edges — make_wallpaper rewritten; Canva retried, account AI
> quota still hard-blocked). A new pre-baked `ring.png` comet-ring sprite orbits the emblem
> on every doorway (login gained a scale-settle entrance, a hairline spark and drifting
> motes; lock and logout carry mirrored rings; the logout watermark breathes). The bar
> brand widened to 1.5× panel height with the ring orbiting continuously. NEW widget:
> `org.moos.heroclock` — the glass desktop Hero Clock (bilingual, live seconds, the mark in
> the corner; every size derives from min(width,height) — height-only sizing shoved the
> seconds strip out of the card on a square window, found live). Lock clock's tick
> breathes; panel clock glints on hover. Gates extended (heroclock completeness + the
> always-on shader ban loop), both watched go red.

> **Session F — the brand session (2026-07-16, full writeup in `docs/FIXES_2026-07-16c.md`).**
> The owner's vector logo landed (`artwork/logo/`) and the animated MoOS brand now lives on
> every doorway surface: the login scene is `org.moos.ui2.greeter` (a Plasma/Wallpaper package
> the greeter's wallpaper process loads — the greeter QML itself is compiled into the binary),
> the lock screen brand breathes and its clock has a floor below it (4K collision fixed), the
> logout greeter carries the animated mark + a draining countdown hairline and its NINE action
> icons are -symbolic now (they all drew as solid teal blobs — isMask over full-colour disc
> icons), and the bar opens with `org.moos.brand` (animated emblem + MoOS-glance popup;
> Kickoff stays the launcher, wearing view-app-grid-symbolic; THEME_REV is 18). Every family
> theme got real designed wallpaper art (glass waves per palette — make_wallpaper rewrite;
> Canva was quota-blocked, the deterministic generator ships the art). All motion is
> Animators-only over pre-baked sprites (`artwork/generate_login_scene.py`); the Lottie file
> in the logo delivery has zero keyframes and is provenance only.

> **State on 2026-07-16 (session E).** The machine is green: `moos-selfcheck` all-pass,
> `post-update-check.sh` 39/0, **zero failed units**, boot to graphical in 4.8 s of userspace
> (GRUB timeout already 1 s; firmware is the remaining 10 s and is out of OS control). The
> NVIDIA fix is proven on hardware (~9 ms/token on CUDA). `fwupd-refresh` — the last open bug —
> now **completes successfully** (Result=success; keep the `10-moos-log-the-error.conf` drop-in
> so any recurrence names its own cause).
>
> **Session E found and fixed the two-stores regression:** Bazaar installed at SYSTEM scope
> (moos-setup's checklist) showed a second visible store, because the old hide only edited the
> per-user flatpak export. The fix is `/usr/bin/moos-one-store` — a NoDisplay override in
> `~/.local/share/applications`, the one dir that outranks BOTH export scopes — called by
> `moos-store-browse` AND `moos-setup`. Three new gates hold it: a static relationship gate in
> `tests/verify_user_experience.py` (both installers must route through the helper; the helper
> must not touch flatpak exports), and a live `moos-selfcheck` check that resolves Bazaar's menu
> entry the way the menu does. All were broken on purpose and watched go red.
>
> **Session E then drove the installer wizard end-to-end for the FIRST time** (ISO 176 in QEMU,
> QMP mouse/keys — synthetic input works in a VM even though it does not on the real machine)
> and the walkthrough caught two shipped bugs no gate had ever seen:
>
> 1. **The wizard called a SUCCEEDING install "stalled."** The backend finished the whole
>    install (target disk bootable, `Installation complete!`, 92 PROGRESS lines written) while
>    the front-end reported FAIL: the launcher's `--cache` already IS `~/.cache/moos-installer`,
>    and the QML appended another `/moos-installer` to it, polling a file nobody writes.
>    One-line QML fix; a three-party relationship gate (moos-open ↔ launcher ↔ QML) now pins
>    the status path.
> 2. **The live session typed English (US) on the owner's German keyboard** while the panel
>    indicator claimed "DE". KWin (Wayland) compiles the keymap locale1 answers — NOT the
>    shipped kxkbrc — and the image shipped neither of localed's sources, so the live ISO ran
>    with localectl fully unset. Proven live: `sudo localectl set-x11-keymap de,ara pc105`
>    flipped the running session to German instantly. The image now ships
>    `/etc/vconsole.conf` (KEYMAP=de) and `/etc/X11/xorg.conf.d/00-keyboard.conf` (de,ara,
>    alt_shift_toggle), both gated against kxkbrc's LayoutList as a relationship;
>    moos-firstboot still rewrites both per the install answers (its no-recipe fallback now
>    matches the image instead of reverting to `us`), and `moos-selfcheck` says explicitly
>    when KWin refused to answer and only config was checked.
>
> The installed target from that walkthrough also proved: timezone page 5 works (searched
> "vienna", selected Europe→Vienna), disk/account/confirm/hold-to-commit all behave, and the
> ISO's offline install path (embedded image, no network) completes.
>
> **ISO `44.20260716.179` (commit `0149736`) is built, WALKED AGAIN end-to-end in QEMU and
> verified fixed:** the live session types German (physical z,z,y,y → "yyzz"; localectl answers
> de/de,ara), the wizard's progress bar moves (34% → 80% → success page), and the whole journey
> is photographed. It lives in `~/Desktop/MoOS-ISO/` with BUILD-INFO.txt, sha256 and proof/.
> The older ISOs (175 broken splash, 176 stalled-wizard) are deleted. The QMP driver scripts
> used for walkthroughs are kept in `~/iso-test/` (drive.py, detype.py).
>
> **Two traps this session cost real time on, both worth knowing before you start:**
> - **Root is `pkexec`, not `sudo`.** `50-moos-devmode.rules` authorises the local active wheel
>   user for `org.freedesktop.policykit.exec`, so `pkexec` runs as root with no prompt while
>   `sudo` still asks for a password. A previous session hit `sudo`, concluded root was out of
>   reach, and left the decisive `fwupd` test unrun for a day. But the rule's allowlist is
>   narrow (`systemctl`, `journalctl`, `bootc`, `rpm-ostree`, `moai-do`, `moos-*`) — `pkexec`
>   on anything else (`localectl`, `cp`) **raises a password dialog on the owner's screen**, and
>   polkit's cache expires every few minutes so it keeps coming back. Do not make the owner
>   authenticate for your own diagnostics.
> - **Mo AI's units are USER units.** `systemctl is-active moai.service` in the system scope
>   answers `inactive` — for a unit that does not exist there. Use `systemctl --user`.

## Active visual work: the MoOS theme FAMILY (UI2 engine)

> **Update 2026-07-30 (ship-readiness milestone) — the adversarially-verified desktop audit
> and its fixes.** Full handoff with root causes, measurements, rejected approaches, design
> decisions and the deferred-work plan: **`docs/SESSION_HANDOFF_2026-07-29.md`** (13 commits,
> `0124a6d..24a2126`+docs). At handoff the dev machine still BOOTS 44.20260729.452
> (digest ff45fe58…) — every fix below lands at the next update+reboot; the milestone CI is
> run 30497407799. A 16-agent audit swept every desktop surface (windows, session screens,
> icons, shell, apps; the motion inspector died and was re-run separately); 8 findings were
> confirmed by independent refuters, and the dropped-by-cap findings were recovered from the
> journal. Everything actionable landed on `main` today, each verified live before push:
>
> - **Windows (`2290dbb`, THEME_REV 24):** the maximized titlebar was the `title` gradient
>   sampled outside its span — flat #527F79 slab, 3.12:1 captions, identical across all 7
>   light palettes. No gradient basis survives FrameSvg's centre-cell stretch (measured:
>   userSpaceOnUse AND objectBoundingBox both render a barely-moving ramp), so the maximized
>   bar is now FLAT in the ramp's terminal colour — worst caption contrast across 16 themes
>   is 10.28:1, focus flash 1.06–1.16:1 (was 2.95). Buttons centred (ButtonMarginTop=6 +
>   ButtonMarginTopMaximized=6 — the maximized key does NOT inherit), minimize glyph
>   centred (y=9.15), and the Aurorae blur mask is GONE: the frame is opaque, and
>   hasElementPrefix("mask") made KWin blur behind it every frame. Material decision on
>   record: persistent surfaces solid, glass for transient shell surfaces only.
> - **Session (`97f2b89`, `c9a9c25`, `17ecd65`):** lock/login Arabic strings wore Noto via
>   `font.family: "Inter"` (no Arabic coverage) at six sites — all bind IBM Plex Sans Arabic
>   now (`font.families` still fails to load on Qt 6.11.1; see Logout.qml). The brand comet
>   ring's head was a razor chop (fade peaked at the same degree the sweep zeroed) — capped
>   over 6°, all 21 comet copies regenerated (plymouth's full-circle ring.png is a different
>   asset, untouched). The lock halo dropped the untintable glow-cyan/violet rasters for
>   accentA/accentB RadialGradients — the mirrored logout surface made this exact change
>   earlier and the two had drifted apart on 14 of 16 palettes.
> - **Shell (`3cf2e4b`):** the portal's remote-control SNI is UNHIDDEN — hidden SNIs do NOT
>   surface when Active on Plasma 6 (measured during a live remote session), so hiding it
>   blinded the user to being watched; the gate contract flipped with it. The launcher's 16
>   explicit `layoutDirection` lines double-mirrored under plasmashell's LayoutMirroring and
>   rendered BACKWARDS in RTL — deleted, verified live (nav right, grid right-to-left). The
>   dock pill folds date digits to Latin like the lock clock and hero card (one numeral
>   system per glance). Footer: MoOS Themes button wears its app's own icon; the Xwayland
>   bridge hide-list gained its Arabic Id. Existing sessions migrate via THEME_REV 24.
> - **Apps (`c046c81`, `a151e61`, `181217e`, `0124a6d`):** a palette token named `onAccent`
>   beside `accent` is SIGNAL-HANDLER syntax to QML — the binding was swallowed and every
>   primary label rendered #000000 on the accent in three apps; renamed `accentText`, the
>   name is now banned by gate. The updater reported the STAGED deployment as "Current
>   system" (deployments[0]); it selects booted==true now. The a11y sweep's duplicate
>   `Accessible.name` had made Mo Store fail to COMPILE (caught by the engine probe + the
>   build's smoke gate; CI run 30484023329 died exactly there). Store: RTL chips snap to
>   reading start, PageUp/Down + ensure-visible keyboard scrolling, details-sheet polish,
>   sane tab order. Theme picker got the full keyboard treatment. Recovery's rollback button
>   no longer clips at 4K/225%, bilingual strings carry LRI/PDI isolates. Installer timezone
>   rows no longer TypeError on Accessible.name.
> - **Icons (`ea8c591`):** the commissioned Mo AI orb (byte-exact master, still
>   gate-enforced) now sits on the family squircle via `artwork/generate_moai_icon.py` —
>   85.9% solid box at 256px, same as moos-store to the pixel.
> - **Dev-machine note:** `~/.config/plasma-localerc` had drifted to en_US (the next login
>   would have been an English shell); restored to `LANGUAGE=ar` + ar_SA formats. The "DE"
>   tray indicator is the de,ara keyboard layout — deliberate, see the 07-16 note below.
> - **Motion (re-run inspector, fixes in the final batch):** the gating ARCHITECTURE is
>   fully clean — 309 infinite loops swept, every one behind `longDuration > 1` plus a
>   visibility/state term. Four cost bugs found and fixed same-day: the Store's index
>   pulse was unbounded when the catalogue build FAILS (~12% of a core forever; now bounded
>   by `indexPoll.running` + a failed-state label), Mo AI's ambient scene cost ~13% for the
>   window's whole life (now `paused: !root.active`), the logout countdown bar ignored
>   animations-off (950ms Behavior now gated, 16 variants), and Mo AI's remote live-ring
>   lacked its visibility term. plasmashell's ~9% idle reading is UNATTRIBUTED — the desktop
>   was not quiet during measurement; re-measure via the post-update checklist.
> - **Deliberately NOT done:** window titlebars stay opaque (documented material decision,
>   not an oversight); the hero logo artwork itself is untouched (owner's brand asset — only
>   its seating/halo/comet integration changed); the wallpaper `images_dark` duplication was
>   REFUTED as a defect (composefs dedupes to one object on disk, and images_dark is the
>   live dark-variant path).
>
> **Update 2026-07-16 (session C) — read this before touching themes, the keyboard, or Mo Remote.**
> Full writeup in `docs/FIXES_2026-07-16.md`. Four things landed and are on `main`:
>
> 1. **Theme FAMILY.** MoOS is no longer "ONE look" — it is a **family** on the single UI2
>    engine. Graphite (dark) + Tidal (light) stay the base; four palette-driven members were
>    added — **MoOS Nova, Amethyst, Midnight, Aurora** — each a full package set under
>    `org.moos.ui2.*`, generated by `artwork/generate_moos_themes.py` from
>    `artwork/moos-themes/palettes.json` (it recolours the working UI2 SVGs/decoration + reuses
>    `generate_moos_ui2.py`'s colour math; it does NOT revive the retired Nova/UI1 lineages).
>    `moos-theme <dark|light|nova|amethyst|midnight|aurora|list>` switches instantly;
>    `moos-apply-theme` is family-aware so a pick persists. `verify_identity.py` +
>    `tests/verify_user_experience.py` + `tests/test_moos_theme_safety.py` now enforce the
>    *family* (all MoOS-branded, no foreign, no old generation). The old top-level
>    `org.moos.nova`/`org.moos.ui` are still forbidden. `build.sh` hides the stock Breeze
>    Global Themes from the picker (Hidden=true, non-destructive) — Breeze stays the fallback
>    engine. Every theme was verified applying live. Passages below saying "ONE MoOS look"
>    describe the pre-family state.
> 2. **Keyboard = de,ara.** The owner's hardware is a GERMAN keyboard, so the default xkb layout
>    is now `de,ara` (`system_files/etc/xdg/kxkbrc`, installer `xkbForLang`), Alt+Shift toggle.
>    This is a LAYOUT only — the UI language stays bilingual ar/en (no German catalogues). The
>    old comment saying "de,ara was wrong" assumed US hardware; it does not, here.
> 3. **Mo Remote + terminal fixes** (session B→C): Arabic typed from the phone now works
>    (`agent-linux/InputInjector.cs` routes non-ASCII through clipboard, not portal keysyms);
>    the terminal's bold text is legible again (the Konsole scheme's Intense fg was inverted);
>    generic `monospace` no longer resolves to Kawkab (fontconfig binding).
> 4. **Build robustness.** `build.sh` writes the Tailscale repo file inline instead of
>    curl-ing it — a `pkgs.tailscale.com` 504 took a whole build down on 2026-07-16.

The owner rejected MoOS UI revision 15 as visually insufficient after reviewing
it on the installed machine. It remains installed and untouched as the explicit
fallback. The isolated **MoOS UI2** Graphite Dark / Tidal Light family is now
implemented, selected as the working-tree default, and proven in both variants
on the installed Plasma session. Its palette, package IDs, generated-image
prompts, independent dashboard, real screenshots, measured proof and rollback
rules are documented in [`artwork/MOOS_UI2_DESIGN.md`](artwork/MOOS_UI2_DESIGN.md).
**Correction (2026-07-27): `moos-theme ui1-dark|ui1-light` does not exist.** It was
planned, documented here as supported, and never implemented — `grep -c ui1
system_files/usr/bin/moos-theme` returns 0 — and UI1 itself was removed from the
shipped image in July 2026, so the command could not work even if it were added.
An agent trusting this line would run a nonexistent rollback on the owner's daily
driver. The real fallbacks, in increasing order of blast radius:
`moos-theme undo` (previous MoOS theme) → `plasma-apply-lookandfeel
org.kde.breezedark.desktop` (leave the MoOS family entirely) → `sudo rpm-ostree
rollback` + reboot (previous image). Do not leave user-local UI2 staging shadows
after testing.

### Revision 16.1 — the surfaces UI2 had missed

A full sweep of every visual surface found four places where the desktop was UI2
and the thing sitting on it was not. All four are fixed, and each one is now held
by a gate that was broken on purpose and watched go red:

- **A QML binding loop, live in the shipped image.** `WeatherScene.qml` bound
  `sourceSize.height` to `sourceSize.width` — both halves of one `QSize`, so the
  property depended on itself. Qt resolves that by *dropping* the binding, so the
  weather art decoded at a stale size and plasmashell logged the loop 21 times.
  The build already ran the dashboard and already grepped its log for
  `binding loop`, and **could never have caught it**: under
  `QT_QPA_PLATFORM=offscreen` the card is never laid out to a real width, the
  binding never re-enters, and Qt has no loop to detect. Reproduced deliberately.
  The gate that bites is therefore **static**, in `verify_user_experience.py`.
- **The login screen was still the retired Nova generation.** Everything moved to UI2 except the greeter,
  so the machine booted to a NovaHorizonII login screen and a Graphite desktop a
  second later. The gate could not catch it because it asserted the literal string
  `"NovaHorizon"` — it was pinning the bug in place. It now requires the login and
  lock screens to name the **same** wallpaper.
- **The boot splash was Nova navy** (`#050A14`, `#2E7BFF` bar) on a graphite OS. It
  is now gated against `artwork/moos-ui2/palette.json` rather than a hard-coded hex.
- **The kde-settings profile still named `org.moos.nova`** — a third family, which
  the theme switcher cannot even reach. This is the exact cascade layer AGENTS.md
  blames for Plasma resolving a stale name and persisting Breeze.

The pattern in three of those four: **the gate named a constant, and the constant
went stale.** The replacements gate a *relationship* (login screen == lock screen;
splash == palette; kde-profile == the image's own default), so the next theme
family inherits them for free.

`artwork/MOOS_UI2_DESIGN.md` ends with a coverage-gap list that is now largely
**closed**: teal MoOSUI2/MoOSUI2Light icon themes are built in build.sh,
libadwaita/Flatpak apps get the UI2 palette (moos-ui2.css + the gtk-4.0 read
hole), the lock screen is the MoOS shell-package override, and the desktop
dashboard lives INSIDE the wallpaper (org.moos.ui2.wallpaper — below the icons,
so it can never cover them). The Welcome (apps/welcome) is a real onboarding
wizard again; Mo Store (apps/store, /usr/bin/moos-store, org.moos.store.desktop)
is the standalone storefront. Verify against the gates, not this paragraph.

## Previous visual work: MoOS UI

The working tree contains the new **MoOS UI** dark/light visual pair, first-party
Mo AI and Mo PC Remote icon masters, a warm matched wallpaper, and the glass
desktop-widget evolution. The implementation contract, palette, generated-image
prompts, rollout rules and one-command regeneration path are in
[`artwork/MOOS_UI_DESIGN.md`](artwork/MOOS_UI_DESIGN.md). The retired Nova
generation (UI1-era) is NO LONGER installed — it was removed from the shipped
image in July 2026; see the removal note at the end of this section and use the
real fallbacks listed under "Active visual work" above. Do not hand-edit
generated MoOS UI package output;
change its masters and regenerate it. (Removed 2026-07-27: `artwork/generate_moos_ui.py` was the UI1 generator. It copied `plasma/desktoptheme/Nova` -> `MoOSUI`, and neither directory has existed in `system_files/` since UI1 was removed from the shipped image in July 2026 — running it produced nothing. UI2 is generated by `generate_moos_ui2.py` and `generate_moos_themes.py`.)

Visual revision 15 incorporates direct hardware review: the desktop widget is now
a wide animated live dashboard, and the Light dock owns a warm-mauve FrameSvg with
the exact Dark geometry. Both variants pin adaptive transparency off so Plasma
cannot turn only the Light dock into an opaque white slab. Current hardware proof
is under `artwork/moos-ui/live-tests/*-v2.png`.

---

## The shape of the thing

| Repository | What it is | How it reaches the user |
|---|---|---|
| `~/moos-image` | The OS. A bootc image built from `Containerfile` + `build_files/build.sh` + a literal filesystem tree in `system_files/`. | Push to `main` → GitHub Actions builds **two editions** (`moos`, `moos-nvidia`), signs them with sigstore, pushes to `ghcr.io/moalfarras-sys/`. The user's machine stages the resolved signed digest through `moai-do update`. |
| `~/MoPlayerMoOS` | The IPTV player. Flutter. Its own repository: **github.com/moalfarras-sys/MoPlayerMoOS**. | **Vendored** into `moos-image/moplayer/` by `just sync-moplayer`, then compiled *inside* the image by a Containerfile stage. The image ships the binary, never the toolchain. |
| `~/MoPlayerios` | An iOS build of MoPlayer. Not part of the OS. | — |

The machine this is developed on **boots the thing being developed**:
`ghcr.io/moalfarras-sys/moos-nvidia:latest`, signature-enforced. That is the whole
reason the gates below exist.

### Changing MoPlayer, end to end

MoPlayer has two homes and they are not equal. Its **repository** is where the work
happens; `moos-image/moplayer/` is a **snapshot** of it, and the snapshot is what
the image compiles. A change that lives only in one of them ships as half a change.

```
1. work + commit in ~/MoPlayerMoOS   (`just check` there: analyze + 114 tests)
2. push it                            → github.com/moalfarras-sys/MoPlayerMoOS
3. cd ~/moos-image && just sync-moplayer
      ↳ refuses a dirty MoPlayer tree — vendoring copies `git ls-files`, so an
        UNCOMMITTED file is copied by nobody and the image fails on a missing import
      ↳ also installs the launcher/.desktop/icons into system_files/ itself
4. commit the re-vendor, push          → CI builds and signs both editions
5. on the machine: `moai-do update`, then reboot from the MoOS power UI after the signed digest is staged
6. `./tests/post-update-check.sh`      → confirms the booted digest IS the published one
```

Never edit `moos-image/moplayer/` by hand. It is generated, and the next
`sync-moplayer` will silently erase you.

---

## The five traps that have actually bitten

These are not style notes. Each one shipped, or nearly shipped, and each one cost
hours to find because **the gate was green while the thing was broken**.

### 1. The shadowed-config trap
The image is right, the user still does not get it. `/etc/xdg/…` and
`/usr/share/…` are *defaults*; a file in `~/.config` or `~/.local/share`
**shadows them forever**. Staging a fix into the home directory to "prove" it on
the running desktop leaves that shadow behind. `moos-apply-theme` exists to remove
those shadows once the system copy is correct — extend it rather than writing a
new one.

**Corollary that cost two hours today:** `moos-selfcheck` verified the *system's*
keyboard layout (`localectl`, which said `de,ara`) while the *session* was running
`us`, because fcitx5 had rewritten `~/.config/kxkbrc`. A check that reads the
image instead of the running desktop cannot fail. It asks KWin now.

### 2. A gate that matches its own comment
Every file here documents the bug it prevents — so a gate written as
`"Kawkab Mono" in text` passes forever, because the *comment* names Kawkab Mono.
`tests/verify_user_experience.py` has a `code()` helper that strips comments.
**Use it.** And after writing a gate, **break the thing on purpose and watch the
gate go red.** A gate that has never failed has never been tested.

### 3. The build context is not the git tree
`COPY system_files/ /` copies from the *working tree*, and `.gitignore` has no say
in it. The image shipped `/usr/bin/__pycache__/moai-control.cpython-313.pyc` — the
bytecode cache of the build machine — while CI, building from a fresh clone,
shipped nothing of the sort. **Two different images from one commit.**
`.containerignore` now excludes it, and a gate in `build.sh` fails the build if any
`__pycache__` reaches `/usr/bin`.

And note the pattern syntax: `__pycache__/` matches only the **context root**. It
must be `**/__pycache__/`. The first version of that file looked right, read right,
and excluded nothing. The gate caught it.

### 4. Vendoring drops what git does not track
`just sync-moplayer` copies `git ls-files` from `~/MoPlayerMoOS`. An **untracked**
file is copied by nobody: the vendored tree keeps the import and loses the file,
and the image fails twenty minutes later, inside a container, on a missing URI. It
**refuses a dirty tree** now, and a gate walks every relative import in the
vendored source and fails if the target was not vendored.

### 5. The local LLM owns the graphics card
MoOS ships a local model that holds **~6 GB of an 8 GB card** while loaded. With
that little left, EGL cannot make a context: `eglMakeCurrent failed` → libepoxy
asserts → **the process aborts**. The user's own OS killed its own video player,
silently. `/usr/bin/moplayer` calls `moos-gpu-headroom` first, which unloads *only*
the brain and only when the card is nearly full. A gate requires the launcher in
`system_files/` to be **byte-identical** to MoPlayer's own
`packaging/moos/moplayer` — the guard lived in only one of them for two hours, one
`install -D` away from being lost.

**Practical rule:** check `nvidia-smi` free memory before launching anything
GPU-heavy for a screenshot. Do not open a browser to "set up a scene" — that
exhausted VRAM and took KWin down with a SIGSEGV.

---

## Verification: how to actually see things

- **Synthetic input does not work on this machine.** `ydotoold` runs, the uinput
  device exists, and KWin receives nothing — in logical *or* physical coordinates.
  Proven by clicking a window's close button in both spaces and watching the
  process live. **Never plan a loop that needs to drive a GUI.** Reach the state
  from outside instead: `moplayer --section live`, `moplayer <subscription-link>`,
  a route the app opens on. If a state can only be reached by clicking, add an
  honest CLI seam (it is usually a feature someone wanted) or ask the user.
- **Screenshot:** `spectacle -b -n -f -o out.png` (not `grim` — wlroots only), then
  crop and zoom with ImageMagick and *read the image*.
- **A new window opens behind a fullscreen app.** Make a temp virtual desktop,
  switch, launch, capture, switch back, remove.
- `konsole --geometry` **is not a valid option** — the process exits instantly and
  no window appears. This silently blinded a whole session.

---

## MoPlayer: the IPTV facts that decide the design

Measured against the maintainer's real subscription, not assumed:

- A subscription is sold as **one link**:
  `…/get.php?username=U&password=P&type=m3u_plus`. Pasted into an M3U field it
  *works* — and yields channels and nothing else. Read as what it is (a panel plus
  an account), the same string opens the whole Xtream API: **12,653 channels,
  20,187 films, 10,550 series.** That is `lib/services/source/source_link.dart`,
  and it is used by both the login screen and the command line.
- **`max_connections = 1`.** One stream at a time. Never design a flow that tunes a
  channel to show a preview — the user knocks their own stream off the air. This is
  why the live screen's third pane follows the channel you are *looking at*.
- Panels lie about their own API: this one answers `get_short_epg` and
  `get_simple_data_table` with `[]` for **every** channel, while `xmltv.php`
  returns 2,587 programmes. An "empty" guide is usually an unimplemented endpoint.
- The panel publishes **duplicate** `<programme>` elements, and serves its
  catalogue with 32 identical-artwork recorded matches first. Sort by `added` or
  the film wall reads as a failed image load.
- The home page's football comes from that guide, joined against the user's own
  channels, so every card is one press from playing. A fixture on a channel the
  account does not carry is **not drawn** — a card that cannot be pressed is a
  disappointment dressed as a feature.

---

## Owner's UX rules (do not "improve" these away)

- The dock has **seven** slots: search · home · live · movies · series · favorites ·
  settings. Home *is* in the dock — the corner logo was not enough.
- Every browse page: **groups (vertical) · wall · preview**. The preview follows
  hover **and keyboard focus**.
- **The mouse wheel scrolls the page.** A rail must never turn a vertical wheel
  into sideways movement — the home page is a column of rails, so that makes
  everything below the fold unreachable. Shift+wheel and the hover arrows move a
  rail. There is a widget test that fails if this regresses.
- Settings is an Apple-style panel. Its Updates section is honest: MoPlayer ships
  *inside* the image and `bootc` replaces the whole OS atomically, so there is no
  self-update button, because there is no self-update.
- The brand palette is **measured off `assets/branding/logo.png`**, not chosen
  beside it. A test opens the PNG and fails if the tokens drift.

---

## Gates — what runs, and where

| Gate | Runs in |
|---|---|
| `tests/verify_user_experience.py` | CI (before the build) **and** `just build` |
| `tests/test_device_plan.py` | same |
| `tests/test_moai_do.py` | same — covers all 17 `moai-do` actions and rejects anything off the list |
| `build_files/verify_image_experience.py` | *inside* the image, after every package and rebrand |
| `__pycache__` / bytecode-cache gate | inside the image, at the end of `build.sh` |
| MoPlayer bundle completeness | inside the `moplayer-build` stage |
| MoPlayer: `flutter analyze` + 114 tests | `just check` in `~/MoPlayerMoOS` |

They were honour-system until today: **not in CI, not in `just build`**. If you add
a gate, wire it into both, and break it once to prove it fires.

---

## Working rules

- `git status --short` before every batch. Another agent may be in the same tree —
  it has happened, and a commit landed on the wrong branch because of it.
- Do not commit, push, or change the installed image without the owner asking.
- Every visible fix adds a gate or a test that would have caught it.
- Do not invent a new file under `system_files/` before searching for the surface
  that already does that job.
