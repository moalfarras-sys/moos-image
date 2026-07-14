/*
    SPDX-FileCopyrightText: 2014 Aleix Pol Gonzalez <aleixpol@blue-systems.com>
    SPDX-FileCopyrightText: 2026 Moalfarras

    SPDX-License-Identifier: GPL-2.0-or-later

    The MoOS UI2 lock screen entry point. Byte-for-byte the contract kscreenlocker
    expects (the "magical properties" below are read by name by the greeter); the
    look is delivered by MoOSLockScreenUi, a restyle of Plasma 6.7's LockScreenUi
    that keeps every authenticator connection and the MainBlock auth path exactly
    as shipped — the visual layer is MoOS, the security path is untouched.
*/
import QtQuick

Item {
    id: root
    property bool debug: false
    property string notification
    signal clearPassword()
    signal notificationRepeated()

    // These are magical properties that kscreenlocker looks for
    property bool viewVisible: false

    LayoutMirroring.enabled: Application.layoutDirection === Qt.RightToLeft
    LayoutMirroring.childrenInherit: true

    implicitWidth: 800
    implicitHeight: 600

    MoOSLockScreenUi {
        anchors.fill: parent
    }
}
