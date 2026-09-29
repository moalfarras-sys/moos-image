import QtQuick

// Supplies the portal shader with Mira's original frames and the weights to blend them:
//  - expression changes cross-fade whole frames (180 ms);
//  - blinks blend only the eye band of the blink frame (close 70 ms, hold 50 ms, open 130 ms),
//    at a natural, never-repeating rhythm with occasional double blinks;
//  - speech blends only the mouth band of the two speaking frames, driven by the real voice level
//    with a fast attack and a slower release so the mouth never trails the sound.
Item {
    id: root
    anchors.fill: parent
    property string style: "rose"
    property string expression: "neutral"
    property string phase: "idle"
    property bool speaking: false
    property real level: 0
    property bool motion: true

    property alias a: imgA
    property alias b: imgB
    property alias eyes: imgEyes
    property alias mouthRound: imgRound
    property alias mouthOpen: imgOpen
    property real mix: 0
    property real blinkW: 0
    property real mouth: 0
    readonly property real openW: speaking && motion ? smooth(0.34, 0.68, mouth) : 0
    readonly property real roundW: speaking && motion ? smooth(0.07, 0.28, mouth) * (1 - openW) : 0

    function smooth(e0, e1, x) { const t = Math.max(0, Math.min(1, (x - e0) / (e1 - e0))); return t * t * (3 - 2 * t) }
    function url(name) { return "image://mira/" + style + "/" + name }

    property string shown: "neutral"
    Image { id: imgA; visible: false; source: root.url(root.shown); sourceSize: Qt.size(768, 768); smooth: true; mipmap: true }
    Image { id: imgB; visible: false; source: root.url(root.shown); sourceSize: Qt.size(768, 768); smooth: true; mipmap: true }
    Image { id: imgEyes; visible: false; source: root.url("blink"); sourceSize: Qt.size(768, 768); smooth: true; mipmap: true }
    Image { id: imgRound; visible: false; source: root.url("speaking_round"); sourceSize: Qt.size(768, 768); smooth: true; mipmap: true }
    Image { id: imgOpen; visible: false; source: root.url("speaking_open"); sourceSize: Qt.size(768, 768); smooth: true; mipmap: true }

    // ── expression cross-fade ───────────────────────────────────────
    NumberAnimation {
        id: fade
        target: root; property: "mix"; from: 0; to: 1; duration: 180; easing.type: Easing.InOutQuad
        onFinished: { imgA.source = imgB.source; root.mix = 0 }
    }
    function show(name) {
        if (name === shown && !fade.running) return
        if (fade.running) { fade.stop(); imgA.source = imgB.source; mix = 0 }
        shown = name
        imgB.source = url(name)
        if (!motion) { imgA.source = imgB.source; mix = 0 } else fade.start()
    }
    onExpressionChanged: show(expression)
    onStyleChanged: { fade.stop(); imgA.source = url(shown); imgB.source = url(shown); mix = 0 }
    Component.onCompleted: { shown = expression; imgA.source = url(shown); imgB.source = url(shown) }

    // ── mouth: fast attack, slower release ──────────────────────────
    NumberAnimation { id: mouthAnim; target: root; property: "mouth"; easing.type: Easing.OutQuad }
    onLevelChanged: {
        const target = speaking ? level : 0
        mouthAnim.stop()
        mouthAnim.to = target
        mouthAnim.duration = target > mouth ? 40 : 110
        mouthAnim.start()
    }
    onSpeakingChanged: if (!speaking) { mouthAnim.stop(); mouthAnim.to = 0; mouthAnim.duration = 120; mouthAnim.start() }

    // ── blinking ────────────────────────────────────────────────────
    SequentialAnimation {
        id: blink
        property bool twice: false
        NumberAnimation { target: root; property: "blinkW"; to: 1; duration: 70; easing.type: Easing.InQuad }
        PauseAnimation { duration: 50 }
        NumberAnimation { target: root; property: "blinkW"; to: 0; duration: 130; easing.type: Easing.OutQuad }
        onFinished: {
            if (twice) { twice = false; again.start() } else root.schedule()
        }
    }
    Timer { id: again; interval: 160; onTriggered: blink.start() }
    Timer { id: nextBlink; onTriggered: root.blinkNow() }

    function blinkNow() {
        if (!motion || !visible || blink.running) return
        blink.twice = Math.random() < 0.1
        blink.start()
    }
    // Gamma-like interval (sum of two exponentials): mean ~3.5 s at rest, ~2.3 s while listening,
    // fewer while thinking; never sooner than 0.8 s.
    function schedule() {
        if (!motion) return
        const mean = phase === "listening" ? 2.3 : phase === "thinking" || phase === "executing" ? 5.0 : 3.5
        const g = -Math.log(1 - Math.random()) - Math.log(1 - Math.random())
        nextBlink.interval = Math.max(800, Math.round(g / 2 * mean * 1000))
        nextBlink.restart()
    }
    // People blink at the end of a turn: after you stop talking, and when Mira finishes.
    onPhaseChanged: {
        if (phase === "thinking" || phase === "idle") Qt.callLater(function() { if (Math.random() < 0.7) root.blinkNow() })
    }
    onMotionChanged: { if (motion) schedule(); else { nextBlink.stop(); blink.stop(); blinkW = 0 } }
    Timer { interval: 900; running: true; onTriggered: root.schedule() }
}
