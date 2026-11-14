"""Event-driven notification of native audio-device catalogue changes.

Only pactl's subscription is opened. This observer never captures audio,
changes a device/default, or installs anything. Failure leaves manual refresh
to the existing settings owner; there is no background retry/polling loop.
"""
import re

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal

MAX_EVENT_BYTES = 128
_EVENT = re.compile(rb"Event '(?:new|change|remove)' on (?:source|sink|card|server) #([0-9]{1,10})\r?\n")


def is_device_event(line):
    """Accept one complete, bounded native event; stream/client events are ignored."""
    if not isinstance(line, bytes) or len(line) > MAX_EVENT_BYTES:
        return False
    match = _EVENT.fullmatch(line)
    return bool(match and int(match[1]) <= 4294967295)


class EventLines:
    """Bound incomplete lines and discard an entire oversized line before rearming."""
    def __init__(self):
        self.pending = bytearray()
        self.discarding = False

    def feed(self, data):
        matched = False
        for byte in data:
            if byte == 10:
                if not self.discarding and is_device_event(bytes(self.pending) + b'\n'):
                    matched = True
                self.pending.clear()
                self.discarding = False
            elif not self.discarding:
                if len(self.pending) >= MAX_EVENT_BYTES - 1:
                    self.pending.clear()
                    self.discarding = True
                else:
                    self.pending.append(byte)
        return matched


class AudioDeviceObserver(QObject):
    changed = Signal()
    failed = Signal()
    stopped = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._process = None
        self._lines = EventLines()
        self._stopping = False
        self._failed = False
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(200)
        self._debounce.timeout.connect(self._emit_changed)
        self._kill_timer = QTimer(self)
        self._kill_timer.setSingleShot(True)
        self._kill_timer.setInterval(1000)
        self._kill_timer.timeout.connect(self._kill)

    def _make_process(self):
        process = QProcess(self)
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert('LC_ALL', 'C')
        process.setProcessEnvironment(environment)
        process.setStandardInputFile(QProcess.nullDevice())
        process.setStandardErrorFile(QProcess.nullDevice())
        process.setProgram('/usr/bin/pactl')
        process.setArguments(['subscribe'])
        return process

    def start(self):
        """Start once, asynchronously. A failed subscription needs an explicit restart."""
        if self._process is not None:
            return
        self._lines = EventLines()
        self._stopping = self._failed = False
        process = self._process = self._make_process()
        process.readyReadStandardOutput.connect(lambda: self._read(process))
        process.started.connect(lambda: self._started(process))
        process.errorOccurred.connect(lambda error: self._error(process, error))
        process.finished.connect(lambda code, status: self._finished(process, code, status))
        process.start()

    def _started(self, process):
        if process is self._process and self._stopping:
            process.terminate()

    def _read(self, process):
        if process is not self._process:
            return
        while process.bytesAvailable():
            data = bytes(process.read(4096))
            if not data:
                break
            if not self._stopping and not self._failed and self._lines.feed(data):
                self._debounce.start()

    def _emit_changed(self):
        if self._process is not None and not self._stopping and not self._failed:
            self.changed.emit()

    def _error(self, process, _error):
        if process is not self._process:
            return
        self._fail()
        if self._process is not None and self._process.state() == QProcess.NotRunning:
            self._release()
        else:
            self.stop()

    def _fail(self):
        if not self._stopping and not self._failed:
            self._failed = True
            self._debounce.stop()
            self.failed.emit()

    def _finished(self, process, _code, _status):
        if process is not self._process:
            return
        self._fail()  # an unexpected exit0 is still a lost subscription
        self._release()

    def _release(self):
        process, self._process = self._process, None
        self._debounce.stop()
        self._kill_timer.stop()
        self._lines = EventLines()
        if process is not None:
            process.deleteLater()
            self.stopped.emit()

    def stop(self):
        """Terminate our subscriber; retain this object/event loop until stopped()."""
        self._stopping = True
        self._debounce.stop()
        self._lines = EventLines()
        if self._process is None:
            return
        if self._process.state() == QProcess.NotRunning:
            self._release()
            return
        self._process.terminate()
        self._kill_timer.start()

    def _kill(self):
        if self._process is not None and self._process.state() != QProcess.NotRunning:
            self._process.kill()

    def close(self):
        """Final shutdown only, including after the GUI event loop has stopped.

        Ordinary stop() is asynchronous. This bounded final reap prevents Qt
        destroying a still-running owned process when aboutToQuit has fired.
        A refused reap retains the process and reports False.
        """
        process = self._process
        self.stop()
        if process is None or process.state() == QProcess.NotRunning:
            return True
        if not process.waitForFinished(250):
            process.kill()
            process.waitForFinished(1000)
        if process.state() == QProcess.NotRunning:
            if self._process is process:
                self._release()
            return True
        return False
