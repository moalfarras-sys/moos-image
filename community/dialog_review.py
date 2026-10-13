"""Exercise the actual client and KDE picture picker in a private test process.

Run on MoOS with an isolated HOME/display/session bus; never the owner's bus.
The image's runtime staging excludes this developer fixture.
"""
import argparse
import json
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--language', choices=('ar', 'en'), default='ar')
    parser.add_argument('--source-root', type=Path,
                        default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args()
    args.output.mkdir(mode=0o700, parents=True, exist_ok=True)
    sys.path.insert(0, str(args.source_root))
    sys.path.insert(0, '/usr/lib/mira/site')
    from community import client
    from PySide6.QtCore import QTimer, Qt, QUrl
    from PySide6.QtWidgets import QApplication, QDialog
    from PySide6.QtQml import QQmlApplicationEngine, QQmlExpression

    record = {'scope': 'Actual client bootstrap/native KDE dialog/private profile, no account or network',
              'language': args.language, 'passed': False, 'network_requests': 0}
    def forbid_request(*a, **kw):
        record['network_requests'] += 1
        raise AssertionError('dialog review must not contact a service')
    client.Api.request = forbid_request
    class ReviewTimer(QTimer):
        @staticmethod
        def singleShot(delay, callback):
            # Give the native dialog's asynchronous file model time to draw;
            # the production capture hook normally closes its window at 500ms.
            QTimer.singleShot(2500 if callback.__name__ == 'capture' else delay, callback)
    client.QTimer = ReviewTimer

    class Engine(QQmlApplicationEngine):
        def load(self, url):
            super().load(url)
            assert self.rootObjects(), 'actual client QML did not load'
            root = self.rootObjects()[0]
            context = self.contextForObject(root)
            self.rootContext().setContextProperty('moosDialogReviewFolder', QUrl.fromLocalFile(str(args.output.resolve())))
            controller = self.rootContext().contextProperty('community')
            before = json.dumps(controller.data, sort_keys=True)

            def inspect_picker():
                try:
                    widgets = list(QApplication.allWidgets())
                    record['application_class'] = QApplication.instance().metaObject().className()
                    record['native_file_widgets'] = sum(w.inherits('KFileWidget') for w in widgets)
                    dialogs = [w for w in widgets if w.inherits('KDEPlatformFileDialog')]
                    record['native_dialogs'] = len(dialogs)
                    assert record['native_file_widgets'] > 0 and dialogs, 'native KDE file picker absent'
                    dialog = dialogs[0]
                    record['rtl'] = dialog.layoutDirection() == Qt.RightToLeft
                    assert record['rtl'] == (args.language == 'ar'), 'wrong picker direction'
                    record['review_size'] = [dialog.width(), dialog.height()]
                    assert dialog.grab().save(str(args.output/'native-picker.png')), 'native picker pixels absent'
                    QDialog.reject(dialog)
                    QQmlExpression(context, root, 'picturePicker.close()').evaluate()
                    record['cancel_preserved_state'] = json.dumps(controller.data, sort_keys=True) == before
                    assert record['cancel_preserved_state'], 'cancel changed private attachment/draft state'
                    assert record['network_requests'] == 0, 'unexpected service request'
                    record['passed'] = True
                except Exception as error:
                    record['error'] = str(error)
                    modal = QApplication.activeModalWidget()
                    if modal is not None:
                        QDialog.reject(modal)
                finally:
                    (args.output/'receipt.json').write_text(json.dumps(record, indent=2)+'\n')
                    print(json.dumps(record), flush=True)
                    if not record['passed']:
                        QApplication.instance().exit(2)

            def open_picker():
                # KDE may enter its nested modal loop inside open(). Schedule
                # observation first so the proof runs while that dialog exists.
                QTimer.singleShot(1200, inspect_picker)
                expression = QQmlExpression(context, root,
                                           'picturePicker.currentFolder = moosDialogReviewFolder; picturePicker.open()')
                expression.evaluate()
                if expression.hasError():
                    record['open_error'] = expression.error().toString()
                    QApplication.instance().exit(2)
            QTimer.singleShot(0, open_picker)

    client.QQmlApplicationEngine = Engine
    sys.argv = ['moos-community', '--review', '--service-url', 'http://127.0.0.1:9',
                '--profile', str(args.output/'profile'), '--capture', str(args.output/'client.png'),
                '--language', args.language]
    try:
        client.main()
    except SystemExit as result:
        if result.code:
            raise
        # A launcher frame can close before a stalled picker is inspected.
        # Missing observation is a failure, even if the client exited cleanly.
        if not record['passed'] or 'open_error' in record:
            raise SystemExit('Native dialog observation did not complete')


if __name__ == '__main__':
    main()
