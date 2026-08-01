# Mo AI Workspace — architecture and execution ledger

Last updated: 2026-08-01

This is the durable implementation map for rebuilding the existing Mo AI. It is
deliberately a ledger, not a promise: checked items exist and have passed the
named evidence; unchecked items are not complete. A future agent starts here,
then reads `AGENTS.md`, `skills/moos-engineering/SKILL.md`, and
`PROJECT_STATE.md` before changing code.

## Product decision

Mo AI remains a native MoOS Qt 6 / Kirigami application. Rewriting it in a new
language would discard working hardware, update, compatibility, model and remote
control paths without improving the product. The safe migration is incremental:

1. keep `/usr/bin/moai` and `org.moos.moai.desktop` as the stable entry point;
2. split the 5,000-line QML window into product surfaces behind stable APIs;
3. make `moai-agent-api` the per-user workspace backend for conversations,
   projects, tasks, attachments, terminal sessions and channel state;
4. keep `moai-gateway` as the only model front door;
5. keep privileged system changes in the fixed `moai-do` allowlist, with visible
   confirmation and Polkit. Neither QML nor arbitrary model text receives a
   privileged shell.

## Target information architecture

```text
Mo AI
├── Workspace sidebar
│   ├── New chat
│   ├── Search
│   ├── Conversations (pin / rename / archive)
│   ├── Projects
│   └── Tasks
├── Conversation canvas
│   ├── Markdown / code / tool-result timeline
│   ├── text / voice / image / file composer
│   ├── Local / Cloud / Hybrid route indicator
│   └── approval cards for sensitive tools
├── Workbench
│   ├── project files and changes
│   ├── task plan and live tool progress
│   └── real terminal tabs (user-owned PTYs)
├── Device tools
│   └── current Device / Apps / Compatibility / Remote capabilities
└── Settings
    ├── Models & Providers
    ├── OpenClaw / Telegram / WhatsApp
    ├── Voice
    ├── Permissions
    ├── Memory / Projects / Terminal / Privacy
    └── Appearance
```

The desktop and phone channels share the same OpenClaw session store and agent
workspace. Channel adapters do not own a second memory or a second tool policy.

## Security boundaries

- Loopback is not an authorization boundary. Every mutating workspace request
  carries `X-Moai-Agent: 1`, rejects foreign origins, caps request bodies and
  never returns stored credentials.
- Read-only, project-write, system-control and full-control are explicit policy
  levels. Full control is never the shipped default.
- A desktop terminal is a real user terminal, not a privileged terminal. Model
  access to it is a separate approved tool operation with an audit record.
- Project paths resolve inside the real home directory; symlink escapes and
  arbitrary absolute paths are rejected.
- System operations remain fixed `moai-do` actions. Free-form `pkexec`, `sudo`,
  or a `moos://` command payload is forbidden.
- Attachments are copied into a private per-user store with generated names,
  size/type checks and no executable permission.

## Runtime and power model

`moai-agent-api`, `moai-control` and `moai-gateway` stay lightweight. OpenClaw,
the local model and speech engine start on demand. Existing idle timers remain
the source of truth and must be extended—not duplicated—when terminal/task idle
cleanup lands. No decorative perpetual animation is allowed.

## Delivery ledger

### Phase 0 — audit and contracts

- [x] Inspect current QML, gateway, control API, agent API, OpenClaw bootstrap,
  user units, permission tiers and existing gates on current `main`.
- [x] Preserve Qt/QML + Python; reject a risky language rewrite.
- [x] Record the target architecture and honest phase ledger in this file.
- [x] Add a machine-readable `/api/capabilities` endpoint and contract tests;
  unavailable work (binary extraction and model terminal access) reports false.

### Phase 1 — workspace foundation

- [x] Conversation metadata: search, pin, rename and archive without modifying
  OpenClaw's own session schema.
- [x] Project registry with canonical paths, recent activity and per-project
  permission policy.
- [x] Persistent task records: plan, steps, status, errors, result, stop/retry.
- [x] Replace the fixed 76 px rail with a responsive workspace sidebar while
  preserving direct `moai --panel …` compatibility shims. It stays compact at
  the supported 720 px minimum and expands to 188 px at 1120 px, with readable
  12 px horizontal labels and a labelled Settings action. Real source-QML
  captures inspected both 720×540 RTL compact and 1440×900 RTL expanded states
  (`/var/tmp/moai-sidebar-{compact,expanded}.png`) without clipping.
- [x] Merge the workspace conversation/history sidebar visually into the
  primary conversation canvas. The searchable/archived session drawer now
  opens a real OpenClaw JSONL thread in the central chat and continues with its
  exact guarded OpenClaw session key. The primary
  streaming/multimodal canvas now routes through the
  same token-authenticated, loopback OpenClaw runtime used by phone channels.
  Stable per-chat session ids preserve memory; direct-model fallback is explicit
  when OpenClaw is unavailable. Live 4K RTL evidence loaded session
  `3630741b-c82d-40a8-95ba-2b333031eafc` and its four real messages; a following
  gateway request with that same session key returned the remembered token
  `MOAI-LOCAL-UNIFIED-READY` and `X-MoAI-Agent: openclaw`.

### Phase 2 — composer and content

- [x] Markdown/fenced code rendering, selectable replies with a one-click Qt
  clipboard action, and structured OpenClaw tool-call/result cards. Tool cards
  preserve running/success/error state with semantic theme colours. Transcript
  reads are bounded to the newest 8 MiB, 400 cards and 12,000 characters per
  card so a long-lived phone session cannot freeze the desktop. A real 4K RTL
  source run rendered `exec` arguments and its actual `opened (setsid): code`
  result from OpenClaw session `b8c34309-36c9-4dcd-9280-239be24e4ab6`.
- [x] Private attachment ingest for images, text and common documents through
  drag/drop and picker. PDF extraction uses fixed `/usr/bin/pdftotext` argv,
  the first 50 pages and a bounded private temporary output; DOCX/ODT read only
  their exact bounded XML member without extracting ZIP paths. All document
  text is capped at 512 KiB before entering chat. Image payloads use the OpenAI
  multimodal shape and the capability-verified vision route. Other binary
  formats remain metadata-only rather than pretending their content was read.
- [x] Desktop push-to-talk capture uses PipeWire and the existing local speech
  service. Live capture reached transcription; an English synthesized speech
  proof traversed the shipped `moai-transcribe`/Speaches path, auto-detected
  `en` at 0.93 and returned `Hello, I am the MOAI assistant.`. The wrapper now
  defaults to bilingual auto-detection while retaining validated `ar`/`en`
  overrides. Intentional Speaches idle shutdown accepts the container's normal
  forced-worker exit 137 instead of leaving a failed user unit. A real human
  Arabic microphone sample remains desirable visual/release evidence.
- [x] Vision requests route only to a model that explicitly advertises image
  input. Ollama rows use the real `/api/show` `vision` capability; provider
  rows preserve advertised `input`/`modalities`; uncertainty is conservatively
  text-only. QML no longer guesses from `vl` in a name and keeps an image unsent
  with a clear error when no eligible route exists. Dynamically discovered,
  already-pulled Ollama models may cross the OpenClaw model override after the
  fixed local availability check. A clean live source request sent a PNG through
  Mo AI → unified OpenClaw → `qwen3-vl:4b` and received `blue` in 17.6 seconds
  with `X-MoAI-Agent: openclaw`.
- [x] Streaming responses expose real XHR cancellation and regeneration. Retry
  removes the previous user/assistant turn and resends the exact stored content
  payload, so image/document parts are preserved without duplicating history;
  it does not reconstruct attachments from display text. Direct-agent fallback
  and stream truncation remain explicit in the response/header UI and tests.

### Phase 3 — agent workbench

- [x] Real PTY backend with terminal tabs, bounded output, stop and exit status.
- [x] Terminal UI rendered inside Mo AI; no fake command list. Live evidence
  showed `printf 'Mo-AI-terminal-live\n'` and its real shell output.
- [x] Project file tree, bounded UTF-8 preview and real Git status/diff review;
  fixed Git argv, canonical-root enforcement and symlink escape tests are in
  `test_moai_workspace.py`. The live 4K RTL workbench evidence is
  `/var/tmp/moai-project-workbench-direct.png`.
- [x] OpenClaw's real exec-approval queue is tied to tracked tasks by their
  guarded `moai-task-<uuid>` session key. Task cards show the exact bounded
  command/cwd and only the decisions OpenClaw allows (`allow-once`, optional
  `allow-always`, `deny`). Mo AI resolves through the official Gateway
  WebSocket protocol; the credential and arbitrary RPC methods never reach
  QML. A live source-API proof listed request
  `9c42b3e3-b9a4-4c52-bcfb-cbf296315cc5`, denied it, observed an empty queue,
  and persisted the hashed-command decision in the audit ledger. The four
  actual enforcement levels (read, project, system-with-approval, full) remain
  implemented and tested.
- [ ] Append-only audit events for every executed tool and policy decision.
  The bounded persistent ledger now covers task process actions, project reads,
  Git diff, permission/project policy changes and approval decisions (with a
  command hash rather than duplicated command text). All OpenClaw tool outcomes
  still need ingestion before this item can close.
- [x] Tracked task execution launches only the fixed OpenClaw binary/arguments,
  persists real exit output, extracts actual JSONL tool-call names, and controls
  its process group for pause, resume and cancel. The 4K RTL/Light task surface
  was inspected in `/var/tmp/moai-task-runner.png`.

### Phase 4 — brains and channels

- [x] Add `hybrid` routing with a documented privacy/availability/complexity
  policy and deterministic fallback; never silently send private files to cloud.
- [x] One session/memory/tool backend for desktop and OpenClaw. A real local
  two-turn desktop request returned `MOAI-LOCAL-UNIFIED-READY` from memory, and
  the shared OpenClaw index recorded session
  `agent:main:openai-user:moai-desktop-local-proof`. The source QML streaming
  proof is `/var/tmp/moai-unified-chat-live.png` and visibly reports
  `Unified agent` beside `qwen3-vl:4b`.
- [x] OpenClaw can select `moai/hybrid`, an internal loopback provider that sends
  phone turns through `moai-gateway`'s privacy/availability/complexity policy
  without recursively invoking the agent endpoint.
- [x] Telegram verified end to end with the owner allowlist. Current config is
  `dmPolicy=allowlist` for owner `1142563280`; a real `agent:main:main` session
  contains five owner-marked inbound turns and two assistant delivery mirrors
  whose ids are explicitly `telegram-final:…:1142563280`. A cold-start source
  `/api/channels` proof then waited for the actual Gateway socket and returned
  `@Moalfarras_bot`, polling and `connected:true`. The status implementation was
  fixed to wait for loopback readiness rather than racing systemd startup.
- [ ] WhatsApp: the installed OpenClaw build confirms a supported WhatsApp Web
  login adapter and Mo AI exposes its fixed login route. Account pairing and an
  end-to-end message are not yet verified.

### Phase 5 — settings and product polish

- [x] Reorganize settings into twelve distinct functional pages: Models,
  Providers, OpenClaw, Telegram, WhatsApp, Voice, Permissions, Memory, Projects,
  Terminal, Privacy and Appearance. Privacy exposes all three real brain modes;
  secret fields stay write-only; OpenClaw shows live setup status; Terminal opens
  the real PTY workspace; Appearance delegates to the shared MoOS theme picker.
  The unreachable duplicate Health settings page was removed. Live 4K RTL source
  evidence covered the twelve-page grid, Hybrid selection and configured
  OpenClaw status.
- [ ] Light/dark and Arabic/English coverage at compact, desktop and 4K sizes.
  Partial evidence now exists for the complete Settings grid and Terminal page
  in English/LTR at the enforced compact minimum `720×540`, plus Permissions in
  Dark/RTL on the live 4K session. The exact prior `MoOS Scholar Light` theme was
  restored after review. Chat, Projects, Tasks and Terminal still need the full
  cross-product before this item can close.
  A source-only `--layout-direction ltr|rtl` review switch now makes both
  directions deterministic without changing the owner's KDE session. New live
  captures verified 720×540 Light/LTR Providers, 1440×900 Dark/LTR Chat and
  720×540 Dark/RTL Terminal; the exact Scholar Light theme was restored. These
  add real matrix cells but do not yet close the full cross-product.
- [x] Keyboard navigation, focus order, screen-reader labels and reduced motion.
  Every hand-drawn action uses the shared Tab/Enter/Space `ActionArea`; modal
  sheets take focus and close with Escape. A live Qt accessibility run with
  `QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1` exposed Mo AI through AT-SPI, found zero
  unnamed interactive controls after adding explicit labels/`labelledBy` links
  for secret fields and switches, and real `ydotool` Tab traversal reached named
  chat actions, composer, modal Close and Settings tabs in order. The existing
  real-QML motion gate proves all fixed transitions collapse and all loops stop
  when KDE animations are disabled.
- [ ] Remove superseded panels and code only after runtime consumers and gates
  prove they are unused.

### Phase 6 — release proof

- [ ] Source and image builds pass the exact CI gates.
- [ ] Live functional evidence: chat, voice, image, file, terminal, each brain
  route, task stop/resume, approvals and both configured phone channels.
- [ ] Live screenshots: light/dark × RTL/LTR × compact/4K primary screens.
- [ ] Update `PROJECT_STATE.md` and `MOOS_ROADMAP.md` with only verified facts.
- [ ] Publish and signature-verify all three images, stage the live update,
  reboot with user consent and run `tests/post-update-check.sh`.

## Verification commands

Fast gates after every slice:

```bash
python3 -m py_compile system_files/usr/bin/moai-agent-api \
  system_files/usr/bin/moai-control system_files/usr/bin/moai-gateway
bash -n system_files/usr/bin/moai system_files/usr/bin/moai-do \
  system_files/usr/bin/moos-open build_files/build.sh
just check
```

The release gate is a full local image build followed by the signed CI matrix.
Visual claims additionally require screenshots from the running QML surface.
