# MCP servers for MoOS

**What this is:** the four MCP servers every agent working on this repo gets, why each one
earns its place, and the one command that sets them up. Config lives in
[`.mcp.json`](../.mcp.json) (committed) and [`.claude/settings.json`](../.claude/settings.json)
(committed); machine-local values and secrets live in `.claude/settings.local.json`
(**gitignored, never committed**). Both committed files are guarded by
`tests/test_mcp_config.py`, which runs in `just check` and in CI's "Repo gates" step.

## TL;DR

```bash
just mcp-setup          # reuses or installs native Chromium, writes the local env
just check              # the gate that proves the config is still honest
```

Then add any API keys you want to `.claude/settings.local.json` (see [Credentials](#credentials)).
Everything except image generation works with **no key at all**.

---

## The four servers

| Server | Answers the question | Credential |
|---|---|---|
| `sequential-thinking` | *"I am about to change something load-bearing — have I actually thought it through?"* | none |
| `context7` | *"What is the CURRENT API for this, not the one I remember?"* | optional |
| `chrome-devtools` | *"What does this actually LOOK like, and what does it cost to draw?"* | none (needs a Chrome binary) |
| `image-gen` | *"Make me a wallpaper / boot plate / icon study."* | `GEMINI_API_KEY` |

### `sequential-thinking` — thinking

`npx -y @modelcontextprotocol/server-sequential-thinking`, from Anthropic's reference set.
Structured multi-step reasoning where a later thought is allowed to *revise* an earlier one and
branch off it.

The reason it is here and not just "nice to have": this repo's documented failure mode is a
confident, plausible, wrong conclusion — six traps in `PROJECT_STATE.md` where **the gate was
green while the thing was broken**, most recently a visual tier probe that had never once fired
on the machine it was written for. Use it before touching `build.sh`'s scrub sections, the
initramfs path, the NVIDIA kmod, or anything a gate claims to already cover.

### `context7` — thinking like a programmer

Remote HTTP server at `https://mcp.context7.com/mcp`. Fetches version-current documentation and
real code samples for a named library, instead of the agent recalling an API from training.

This repo is a pile of fast-moving APIs an agent will confidently misremember: **Qt 6 / QML**,
**KDE Plasma 6** (Plasma Style, Aurorae, KWin effects, `plasma-login-manager`), **Flutter/Dart**
(MoPlayer), **React 19 + Vite 8** (the Mo Remote controller PWA), **bootc/OSTree**, **cosign**,
and **GitHub Actions**. A QML property that was renamed between Plasma releases is exactly the
kind of thing that builds clean and fails on the real desktop.

Works anonymously. A free key only raises the rate limit.

### `chrome-devtools` — design and system tuning

Google's official `chrome-devtools-mcp`: a real headless Chrome the agent can navigate,
screenshot, snapshot the accessibility tree of, emulate a phone with, trace, and run Lighthouse
against. 29 tools.

Two concrete jobs in MoOS:

1. **Mo Remote's controller** (`moremote/controller`) is a genuine React 19 + Vite PWA — the one
   MoOS surface a browser can actually render. The agent can now open it, drive it, read its
   console, emulate the phone viewport it is designed for, and take a performance trace instead
   of reasoning about H.264 decode and gesture latency from the source alone.
2. **Artwork review.** `artwork/` generates 2000+ SVGs. The agent can build an HTML contact sheet
   of what it just generated, screenshot it, and *look* — which is the specific discipline
   `docs/MOOS_DESIGN_PLAN.md` exists to enforce after a whole session of changes turned out to be
   invisible.

It does **not** render QML, Plasma or the login screen. Those are still verified on the live
session per `skills/moos-engineering/SKILL.md`. A browser screenshot is not a desktop screenshot.

Usage statistics and CrUX URL reporting are **switched off** in `.mcp.json` — MoOS pages are not
public and their URLs are not Google's business.

### `image-gen` — image generation

`mcp-image@0.13.2`, exposing one `generate_image` tool. Its npx invocation explicitly
includes `ajv@8.17.1`: the standalone package failed during startup on the ARM host
because `ajv-formats` could not resolve `ajv`. Both versions are pinned together;
verify `initialize` and `tools/list` before updating them. Text-to-image and image-to-image editing, on
Gemini ("Nano Banana") by default, or OpenAI's `gpt-image` with `MOOS_IMAGE_PROVIDER=openai`.
Generates any aspect ratio up to 4K — which matters, because the reference session is 4K at 225%.

**Output goes to `/tmp/moos-generated-images`, deliberately outside the repo.** A generated image
is a draft. It reaches `system_files/usr/share/` only after a human has looked at it and
`artwork/verify_visuals.py` passes on it. Set `MOOS_IMAGE_OUT` to change the directory.

This does not replace `artwork/generate_*.py`. Those are deterministic, reproducible, and
gate-checked; the shipped identity is generated code, not a prompt. Use `image-gen` for
exploration, hero plates, wallpapers and texture studies — the things a script cannot invent.

---

## Credentials

Nothing here is required to start working. Only image generation needs a key.

| Variable | Needed for | Where to get it | Cost |
|---|---|---|---|
| `GEMINI_API_KEY` | `image-gen` (default provider) | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) | model/account dependent; no free image-generation guarantee |
| `OPENAI_API_KEY` | `image-gen` only if you set `MOOS_IMAGE_PROVIDER=openai` | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) | paid |
| `CONTEXT7_API_KEY` | `context7` — **optional**, raises the rate limit | [context7.com/dashboard](https://context7.com/dashboard) | free tier |
| `MOOS_CHROME` | `chrome-devtools`, if Chrome is not at `/opt/google/chrome/chrome` | written for you by `just mcp-setup` | — |

**Never put a key in `.mcp.json` or `.claude/settings.json`.** Both are committed, and
`tests/test_mcp_config.py` fails the build if a value in either one looks like a live credential.
Keys go in `.claude/settings.local.json`, which `.gitignore` keeps out of every commit:

```json
{
  "env": {
    "GEMINI_API_KEY": "AIza...",
    "MOOS_CHROME": "/var/home/YOU/.cache/moos-mcp/chrome"
  }
}
```

A missing variable is **not** fatal: Claude Code warns, the server still starts, and only the
call that needs the key fails.

### `MOOS_CHROME` is the exception: it must be a real shell export

**`settings.local.json` alone does not work for it, and this was measured.** With `MOOS_CHROME`
set in that file *and* visible to every command Claude Code ran, `chrome-devtools` still died on
the first navigate with:

```
Browser was not found at the configured executablePath (/opt/google/chrome/chrome)
```

— the unsubstituted default. `.mcp.json` expands `${VAR}` from the environment the CLI was
**launched with**, and the settings `env` block is applied after that, so a variable that lives
only in settings never reaches the server's argv.

`just mcp-setup` therefore writes **both**: the settings entry (for anything that reads it later)
and an `export` in `~/.bashrc` (the half that actually works). It is idempotent — running it twice
rewrites the line rather than appending a second one. **Open a new terminal before restarting
Claude Code**, or the export is not in the environment yet.

The same applies to any credential you want an MCP server's `env` block to expand: put it in your
profile, not only in `settings.local.json`.

---

## Setup

### `just mcp-setup`

Run once per machine. It:

1. reuses a runnable browser from `MOOS_CHROME`, the system, or existing Playwright/Puppeteer
   caches; if none exists, downloads native Chromium with Playwright (including Linux ARM64),
2. symlinks it to the stable path `~/.cache/moos-mcp/chrome` so a Chrome version bump does not
   break the config,
3. writes `MOOS_CHROME` into `.claude/settings.local.json`, merging rather than overwriting any
   keys already there.

Then open a new terminal and restart your Claude Code session so it re-reads the config.
Run `/mcp` to inspect each connection. A connected browser server is not enough: use
`list_pages` to prove its browser actually launches.

### Verified development environment (2026-09-06)

On the Oracle ARM host, credential-free JSON-RPC `initialize` and `tools/list`
passed for sequential-thinking (1 tool), Context7 (2 tools, anonymous HTTP),
Chrome DevTools (29 tools), and the corrected image server (1 tool). The old
image invocation failed with `Cannot find module 'ajv'`; the pinned pair above
passed both protocol requests. No image-generation request or paid API call was made.

The configured default `/opt/google/chrome/chrome` was absent. The existing native
Playwright browser at `~/.cache/ms-playwright/chromium-1243/chrome-linux-arm64/chrome`
successfully launched through Chrome DevTools and returned an isolated `about:blank`
page. Setup now discovers that browser rather than downloading a duplicate.
These probes verify the configured server processes, not automatic registration
in every editor or coding-agent client.

The persistent .NET SDK is `~/.local/share/dotnet` (10.0.400, ARM64 runtime
10.0.11). A temporary `net10.0` console project compiled and ran on both host
and VS Code Flatpak using the explicit SDK path. Repository projects target
`net10.0`, with the Windows agent targeting `net10.0-windows`/`win-x64`;
this smoke test does not prove Windows execution or every project build.
VS Code's local settings already select this SDK and add it to new terminals.
An older inherited agent shell may still lack `dotnet` on PATH; use
`~/.local/share/dotnet/dotnet` without reloading the owner's editor.

### Approval

`.claude/settings.json` lists all four in `enabledMcpjsonServers`, so no agent has to approve
them one by one. One caveat from Claude Code's own docs: in a **freshly cloned** repo those
committed approvals are ignored until you have trusted the folder — run `claude` in the repo once
and accept the workspace trust dialog. After that the approvals apply.

### In GitHub Actions

`.github/workflows/claude.yml` runs `claude-code-action` on `@claude` mentions. There is no Chrome
in that runner, so `chrome-devtools` reports a connection failure there and the other three work
normally. That is expected and harmless — it is a warning to the agent, not a failed job. Do not
"fix" it by deleting the server.

---

## Adding a fifth server

Think hard first. Every server's tool definitions are spent from the agent's context budget, and
every credential is one more thing this project has to trust. The set above is deliberately small.

If you do add one:

1. **Prove it runs here before you commit it.** Drive it over stdio and confirm `initialize` and
   `tools/list` return. A server that fails to connect is worse than no server: it burns a
   startup probe on every session and tells the agent a story about tools it does not have.
2. Add it to `.mcp.json` with `${VAR}` for every credential.
3. Add it to `enabledMcpjsonServers` **and** `permissions.allow` as `mcp__<name>` in
   `.claude/settings.json` — `tests/test_mcp_config.py` fails if you forget either.
4. Document it here: what question it answers, and what it costs.

### Considered and rejected

- **GitHub MCP** — `gh` is already installed and already allowed without a prompt. The MCP server
  would add ~30 tool definitions to do what `gh pr view`, `gh run view --log-failed` and
  `gh issue` already do from Bash.
- **Playwright MCP** — real overlap with `chrome-devtools`, which additionally gives performance
  traces and Lighthouse. Two browser servers is two browser downloads and double the tools.
- **Filesystem / Git / Memory reference servers** — Read, Write, Edit, Grep and Bash `git` already
  cover these natively, and Claude Code has its own memory.
- **Figma** — MoOS has no Figma file. The design system is generated by `artwork/*.py`; the
  source of truth is code, and `docs/MOOS_DESIGN_PLAN.md` is the brief.
