// SPDX-License-Identifier: GPL-2.0-or-later
// The Mo AI page's only way out of System Settings: HTTP to the two loopback services the
// Mo AI app uses, on THIS account's ports. moai-agent-api owns the brain, the key, the
// phone channels and the permission tiers; moai-control serves the model list and the
// free-model measurement. The ports come from the session (60-moai-ports), read through
// the backend's three-name allowlist, and fall back to the single-user defaults.
//
// Never a file URL and never another host. Each service refuses a request without its
// own header, which is what keeps a web page from driving them; this client sends it.
// QML's XMLHttpRequest has no timeout of its own (measured on this Qt: no `timeout`
// property), so every request carries a timer that gives up and says so.
import QtQuick

QtObject {
    id: service

    readonly property string agentBase: "http://127.0.0.1:" + service.port("MOAI_AGENT_PORT", 8077)
    readonly property string controlBase: "http://127.0.0.1:" + service.port("MOAI_CONTROL_PORT", 8079)
    property Component timerType: Component { Timer { repeat: false } }

    function port(name, fallback) {
        var value = parseInt(kcm.env(name), 10)
        return value > 0 && value < 65536 ? value : fallback
    }

    // done({ ok, offline, timedOut, status, data, error }). `ok` means HTTP 200 with a JSON
    // object and no "error" key: the only answer that may be shown as a success. `timedOut`
    // means no answer in time, which for a write is NOT "nothing happened": it may still land.
    function request(agent, method, path, body, limitMs, done) {
        var xhr = new XMLHttpRequest()
        var settled = false
        var timedOut = false
        var limit = service.timerType.createObject(service, { interval: limitMs })
        function finish(result) {
            if (settled)
                return
            settled = true
            if (limit) {
                limit.stop()
                limit.destroy()
            }
            done(result)
        }
        if (limit) {
            limit.triggered.connect(function () {
                timedOut = true
                xhr.abort()
                finish({ ok: false, offline: true, timedOut: true, status: 0, data: null, error: "" })
            })
        }
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== XMLHttpRequest.DONE)
                return
            var data = null
            try {
                data = JSON.parse(xhr.responseText)
            } catch (e) {
                data = null
            }
            var object = data !== null && typeof data === "object" && !Array.isArray(data)
            var error = object && typeof data.error === "string" ? data.error : ""
            finish({ ok: !timedOut && xhr.status === 200 && object && error === "",
                     offline: timedOut || xhr.status === 0, timedOut: timedOut, status: xhr.status,
                     data: object ? data : null, error: error })
        }
        xhr.open(method, (agent ? service.agentBase : service.controlBase) + path)
        xhr.setRequestHeader(agent ? "X-Moai-Agent" : "X-Moai-Control", "1")
        if (body !== null)
            xhr.setRequestHeader("Content-Type", "application/json")
        if (limit)
            limit.start()
        xhr.send(body === null ? "" : JSON.stringify(body))
    }
}
