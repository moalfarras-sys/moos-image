// Native Settings visual/interaction review. Run with moos-qml-shell, --status=file://… and --out=/existing/directory.
// Captures source QML in the active palette; never installs a desktop override.
import QtTest as Test
import QtQuick
Item {
    id: harness
    property var app
    property var snapshot
    property var frame
    property int step: -1
    property string out: Qt.application.arguments.filter(a => a.indexOf('--out=') === 0)[0].substring(6)
    function argument(prefix, fallback) {
        var found = Qt.application.arguments.filter(a => a.indexOf(prefix) === 0)[0]
        return found ? found.substring(prefix.length) : fallback
    }
    Component.onCompleted: {
        var component = Qt.createComponent(argument('--source=', Qt.resolvedUrl('../../system_files/usr/share/moos/apps/settings/main.qml')))
        if (component.status !== Component.Ready) { console.error(component.errorString()); Qt.exit(1); return }
        app = component.createObject(null, {width: Number(argument('--width=', 1400)), height: Number(argument('--height=', 900)), minimumWidth: 800, minimumHeight: 640})
        console.warn("REVIEW_LOCALE", Qt.locale().name, app.rtl)
        var expectedRtl = argument("--rtl=", "")
        if (expectedRtl !== "" && app.rtl !== (expectedRtl === "true")) { console.error("Wrong review locale"); Qt.exit(1); return }
        var children = Array.from(app.contentItem.children)
        frame = Qt.createQmlObject('import QtQuick; Rectangle { anchors.fill: parent; color: "' + app.color + '" }', app.contentItem)
        for (var child of children) child.parent = frame
        driver.parent = app.contentItem
        interaction.start()
    }
    function find(item, name) {
        if (item.objectName === name) return item
        for (var child of item.children || []) {
            var result = find(child, name)
            if (result) return result
        }
        return null
    }
    Test.TestCase { id: driver; name: "SettingsReview"; when: false }
    Timer {
        id: interaction
        interval: 1200
        onTriggered: {
            try {
                var field = harness.find(harness.frame, "settingsSearch")
                harness.app.requestActivate()
                driver.wait(100)
                field.forceActiveFocus()
                for (var key of [Qt.Key_A, Qt.Key_U, Qt.Key_D, Qt.Key_I, Qt.Key_O]) driver.keyClick(key)
                console.warn("KEY_RESULT", harness.app.searchQuery, field.text, field.activeFocus)
                driver.compare(harness.app.searchQuery, "audio")
                console.warn("RESULTS", harness.app.visibleCommands.length)
                driver.compare(harness.app.visibleCommands.length, 1)
                driver.keyClick(Qt.Key_Escape)
                driver.compare(harness.app.searchQuery, "")
                driver.compare(field.text, "")
                harness.app.searchQuery = "network"
                harness.app.selectSection("devices")
                driver.compare(field.text, "")
                harness.app.searchQuery = "audio"
                driver.compare(field.text, "audio")
                harness.app.selectSection("home")
                if (Qt.application.arguments.indexOf("--workspace") >= 0) {
                    for (var section of ["appearance", "connectivity", "apps", "system"]) {
                        var card = harness.find(harness.frame, "workspace-" + section)
                        console.warn("WORKSPACE_CARD", section, card, card ? card.visible : false)
                        driver.verify(card !== null, "Workspace card exists: " + section)
                        card.forceActiveFocus()
                        driver.keyClick(Qt.Key_Return)
                        console.warn("WORKSPACE_RESULT", section, harness.app.activeSection, card.activeFocus)
                        driver.compare(harness.app.activeSection, section)
                        harness.app.selectSection("home")
                    }
                    console.warn("WORKSPACE_NAVIGATION_PASSED")
                }
                console.warn("SETTINGS_INTERACTIONS_PASSED")
                harness.snapshot = JSON.parse(JSON.stringify(harness.app.status))
                clock.start()
            } catch (error) { console.error(error); Qt.exit(1) }
        }
    }
    Timer {
        id: clock
        interval: 1000
        repeat: true
        onTriggered: {
            clock.stop()
            harness.step++
            if (harness.step < harness.app.sections.length) {
                harness.app.selectSection(harness.app.sections[harness.step].id)
            } else {
                harness.app.statusBusy = true // freeze polling only for explicit failure fixtures
                var scenario = harness.step - harness.app.sections.length
                harness.app.selectSection(scenario === 2 ? "connectivity" : "home")
                if (scenario === 0) harness.app.statusFailure()
                else if (scenario === 1) {
                    harness.snapshot.generatedAt = Date.now()/1000
                    harness.app.acceptStatus(harness.snapshot)
                    harness.app.searchQuery = "no-such-setting"
                } else {
                    var fixture = JSON.parse(JSON.stringify(harness.snapshot))
                    fixture.generatedAt = Date.now()/1000
                    fixture.destinations.bluetooth = false
                    fixture.deployment.signed = false
                    fixture.deployment.rollback = 0
                    fixture.network.connected = true
                    fixture.network.full = false
                    fixture.network.connectivity = "portal"
                    harness.app.acceptStatus(fixture)
                }
            }
            capture.start()
        }
    }
    Timer {
        id: capture
        interval: 1000
        onTriggered: {
            var name = harness.step < harness.app.sections.length ? harness.app.activeSection
                : ["unavailable", "empty-search", "missing-module"][harness.step - harness.app.sections.length]
            harness.frame.grabToImage(function(result) {
                console.warn("SAVED", name, result.saveToFile(harness.out + '/' + name + '.png'))
                if (Qt.application.arguments.indexOf("--home-only") >= 0) { Qt.quit(); return }
                if (harness.step + 1 < harness.app.sections.length + 3) clock.start()
                else end.start()
            })
        }
    }

    Timer { id: end; interval: 500; onTriggered: {
        if (Qt.application.arguments.indexOf("--open-audio") >= 0) harness.app.openRoute("moos://settings/audio")
        finish.start()
    } }
    Timer { id: finish; interval: 2000; onTriggered: Qt.quit() }
}
