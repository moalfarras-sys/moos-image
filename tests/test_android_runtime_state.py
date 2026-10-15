#!/usr/bin/env python3
"""Real status responses must agree across setup, admission and the Store."""
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    loader=importlib.machinery.SourceFileLoader(name,str(path))
    spec=importlib.util.spec_from_loader(name,loader);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;loader.exec_module(module);return module
RUNTIME=load('runtime_state_review',ROOT/'system_files/usr/lib/moos/moos_android_runtime.py')
STORE=load('runtime_store_review',ROOT/'system_files/usr/bin/moos-storectl')

class StatusReadback(unittest.TestCase):
    def test_only_one_successful_known_session_is_ready(self):
        for code,out,err,expected in [(0,'Session: RUNNING\n','','RUNNING'),(0,'Session: STOPPED\n','','STOPPED'),
            (0,'Session: FROZEN\n','','FROZEN'),(1,'Session: RUNNING\n','','unknown'),
            (0,'Session: RUNNING\n','ERROR: failed connection','unknown'),
            (0,'Session: RUNNING\nSession: STOPPED\n','','unknown'),
            (0,'Session: RUNNING\nSession: RUNNING\n','','unknown'),
            (0,'not a known response','','unknown'),(0,'x'*65537,'','unknown')]:
            with self.subTest(code=code,out=out[:80],err=err):
                self.assertEqual(RUNTIME.status_state(code,out,err),expected)
                result=STORE.CommandResult(code,err,output=out)
                self.assertEqual(STORE.Controller._android_running(result),expected=='RUNNING')

    def test_uninitialized_is_distinct_from_an_error_and_a_running_session(self):
        self.assertEqual(RUNTIME.status_state(0,'','[12:34:56] WayDroid is not initialized, run init'),'uninitialized')
        for code,out,err in [(1,'','WayDroid is not initialized'),(0,'Session: RUNNING\n','WayDroid is not initialized'),
                             (0,'','WayDroid is not initialized\nERROR: no permission')]:
            self.assertEqual(RUNTIME.status_state(code,out,err),'unknown')

    def test_failed_or_ambiguous_status_never_starts_a_session(self):
        for response in [STORE.CommandResult(1,output='Session: RUNNING\n'),
                         STORE.CommandResult(0,'ERROR: refused',output='Session: STOPPED\n'),
                         STORE.CommandResult(0,output='Session: RUNNING\nSession: STOPPED\n')]:
            controller=object.__new__(STORE.Controller);controller.runner=mock.Mock()
            controller.runner.capture.return_value=response
            with self.assertRaises(STORE.StoreError): controller._ensure_android_session(object())
            controller.runner.spawn.assert_not_called()
            controller.runner.capture.assert_called_once_with([STORE.WAYDROID,'status'],timeout=2)

    def test_actual_setup_action_refuses_failed_status_before_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);bin=p/'bin';bin.mkdir();marker=p/'mutations'
            for name in ['waydroid','pkexec','systemctl','moos-gpu-headroom']:
                script=bin/name
                if name=='waydroid': script.write_text('#!/bin/sh\nif [ "$1" = status ]; then printf "Session: RUNNING\\n"; exit 1; fi\nprintf mutation >> "$MARKER"\nexit 97\n')
                else: script.write_text('#!/bin/sh\nprintf mutation >> "$MARKER"\nexit 97\n')
                script.chmod(0o755)
            logger=bin/'logger';logger.write_text('#!/bin/sh\nexit 0\n');logger.chmod(0o755)
            env={**os.environ,'HOME':td,'XDG_CONFIG_HOME':td,'XDG_DATA_HOME':td,'XDG_STATE_HOME':td,
                 'XDG_RUNTIME_DIR':td,'DBUS_SESSION_BUS_ADDRESS':'unix:path=/nonexistent','DISPLAY':'','WAYLAND_DISPLAY':'',
                 'PATH':str(bin)+':/usr/bin:/bin','MARKER':str(marker)}
            r=subprocess.run(['/bin/bash',str(ROOT/'system_files/usr/bin/moai-do'),'--confirmed','setup-waydroid'],
                             env=env,capture_output=True,text=True,timeout=10)
            self.assertNotEqual(r.returncode,0,r.stdout+r.stderr)
            self.assertIn('Could not verify Android app support',r.stderr)
            self.assertFalse(marker.exists(),'setup must not mutate on an unsuccessful status response')

if __name__=='__main__': unittest.main(verbosity=2)
