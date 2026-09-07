// Real source UI against isolated live services. No fixtures or automatic approvals.
import QtQuick
import QtTest as Test
Item {
    id: harness
    property var app
    property var frame
    property int captures: 0
    property string approved: ""
    property string out: Qt.application.arguments.filter(a => a.indexOf('--out=') === 0)[0].substring(6)
    Test.TestCase { id: driver; name: "MoAIAgentReview"; when: false }
    function find(item, name) {
        if (item.objectName === name) return item
        for (var child of item.children || []) {
            var match = find(child, name)
            if (match) return match
        }
        return null
    }
    Component.onCompleted: {
        var component = Qt.createComponent(Qt.resolvedUrl('../../system_files/usr/share/moos/apps/moai/main.qml'))
        if (component.status !== Component.Ready) { console.error(component.errorString()); Qt.exit(1); return }
        app = component.createObject(null, {width: 1400, height: 1000})
        var children = Array.from(app.contentItem.children)
        frame = Qt.createQmlObject('import QtQuick; Rectangle { anchors.fill: parent; color: "' + app.color + '" }', app.contentItem)
        for (var child of children) child.parent = frame
        driver.parent = app.contentItem
        begin.start()
    }
    Timer {
        id: begin; interval: 2000
        onTriggered: {
            harness.app.langOverride = Qt.application.arguments.indexOf('--arabic') >= 0 ? 'ar' : 'en'
            harness.app.route = 'cloud:openrouter/free'
            if (Qt.application.arguments.indexOf('--send-test') >= 0) {
                harness.app.chatSessionId = 'moai-native-project-review'
                harness.app.sendPrompt('In the registered Agent arithmetic review project, inspect files and Git status, fix the arithmetic bug in add.py without modifying tests, run python3 -m unittest -v, inspect Git diff and report the verified result. Request the necessary approvals. Use real tools.')
            } else {
                var xhr = new XMLHttpRequest()
                xhr.open('GET', harness.app.agentApi + '/api/sessions')
                xhr.setRequestHeader('X-Moai-Agent', '1')
                xhr.onreadystatechange = function() {
                    if (xhr.readyState !== XMLHttpRequest.DONE || xhr.status !== 200) return
                    var row = JSON.parse(xhr.responseText).find(s => s.key === 'moai-native-project-review')
                    if (row) {
                        harness.app.agentOpenPrimary(row.id, row.key, row.label)
                        if (Qt.application.arguments.indexOf('--followup') >= 0) followup.start()
                    }
                }
                xhr.send()
            }
            capture.start()
        }
    }
    Timer { id: followup; interval: 2000; onTriggered: harness.app.sendPrompt('Continue our existing task: run exactly python3 -m unittest -v again, inspect Git diff and report whether the previous fix is still correct. Do not edit anything.') }
    Timer {
        id: capture; interval: 5000; repeat: true
        onTriggered: {
            harness.captures++
            harness.frame.grabToImage(function(result) { result.saveToFile(harness.out + '/chat.png') })
            if (harness.app.agentToolEvents.length > 0 && !harness.app.agentActivityVisible) {
                var button = harness.find(harness.frame, 'agentActivityButton')
                if (button) driver.mouseClick(button, button.width / 2, button.height / 2)
            } else if (harness.app.agentActivityVisible && Qt.application.arguments.indexOf('--approve-test') >= 0 && harness.app.agentApprovals.length === 1) {
                var approval = harness.app.agentApprovals[0]
                var payload = JSON.parse(approval.command)
                if (approval.id !== harness.approved && approval.cwd === '/var/home/moos/.cache/moai-agent-review/project'
                        && payload.tool === 'run_command' && payload.arguments.command === 'python3 -m unittest -v') {
                    var allow = harness.find(harness.app.contentItem, 'agentAllowOnce')
                    if (allow) {
                        driver.mouseClick(allow, allow.width / 2, allow.height / 2)
                        harness.approved = approval.id
                        console.warn('MOAI_NATIVE_APPROVAL_CLICKED')
                    }
                }
            }
            if (harness.captures >= 100) Qt.quit()
        }
    }
}
