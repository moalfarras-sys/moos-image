"""The base of every page in Mira's window.

A page is a QObject with one `state` map that QML binds to, slots QML calls, and work that runs on
a thread and comes back on the Qt thread. What a page may reach of the rest of Mira is passed in as
`host` (the Controller), and a page uses only these parts of it:

    host.lang                          'ar' | 'en'
    host.s                             the merged interface words
    host.request_confirmation(item)    put a system change in front of the owner (an ActionCards card);
                                       item = {'kind': 'moai', 'name': <Mo AI tool>, 'args': {...},
                                       'detail': str, 'origin': <page>}
    host.toast.emit(kind, text)        a short notice (kind: ok | pending | error | info)
    host.prefill.emit(text)            put words in the composer (never sent for the owner)
    host.showSheet.emit(name)          open another destination ('' = the conversation)
    host.send(text)                    ask Mira in the conversation (only on the owner's own click)
"""
import os
import threading

from PySide6.QtCore import QObject, Property, Signal, Slot

TEST_MODE = os.environ.get('MIRA_TEST_MODE') == '1'


class Page(QObject):
    changed = Signal()
    _done = Signal(str, object)     # (tag, result) from a worker thread, delivered on the Qt thread

    def __init__(self, host, parent=None):
        super().__init__(parent)
        self.host = host
        self._state = dict(self.initial())
        self._done.connect(self._deliver)

    # ── for subclasses ───────────────────────────────────────────────
    def initial(self):
        """The state before anything was read (QML must render it)."""
        return {}

    def update(self, **fields):
        self._state = {**self._state, **fields}
        self.changed.emit()

    def run(self, tag, fn, *args, **kwargs):
        """Run `fn` on a thread; its result arrives at `self.on_<tag before ':'>(tag, result)`."""
        def work():
            try:
                result = fn(*args, **kwargs)
            except Exception as exc:   # the backend's own message, never a traceback
                result = {'status': 'error',
                          'error': str(exc) if isinstance(exc, (ValueError, RuntimeError)) else type(exc).__name__}
            self._done.emit(tag, result)
        threading.Thread(target=work, daemon=True).start()

    def text(self, key):
        return self.host.s.get(key, key)

    @property
    def lang(self):
        return self.host.lang

    # ── for QML and the controller ───────────────────────────────────
    def _get_state(self):
        return self._state
    state = Property('QVariantMap', _get_state, notify=changed)

    @Slot()
    def refresh(self):
        """Read everything the page shows again. Subclasses override."""

    def activated(self):
        """The owner opened this page. In review/test mode (MIRA_TEST_MODE=1) nothing is read from
        the machine: the page keeps its initial or review() state."""
        if TEST_MODE:
            return
        self.refresh()

    def review(self):
        """Fill the state with visibly-sample data for review renders (MIRA_TEST_MODE only)."""

    def _deliver(self, tag, result):
        handler = getattr(self, 'on_' + tag.split(':', 1)[0], None)
        if handler is not None:
            handler(tag, result)
