#!/usr/bin/env python3
"""Gate the Remote clipboard bridge's bounded subprocess and honest API contract."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
linux = (ROOT / "moremote/agent-linux/ClipboardBridge.cs").read_text(encoding="utf-8")
injector = (ROOT / "moremote/agent-linux/InputInjector.cs").read_text(encoding="utf-8")
portal = (ROOT / "moremote/agent-linux/mo-remote-portal.py").read_text(encoding="utf-8")
windows = (ROOT / "moremote/agent/Core/ClipboardBridge.cs").read_text(encoding="utf-8")
api = (ROOT / "moremote/agent/Web/WebApi.cs").read_text(encoding="utf-8")
tests = (ROOT / "moremote/tests/MoRemote.Tests/Program.cs").read_text(encoding="utf-8")

def code(text: str) -> str:
    """Strip comments, so a gate that requires a name to be ABSENT cannot be broken — or
    satisfied — by the paragraph explaining why it is absent."""
    return "\n".join(
        line for line in text.splitlines()
        if not line.lstrip().startswith(("//", "#"))
    )


checks = {
    "Linux clipboard output is still read synchronously before its timeout can fire":
        "WaitForExitAsync(deadline.Token)" in linux
        and "ReadBoundedAsync(process.StandardOutput.BaseStream" in linux,
    "a timed-out clipboard helper can survive and retain the request":
        "process.Kill(entireProcessTree: true)" in linux,
    "clipboard reads can allocate an unbounded payload":
        "MaxClipboardBytes = 25_000_000" in linux
        and 'throw new InvalidDataException("Clipboard exceeds its size limit")' in linux,
    "subprocess arguments can be reinterpreted through shell-style string splitting":
        "start.ArgumentList.Add(arg)" in linux,
    "Linux clipboard writes still discard the helper exit status":
        "return process.ExitCode == 0" in linux
        and "public static bool SetText" in linux,
    "Windows clipboard writes still cannot report timeout or failure":
        "public static bool SetText" in windows and "return t.Join(5000) && result" in windows,
    "the phone API still claims clipboard success after the platform rejected it":
        api.count('error = "clipboard_unavailable"') == 2
        and "ClipboardBridge.SetText" in api and "ClipboardBridge.SetImagePng" in api,
    # ---------------------------------------------------------------- typing no longer lives here
    #
    # These four contracts used to pin the clipboard BORROW that typed Arabic. That mechanism is
    # retired: it raced on three fronts (one shared slot, a wl-copy that returns before the
    # selection is servable, an asynchronous fetch by the target app) and every scrambling report
    # in this project's history came out of it. Arabic is now typed by selecting the keymap group
    # that carries the characters and pressing the positions — see AraKeymap and
    # InputInjector.Deliver. Each contract below is the SAME guarantee, re-expressed against the
    # mechanism that replaced it, so nothing is weakened by the migration.

    # WAS: the confirmed clipboard write. NOW: typing must not touch the clipboard at all, and the
    # confirmed write must not linger as a trap for whoever assumes it still does.
    "typing still reaches for the clipboard":
        "ClipboardBridge" not in code(injector)
        and "SetTextConfirmed" not in code(linux),

    # WAS: read the clipboard back before pasting. NOW: the group change must ride the keymap's own
    # Alt+Shift switch so it travels in the SAME ordered stream as the letters. An out-of-band
    # setLayout overtakes keys already in flight — measured end to end, 4 of 12 words lost their
    # tail to the German layout ("مكتوب" -> "مكتوf"). Neither setLayout's reply nor the
    # layoutChanged signal is a barrier: both fire in ~0.15 ms and both mean ACCEPTED, not APPLIED.
    # …and a swallowed chord must be self-correcting. Pacing alone was not enough: sent back to
    # back the second Alt+Shift is sometimes swallowed, the group lands one short ("كيف الحال"
    # arrived ";dt hgphg"), and the tracked index desyncs so every LATER switch is wrong too.
    # Each chord is therefore followed by a bounded read of the group KWin actually has, which
    # re-syncs from the compositor instead of trusting our own count.
    "the group change can still overtake keys already in flight":
        "_toggle_events" in code(portal)
        and "grp:alt_shift_toggle" in code(portal)
        and "def _read_layout():" in code(portal)
        and "MAX_TOGGLE_ATTEMPTS" in code(portal),

    # WAS: an unconfirmed copy must SKIP its paste. NOW: a run whose group cannot be reached must
    # be dropped, not typed — the other layout's reading of those positions is exactly the
    # corruption this design exists to prevent. Fail closed, same as before.
    # The guarantee is FAIL CLOSED, checked as behaviour rather than as one sentence. It used to
    # require the literal "no Arabic keyboard layout is configured" — a proxy that stopped being
    # true when select_group learned to resolve groups other than Arabic, so a machine missing a
    # `us` group was told to install an ARABIC keyboard and this assertion fired on the fix.
    # What must hold: the resolver can fail, a failure RETURNS FALSE (so Deliver drops the run
    # instead of typing it against whatever group is live), and the warning names the group.
    "a run whose keymap group is unavailable is still typed anyway":
        "dropped a typed run" in code(portal)
        and "def _group_index(name):" in code(portal)
        and "if idx is None:" in code(portal)
        and "keyboard layout is configured" in code(portal)
        and 'layout_state["warned"]' in code(portal),

    # WAS: the clipboard borrow must be returned. NOW: the borrowed GROUP must be handed back —
    # leaving a desk keyboard on Arabic because a phone typed a word is the same theft.
    "the borrowed keymap group is never handed back":
        "def restore_layout():" in code(portal)
        and code(portal).count("restore_layout()") >= 2,

    "no behavioural proof exercises a genuinely hung helper and an oversized result":
        '"sleep 20"' in tests and "clipboard timeout is real and bounded" in tests
        and "oversized clipboard output is rejected" in tests,
    # The "paste anyway" ban that stood here is retired with the mechanism it guarded: there is
    # no paste left to make anyway. Its GUARANTEE — fail closed, drop rather than deliver the
    # wrong thing — moved up to "a run whose keymap group is unavailable is still typed anyway",
    # which is the same promise about the same failure, in the mechanism that replaced it.
    # 2026-08-03, from the live agent log: at the owner's real typing cadence the phone's 220 ms
    # window loses its race and text arrives letter-by-letter — and the agent then held EVERY
    # chunk, even a client-coalesced whole word, for its own fixed 140 ms gather. A fixed tax on
    # every word of Arabic. Multi-character chunks now flush at once (the gather exists to merge
    # single letters), and the agent's gather carries the same 700 ms age cap as the client's,
    # which was the half of the shipped "240 chars / 700 ms" bound that only existed client-side.
    # The gather survives, and so does its bound — only its PURPOSE changed. It no longer
    # amortises a clipboard cycle; it amortises a GROUP SWITCH, which KWin announces to
    # plasmashell's OSD service, which paints a layout pill across the middle of the screen and
    # therefore into the video stream. One switch per word, not one per letter.
    "the agent still taxes already-coalesced words with its own gather delay":
        injector.count("text.Length > 1 ||") == 2
        and "TextMaxHoldMs = 700;" in injector
        and "_pendingSince" in injector,
}

failed = [message for message, ok in checks.items() if not ok]
if failed:
    raise SystemExit("remote clipboard runtime gate failed:\n- " + "\n- ".join(failed))
print("remote clipboard runtime gate passed")
