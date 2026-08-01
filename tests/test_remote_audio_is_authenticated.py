#!/usr/bin/env python3
"""The desktop's sound must never be reachable without a session.

WHAT HAPPENED, so nobody re-introduces it by being helpful:

`moos-cloud-audio` streams the default sink's monitor — every call, every meeting, every video
the machine plays — and it has no authentication of any kind. Its own header says so. That was
survivable while it only listened on loopback.

`mo-pc-remote` then published it with `tailscale serve --set-path=/audio`, which re-publishes a
loopback socket to the WHOLE TAILNET. The result, measured on the maintainer's machine on
2026-07-29:

    POST https://<host>/api/login  (wrong PIN)        -> 401
    GET  https://<host>/audio/stream.webm (no creds)  -> 200 audio/webm, a live Opus stream

Same host, same port, same certificate. The user typed a 6-digit PIN at the front door and
reasonably believed the URL was behind it. It was not, and nothing on the desktop indicated that
anyone was listening.

The mount was created from TWO places — `enable_anywhere()` and a self-heal inside
`tailscale_url()` that re-created it on every panel open — so removing it by hand did not stick.

THE INVARIANT THIS GUARDS:

1. Nothing may publish the audio service as a separate unauthenticated mount.
2. The agent must expose the audio behind the same session check as everything else.
3. The controller must send the token, and must not corrupt the query string doing it.
4. `mo-pc-remote` must actively REMOVE a legacy mount, because a machine exposed once stays
   exposed until something takes it down.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PANEL = ROOT / "system_files/usr/bin/mo-pc-remote"
AGENT = ROOT / "moremote/agent/Web/WebApi.cs"
SCREEN = ROOT / "moremote/controller/src/ui/RemoteScreen.tsx"
BUILD = ROOT / "build_files/build.sh"

errors = []


def code(raw: str, comment: str) -> str:
    """Strip comments, so the prose explaining this bug cannot satisfy a gate about it.

    Every file here documents the exposure at length, and those comments contain the exact
    strings the checks below search for. Without this the gate would pass on a file that had
    been reverted to the broken behaviour but kept its explanation.
    """
    return "\n".join(
        line for line in raw.splitlines() if not line.strip().startswith(comment)
    )


def read(p: Path) -> str:
    if not p.is_file():
        errors.append(f"{p.relative_to(ROOT)} is missing — the audio path cannot be checked")
        return ""
    return p.read_text(encoding="utf-8")


panel = code(read(PANEL), "#")
agent = code(read(AGENT), "//")
screen = code(read(SCREEN), "//")
build = code(read(BUILD), "#")

if "tailscale serve /audio" in build:
    errors.append("build.sh still claims the retired unauthenticated /audio mount is active")
if "authenticated agent proxies /api/audio/stream.webm" not in build:
    errors.append("build.sh does not describe the authenticated audio route it actually ships")

# 1. Nothing may create the unauthenticated mount, from any call site.
if "--set-path=/audio" in panel and '"off"' not in panel:
    errors.append(
        "mo-pc-remote passes --set-path=/audio without 'off' — that publishes moos-cloud-audio, "
        "which has NO authentication, to the whole tailnet next to a PIN-protected desktop")
if re.search(r"\bmount_audio\s*\(", panel):
    errors.append(
        "mo-pc-remote still defines or calls mount_audio() — the function that created the "
        "unauthenticated tailnet mount. The sound goes through the agent now")

# 2. It must actively take a legacy mount DOWN, or machines already exposed stay exposed.
if not re.search(r"def unmount_audio\s*\(", panel):
    errors.append("mo-pc-remote defines no unmount_audio() — an already-exposed machine would "
                  "never close itself")
if panel.count("unmount_audio(") < 2:
    errors.append(
        f"unmount_audio is referenced {panel.count('unmount_audio(')} time(s); it must be DEFINED "
        "and CALLED from the panel-open path, so opening Mo PC Remote retracts a stale mount")

# 3. The agent must serve the audio, behind the session check.
if "/api/audio/stream.webm" not in agent:
    errors.append("the agent exposes no /api/audio/stream.webm — the sound has no authenticated "
                  "route to travel on")
else:
    route = agent[agent.index("/api/audio/stream.webm"):]
    window = route[:2000]
    if "ValidateAndTouch" not in window:
        errors.append("the agent's audio route never calls Sessions.ValidateAndTouch — it would "
                      "serve the machine's sound to anyone who can reach the port")
    if "Status401Unauthorized" not in window:
        errors.append("the agent's audio route never answers 401 — an unauthenticated caller must "
                      "be refused, not quietly given a stream")
    if "ResponseHeadersRead" not in window:
        errors.append("the agent's audio route buffers instead of streaming "
                      "(HttpCompletionOption.ResponseHeadersRead missing) — an endless stream "
                      "would grow in memory and the listener would hear nothing")
    if "InfiniteTimeSpan" not in window:
        errors.append("the agent's audio route leaves HttpClient's default 100s timeout in place "
                      "— the sound would cut out every 100 seconds")

# 4. The controller must authenticate, and must not corrupt the query string doing it.
audio_url = re.search(r"const AUDIO_URL\s*=\s*(.+)", screen)
if not audio_url:
    errors.append("RemoteScreen defines no AUDIO_URL")
else:
    value = audio_url.group(1)
    if "token" not in value:
        errors.append(f"AUDIO_URL carries no token ({value.strip()}) — an <audio> element cannot "
                      "send an Authorization header, so the token must ride in the query string")
    if "api/audio" not in value:
        errors.append(f"AUDIO_URL does not point at the agent's authenticated route ({value.strip()})")
# every cache-buster must extend the existing query string, never start a new one
for bad in re.finditer(r"\$\{AUDIO_URL\}\?", screen):
    errors.append(
        "a cache-buster appends '?' to AUDIO_URL, which already has a query string — the token "
        "would become part of a parameter NAME and the request would arrive unauthenticated")

if errors:
    print("GATE FAIL: the desktop's sound is reachable without a session.\n")
    for e in errors:
        print(f"  - {e}")
    print("\nWhy this matters: moos-cloud-audio taps the default sink's monitor. Published without")
    print("authentication it is a live tap on every call, meeting and video, with nothing on the")
    print("desktop to say anyone is listening.")
    sys.exit(1)

print("OK: the sound travels the agent's authenticated route; no unauthenticated mount is created, "
      "and a legacy one is retracted on panel open.")
