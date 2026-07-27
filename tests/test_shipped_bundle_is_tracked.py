#!/usr/bin/env python3
"""Gate: the controller bundle that index.html points at must actually be in git.

WHY THIS EXISTS

Nothing in CI builds the frontend. The Containerfile does:

    COPY moremote/ ./
    RUN dotnet publish agent-linux/MoRemoteLinux.csproj ...

and MoRemoteLinux.csproj pulls `../agent/wwwroot/**` in as Content. So the web UI that ships to
every phone and browser is whatever is COMMITTED under moremote/agent/wwwroot — never a fresh
`npm run build`.

Now the trap. moremote/.gitignore ignores the build output:

    agent/wwwroot/assets/
    agent/wwwroot/index.html

but those files are in the repo anyway, force-added once long ago. Vite hashes asset filenames, so
the moment anyone edits the frontend and rebuilds:

  * the OLD asset (tracked) disappears from disk    -> git stages a deletion
  * the NEW asset (ignored) is invisible to `git add`, `git add -A`, `git commit -a`
  * index.html (tracked, not ignored for content changes) updates to the new name

and a perfectly ordinary commit ships an index.html whose <script src> points at a file that is not
in the image. The agent answers that request with index.html itself (MapFallbackToFile), so there is
no 404 in any log — the browser just gets HTML where it asked for JavaScript and renders a blank
page. Every gate in this repo would still be green.

That is not hypothetical: it is the state the tree was in when this gate was written.

The fix is a `git add -f` per asset, which nobody can be expected to remember. So this checks it
instead, and it costs milliseconds.
"""

from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
WWWROOT = ROOT / "moremote/agent/wwwroot"
INDEX = WWWROOT / "index.html"

# Vite emits assets/index-<hash>.<ext>; this is what index.html references them as.
REF = re.compile(r"""assets/[A-Za-z0-9._-]+\.(?:js|css)""")


def tracked(paths: list[str]) -> set[str]:
    """Which of these repo-relative paths git has in the index."""
    if not paths:
        return set()
    try:
        out = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "--cached", "--", *paths],
            capture_output=True, text=True, check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"SKIP: cannot ask git which files are tracked ({exc})")
        sys.exit(0)
    return {line.strip() for line in out.splitlines() if line.strip()}


def main() -> int:
    if not INDEX.is_file():
        print(f"GATE FAIL: {INDEX.relative_to(ROOT)} is missing — the controller has no entry point.")
        return 1

    referenced = sorted(set(REF.findall(INDEX.read_text(encoding="utf-8"))))
    if not referenced:
        print("GATE FAIL: index.html references no assets/*.js or *.css at all. A Vite build always"
              " emits both, so this index.html is not one — the image would serve a blank page.")
        return 1

    errors: list[str] = []
    rel = [f"moremote/agent/wwwroot/{r}" for r in referenced]
    in_git = tracked(rel)

    for r, path in zip(referenced, rel):
        if not (WWWROOT / r).is_file():
            errors.append(f"index.html references {r}, which does not exist on disk. Run"
                          f" `npm run build` in moremote/controller.")
        elif path not in in_git:
            errors.append(f"index.html references {r}, which exists but is NOT tracked by git."
                          f" moremote/.gitignore hides assets/, so it needs an explicit add:\n"
                          f"        git add -f {path}")

    # The reverse: a tracked asset nobody references is a leftover from a previous build. Harmless to
    # serve, but it means the last rebuild half-landed, and the half that is missing is the half that
    # matters. Catching it here is what turns "the page is blank" into one line of output.
    all_tracked = tracked(["moremote/agent/wwwroot/assets"])
    stale = sorted(all_tracked - set(rel))
    for path in stale:
        errors.append(f"{path} is tracked but index.html does not reference it — a stale bundle from"
                      f" an earlier build. Remove it: git rm --cached {path}")

    if errors:
        print("GATE FAIL: the shipped controller bundle and git disagree.\n")
        for e in errors:
            print(f"  - {e}")
        print("\nWhy this matters: CI never runs `npm run build` — the image ships what is committed"
              "\nunder moremote/agent/wwwroot. A referenced-but-untracked asset means the agent"
              "\nanswers the script request with index.html (MapFallbackToFile), which is a 200, not"
              "\na 404 — so the browser renders a blank page and no log says why.")
        return 1

    print(f"OK: index.html references {len(referenced)} asset(s), all present and tracked "
          f"({', '.join(referenced)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
