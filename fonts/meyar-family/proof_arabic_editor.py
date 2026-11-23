#!/usr/bin/env python3
"""Render a real Arabic editing journey from one font, using native Qt and Fontconfig."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import xml.etree.ElementTree as ET

from PySide6.QtCore import Qt, qVersion
from PySide6.QtGui import (QFont, QFontDatabase, QInputMethodEvent, QRawFont,
                           QTextBlockFormat, QTextCharFormat)
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QTextEdit

ROWS = [
    ('الملفات والإعدادات', 74, 650),
    ('مِعْيَارٌ لِلْعَرَبِيَّةِ', 55, 550),
    ('لِقَاءٌ عَائِلِيٌّ، واتِّصَالٌ مُسْتَقِرٌّ.', 34, 450),
    ('اِفْتَحْ لَوْحَةَ الْمَفَاتِيحِ وَالتَّطْبِيقَاتِ.', 23, 400),
    ('أَّ  آَّ  إِّ  بِّ  مِعْيَارٌ  اللهُ  لَأْلَاءٌ', 22, 700),
    ('الملفات، النظام، الحساب، لوحة المفاتيح', 17, 400),
    ('إشعارات النظام والتحديثات', 14, 400),
]


def insert_text(editor, text):
    event = QInputMethodEvent()
    event.setCommitString(text)
    QApplication.sendEvent(editor, event)


def capture(source, output, private):
    # Retain the machine's actual rendering rules. A minimal private config
    # silently substitutes full hinting for the V3's slight hinting.
    fonts = private / 'fonts'
    fonts.mkdir()
    path = fonts / source.name
    shutil.copyfile(source, path)
    config = ET.Element('fontconfig')
    ET.SubElement(config, 'include').text = '/etc/fonts/fonts.conf'
    ET.SubElement(config, 'reset-dirs')
    ET.SubElement(config, 'dir').text = str(fonts)
    file = private / 'fonts.conf'
    ET.ElementTree(config).write(file, encoding='utf-8')
    os.environ.update(FONTCONFIG_FILE=str(file), XDG_CACHE_HOME=str(private / 'cache'),
                      QT_QPA_PLATFORM='offscreen')

    app = QApplication([])
    app.setStyle('Fusion')
    app.setCursorFlashTime(0)
    expected = bytes(QRawFont(str(path), 22).fontTable('glyf'))
    assert expected
    loaded = QFontDatabase.addApplicationFont(str(path))
    assert QFontDatabase.applicationFontFamilies(loaded) == ['Meyar Arabic']
    editor = QTextEdit()
    editor.setLayoutDirection(Qt.RightToLeft)
    editor.setAcceptRichText(False)
    editor.setFrameStyle(0)
    editor.resize(990, 715)
    editor.document().setDocumentMargin(28)
    editor.setStyleSheet('QTextEdit { background: #f8f7f4; color: #192a30; }')
    editor.setCursorWidth(0)
    editor.show()

    for index, (text, size, weight) in enumerate(ROWS):
        cursor = editor.textCursor()
        if index:
            cursor.insertBlock()
        block = QTextBlockFormat()
        block.setLayoutDirection(Qt.RightToLeft)
        block.setAlignment(Qt.AlignRight | Qt.AlignAbsolute)
        cursor.setBlockFormat(block)
        font = QFont('Meyar Arabic')
        font.setPixelSize(size)
        font.setVariableAxis(QFont.Tag('wght'), weight)
        char = QTextCharFormat()
        char.setFont(font)
        cursor.setCharFormat(char)
        editor.setTextCursor(cursor)
        insert_text(editor, text)
    document = '\n'.join(text for text, _, _ in ROWS)
    assert editor.toPlainText() == document
    extra = ' — مَرْحَبًا'
    insert_text(editor, extra)
    assert editor.toPlainText() == document + extra
    for modifiers, suffix in [(Qt.ControlModifier, ''),
                              (Qt.ControlModifier | Qt.ShiftModifier, extra),
                              (Qt.ControlModifier, '')]:
        QTest.keyClick(editor, Qt.Key_Z, modifiers)
        assert editor.toPlainText() == document + suffix
    editor.clearFocus()
    app.processEvents()

    rows = []
    block = editor.document().begin()
    while block.isValid():
        layout = block.layout()
        assert layout.lineCount() == 1, block.text()
        line = layout.lineAt(0)
        top, bottom = float('inf'), -float('inf')
        for run in line.glyphRuns(0, -1, layout.GlyphRunRetrievalFlag.RetrieveAll):
            raw = run.rawFont()
            assert raw.familyName() == 'Meyar Arabic' and bytes(raw.fontTable('glyf')) == expected
            for gid, pos in zip(run.glyphIndexes(), run.positions()):
                assert gid
                ink = raw.pathForGlyph(gid).boundingRect().translated(pos)
                if not ink.isEmpty():
                    top, bottom = min(top, ink.top()), max(bottom, ink.bottom())
        assert line.y() <= top < bottom <= line.y() + line.height(), (block.text(), top, bottom)
        rows.append(dict(text=block.text(), width=line.naturalTextWidth(), height=line.height(),
                         inkTop=top, inkBottom=bottom))
        block = block.next()
    assert editor.verticalScrollBar().maximum() == editor.horizontalScrollBar().maximum() == 0
    assert editor.grab().save(str(output))
    info = dict(fontSha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                glyfSha256=hashlib.sha256(expected).hexdigest(), qt=qVersion(),
                platform=app.platformName(), dpr=editor.devicePixelRatioF(),
                document='QTextEdit', inputMethodUndoRedo=True, rows=rows)
    output.with_suffix('.json').write_text(json.dumps(info, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('image', type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='meyar-editor-') as tmp:
        capture(args.source, args.image, Path(tmp))
