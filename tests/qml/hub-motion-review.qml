import QtQuick
import QtQuick.Window
import QtTest
import "../../system_files/usr/share/plasma/wallpapers/org.moos.ui2.wallpaper/contents/ui" as Hub
Window {
    width: 640; height: 240; visible: true
    Hub.HubReveal { id: reveal; motionEnabled: true; motionLevel: 1 }
    TestCase { id: driver; name: "MoOSHubReveal"; when: false }
    Timer { interval: 600; running: true; repeat: false
        onTriggered: {
          try {
            driver.wait(600)
            driver.compare(reveal.progress, 1)
            reveal.motionLevel = 2
            driver.verify(reveal.progress < 1)
            driver.wait(40)
            driver.verify(reveal.progress > 0 && reveal.progress < 1)
            reveal.motionEnabled = false
            driver.compare(reveal.progress, 1)
            reveal.motionLevel = 1
            driver.compare(reveal.progress, 1)
            driver.wait(500)
            driver.compare(reveal.progress, 1)
            reveal.motionEnabled = true
            driver.verify(reveal.progress < 1)
            driver.wait(600)
            driver.compare(reveal.progress, 1)
            console.warn("MOOS_MOTION_PASSED: real Hub reveal, change preview, interruption, still and idle")
            Qt.quit()
          } catch(error) { console.error(error); Qt.exit(1) }
        }
    }
}
