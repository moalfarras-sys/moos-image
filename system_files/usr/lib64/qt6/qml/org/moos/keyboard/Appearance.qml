// SPDX-License-Identifier: GPL-3.0-or-later
pragma Singleton
import QtCore

Settings {
    location: StandardPaths.writableLocation(StandardPaths.GenericConfigLocation) + "/moos-keyboardrc"
    category: "Appearance"
    property int heightPercent: 35
    property int surfaceOpacity: 94
    property bool showSuggestions: true
    property string recentEmoji: ""
}
