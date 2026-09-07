#!/usr/bin/env python3
"""Containment-scoped desktop actions and preview launch boundary."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
QML = ROOT / 'system_files/usr/share/plasma/shells/org.kde.plasma.desktop/contents/explorer/WidgetExplorer.qml'
LAUNCHER = ROOT / 'system_files/usr/bin/moos-desktop-edit'
EDIT_MODE = ROOT / 'system_files/usr/share/plasma/shells/org.kde.plasma.desktop/contents/views/DesktopEditMode.qml'


class DesktopCustomize(unittest.TestCase):
    def test_native_owners_and_no_implicit_placement(self):
        source = QML.read_text()
        self.assertIn('Shell.WidgetExplorer', source)
        self.assertIn('model: catalog.widgetsModel', source)
        self.assertIn('containment = root.containment.plasmoid', source)
        self.assertEqual(source.count('catalog.addApplet('), 1)
        self.assertRegex(source, r'onClicked: \{\s+const before = main.applets.length\s+catalog.addApplet')
        self.assertNotIn('widgetExplorer.removeAllInstances(', source)
        for forbidden in ['writeConfig(', '.destroy(', 'addWidget(', 'evaluateScript', 'XMLHttpRequest', 'plasma-org.kde.plasma.desktop-appletsrc']:
            self.assertNotIn(forbidden, source)
        self.assertIn('text/x-plasmoidservicename', source)
        self.assertIn('MoUI.Locale.rtl', source)
        self.assertIn('MoUI.Card', source)
        self.assertIn('visual?.errorInformation', source)
        self.assertIn('model.isSupported', source)
        self.assertIn('Image.Ready', source)

    def test_source_actions_scope_confirmation_and_stale_objects(self):
        node = shutil.which('node')
        self.assertIsNotNone(node, 'Node is required to execute the shipped action functions')
        functions = '\n'.join(re.findall(r'    function .*?\n    }', QML.read_text(), re.S))
        program = '''
const assert = require('node:assert/strict');
let applets=[], pendingRemoval=[], message='', selected=null, editable=true, desktopTarget=true;
let shown=0, removed=[], confirmed=0;
const confirmation={open(){shown++}};
const local=(ar,en)=>en;
const make=(id,enabled=true)=>({id,internalAction(name){return {enabled,trigger(){removed.push(id)}}}});
''' + functions.replace('    function local(ar, en) { return MoUI.Locale.local(ar, en) }', '') + '''
const a=make(1), b=make(2), otherDesktop=make(3), locked=make(4,false);
applets=[a,b,locked];
removeWidgets([a,otherDesktop,locked]);
assert.equal(shown,1); assert.deepEqual(pendingRemoval,[a]); assert.deepEqual(removed,[]);
// Cancel must not remove. The popup close handler clears this snapshot.
pendingRemoval=[]; assert.deepEqual(removed,[]);
removeWidgets([a,b]); applets=[b]; confirmRemoval();
assert.deepEqual(removed,[2]); assert.deepEqual(pendingRemoval,[]);
assert.ok(message.includes('Undo'));
assert.ok(retired('org.moos.heroclock')); assert.ok(!retired('org.kde.plasma.systemmonitor.memory'));
selectWidget({pluginName:'org.moos.heroclock',name:'Clock',isSupported:true});
assert.equal(selected.supported,false);
selectWidget({pluginName:'org.test.old',name:'Old',isSupported:false,unsupportedMessage:'Requires another API'});
assert.equal(selected.supported,false); assert.equal(selected.reason,'Requires another API');
console.log('Containment action behavior passed');
'''
        result = subprocess.run([node, '-e', program], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_preview_refuses_paths_options_shell_text_and_missing_packages(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder); log=base/'calls'
            for name, body in {
                'kdialog':'exit 0',
                'kpackagetool6':'printf "package:%s\\n" "$*" >> "$CALL_LOG"\n[ "${MISSING:-0}" = 0 ]',
                'plasmawindowed':'printf "preview:%s\\n" "$*" >> "$CALL_LOG"',
                'gdbus':'printf "explorer\\n" >> "$CALL_LOG"',
            }.items():
                p=base/name; p.write_text('#!/bin/sh\n'+body+'\n'); p.chmod(0o755)
            env=dict(os.environ, PATH=folder+':/usr/bin:/bin', CALL_LOG=str(log))
            for value in ['', '../org.widget', '/tmp/evil', '--help', 'x.y;touch /tmp/oops', 'x.y$(id)', 'x.y%2Fz', 'x.'+'a'*256]:
                result=subprocess.run(['bash',str(LAUNCHER),'--preview',value],env=env,capture_output=True)
                self.assertNotEqual(result.returncode,0,value)
                self.assertFalse(log.exists(), value)
            result=subprocess.run(['bash',str(LAUNCHER),'--preview','org.test.widget'],env=dict(env,MISSING='1'),capture_output=True)
            self.assertNotEqual(result.returncode,0)
            self.assertNotIn('preview:',log.read_text()); log.unlink()
            subprocess.run(['bash',str(LAUNCHER),'--preview','org.test.widget'],env=env,check=True)
            self.assertEqual(log.read_text().splitlines(), ['package:--type Plasma/Applet --show org.test.widget','preview:org.test.widget'])
            self.assertNotIn('explorer',log.read_text()); log.unlink()
            subprocess.run(['bash',str(LAUNCHER)],env=env,check=True)
            self.assertEqual(log.read_text(),'explorer\n')

    def test_edit_mode_draws_the_desktop_under_software_rendering(self):
        """Arrange must show the real desktop on every GPU-less MoOS edition.

        Plasma's edit-mode backdrop is built from two MultiEffect blocks that
        blur `containment`. MultiEffect is a shader effect: on the Qt Quick
        *software* backend it renders NOTHING. That backend is what the Oracle
        A1 (moos-arm) and moos-cloud actually run -- no GPU -- so upstream's
        Arrange screen painted a black rectangle where the desktop should be,
        and the widgets the user was trying to arrange were invisible. It looked
        exactly like a crashed shell.

        The overlay keeps both effects for GPU sessions and, when the backend is
        software, hides them and lifts the real interactive containment above the
        backdrop instead -- the user arranges the actual desktop.

        This gate exists because NOTHING else can see it. The QML is a verbatim
        overlay of an upstream shell file; the next person to re-sync it from
        plasma-workspace would drop these three edits, every other gate would
        stay green, and Arrange would go black again on the maintainer's own
        machine. Do not delete this gate to make an upstream re-sync pass --
        re-apply the guard.
        """
        source = EDIT_MODE.read_text()

        self.assertIn(
            'readonly property bool softwareRendering: GraphicsInfo.api === GraphicsInfo.Software',
            source,
            'the software-backend probe is the whole basis of the fix')

        effects = source.count('MultiEffect {')
        self.assertEqual(effects, 2, 'upstream ships exactly two edit-mode MultiEffect blocks')
        guarded = len(re.findall(r'MultiEffect \{\n\s*visible: !editModeItem\.softwareRendering\n', source))
        self.assertEqual(
            guarded, effects,
            'every MultiEffect must be hidden on the software backend; an unguarded '
            'one paints an opaque black backdrop over the desktop')

        # Without the z-lift the containment stays *behind* the backdrop, so
        # hiding the effects alone would leave Arrange empty rather than black.
        self.assertRegex(
            source,
            r'Binding \{\s*target: containmentParent\s*property: "z"\s*value: 1\s*'
            r'when: editModeItem\.softwareRendering && editModeItem\.open',
            'the real containment must be raised above the backdrop in software mode')
        # Restoring the binding matters: a GPU session must get its z back.
        self.assertIn('restoreMode: Binding.RestoreBindingOrValue', source)

    def test_shell_overlay_keeps_plasma_the_owner(self):
        """The overlay may not fork Plasma's state, only its presentation.

        `COPY system_files/ /` drops these two files on top of plasma-workspace's
        own shell package. That is the supported way to restyle the shell, but it
        means any state this QML writes itself would be a second, competing
        source of truth for the desktop layout -- and the loser would be
        plasma-org.kde.plasma.desktop-appletsrc, the file that decides whether the
        user's desktop comes back after a reboot.
        """
        for path in (EDIT_MODE, QML):
            source = path.read_text()
            for forbidden in ('appletsrc', 'KConfig', 'writeConfig(',
                              'Qt.createQmlObject', 'import QtQuick.Process'):
                self.assertNotIn(forbidden, source, f'{path.name} must not own shell state')

    def test_fixed_graphical_routes_and_reset_contract(self):
        source=QML.read_text(); router=(ROOT/'system_files/usr/bin/moos-open').read_text()
        self.assertIn('settings/desktop)           gui moos-desktop-edit',router)
        self.assertIn('desktop/preview/*)',router)
        self.assertIn('gui moos-desktop-edit --preview "$id"',router)
        self.assertIn('moos://settings/themes',source)
        self.assertIn('main.removeWidgets(main.applets)',source)
        self.assertIn('onClosed: main.pendingRemoval = []',source)
        self.assertIn('main.confirmRemoval(); confirmation.close()',source)
        self.assertIn('main.desktopTarget',source)
        self.assertIn('exec plasmawindowed "$id"',LAUNCHER.read_text())
        self.assertNotIn('term ',LAUNCHER.read_text())


if __name__ == '__main__': unittest.main()
