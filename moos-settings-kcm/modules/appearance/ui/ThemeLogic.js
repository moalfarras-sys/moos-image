.pragma library
// SPDX-License-Identifier: GPL-2.0-or-later
// kcm_moos_appearance's pure functions: what moos-theme reported, how a chosen image
// becomes the token moos-theme accepts, and which failure a run ended in. They hold no
// state and touch nothing, so tests/test_moos_ui2.py executes this file in node.

// The ids moos-theme apply-lnf and the backend's theme-apply-lnf verb both accept.
var LOOK = /^org\.moos\.ui2(?:\.[a-z0-9]+)*$/
var MOTIONS = ["still", "gentle", "alive"]
var CLARITIES = ["clear", "balanced", "solid"]

function isLook(id) {
    var text = String(id || "")
    return text.length <= 64 && LOOK.test(text)
}

// `moos-theme` (status) prints one line: "MoOS Nova   (org.moos.ui2.nova)" for a MoOS
// look, "… unset (default: MoOS UI)" when none was chosen, and "… not a MoOS theme: <id>"
// for anything else. Only a MoOS id the tool itself named counts as the current look; a
// foreign id is never carried into the page, so it can never be shown.
function lookState(output, ok) {
    var text = String(output || "").trim()
    if (!ok || text === "")
        return { kind: "unknown", id: "" }
    var named = /\((org\.moos\.ui2(?:\.[a-z0-9]+)*)\)$/.exec(text)
    if (named && isLook(named[1]))
        return { kind: "moos", id: named[1] }
    var other = /not a MoOS theme: (\S+)$/.exec(text)
    if (other)
        return isLook(other[1]) ? { kind: "moos", id: other[1] } : { kind: "foreign", id: "" }
    if (text.indexOf("unset (default: MoOS UI)") >= 0)
        return { kind: "unset", id: "" }
    return { kind: "unknown", id: "" }
}

// `moos-theme motion` / `moos-theme clarity` print exactly one value of their set.
function reportedChoice(output, ok, allowed) {
    var value = String(output || "").trim()
    return ok && allowed.indexOf(value) >= 0 ? value : ""
}

// The desktop canvas token, encoded exactly as the retired picker did and as moos-theme
// wallpaper-token decodes it (decodeURIComponent): a local file URL, percent-encoded with
// the five characters encodeURIComponent leaves alone encoded too. "" when the choice is
// not a local file, or the token would not pass the backend's 4096-character rule.
function wallpaperToken(fileUrl) {
    var raw = String(fileUrl || "")
    if (raw.indexOf("file:///") !== 0)
        return ""
    var encoded = encodeURIComponent(raw).replace(/[!'()*]/g, function(c) {
        return "%" + c.charCodeAt(0).toString(16).toUpperCase()
    })
    if (encoded.length > 4096 || !/^[A-Za-z0-9_.~%-]+$/.test(encoded))
        return ""
    return encoded
}

// Why a moos-theme run failed, from what it wrote to stderr. The page words each kind in
// the owner's language; the raw text only ever reaches the clipboard ("Copy details"),
// because it is an engineer's message and may name the desktop's parts.
function failureKind(exitCode, errorOutput) {
    var text = String(errorOutput || "")
    if (text.indexOf("rollback verification failed") >= 0)
        return "rollback-failed"
    if (text.indexOf("restoring the exact snapshot") >= 0
            || text.indexOf("restoring the state from before undo") >= 0)
        return "rolled-back"
    if (text.indexOf("another theme or motion transaction is still running") >= 0)
        return "busy"
    if (text.indexOf("no exact previous theme snapshot") >= 0)
        return "no-undo"
    if (text.indexOf("a MoOS look must be active") >= 0)
        return "not-moos"
    if (text.indexOf("is not installed") >= 0)
        return "missing"
    if (exitCode === -1 && text.indexOf("could not start") >= 0)
        return "no-tool"
    if (exitCode === -1 && text.indexOf("timed out") >= 0)
        return "stopped"
    return "other"
}

// What a run wrote (its first lines), for the clipboard only.
function detail(errorOutput, output) {
    var text = String(errorOutput || "").trim() || String(output || "").trim()
    return text.split("\n").slice(0, 8).join("\n")
}

// Columns for the look grid: as many as fit, and an even number whenever there are two
// or more, so each family's dark look sits beside its light sibling.
function columns(width, minimum) {
    var fit = Math.max(1, Math.floor(width / Math.max(1, minimum)))
    return fit > 1 && fit % 2 === 1 ? fit - 1 : fit
}
