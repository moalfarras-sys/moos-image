#!/usr/bin/env python3
"""The rig's workload: a busy window, and (when asked) a ScreenCast request for its output.

A column of text scrolling at the display rate is what a build log or a chat does to a desktop.
With RIG_CAST_OUTPUT set it also asks the compositor to cast that output, the way Plasma's own
task manager does, and prints `RIG node <id>`: the PipeWire node a plain client can then read.
That request needs KWIN_WAYLAND_NO_PERMISSION_CHECKS=1 in the RIG compositor's environment — it
is refused by the owner's session, which is why this cannot be pointed at it by mistake."""
import os
import sys

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

CAST = os.environ.get("RIG_CAST_OUTPUT", "")
WIDTH, HEIGHT = (int(v) for v in os.environ.get("RIG_WINDOW", "1100x720").split("x"))
LINE = "cargo build --release  بناء المشروع  compiling moos-shell v0.9."

QML = f'''
import QtQuick
import QtQuick.Window
{"import org.kde.taskmanager as TaskManager" if CAST else ""}
Window {{
    id: w
    visible: true
    width: {WIDTH}; height: {HEIGHT}
    color: "#11151a"
    title: "rig workload"
    {f'TaskManager.ScreencastingRequest {{ outputName: "{CAST}"; onNodeIdChanged: if (nodeId) console.warn("RIG node", nodeId) }}' if CAST else ""}
    Item {{
        anchors.fill: parent; clip: true
        Column {{
            id: log
            width: parent.width
            Repeater {{
                model: 80
                Text {{
                    width: log.width; color: index % 3 ? "#c8d2dc" : "#7fd1ff"
                    font.family: "monospace"; font.pixelSize: 15
                    text: "[" + index + "] {LINE}" + index + " (/var/home/dev/src)"
                }}
            }}
            NumberAnimation on y {{ from: 0; to: -900; duration: 6000; loops: Animation.Infinite }}
        }}
    }}
    Rectangle {{
        width: 90; height: 90; radius: 18; color: "#9f7bff"; x: 60; y: 60
        RotationAnimation on rotation {{ from: 0; to: 360; duration: 2000; loops: Animation.Infinite }}
    }}
}}
'''

app = QGuiApplication(sys.argv)
engine = QQmlApplicationEngine()
engine.loadData(QML.encode("utf-8"), QUrl("file:///rig.qml"))
if not engine.rootObjects():
    print("RIG client failed to load", file=sys.stderr, flush=True)
    sys.exit(2)
print("RIG client up", file=sys.stderr, flush=True)
QTimer.singleShot(int(os.environ.get("RIG_SECONDS", "40")) * 1000, app.quit)
sys.exit(app.exec())
