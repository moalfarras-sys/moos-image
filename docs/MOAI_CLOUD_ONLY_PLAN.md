# Mo AI — cloud-only brain, free by default

**Owner decision, 2026-09-06:** Mo AI must never download or run a model on the
user's computer. No local engine, no weights on disk, no multi-gigabyte first
run. The brain is a cloud API, and the default must be one a person can use
**without paying and without a credit card**. Paid providers stay available for
whoever wants them.

This file is the contract. Every edition of Mo AI — `moos`, `moos-nvidia`,
`moos-cloud`, `moos-arm` — follows it, and any agent picking up this work reads
this before touching `moai-*`.

---

## 1. Why, in the owner's terms

A local model on this class of machine is not a feature, it is a tax:

- The Oracle A1 measured **923 s** for the first message against `qwen3:8b` on
  CPU — the agent's own ~8.5k-token system prompt being read once. The KV cache
  does not survive the gaps between phone messages, so most messages arrive at a
  cold brain and pay it again.
- The engine image alone is **4.21 GB** of podman storage before any weights.
- `/boot` on this host was 78% full with two deployments. Disk is not free here.
- The desktop OOM incident of 2026-09-06 (S03) is unresolved. Adding a
  multi-gigabyte resident process to that machine is the opposite of the fix.

The cloud path measured **9 s flat from the first message** and is stronger at
code. The only thing local ever bought was privacy and offline use, and the
owner has decided that trade explicitly.

## 2. The free-tier landscape (researched 2026-09-06)

All of these are OpenAI-wire compatible, which is the wire `moai-gateway`
already speaks, so they need catalogue entries and nothing else.

| Provider | Free allowance | Card? | Endpoint |
|---|---|---|---|
| **Cerebras** | ~1M tokens/day — the largest free volume | no | `https://api.cerebras.ai/v1` |
| **Groq** | ~30 req/min, 131K context, `gpt-oss-120b` | no | `https://api.groq.com/openai/v1` |
| **NVIDIA NIM** | 120+ open-weight models | no | `https://integrate.api.nvidia.com/v1` |
| **OpenRouter** | ~50 req/day across 14 free models | no | `https://openrouter.ai/api/v1` |
| **Google AI Studio** | free tier on Gemini Flash | no | `…/v1beta/openai` |

**The architectural point:** each provider rate-limits independently, so routing
across several multiplies the free allowance. That is why the design below is a
*ladder*, not a single default.

## 3. The design

### 3.1 One route, no local branch

`moai-gateway` is the only process that sees a chat. Today it can route to a
local engine (Ollama on 11434 / RamaLama on 8081) or to a cloud provider. The
local branch goes away — not disabled behind a flag, **removed**, so no code path
can start an engine or trigger a download.

### 3.2 A free ladder, not one provider

Mo AI holds an ordered list of configured providers and walks it: first that
answers wins; a 429 or 5xx falls through to the next. A user with three free keys
gets three independent free allowances and never sees a rate limit.

### 3.3 Free first in the catalogue

`PROVIDERS` in `moai-agent-api` is what the settings UI offers. Free-tier entries
come first and are labelled as free, with their free model pre-selected. Paid
entries stay, unlabelled, below them.

### 3.4 Nothing is downloaded, ever

- No `ollama`/`ramalama` package in any edition's build.
- No `moai-brain.container`, no Modelfile, no `moai-local-engine`.
- `moos-ensure-brain{,.service,.timer}` and `moai-idle{,.service,.timer}`
  retire — both existed only to manage a local engine.
- Mo AI's QML offers a provider + key, never a model download.

## 4. Staged execution

A 40-file, ~380-reference migration lands in reviewable stages. Each stage is
independently correct: at no point is Mo AI half-migrated and broken.

| Stage | Work | Gate |
|---|---|---|
| **C1** | Free providers enter the catalogue, free-first, labelled | Catalogue gate: free entries exist, come first, carry a free model |
| **C2** | ✅ **landed.** `ensure_local()` refuses before its lock or any `systemctl`, so no engine can start and no model can download | Gate proves the refusal is the FIRST statement and unconditional; bite-tested behind a flag and below the lock |
| **C2b** | Delete the now-unreachable ~300 lines of local machinery in `moai-gateway` | Gate: no local port, unit or engine name survives |
| **C3** | Provider ladder with fall-through on 429/5xx | Executable test against stubbed providers |
| **C4** | Retire `moos-ensure-brain`, `moai-idle`, `moai-local-engine`, `moai.service`, the container + Modelfiles | Gate: the units and files are absent from the built image |
| **C5** | Builds stop installing any local engine; QML drops the download path | Finished-image gate asserts no engine package |
| **C6** | `moai-brain-mode` becomes provider selection, not local/hybrid/cloud | Gate + the `moos-open`/`moai-do` route cross-check |

**Do not skip C2's gate.** The failure this whole plan exists to prevent is a
chat message quietly starting a multi-gigabyte download, and only a gate that
reads the shipped `moai-gateway` can prove that path is gone.

## 5. Hermes Agent — what it is and how it relates

[Hermes Agent](https://hermes-agent.nousresearch.com/) (Nous Research, MIT,
v0.21.0) is an open-source agent with persistent memory, 40+ tools including web
browsing and vision, subagents, scheduled automation, and a single gateway to
Telegram / Discord / Slack / WhatsApp / Signal / Email / CLI.

MoOS already has the *shape* of this: `moai-gateway` is a front door, OpenClaw is
the messaging gateway, `moai-do` is the privileged action allowlist. What Hermes
has that Mo AI does not is **persistent memory, self-generated skills, and
subagents**.

**Integration position — deliberate, not timid.** Hermes' execution backends
include `local`, Docker and SSH, and its desktop app runs an agent with tool
access. MoOS's security contract (`AGENTS.md`) is that a model may *name* an
action from `moai-do`'s fixed allowlist and never execute anything itself. Those
two designs conflict, and the MoOS one wins on the machine.

So the useful borrowing is the **capabilities**, not the runtime:

1. **Persistent memory** — a per-user store Mo AI reads at the start of a turn
   and writes at the end. Highest value, no privilege change. Start here.
2. **Skills** — named, reviewable procedures, stored as data, executed only
   through `moai-do`. Never model-generated shell.
3. **Subagents** — a bounded second conversation for long tasks.
4. **Tools** — web search and fetch first; they need no local privilege.

What MoOS must NOT adopt: any path where the model executes a command it wrote.
That is the one rule `AGENTS.md` calls unbreakable, and Hermes' `local` backend
is exactly that path.

## 5b. A defect C2 created, and what is still owed

Closing `ensure_local()` made every UI surface that offers a model download a
**dead button**, and `AGENTS.md` is explicit that a button which does nothing is
a defect. That was created by this work, so it is recorded here rather than
discovered later.

**Fixed immediately:** `moos-open`'s `brain/start` route ran `moai-start`, which
brings up a local engine. It now opens `moai-config`, the cloud provider setup —
which is what "start the brain" means once the brain is a cloud API. Mo AI's
`startBrain()` therefore still works and lands somewhere useful.

**Still owed (stage C5), and currently misleading:** `system_files/usr/share/moos/apps/moai/main.qml`
still carries the local-download UI — `pullModel` / `pullPercent` / `pullError`,
the "one-tap download" row, and a status line that promises *"the first run
downloads the model (~2.5 GB)"*. None of it can succeed now. It does not crash
and it does not download, but it tells the user something untrue.

**C5 must ship before this branch is promoted.** A release that says it will
download 2.5 GB and then refuses is worse than either behaviour on its own.

## 6. What must stay true

- The gateway remains the only process that sees the API key.
- Privileged actions remain `moai-do`'s fixed allowlist with Polkit.
- Arabic stays first-class in every string this touches.
- No edition gets a different answer: one implementation, four editions.

## 7. Open, honestly

- The provider ladder is designed, not yet measured. Latency and failover
  behaviour need a real test against real free endpoints.
- Free tiers change. The catalogue is a starting point, not a guarantee, and the
  gate checks its *shape*, never that a third party is still generous.
- Hermes integration beyond memory is unscoped work, not a promise.

Sources for §2 and §5: [OpenRouter free-model comparison](https://openrouter.ai/blog/tutorials/free-llm-apis-compared/),
[awesome-free-llm-apis](https://github.com/mnfst/awesome-free-llm-apis),
[Hermes Agent](https://hermes-agent.nousresearch.com/).
