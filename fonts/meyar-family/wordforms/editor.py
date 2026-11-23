"""Edit actual selectable word-form fonts in an ordinary Qt text editor."""
import argparse
from pathlib import Path
import sys
from PySide6.QtGui import QFont, QFontDatabase, QRawFont, QTextCursor
from PySide6.QtWidgets import QApplication, QComboBox, QTextEdit, QVBoxLayout, QWidget


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--capture', type=Path)
    parser.add_argument('--size', type=int, choices=(16,24,42), default=42)
    args = parser.parse_args()
    app = QApplication([])
    reviewed = {}
    for kind in ['Arabic', 'Sans']:
        path = args.directory / f'MeyarForm{kind}-Regular.ttf'
        raw = QRawFont(str(path), 42, QFont.HintingPreference.PreferDefaultHinting)
        assert raw.isValid()
        reviewed[raw.familyName()] = bytes(raw.fontTable('glyf'))
        handle = QFontDatabase.addApplicationFont(str(path))
        assert handle >= 0 and f'Meyar Form {kind}' in QFontDatabase.applicationFontFamilies(handle)
    window = QWidget()
    window.setWindowTitle('مِعيار — محرّر الخط')
    layout = QVBoxLayout(window)
    sizes = QComboBox()
    for size in (42, 24, 16):
        sizes.addItem(f'{size} px', size)
    sizes.setCurrentIndex(sizes.findData(args.size))
    layout.addWidget(sizes)
    editor = QTextEdit()
    editor.setAcceptRichText(False)
    layout.addWidget(editor)
    def apply_size():
        font = QFont()
        font.setFamilies(['Meyar Form Sans','Meyar Form Arabic'])
        font.setPixelSize(sizes.currentData())
        editor.document().setDefaultFont(font)
        editor.setFont(font)
    sizes.currentIndexChanged.connect(apply_size)
    apply_size()
    editor.setPlainText('مِعْيَارٌ   المَفَاتِيح   نَوَافِذ   اتِّصَال\nMeyar   Flow   Architecture\nΕλληνικά   Кириллица\n١٢٣   3.14   →   ⌘   ★')
    editor.moveCursor(QTextCursor.End)
    window.resize(930,525)
    window.show()
    if args.capture:
        app.processEvents()
        original = editor.toPlainText()
        editor.insertPlainText(' مِعيار')
        editor.undo()
        assert editor.toPlainText() == original
        editor.redo()
        assert editor.toPlainText() == original + ' مِعيار'
        editor.undo()
        editor.document().documentLayout().documentSize()
        app.processEvents()
        editor.grab()
        for index, expected in [(0, 'Meyar Form Arabic'), (1, 'Meyar Form Sans')]:
            block = editor.document().findBlockByNumber(index)
            layout = block.layout()
            assert layout.lineCount() >= 1, block.text()
            runs = layout.lineAt(0).glyphRuns(0, -1, layout.GlyphRunRetrievalFlag.RetrieveAll)
            assert any(run.rawFont().familyName() == expected and
                       bytes(run.rawFont().fontTable('glyf')) == reviewed[expected]
                       for run in runs), (expected, [run.rawFont().familyName() for run in runs])
        assert editor.grab().save(str(args.capture))
    else:
        sys.exit(app.exec())


if __name__ == '__main__':
    main()
