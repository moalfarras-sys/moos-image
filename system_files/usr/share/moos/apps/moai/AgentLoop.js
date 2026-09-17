// Mo AI's native tool loop — the parts that are pure logic, kept out of the window so that
// tests/test_moai_agent_loop.py can run them in node against scripted provider streams.
//
// The window owns the network and the dialog; this file owns the decisions that were wrong in
// wave W4 and invisible from the outside:
//   * one tool call per answer, and a follow-up request WITHOUT tools, so the model could never
//     look, then repair, then check;
//   * `history.slice(-12)` could keep a `tool` message and drop the assistant `tool_calls`
//     message it answers, which every OpenAI-compatible provider rejects with HTTP 400;
//   * executor output was shown raw: both halves of "عربي | English" and emoji used as icons.
.pragma library

var MAX_CALLS_PER_ANSWER = 4;

// ── Streaming ────────────────────────────────────────────────────────────────
function newStream() {
    return { text: "", toolCalls: [], error: "", reasonedChars: 0, sawData: false };
}

// Feed ONE complete SSE line ("data: {...}"). Returns true when the line changed the stream.
function feed(stream, line) {
    var trimmed = String(line || "").trim();
    if (trimmed.indexOf("data:") !== 0) { return false; }
    var payload = trimmed.substring(5).trim();
    if (payload === "" || payload === "[DONE]") { return false; }
    var event;
    try { event = JSON.parse(payload); } catch (error) { return false; }   // a split line
    if (event.error) {
        stream.error = String(event.error.message || event.error);
        return true;
    }
    var choice = event.choices && event.choices[0];
    if (!choice) { return false; }
    var delta = choice.delta || choice.message || {};
    var changed = false;
    if (delta.reasoning_content) { stream.reasonedChars += String(delta.reasoning_content).length; }
    var calls = delta.tool_calls || [];
    for (var i = 0; i < calls.length; ++i) {
        var call = calls[i];
        var slot = call.index !== undefined ? call.index : i;
        if (!stream.toolCalls[slot]) { stream.toolCalls[slot] = { id: "", name: "", arguments: "" }; }
        var target = stream.toolCalls[slot];
        if (call.id) { target.id = call.id; }
        if (call.function && call.function.name) { target.name += call.function.name; }
        if (call.function && call.function.arguments) { target.arguments += call.function.arguments; }
        stream.sawData = true;
        changed = true;
    }
    if (delta.content) {
        stream.text += delta.content;
        stream.sawData = true;
        changed = true;
    }
    return changed;
}

// The calls of one finished answer, normalised. A call whose arguments are not a JSON object is
// kept — with `invalid: true` — so the model is TOLD its call was malformed instead of seeing it
// vanish. Extra calls beyond the cap are answered too, never silently dropped.
function finishedCalls(stream) {
    var out = [];
    for (var i = 0; i < stream.toolCalls.length; ++i) {
        var raw = stream.toolCalls[i];
        if (!raw || !raw.name) { continue; }
        var args = {};
        var invalid = false;
        if (String(raw.arguments || "").trim() !== "") {
            try {
                args = JSON.parse(raw.arguments);
                if (args === null || typeof args !== "object" || Array.isArray(args)) { invalid = true; args = {}; }
            } catch (error) { invalid = true; }
        }
        out.push({
            id: raw.id || ("call_" + i),
            name: raw.name,
            args: args,
            invalid: invalid,
            skipped: out.length >= MAX_CALLS_PER_ANSWER
        });
    }
    return out;
}

// ── Confirmation ─────────────────────────────────────────────────────────────
// The same rule moai_tool_schemas.needs_confirmation() applies on the executor's side. The
// executor decides; this only chooses whether to show the card BEFORE asking it.
function needsConfirmation(meta, args) {
    if (!meta) { return true; }
    if (meta.category === "user_confirm" || meta.category === "privileged_confirm") { return true; }
    var rules = meta.confirm_values || {};
    for (var key in rules) {
        if (rules[key].indexOf(String((args || {})[key])) !== -1) { return true; }
    }
    return false;
}

// ── History ──────────────────────────────────────────────────────────────────
// The OpenAI shape for one answered batch: ONE assistant message carrying every call, then one
// `tool` message per call, in order.
function toolMessages(text, calls, results) {
    var messages = [{
        role: "assistant",
        content: text && String(text).trim() !== "" ? text : null,
        tool_calls: calls.map(function (call) {
            return { id: call.id, type: "function",
                     "function": { name: call.name, arguments: JSON.stringify(call.args || {}) } };
        })
    }];
    for (var i = 0; i < calls.length; ++i) {
        messages.push({ role: "tool", tool_call_id: calls[i].id, name: calls[i].name,
                        content: String(results[i] === undefined ? "" : results[i]) });
    }
    return messages;
}

// Keep the newest `limit` messages WITHOUT splitting a tool group: a `tool` message whose
// assistant `tool_calls` message was cut off is a provider error, not a shorter conversation.
function trimHistory(history, limit) {
    if (history.length <= limit) { return history; }
    var start = history.length - limit;
    // Begin the window on a person's message when there is one: that can never be the middle of
    // a group, and a conversation that opens with the person's turn is what every provider
    // accepts. Otherwise at least step past orphaned `tool` messages.
    for (var i = start; i < history.length; ++i) {
        if (history[i].role === "user") { return history.slice(i); }
    }
    while (start < history.length && history[start].role === "tool") { start += 1; }
    return history.slice(start);
}

// ── Presentation ─────────────────────────────────────────────────────────────
// Executors answer "عربي | English" on one line and decorate with emoji. A chat row shows ONE
// language and no emoji-as-icon; the model still receives the untouched text.
function forDisplay(text, arabic, maxLines) {
    var lines = String(text || "").replace(/\r/g, "").split("\n");
    var out = [];
    for (var i = 0; i < lines.length; ++i) {
        var line = lines[i];
        var bar = line.indexOf(" | ");
        if (bar !== -1 && /[؀-ۿ]/.test(line)) {
            var left = line.substring(0, bar), right = line.substring(bar + 3);
            var leftArabic = /[؀-ۿ]/.test(left);
            line = (arabic === leftArabic) ? left : right;
        }
        line = line.replace(/[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE0F}\u{200D}]/gu, "")
                   .replace(/\[[0-9;]*m/g, "")
                   .replace(/\s+$/, "");
        out.push(line);
    }
    while (out.length && out[0].trim() === "") { out.shift(); }
    while (out.length && out[out.length - 1].trim() === "") { out.pop(); }
    var limit = maxLines || 40;
    if (out.length > limit) {
        var hidden = out.length - limit;
        out = out.slice(out.length - limit);
        out.unshift(arabic ? ("… " + hidden + " سطراً أقدم مخفية") : ("… " + hidden + " earlier lines hidden"));
    }
    return out.join("\n");
}
