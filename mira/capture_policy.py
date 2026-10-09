"""Event-driven permission to capture one explicitly selected microphone.

Mute, missing/unknown identity and a lost subscription stop capture. A generation
also invalidates audio already handed to recognition across those boundaries.
Nothing here records audio, chooses another source or changes the owner's mute.
"""
from dataclasses import dataclass
import json
import os
import re
import subprocess
import threading


@dataclass(frozen=True)
class SourceState:
    reason: str = 'unknown'
    index: int | None = None

    @property
    def allowed(self):
        return self.reason == 'ready'


def inspect_source(source):
    try:
        if source == '@DEFAULT_SOURCE@':
            source = subprocess.run(['pactl', 'get-default-source'], check=True,
                                    capture_output=True, text=True, timeout=3,
                                    env=os.environ | {'LC_ALL': 'C.UTF-8'}).stdout.strip()
        result = subprocess.run(['pactl', '-f', 'json', 'list', 'sources'], check=True,
                                capture_output=True, text=True, timeout=3,
                                env=os.environ | {'LC_ALL': 'C.UTF-8'})
        sources = json.loads(result.stdout)
        if not isinstance(sources, list):
            return SourceState()
        found = [item for item in sources if isinstance(item, dict) and item.get('name') == source]
        if len(found) != 1:
            return SourceState('missing')
        item = found[0]
        index = item.get('index')
        if type(index) is not int or index < 0:
            return SourceState()
        if item.get('monitor_of_sink') not in (None, 'n/a', 4294967295) or '.monitor' in source:
            return SourceState('monitor_refused', index)
        if item.get('mute') is not False:
            return SourceState('muted' if item.get('mute') is True else 'unknown', index)
        ports = item.get('ports') or []
        active = item.get('active_port')
        if not isinstance(ports, list):
            return SourceState()
        if any(isinstance(port, dict) and port.get('name') == active
               and port.get('availability') in ('not available', 'no') for port in ports):
            return SourceState('unavailable', index)
        return SourceState('ready', index)
    except (OSError, subprocess.SubprocessError, ValueError, TypeError):
        return SourceState()


def _subscribe():
    return subprocess.Popen(['pactl', 'subscribe'], stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True,
                            env=os.environ | {'LC_ALL': 'C.UTF-8'})


def _terminate(process):
    if process is not None:
        try:
            process.terminate()
        except ProcessLookupError:
            pass


class SourceWatch:
    def __init__(self, source, on_state=None, *, probe=None, subscribe=None):
        self.source = source
        self._probe = probe or (lambda: inspect_source(source))
        self._subscribe = subscribe or _subscribe
        self._on_state = on_state or (lambda _state: None)
        self._condition = threading.Condition()
        self._state = SourceState()
        self._generation = 0
        self._recorder = None
        self._subscriber = None
        self._closed = threading.Event()
        self._thread = threading.Thread(target=self._run, name='mira-source-watch', daemon=True)

    def start(self):
        self._thread.start()

    def snapshot(self):
        with self._condition:
            return self._generation, self._state

    def permits(self, generation):
        with self._condition:
            return not self._closed.is_set() and self._state.allowed and generation == self._generation

    def attach_recorder(self, recorder, generation):
        with self._condition:
            if self._closed.is_set() or not self._state.allowed or generation != self._generation:
                _terminate(recorder)
                return False
            self._recorder = recorder
            return True

    def detach_recorder(self, recorder):
        with self._condition:
            if self._recorder is recorder:
                self._recorder = None

    def wait_ready(self, timeout=2):
        with self._condition:
            self._condition.wait_for(lambda: self._closed.is_set() or self._state.allowed, timeout)
            return not self._closed.is_set() and self._state.allowed

    def _publish(self, state):
        with self._condition:
            if state == self._state:
                return
            self._state = state
            self._generation += 1
            _terminate(self._recorder)
            self._condition.notify_all()
        self._on_state(state)

    def _relevant(self, event):
        match = re.fullmatch(r"Event '(?:new|change|remove)' on (source|server) #(\d+)\s*", event)
        if not match:
            return False
        _generation, state = self.snapshot()
        return ((match[1] == 'server' and self.source == '@DEFAULT_SOURCE@')
                or (match[1] == 'source' and (state.index is None or int(match[2]) == state.index)))

    def _run(self):
        while not self._closed.is_set():
            process = None
            try:
                # Subscribe BEFORE the first read: a mute during startup must
                # remain queued rather than race an unobserved capture start.
                process = self._subscribe()
                with self._condition:
                    self._subscriber = process
                    if self._closed.is_set():
                        _terminate(process)
                        return
                self._publish(self._probe())
                for event in process.stdout:
                    if self._closed.is_set():
                        return
                    if self._relevant(event):
                        self._publish(self._probe())
            except (OSError, subprocess.SubprocessError, ValueError, TypeError):
                pass
            finally:
                self._publish(SourceState())
                _terminate(process)
                if process is not None:
                    try:
                        process.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                    if process.stdout:
                        process.stdout.close()
                with self._condition:
                    self._subscriber = None
            # Failure-only backoff. The normal path has no periodic probe.
            self._closed.wait(2)

    def close(self):
        self._closed.set()
        self._publish(SourceState())
        with self._condition:
            _terminate(self._subscriber)
            self._condition.notify_all()
        if self._thread.is_alive():
            self._thread.join(timeout=5)
