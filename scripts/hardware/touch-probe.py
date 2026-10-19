#!/usr/bin/env python3
"""Finite owner-operated Wayland touch/stylus check; no input injection or raw-device access.

Run on the native graphical session with moai-open. Only aggregate event counts
are printed on close; no keys, coordinates, camera images or biometrics are saved.
Mouse clicks never qualify as touch. This is a hardware fixture, not a shipped app.
"""
import argparse
import json
import sys

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QApplication, QWidget


class Probe(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MoOS · فحص اللمس والقلم · Touch and pen check")
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents)
        self.counts = dict(touch_begin=0, touch_update=0, touch_end=0,
                           max_contacts=0, pen_press=0, pen_move=0, pen_release=0)
        self.setMinimumSize(440, 320)

    def event(self, event):
        touch = {QEvent.Type.TouchBegin: "touch_begin",
                 QEvent.Type.TouchUpdate: "touch_update", QEvent.Type.TouchEnd: "touch_end"}
        pen = {QEvent.Type.TabletPress: "pen_press", QEvent.Type.TabletMove: "pen_move",
               QEvent.Type.TabletRelease: "pen_release"}
        if event.type() in touch:
            self.counts[touch[event.type()]] += 1
            self.counts["max_contacts"] = max(self.counts["max_contacts"], len(event.points()))
        elif event.type() in pen:
            self.counts[pen[event.type()]] += 1
        else:
            return super().event(event)
        event.accept()
        self.update()
        return True

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.palette().window())
        painter.setPen(self.palette().text().color())
        font = painter.font()
        font.setPointSize(16)
        painter.setFont(font)
        passed = self.counts["touch_begin"] > 0 and self.counts["touch_end"] > 0
        text = ("المس داخل النافذة، اسحب إصبعك، ثم جرّب إصبعين والقلم\n"
                "Touch, drag, then try two fingers and the pen\n\n"
                f"لمسات كاملة / completed touches: {self.counts['touch_end']}\n"
                f"سحب / touch moves: {self.counts['touch_update']}\n"
                f"أقصى أصابع / max contacts: {self.counts['max_contacts']}\n"
                f"ضغطات القلم / pen presses: {self.counts['pen_press']}\n\n"
                + ("وصلت أحداث لمس فعلية / Touch events received" if passed
                   else "بانتظار اللمس / Waiting for touch events")
                + "\nEscape أو أغلق النافذة للانتهاء / Close to finish")
        if passed:
            painter.setPen(QColor("#20a060"))
        painter.drawText(self.rect().adjusted(18, 18, -18, -18),
                         Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=int, default=300, choices=range(10, 601),
                        metavar="10..600")
    args = parser.parse_args()
    app = QApplication(sys.argv[:1])
    probe = Probe()
    screen = next((s for s in app.screens() if s.name().startswith("eDP")), app.primaryScreen())
    rect = screen.availableGeometry()
    probe.resize(min(740, rect.width()), min(470, rect.height()))
    probe.move(rect.center() - probe.rect().center())
    probe.show()
    QTimer.singleShot(args.seconds * 1000, probe.close)
    result = app.exec()
    print(json.dumps({"schema": 1, "counts": probe.counts,
                      "touch_observed": probe.counts["touch_begin"] > 0
                      and probe.counts["touch_end"] > 0,
                      "pen_observed": probe.counts["pen_press"] > 0
                      and probe.counts["pen_release"] > 0}), flush=True)
    return result


if __name__ == "__main__":
    sys.exit(main())
