"""Editable native specimen. Shape each line once, then draw its two word halves."""
import argparse
import math
import sys
import unicodedata
from pathlib import Path

from PySide6.QtCore import QPointF, Qt, QTextBoundaryFinder
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPainter, QPainterPath, QTextLayout
from PySide6.QtWidgets import QApplication, QLabel, QPlainTextEdit, QVBoxLayout, QWidget, QComboBox

ROOT = Path(__file__).resolve().parents[3]
SAMPLE = "مِعْيَار   المَفَاتِيح   ضَوْء   اتِّصَال\nMeyar   Waveform   Architecture\nالعَرَبِيَّة   MoOS   Ελληνικά   Кириллица\n١٢٣   3.14   →   ⌘   ★"


def letter_halves(text):
    """Map UTF-16 cluster starts to an outline. Marks travel with the base."""
    finder = QTextBoundaryFinder(QTextBoundaryFinder.Grapheme, text)
    data = text.encode('utf-16-le')
    halves = {}
    word = []

    def finish():
        for index, (start, end) in enumerate(word):
            for offset in range(start, end):
                halves[offset] = index < (len(word) + 1) // 2
        word.clear()

    start = 0
    while (end := finder.toNextBoundary()) != -1:
        cluster = data[2 * start:2 * end].decode('utf-16-le')
        if any(unicodedata.category(c).startswith('L') for c in cluster):
            word.append((start, end))
        else:
            finish()
        start = end
    finish()
    return halves


def contour(path, sharp):
    """Use short facets on the entry and tangent curves on the exit."""
    out = QPainterPath()
    out.setFillRule(path.fillRule())
    for polygon in path.toSubpathPolygons():
        points = list(polygon)
        if len(points) < 4:
            continue
        if points[-1] == points[0]:
            points.pop()
        # Bound simplification in em space. Preserve a pointed extremum even
        # on a tiny counter or diacritic.
        if sharp:
            # Fit a facet only while the original contour stays within a
            # subpixel error at text sizes. Preserve both extrema of each arc.
            def simplify(arc):
                if len(arc) <= 2:
                    return arc
                chord = arc[-1] - arc[0]
                length = max(.001, math.hypot(chord.x(), chord.y()))
                errors = [abs(chord.x()*(v.y()-arc[0].y()) -
                              chord.y()*(v.x()-arc[0].x())) / length for v in arc]
                split = max(range(len(arc)), key=errors.__getitem__)
                if errors[split] <= 1.05:
                    return [arc[0], arc[-1]]
                return simplify(arc[:split+1])[:-1] + simplify(arc[split:])
            far = max(range(len(points)), key=lambda k: (points[k]-points[0]).manhattanLength())
            corners = simplify(points[:far+1])[:-1] + simplify(points[far:] + points[:1])
            out.moveTo(corners[0])
            for point in corners[1:]:
                out.lineTo(point)
        else:
            # Round the junction locally; long ascenders and connecting
            # strokes stay straight along their original centreline.
            def trim(a, b):
                v = b-a
                length = math.hypot(v.x(), v.y())
                return a + v * min(.38, 2.2 / max(.001, length))
            out.moveTo(trim(points[0],points[-1]))
            for i, point in enumerate(points):
                out.lineTo(trim(point,points[i-1]))
                out.quadTo(point,trim(point,points[(i+1)%len(points)]))
        out.closeSubpath()
    return out


class Specimen(QWidget):
    def __init__(self, editor):
        super().__init__()
        self.editor = editor
        self.pixel_size = 50
        self.setMinimumSize(1000, 530)
        self.paths = {}
        editor.textChanged.connect(self.update)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor('#f7f4ec'))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor('#172e33'))
        y = 12
        for text in self.editor.toPlainText().splitlines():
            font = QFont('Meyar Sans')
            font.setFamilies(['Meyar Sans', 'Meyar Arabic'])
            font.setPixelSize(self.pixel_size)
            layout = QTextLayout(text, font)
            option = layout.textOption()
            option.setAlignment(Qt.AlignRight if text and text[0].isalpha() and unicodedata.bidirectional(text[0]) in ("AL", "R") else Qt.AlignLeft)
            layout.setTextOption(option)
            layout.beginLayout()
            line = layout.createLine()
            if not line.isValid():
                layout.endLayout()
                y += 82
                continue
            line.setLineWidth(self.width()-48)
            while True:
                extra = layout.createLine()
                if not extra.isValid():
                    break
                extra.setLineWidth(self.width()-48)
                previous = layout.lineAt(layout.lineCount()-2)
                extra.setPosition(QPointF(0, previous.y()+previous.height()))
            layout.endLayout()
            halves = letter_halves(text)
            for run in layout.glyphRuns(-1, -1, QTextLayout.GlyphRunRetrievalFlag.RetrieveAll):
                raw = run.rawFont()
                for gid, position, index in zip(run.glyphIndexes(), run.positions(), run.stringIndexes()):
                    sharp = halves.get(index)
                    key = (raw.familyName(), raw.styleName(), raw.pixelSize(), gid, sharp)
                    if key not in self.paths:
                        path = raw.pathForGlyph(gid)
                        if sharp is None:
                            self.paths[key] = path
                        else:
                            from PySide6.QtGui import QTransform
                            normalized = QTransform.fromScale(50 / raw.pixelSize(), 50 / raw.pixelSize()).map(path)
                            self.paths[key] = QTransform.fromScale(raw.pixelSize() / 50, raw.pixelSize() / 50).map(contour(normalized, sharp))
                    painter.save()
                    painter.translate(position + QPointF(24, y))
                    if self.paths[key].isEmpty():
                        from PySide6.QtGui import QGlyphRun
                        one = QGlyphRun()
                        one.setRawFont(raw)
                        one.setGlyphIndexes([gid])
                        one.setPositions([QPointF()])
                        painter.drawGlyphRun(QPointF(), one)
                    else:
                        painter.drawPath(self.paths[key])
                    painter.restore()
            y += max(76, layout.boundingRect().height())
        painter.end()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path)
    args = parser.parse_args()
    app = QApplication([])
    for family in ('Arabic', 'Sans'):
        path = ROOT / 'system_files/usr/share/fonts/meyar' / ('Meyar'+family+'[wght].ttf')
        assert QFontDatabase.addApplicationFont(str(path)) >= 0
    window = QWidget()
    window.setWindowTitle('مِعيار — دراسة شكل الكلمة')
    column = QVBoxLayout(window)
    edit = QPlainTextEdit(SAMPLE)
    edit.setMaximumHeight(125)
    preview = Specimen(edit)
    sizes = QComboBox()
    for size, title in [(50, 'عنوان'), (22, 'قائمة'), (16, 'نص واجهة')]:
        sizes.addItem(f'{title} · {size} px', size)
    def resize_specimen():
        preview.pixel_size = sizes.currentData()
        preview.update()
    sizes.currentIndexChanged.connect(resize_specimen)
    column.addWidget(sizes)
    column.addWidget(preview)
    column.addWidget(QLabel('اكتب هنا لتجربة شكل الكلمة'))
    column.addWidget(edit)
    window.show()
    if args.capture:
        app.processEvents()
        assert preview.grab().save(str(args.capture))
    else:
        sys.exit(app.exec())
