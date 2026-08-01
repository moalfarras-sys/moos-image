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
- [ ] Replace the icon-only rail with a responsive workspace sidebar while
  preserving direct `moai --panel …` compatibility shims.
- [ ] Merge the separate Agent panel into the primary conversation canvas.

### Phase 2 — composer and content

- [ ] Markdown, fenced code, copy actions and structured tool-result cards.
- [x] Private attachment ingest for images and text files, drag/drop and picker;
  image payloads use the OpenAI multimodal shape and select an installed VL
  route. Arbitrary binary document extraction remains open.
- [x] Desktop push-to-talk capture uses PipeWire and the existing local speech
  service. Live capture reached transcription; the silent three-second proof
  correctly returned "no speech", so spoken-language verification remains open.
- [ ] Vision requests routed only to a model that advertises image capability.
- [ ] Streaming responses with stop/regenerate and explicit fallback messages.

### Phase 3 — agent workbench

- [x] Real PTY backend with terminal tabs, bounded output, stop and exit status.
- [x] Terminal UI rendered inside Mo AI; no fake command list. Live evidence
  showed `printf 'Mo-AI-terminal-live\n'` and its real shell output.
- [ ] Project file tree, diff review and test/Git tool result cards.
- [ ] Approval queue tied to task steps. The four actual enforcement levels
  (read, project, system-with-approval, full) are implemented and tested.
- [ ] Append-only audit events for every executed tool and policy decision.
- [x] Tracked task execution launches only the fixed OpenClaw binary/arguments,
  persists real exit output, extracts actual JSONL tool-call names, and controls
  its process group for pause, resume and cancel. The 4K RTL/Light task surface
  was inspected in `/var/tmp/moai-task-runner.png`.

### Phase 4 — brains and channels

- [x] Add `hybrid` routing with a documented privacy/availability/complexity
  policy and deterministic fallback; never silently send private files to cloud.
- [ ] One session/memory/tool backend for desktop and OpenClaw.
- [ ] Telegram verified end to end with the owner allowlist.
- [ ] WhatsApp: the installed OpenClaw build confirms a supported WhatsApp Web
  login adapter and Mo AI exposes its fixed login route. Account pairing and an
  end-to-end message are not yet verified.

### Phase 5 — settings and product polish

- [ ] Reorganize settings into Models, Providers, OpenClaw, Telegram, WhatsApp,
  Voice, Permissions, Memory, Projects, Terminal, Privacy and Appearance.
- [ ] Light/dark and Arabic/English coverage at compact, desktop and 4K sizes.
- [ ] Keyboard navigation, focus order, screen-reader labels and reduced motion.
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
