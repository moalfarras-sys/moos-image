// Test-only driver injected into a temporary shell overlay. Never shipped.
import QtQuick
import QtQuick.Window
import QtTest as Test
Item {
    id: driver
    required property var customizer
    required property var desktopItem
    // Resolved from this file so the driver keeps working from any checkout
    // or worktree; it used to hard-code one clone's absolute path.
    property string output: Qt.resolvedUrl("../../docs/evidence/desktop-edit-20260907/")
                              .toString().replace("file://", "")
    property string lastCommand: ""
    function find(item, name) {
        if (item.objectName === name) return item
        for (const child of item.children || []) { const found = find(child, name); if (found) return found }
        return null
    }
    function capture(name) { customizer.grabToImage(result => result.saveToFile(output + name + '.png')) }
    Test.TestCase { id: test; when: false; name: "LiveDesktop" }
    Timer {
        interval: 700; repeat: true; running: true
        onTriggered: {
            const request = new XMLHttpRequest()
            request.open("GET", "file:///var/home/moos/.local/state/moos-desktop-review/command.json")
            request.onreadystatechange = function() {
                if (request.readyState !== XMLHttpRequest.DONE || !request.responseText) return
                const command = JSON.parse(request.responseText)
                if (command.id === driver.lastCommand) return
                driver.lastCommand = command.id
                try {
                    const main = driver.customizer
                    if (command.action === "search") {
                        main.page = 0; main.selected = null
                        driver.find(main,"widgetSearch").text = command.text
                    } else if (command.action === "select") {
                        const grid = driver.find(main,"widgetCatalog")
                        const tile = Array.from(grid.contentItem.children).find(c => c.model?.pluginName === command.plugin)
                        test.verify(!!tile, "real catalog tile exists")
                        test.mouseClick(tile)
                    } else if (command.action === "add") {
                        test.mouseClick(driver.find(main,"addSelectedWidget"))
                        test.wait(1000)
                        test.verify(main.applets.some(a => a.pluginName === command.plugin), "widget was added")
                    } else if (command.action === "manage") {
                        main.page = 1; main.selected = null
                    } else if (command.action === "move") {
                        const applet = main.applets.find(a => a.pluginName === command.plugin)
                        const item = driver.desktopItem.itemFor(applet)
                        console.warn("DESKTOP_ITEM", item, item.parent, item.x, item.y, item.width, item.height)
                        test.mouseDrag(item, item.width / 2, 10, 260, 160, Qt.LeftButton, Qt.NoModifier, 100)
                    } else if (command.action === "inspect") {
                        for (const a of main.applets) {
                            const item = driver.desktopItem.itemFor(a)
                            console.warn("APPLET_STATE", a.id, a.pluginName, item, item?.fullRepresentationItem, JSON.stringify(item?.fullRepresentationItem?.errorInformation || null), JSON.stringify(item?.errorInformation || null))
                        }
                    } else if (command.action === "remove") {
                        const button = driver.find(main,"removeWidget")
                        test.mouseClick(button)
                    } else if (command.action === "confirm") {
                        test.mouseClick(driver.find(main.Window.window.contentItem,"confirmWidgetRemoval"))
                    } else if (command.action === "capture") {
                        driver.capture(command.name)
                    } else if (command.action === "widget-capture") {
                        const a = main.applets.find(a => a.pluginName === command.plugin)
                        driver.desktopItem.itemFor(a).grabToImage(result => result.saveToFile(driver.output + command.name + '.png'))
                    } else if (command.action === "configure") {
                        const a = main.applets.find(a => a.pluginName === command.plugin)
                        main.actionFor(a, "configure").trigger()
                    } else if (command.action === "preview") {
                        test.mouseClick(driver.find(main, "previewSelectedWidget"))
                    } else if (command.action === "appearance") {
                        main.openAppearance()
                    }
                    console.warn("DESKTOP_TEST_OK", command.id, command.action, main.applets.length)
                } catch (e) { console.error("DESKTOP_TEST_FAILED", command.id, String(e)) }
            }
            request.send()
        }
    }
}
