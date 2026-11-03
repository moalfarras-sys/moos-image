#!/usr/bin/env bash
# Fail the build on a high-severity advisory — and NOT on npm being unable to answer.
#
# WHY THIS IS A SCRIPT
#
# It was one line inside build.yml:
#
#     npm audit --audit-level=high
#
# On 2026-09-19 that line failed the signed build for all three x86 editions, and
# the reason was not a vulnerability:
#
#     npm notice This endpoint is being retired. Use the bulk advisory endpoint instead.
#     npm warn audit 400 Bad Request - POST .../security/audits/quick
#     message: 'Invalid package tree, run npm install to rebuild your package-lock.json'
#     npm error audit endpoint returned an error
#
# The package tree was fine: `npm ci` had just installed 378 packages and `tsc
# --noEmit` had passed, and the same audit on the maintainer's station reports
# "found 0 vulnerabilities". npm's registry simply could not answer, on an
# endpoint npm itself says is being retired.
#
# That is the dangerous kind of red. The obvious way to make it green again is
# `|| true`, and then the gate is gone forever while still appearing in the log.
# So the distinction is made explicitly instead:
#
#   * npm answered, and something is high or critical  -> FAIL, print the advisory
#   * npm answered, nothing at that level              -> pass
#   * npm could not answer                             -> retry, then FAIL, saying
#                                                         plainly that this is a
#                                                         registry failure and not
#                                                         a clean audit
#
# It still fails closed. An unreachable registry means we do not KNOW whether the
# bundle is safe, and "we do not know" must never be spelled the same way as
# "we checked and it is fine". RELEASE.md already covers what to do next: an
# external failure unrelated to the candidate is re-dispatched, not waved through.
#
# The two JSON shapes are stable and were measured, not assumed:
#   answered -> {"auditReportVersion":…, "metadata":{"vulnerabilities":{"high":…}}}
#   failed   -> {"error":{…},"message":…}          (no "metadata" key at all)
set -uo pipefail

level="${1:-high}"
# High is the existing project's least-strict policy. Explicit lower levels
# strengthen it; no argument may disable or weaken that policy.
case "$level" in
    low|moderate|high) ;;
    *) echo "npm audit: supported levels are low, moderate and high" >&2; exit 2 ;;
esac
attempts="${NPM_AUDIT_ATTEMPTS:-3}"
report="$(mktemp)"
trap 'rm -f -- "$report"' EXIT

for attempt in $(seq 1 "$attempts"); do
    npm audit --audit-level="$level" --json >"$report" 2>/dev/null
    npm_status=$?

    verdict="$(python3 - "$report" "$level" "$npm_status" <<'PY'
import json, sys
def unanswered():
    print("unanswered")
    raise SystemExit(0)

try:
    with open(sys.argv[1], encoding="utf-8") as handle:
        report = json.load(handle)
except (OSError, ValueError):
    unanswered()
# Exit1 can mean findings; other failures cannot be cleared by JSON left on
# stdout. An explicit error also wins over apparently healthy metadata.
if sys.argv[3] not in ("0", "1") or not isinstance(report, dict) or "error" in report:
    unanswered()
metadata = report.get("metadata")
if not isinstance(metadata, dict):
    unanswered()
counts = metadata.get("vulnerabilities")
entries = report.get("vulnerabilities")
if not isinstance(counts, dict) or not isinstance(entries, dict):
    unanswered()
levels = ["info", "low", "moderate", "high", "critical"]
if any(type(counts.get(name)) is not int or counts[name] < 0 for name in levels + ["total"]):
    unanswered()
# Native npm reports count affected packages, one per map entry. Validate the
# complete histogram so a high entry cannot disappear behind a zero count.
observed = dict.fromkeys(levels, 0)
for entry in entries.values():
    if not isinstance(entry, dict) or entry.get("severity") not in levels:
        unanswered()
    observed[entry["severity"]] += 1
if any(counts[name] != observed[name] for name in levels) or counts["total"] != len(entries):
    unanswered()
if sys.argv[3] == "1" and not entries:
    unanswered()
selected = levels[levels.index(sys.argv[2]):]
blocking = sum(counts[name] for name in selected)
print(f"found {blocking}" if blocking else "clean")
PY
)"

    case "$verdict" in
        clean)
            echo "npm audit: no ${level}-or-worse advisories"
            exit 0
            ;;
        found\ *)
            echo "::error::npm audit found ${verdict#found } advisory/advisories at ${level} or above in moremote/controller."
            # A heredoc, not `python3 -c '…'`: inside single quotes bash leaves
            # backslash-escaped quotes intact, so the f-string was a syntax error
            # and `|| true` swallowed it — the build log named the count and not
            # one package. Caught by tests/test_npm_audit_gate.py.
            python3 - "$report" "$level" <<'ADVISORIES' || true
import json, sys
with open(sys.argv[1], encoding="utf-8") as handle:
    report = json.load(handle)
levels = ["low", "moderate", "high", "critical"]
selected = levels[levels.index(sys.argv[2]):]
for name, entry in sorted((report.get("vulnerabilities") or {}).items()):
    if entry.get("severity") in selected:
        line = "  {0:>8}  {1}  {2}".format(entry["severity"], name, entry.get("via"))
        print(line[:200])
ADVISORIES
            exit 1
            ;;
        *)
            echo "npm audit attempt ${attempt}/${attempts}: the registry did not return a report" >&2
            head -c 400 "$report" >&2 || true
            echo >&2
            [ "$attempt" -lt "$attempts" ] && sleep $((attempt * 5))
            ;;
    esac
done

echo "::error::npm audit could not obtain a report after ${attempts} attempts. This is a REGISTRY failure, not a clean audit — the bundle has NOT been cleared. Re-dispatch this workflow (RELEASE.md, external-failure rule). Do not silence this check."
exit 1
