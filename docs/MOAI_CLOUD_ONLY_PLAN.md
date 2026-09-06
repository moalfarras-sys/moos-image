# Mo AI — cloud-only inference and Hermes

**Latest owner decision, 2026-09-06:** Mo AI must never download or run a local
model. Cloud models may be **free or paid**. Free is the default; paid is an
explicit labelled selection, never an automatic fallback from a free quota.
This supersedes the earlier strict-free-only request and older local/hybrid plan.
Read `START_HERE_CURRENT_SESSION.md` for the active release checkpoint.

## Shipped-source design

All four editions share `usr/lib/moai/moai_cloud_policy.py` and the same Mo AI
front door. The currently supported provider is OpenRouter, with two visibly
separate choices: Free and Paid by choice. Free routes accept `openrouter/free`
or an explicit `:free` model and send a zero maximum prompt/completion/request/
image price. Caller-supplied paid plugins, alternate models and provider routing
are discarded. A free model keeps that zero ceiling even in paid mode.

The current catalogue is fetched from the provider; free mode filters out every
nonzero/missing/invalid price and every model lacking an explicit free identity.
The documented free router remains available if catalogue fetching fails.
Provider quotas still apply. There is no unlimited-free guarantee and no claim
that a large model always outperforms every other model. Paid inference was
NOT used in this session; its policy boundary is tested with fixtures.

Settings is the single owner of the cost choice (`moai-agent/state.json`). The
gateway reads it, and defaults to free when absent/unreadable. The cloud key stays
in existing private storage and never reaches QML. Local models/engines and local
speech cannot be started through the public chat/pull/setup/preflight routes.
Private/local-only attachments are refused, not silently uploaded.

## Hermes integration

`moai-hermes` adapts an **already installed Hermes Python runtime** behind a
private loopback HTTP service. `moai-gateway` starts that fixed service on demand
for agent requests and forwards to it when ready. Hermes inference comes back
through the same Mo AI cloud policy, so it cannot independently choose a paid
or local provider. A Python I/O boundary restricts it to that gateway and blocks
subprocess execution. Its agent tools are explicitly empty and verified empty.

The owner-installed Hermes 0.21.0 was actually tested: a conversation through
Hermes -> source Mo AI gateway -> free cloud returned Arabic in ~5.8 seconds.
A direct `nvidia/nemotron-3-super-120b-a12b:free` request returned `جاهز` and
reported cost 0. The integration retains the history passed by the Mo AI UI.

The adapter uses an isolated home at `~/.local/share/moai/hermes`, not the
owner's separate `~/.hermes` account or Telegram gateway. A private token guards
its loopback API; browser Origin requests and provider/tool overrides are denied.
The service has bounded memory/restart settings and does not start at login.

**Explicit limits:** text/history only; no Hermes tool execution, persistent
memory, plugin loading or autonomous system changes. Its SSE response is a final
answer frame, not incremental token streaming. A fresh system without Hermes
reports the missing runtime and uses direct cloud; packaging/installing Hermes
for fresh editions remains an acceptance task. Do not claim a dependency is
shipped merely because the owner's installed runtime works.

## Migration and authority

`moai-cloud-migrate` runs before the gateway and after the Agent API's legacy
bootstrap. It keeps a private one-time config backup, removes local fallback
selection, disables local speech and stops/masks fixed legacy Mo AI units.
Existing weights and unrelated user files are preserved. Compatibility commands
open cloud settings or refuse; they cannot start an engine. Some unreachable
legacy helper bodies remain for a subsequent cleanup (C2b); their presence does
not authorize restoring old UI choices or downloads.

Privileged actions remain `moai-do`'s fixed allowlist. Hermes and the model never execute generated commands. The user's terminal workspace is a separate,
explicitly controlled feature, not a model tool.

## Acceptance and next tasks

- C1: free default / explicit paid catalogue; policy fixtures and live free reply.
- C2: public local inference/pull paths refuse; legacy units are retired.
- C2b: delete unreachable old helper bodies after removing legacy-only tests;
  preserve HTTP/identity/privilege coverage and replace old policy tests with
  executable cloud-only behavior. Do not erase a guard to get a green build.
- C3: no cross-provider fallback ladder is shipped. OpenRouter handles provider
  fallback within the selected model. Free quota exhaustion can still stop a reply.
- C4: prove first-login and upgrade migration from every historic local layout;
  local speech UI needs a future cloud transcription feature before re-enabling.
- C5: local engine packages are omitted by both architecture builds. Check the
  actual finished image and signed update, not just package-list source.
- C6: full native QML / phone agent tests, Hermes package availability on fresh
  systems, then incremental streaming and bounded memory under the same authority.

Current changed source tests include catalogue/refusal, executable price/model
policy, atomic migration, Hermes auth/input isolation, and the prior HTTP origin
and stream-error contracts. Run the CURRENT workflow gates on the host.

## Sources checked 2026-09-06

- [OpenRouter free router](https://openrouter.ai/docs/guides/routing/routers/free-router)
- [Provider max-price boundary](https://openrouter.ai/docs/guides/routing/provider-selection)
- [Rate limits](https://openrouter.ai/docs/api_reference/limits)
- [Hermes integrations](https://hermes-agent.nousresearch.com/docs/integrations/)

A provider's marketing free tier is not proof that every API key is unbillable.
Other providers need an explicit, tested billing boundary before joining free mode.
