"""Mira's two original faces, served to QML as aligned portrait squares.

The rose and holographic sprite sheets are used exactly as drawn. `faces.json` (written by
`devtools/align_faces.py`) says where each expression's face sits, so every expression is cropped to
the same framing and a change of expression never makes the head jump. QML asks for
`image://mira/<style>/<expression>` and gets a square portrait with transparent padding where a
narrow cell ends.
"""
import json
from pathlib import Path

from PySide6.QtCore import QRect, QRectF, QSize, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtQuick import QQuickImageProvider

ROOT = Path(__file__).resolve().parent
CALIBRATION = ROOT / 'faces.json'
STYLES = ('rose', 'holo')
EXPRESSIONS = ('neutral', 'happy', 'excited', 'playful', 'thinking', 'sad', 'annoyed',
               'attentive', 'surprised', 'reassuring', 'curious', 'proud', 'sleepy',
               'blink', 'speaking_round', 'speaking_open')
# The holographic set was drawn without a separate "happy"; its warm neutral is that expression.
FALLBACK = {'happy': 'neutral'}
PORTRAIT = 768


class FaceLibrary:
    """Crops and caches each expression once; the sheets stay untouched on disk."""

    def __init__(self, calibration=CALIBRATION):
        data = json.loads(Path(calibration).read_text())
        self.frames = data['styles']
        self.sheets = {}
        self.cache = {}

    def expressions(self, style):
        return sorted(set(self.frames.get(style, {})) | {k for k, v in FALLBACK.items()
                                                         if v in self.frames.get(style, {})})

    def _sheet(self, name):
        if name not in self.sheets:
            image = QImage(str(ROOT / name))
            if image.isNull():
                raise FileNotFoundError(name)
            self.sheets[name] = image.convertToFormat(QImage.Format_ARGB32_Premultiplied)
        return self.sheets[name]

    def portrait(self, style, expression, size=PORTRAIT):
        style = style if style in self.frames else 'rose'
        frames = self.frames[style]
        if expression not in frames:
            expression = FALLBACK.get(expression, 'neutral')
        if expression not in frames:
            expression = next(iter(frames))
        key = (style, expression, size)
        if key in self.cache:
            return self.cache[key]
        frame = frames[expression]
        sheet = self._sheet(frame['sheet'])
        cx, cy, cw, ch = frame['cell']
        x, y, w, h = frame['crop']
        out = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
        out.fill(Qt.transparent)
        painter = QPainter(out)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        # Only the expression's own cell is ever sampled, never its neighbour on the sheet.
        cell = QRectF(cx, cy, cw, ch)
        crop = QRectF(x, y, w, h)
        visible = cell.intersected(crop)
        scale = size / w
        target = QRectF((visible.x() - x) * scale, (visible.y() - y) * scale,
                        visible.width() * scale, visible.height() * scale)
        painter.drawImage(target, sheet, visible)
        painter.end()
        if len(self.cache) > 64:
            self.cache.clear()
        self.cache[key] = out
        return out


class FaceProvider(QQuickImageProvider):
    def __init__(self, library=None):
        super().__init__(QQuickImageProvider.Image)
        self.library = library or FaceLibrary()

    def requestImage(self, image_id, size, requested):
        style, _, expression = image_id.partition('/')
        expression = expression.split('?', 1)[0]
        edge = PORTRAIT
        if requested.isValid() and requested.width() > 0:
            edge = max(128, min(1024, requested.width()))
        image = self.library.portrait(style, expression or 'neutral', edge)
        if size is not None:
            size.setWidth(image.width())
            size.setHeight(image.height())
        return image
