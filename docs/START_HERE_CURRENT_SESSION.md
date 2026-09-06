# Start here — current Mo AI integration and release checkpoint

Updated 2026-09-06. Read this BEFORE continuing this session's unfinished work,
then AGENTS.md, skills/moos-engineering/SKILL.md, PROJECT_STATE.md and
MOAI_CLOUD_ONLY_PLAN.md. Current runtime/source evidence outranks older prose.

## Owner's latest decision

Mo AI must use CLOUD inference only on every edition. No local model engine,
model download, local fallback or local speech model may start through Mo AI.
The newest instruction permits free OR paid cloud models: use free by default;
paid must be an explicit visible selection, never an automatic rescue from a
free quota failure. This supersedes the earlier strict free-only requirement.
Hermes must be integrated into Mo AI, not merely mentioned in a roadmap.

## Working tree and ownership

Work is on fix/system-audit-20260905, PR 74; PR 73 is merged. Query git/GitHub
before acting. The last observed committed head is ef4cd90e. There are intentional
UNCOMMITTED edits for cloud policy, gateway/control/settings, isolated Hermes,
MCP setup, tests and this checkpoint. Preserve them; do not reset/clean/rebase
over them. Other agents have committed to this same directory during the task.
Only the primary agent owns integration, image builds, pushes and deployment.

The coding shell is inside VS Code Flatpak. Run host commands via
flatpak-spawn --host. Rootless images and builds belong to the desktop user:
use podman and systemctl --user, not sudo podman or system service listings.
Never print credential files, full process command lines or private journals.

## Actual state and evidence

- .NET SDK 10.0.400 / runtime 10.0.11: a minimal program compiled and ran on
  both host and editor sandbox. Persistent SDK is ~/.local/share/dotnet.
- MCP: actual initialize/tools-list passed for sequential-thinking, Context7,
  chrome-devtools and repaired mcp-image. Native ARM Chromium is reused through
  ~/.cache/moos-mcp/chrome. Justfile/.mcp.json/docs/MCP.md edits must be retained.
  No image generation or paid MCP request was made.
- Live local Mo AI engine and idle timer were stopped/masked. Models/files were
  not deleted. moai-cloud-migrate preserves private .before-free-cloud backups.
- Source free policy sends ONLY explicit OpenRouter free IDs plus max_price=0,
  strips paid plugins/routing overrides and never falls back to a local engine.
  An explicit paid provider choice is now implemented and labelled; its boundary
  is fixture-tested. No paid inference was made.
- A real source-gateway request to nvidia/nemotron-3-super-120b-a12b:free
  answered Arabic "جاهز" with reported usage cost 0. A short 32-token free-router
  probe returned no visible content; do not count that as a successful reply.
- Installed Hermes 0.21.0 works through the NEW isolated moai-hermes adapter.
  Its constructor had tools=[]; a real request through Hermes -> Mo AI source
  gateway -> free cloud answered Arabic in ~5.8 seconds. No paid request made.
  The adapter does NOT start the owner's Hermes messaging gateway or read its
  ~/.hermes state. It uses ~/.local/share/moai/hermes and a private bearer token.
- Hermes currently offers text conversation/history, no model-executed shell,
  files, MCP tools or persistent memory. SSE is one final-answer frame, not
  incremental generation. These limitations must remain explicit.
- Source probe services: moos-free-cloud-probe (18080), moos-hermes-probe (18090).
  Inspect state before stopping; these are disposable, not the owner's Remote.
- Last live boot readback: 44.20260906.284, digest d204555227e4992ef0424188873bbb0801144fd19937a1e5f38c096e64bb7b35,
  with ostree-unverified-registry origin. The previous deployment .263 retains
  ostree-image-signed origin at 049a620d0f64a997c047dea1e8811b93b394c0afc62ce754bae05506099ce227.
  Restore enforced signed update origin via the normal verified release path;
  never treat unverified origin as successful signed deployment.
- Native build localhost/moos-arm:audit-resume completed earlier at 3c82bd0e0458
  BEFORE the current Mo AI edits. It is not proof of the current working tree.
- /boot DTBs were deduplicated with byte/permission/xattr verification and both
  deployments preserved; free space rose 205 -> 302 MiB at that moment. Recheck
  current space after the owner's subsequent update.

## Next bounded work, in order

1. Finish cloud-only policy (free default / explicit paid), including old
   moai-do install/setup, OpenClaw preflight/bootstrap and voice entry points.
   Current top-level guards leave legacy helper bodies present; audit every
   externally reachable start path before claiming no local inference.
2. Finish settings/model-picker truth and on-demand Hermes service wiring.
   Validate new cloud-policy/migration and Hermes HTTP tests; keep all existing
   HTTP-origin/auth, privilege and identity guarantees.
3. Re-run exact CURRENT workflow gates on HOST. Previous full run had 5 failures
   from intentionally superseded local-mode expectations; most were updated.
   Re-run, do not assume green. test_moai_http_security's remaining routing-model
   expectation was corrected but needs a fresh result. Identity gates were not
   removed or weakened. The updated experience gate now requires local-engine
   retirement rather than starting a deprecated local engine.
4. Visually launch the actual QML using a persistent host helper or isolated
   smoke harness; no ydotool in the owner's live session. Mo PC Remote IS the
   user's display: never stop/restart it or KWin during normal work.
5. Native ARM full build, inspect finished bytes, push reviewed changes, green
   PR/merge, signed release + artifact boot proof, then stage exact digest with
   signature enforcement. User has authorized update/reboot; checkpoint first.
6. Post-reboot verify digest/signature, Remote, services, clock/storage, UI and
   bounded memory series. A local postboot timer scaffold exists under
   ~/.config/systemd/user/moos-audit-postboot.*; its plan file must use the NEW
   old boot ID and final expected digest. It must not count the previous boot.

## Never claim these are complete

Unresolved desktop OOM cause (S03), actual multi-scale keyboard-focus sweep,
deliberate broken-update rollback, real NVIDIA/device matrix, paid-provider
integration until tested, globally shipped Hermes dependency (currently an
adapter for an installed runtime), and universal app compatibility.

Full engineering plans remain docs/MOOS_SYSTEM_DEVELOPMENT_PLAN.md and
MOOS_ROADMAP.md. Update this checkpoint with exact commit/build/digest/results
before handing off; avoid a second contradictory historical plan.
