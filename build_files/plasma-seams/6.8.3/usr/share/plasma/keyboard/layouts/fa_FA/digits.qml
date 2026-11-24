// Copyright (C) 2016 The Qt Company Ltd.
// SPDX-License-Identifier: LicenseRef-Qt-Commercial OR GPL-3.0-only

import QtQuick
import QtQuick.Layouts
import QtQuick.VirtualKeyboard
import QtQuick.VirtualKeyboard.Components
import QtQuick.VirtualKeyboard.Plugins

KeyboardLayout {
    inputMethod: PlainInputMethod {}
    inputMode: InputEngine.InputMode.Numeric

    KeyboardColumn {
        Layout.fillWidth: false
        Layout.fillHeight: true
        Layout.alignment: Qt.AlignHCenter
        Layout.preferredWidth: height
        KeyboardRow {
            Key {
                text: "7"
            }
            Key {
                text: "8"
            }
            Key {
                text: "9"
            }
            BackspaceKey {}
        }
        KeyboardRow {
            Key {
                text: "4"
            }
            Key {
                text: "5"
            }
            Key {
                text: "6"
            }
            Key {
                text: " "
                displayText: "\u2423"
                repeat: true
                showPreview: false
                key: Qt.Key_Space
                highlighted: true
            }
        }
        KeyboardRow {
            Key {
                text: "1"
            }
            Key {
                text: "2"
            }
            Key {
                text: "3"
            }
            HideKeyboardKey {
                visible: true
            }
        }
        KeyboardRow {
            ChangeLanguageKey {
                customLayoutsOnly: true
            }
            Key {
                text: "0"
            }
            Key {
                key: Qt.Key_Comma
                text: "\u066B"
                alternativeKeys: "\u066B,."
            }
            EnterKey {}
        }
    }
}
