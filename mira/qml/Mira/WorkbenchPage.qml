import QtQuick
import QtQuick.Layouts

// Placeholder until the Workbench page lands: the page object (mira.workbenchPage) and its QML are built together.
PageFrame {
    icon: "sparkle"
    title: mira.s.nav_workbench || ""
    subtitle: mira.s.page_loading
}
