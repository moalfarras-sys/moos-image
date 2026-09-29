"""visual_tier: how much Mira moves, read from MoOS's own answers and nothing else.

Every case builds a private home and hands the module its environment, so nothing here reads the
owner's kdeglobals, visual-tier state or session variables, and nothing runs a system tool.

The one process started here is Mira's own face, drawn offscreen on Qt Quick's software scene
graph (StillFaceIsDrawn): `still` is only an honest answer if the still face is really there. The
same probe is the image gate: `python3 test_visual_tier.py --face-probe APP_DIR` runs it against a
staged tree (Containerfile.arm's mira-build stage) or the image's /usr/lib/mira/app (build-arm.sh).
"""
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import visual_tier as vt

ROOT = Path(__file__).resolve().parent
TOOL = ROOT.parent / 'system_files/usr/bin/moos-visual-tier'

# The record moos-visual-tier --apply left on the station on 2026-09-29 (read-only), verbatim
# apart from the budget block.
STATION_STATE = {
    'tier': 'flagship', 'changed': 0,
    'skipped': ['kwinrc/Effect-blur/BlurStrength', 'kdeglobals/KDE/AnimationDurationFactor', 'motion'],
    'motion': 'alive', 'motion_written': 'alive',
    'written': {'kwinrc/Plugins/blurEnabled': 'true', 'kdeglobals/KDE/AnimationDurationFactor': '1'},
    'budget': {'file_indexing': 'content', 'update_concurrency': 4, 'ai_default': 'cloud',
               'remote_encode': '1920x1080@60'},
}


class Home:
    """A throwaway account: ~/.config, ~/.local/state and one system config dir."""

    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name)
        self.system = self.path / 'etc-xdg'
        self.defaults = self.path / '.config/kdedefaults'
        for folder in (self.path / '.config', self.path / '.local/state', self.system, self.defaults):
            folder.mkdir(parents=True, exist_ok=True)
        self.env = {'HOME': str(self.path),
                    'XDG_CONFIG_DIRS': f'{self.defaults}:{self.system}'}

    def close(self):
        self._tmp.cleanup()

    def kdeglobals(self, text, where=None):
        (where or self.path / '.config').joinpath('kdeglobals').write_text(text, encoding='utf-8')

    def state(self, data):
        text = data if isinstance(data, str) else json.dumps(data)
        (self.path / '.local/state/moos-visual-tier.json').write_text(text, encoding='utf-8')

    def pin(self, tier):
        (self.path / '.config/moos-visual-tier').write_text(tier + '\n', encoding='utf-8')

    def policy(self, **extra):
        return vt.policy({**self.env, **extra}, self.path)


class VisualTierTest(unittest.TestCase):
    def setUp(self):
        self.home = Home()
        self.addCleanup(self.home.close)

    # ── what MoOS recorded ─────────────────────────────────────────
    def test_nothing_known_means_full_motion_at_designed_speed(self):
        p = self.home.policy()
        self.assertEqual((p.level, p.reason, p.tier, p.factor, p.scale), ('full', 'default', '', None, 1.0))
        self.assertFalse(p.still)
        self.assertFalse(p.owner_off)

    def test_the_station_record_is_flagship(self):
        self.home.state(STATION_STATE)
        self.home.kdeglobals('[General]\nColorScheme=MoOSUI2Dark\n\n[KDE]\nAnimationDurationFactor=0.75\n')
        p = self.home.policy()
        self.assertEqual((p.level, p.reason, p.tier), ('full', 'tier', 'flagship'))
        self.assertEqual(p.scale, 0.75, "the owner's own speed wins over the tier's default")

    def test_each_tier_maps_to_a_level(self):
        for tier, level, scale in (('essential', 'still', 0.4), ('balanced', 'reduced', 0.85),
                                   ('flagship', 'full', 1.0)):
            with self.subTest(tier=tier):
                self.home.state({'tier': tier})
                p = self.home.policy()
                self.assertEqual((p.level, p.reason, p.tier, p.scale), (level, 'tier', tier, scale))
                self.assertEqual(p.still, tier == 'essential')

    def test_a_record_without_a_tier_still_names_its_motion(self):
        self.home.state({'motion': 'still'})
        self.assertEqual(self.home.policy().tier, 'essential')
        self.home.state({'motion': 'gentle'})
        self.assertEqual(self.home.policy().level, 'reduced')

    def test_malformed_records_say_nothing(self):
        for text in ('{not json', '[]', '"flagship"', json.dumps({'tier': 'turbo'}), ''):
            with self.subTest(text=text):
                self.home.state(text)
                self.assertEqual(self.home.policy().reason, 'default')

    def test_the_tools_own_state_home_is_honoured(self):
        other = self.home.path / 'elsewhere'
        other.mkdir()
        (other / 'moos-visual-tier.json').write_text(json.dumps({'tier': 'essential'}))
        self.home.state({'tier': 'flagship'})
        self.assertEqual(self.home.policy(MOOS_TIER_STATE_HOME=str(other)).tier, 'essential')
        self.assertEqual(self.home.policy(XDG_STATE_HOME=str(other)).tier, 'essential')
        self.assertEqual(self.home.policy(XDG_STATE_HOME='relative/ignored').tier, 'flagship',
                         'a relative XDG path is invalid and must be ignored')

    # ── what the owner said ────────────────────────────────────────
    def test_animations_off_beats_everything(self):
        self.home.state({'tier': 'flagship'})
        self.home.pin('flagship')
        self.home.kdeglobals('[KDE]\nAnimationDurationFactor=0\n')
        p = self.home.policy()
        self.assertEqual((p.level, p.reason, p.scale), ('off', 'off', 0.0))
        self.assertTrue(p.owner_off and p.still)

    def test_a_pin_beats_the_record_and_the_renderer(self):
        self.home.state({'tier': 'flagship'})
        self.home.pin('essential')
        p = self.home.policy()
        self.assertEqual((p.level, p.reason, p.tier, p.pinned), ('still', 'pinned', 'essential', True))
        self.home.pin('flagship')
        p = self.home.policy(LIBGL_ALWAYS_SOFTWARE='1')
        self.assertEqual((p.level, p.reason, p.software), ('full', 'pinned', True),
                         'an owner who pinned flagship on a software machine chose the cost')

    def test_an_unknown_pin_is_ignored(self):
        self.home.state({'tier': 'balanced'})
        self.home.pin('auto')
        self.assertEqual(self.home.policy().reason, 'tier')
        self.home.pin('turbo')
        self.assertFalse(self.home.policy().pinned)

    def test_the_pin_follows_the_tools_config_home(self):
        other = self.home.path / 'tier-config'
        other.mkdir()
        (other / 'moos-visual-tier').write_text('essential\n')
        self.assertEqual(self.home.policy(MOOS_TIER_CONFIG_HOME=str(other)).level, 'still')

    # ── how Mira is drawn ──────────────────────────────────────────
    def test_a_software_renderer_keeps_her_still(self):
        self.home.state({'tier': 'flagship'})
        for extra in ({'LIBGL_ALWAYS_SOFTWARE': '1'}, {'LIBGL_ALWAYS_SOFTWARE': 'true'},
                      {'GALLIUM_DRIVER': 'llvmpipe'}, {'GALLIUM_DRIVER': 'softpipe'}):
            with self.subTest(env=extra):
                p = self.home.policy(**extra)
                self.assertEqual((p.level, p.reason, p.software), ('still', 'software-renderer', True))
                self.assertEqual(p.tier, 'flagship')

    def test_the_software_scene_graph_keeps_her_still_whatever_the_pin(self):
        # Her face, aura and nebula are ShaderEffects, which that scene graph never draws:
        # a loop there animates nothing and costs a core (measured 22 s of CPU in 20 s).
        self.home.state({'tier': 'flagship'})
        self.home.pin('flagship')
        for extra in ({'QT_QUICK_BACKEND': 'software'}, {'QT_QUICK_BACKEND': 'softwarecontext'},
                      {'QT_QUICK_BACKEND': ' Software '}, {'MIRA_STILL': '1'}):
            with self.subTest(env=extra):
                p = self.home.policy(**extra)
                self.assertEqual((p.level, p.reason, p.software, p.pinned),
                                 ('still', 'software-scene-graph', True, True))
                self.assertTrue(vt.software_scene_graph({**self.home.env, **extra}))

    def test_the_arm_session_environment_is_a_software_renderer(self):
        # /etc/environment.d/60-moos-arm-llvmpipe.conf, as build-arm.sh writes it.
        arm = {'LIBGL_ALWAYS_SOFTWARE': '1', 'GALLIUM_DRIVER': 'llvmpipe', 'LP_NUM_THREADS': '2',
               'QT_QUICK_BACKEND': 'software'}
        self.home.state({'tier': 'essential'})
        self.assertTrue(self.home.policy(**arm).still)

    def test_hardware_rendering_is_not_mistaken_for_software(self):
        self.home.state({'tier': 'flagship'})
        for extra in ({'LIBGL_ALWAYS_SOFTWARE': '0'}, {'LIBGL_ALWAYS_SOFTWARE': 'false'},
                      {'QT_QUICK_BACKEND': 'rhi'}, {'GALLIUM_DRIVER': 'radeonsi'},
                      {'MIRA_STILL': '0'}, {'MIRA_STILL': ''}):
            with self.subTest(env=extra):
                self.assertEqual(self.home.policy(**extra).level, 'full')

    # ── the owner's one speed control, through KConfig's cascade ───
    def test_factor_is_read_through_the_xdg_cascade(self):
        self.home.kdeglobals('[KDE]\nAnimationDurationFactor=0.5\n', self.home.defaults)
        self.assertEqual(vt.animation_factor(self.home.env, self.home.path), 0.5)
        self.home.kdeglobals('[KDE]\nAnimationDurationFactor=2\n', self.home.system)
        self.assertEqual(vt.animation_factor(self.home.env, self.home.path), 0.5,
                         'kdedefaults comes before /etc/xdg')
        self.home.kdeglobals('[KDE]\nSingleClick=false\nAnimationDurationFactor=1.25\n')
        self.assertEqual(vt.animation_factor(self.home.env, self.home.path), 1.25,
                         "the owner's own file wins")

    def test_an_immutable_system_entry_wins(self):
        self.home.kdeglobals('[KDE]\nAnimationDurationFactor[$i]=0\n', self.home.system)
        self.home.kdeglobals('[KDE]\nAnimationDurationFactor=1\n')
        self.assertEqual(self.home.policy().level, 'off')
        self.home.kdeglobals('[KDE][$i]\nAnimationDurationFactor=0.3\n', self.home.system)
        self.assertEqual(vt.animation_factor(self.home.env, self.home.path), 0.3)
        self.home.kdeglobals('[$i]\n[KDE]\nAnimationDurationFactor=0.2\n', self.home.system)
        self.assertEqual(vt.animation_factor(self.home.env, self.home.path), 0.2)

    def test_a_locked_group_ignores_higher_files_even_without_the_key(self):
        # KConfig's kiosk rule: [KDE][$i] in /etc/xdg freezes [KDE] as that file leaves it, so the
        # owner's own factor is ignored although the locking file never names it.
        self.home.kdeglobals('[KDE][$i]\nSingleClick=false\n', self.home.system)
        self.home.kdeglobals('[KDE]\nAnimationDurationFactor=0\n')
        self.assertIsNone(vt.animation_factor(self.home.env, self.home.path))
        self.assertEqual(self.home.policy().level, 'full')
        # ...keeping what a lower file had already said
        self.home.kdeglobals('[KDE][$i]\n', self.home.defaults)
        self.home.kdeglobals('[KDE]\nAnimationDurationFactor=0.7\n', self.home.system)
        self.assertEqual(vt.animation_factor(self.home.env, self.home.path), 0.7,
                         'kdedefaults locks [KDE] after /etc/xdg set it; the owner cannot change it')

    def test_a_locked_file_locks_only_the_groups_it_has(self):
        self.home.kdeglobals('[$i]\n[General]\nColorScheme=MoOSUI2Dark\n', self.home.system)
        self.home.kdeglobals('[KDE]\nAnimationDurationFactor=0\n')
        self.assertEqual(vt.animation_factor(self.home.env, self.home.path), 0.0,
                         'a file-level lock without a [KDE] group leaves [KDE] to the owner')
        self.home.kdeglobals('[$i]\n[KDE]\nSingleClick=true\n', self.home.system)
        self.assertIsNone(vt.animation_factor(self.home.env, self.home.path))

    def test_only_the_kde_group_and_the_plain_key_count(self):
        self.home.kdeglobals('[General]\nAnimationDurationFactor=0\n[KDE][Nested]\nAnimationDurationFactor=0\n'
                             '[KDE]\nAnimationDurationFactor[ar]=0\n# AnimationDurationFactor=0\n'
                             'AnimationDurationFactorX=0\n')
        self.assertIsNone(vt.animation_factor(self.home.env, self.home.path))
        self.assertEqual(self.home.policy().level, 'full')

    def test_nonsense_factors_are_ignored(self):
        for value in ('abc', '-1', 'nan', 'inf', ''):
            with self.subTest(value=value):
                self.home.kdeglobals(f'[KDE]\nAnimationDurationFactor={value}\n')
                self.assertIsNone(vt.animation_factor(self.home.env, self.home.path))

    def test_speed_is_clamped(self):
        self.home.kdeglobals('[KDE]\nAnimationDurationFactor=0.001\n')
        self.assertEqual(self.home.policy().scale, 0.05)
        self.home.kdeglobals('[KDE]\nAnimationDurationFactor=40\n')
        self.assertEqual(self.home.policy().scale, 8.0)

    def test_default_xdg_config_dirs_is_etc_xdg(self):
        env = {'HOME': str(self.home.path)}
        with mock.patch.object(vt, '_read', wraps=vt._read) as reader:
            vt.animation_factor(env, self.home.path)
        read = [str(call.args[0]) for call in reader.call_args_list]
        self.assertEqual(read, [str(Path('/etc/xdg/kdeglobals')), str(self.home.path / '.config/kdeglobals')])

    # ── robustness and honesty ─────────────────────────────────────
    def test_a_missing_home_says_nothing_and_never_raises(self):
        ghost = self.home.path / 'does-not-exist'
        p = vt.policy({'HOME': str(ghost)}, ghost)
        self.assertEqual(p.reason, 'default')

    def test_a_reader_bug_cannot_stop_mira_from_opening(self):
        with mock.patch.object(vt, 'animation_factor', side_effect=RuntimeError('boom')):
            self.assertEqual(self.home.policy().level, 'full')

    def test_no_process_is_ever_started(self):
        self.home.state({'tier': 'essential'})
        with mock.patch('subprocess.Popen', side_effect=AssertionError('probed')), \
                mock.patch('os.system', side_effect=AssertionError('probed')):
            self.assertTrue(self.home.policy().still)

    def test_it_uses_the_real_environment_by_default(self):
        with mock.patch.dict('os.environ', {'QT_QUICK_BACKEND': 'software', 'HOME': str(self.home.path),
                                            'XDG_CONFIG_HOME': str(self.home.path / '.config'),
                                            'XDG_STATE_HOME': str(self.home.path / '.local/state')},
                             clear=True):
            self.assertTrue(vt.still())
            self.assertTrue(vt.software_renderer())

    def test_explanations_are_bilingual_and_name_only_moos(self):
        cases = []
        self.home.kdeglobals('[KDE]\nAnimationDurationFactor=0\n')
        cases.append(self.home.policy())
        self.home.kdeglobals('[KDE]\nAnimationDurationFactor=1\n')
        self.home.pin('essential')
        cases.append(self.home.policy())
        (self.home.path / '.config/moos-visual-tier').unlink()
        cases.append(self.home.policy(LIBGL_ALWAYS_SOFTWARE='1'))
        for tier in vt.TIERS:
            self.home.state({'tier': tier})
            cases.append(self.home.policy())
        (self.home.path / '.local/state/moos-visual-tier.json').unlink()
        cases.append(self.home.policy())
        cases.append(self.home.policy(MIRA_STILL='1'))
        self.assertEqual({p.reason for p in cases},
                         {'off', 'pinned', 'software-scene-graph', 'software-renderer', 'tier', 'default'})
        for p in cases:
            ar, en = p.explain('ar'), p.explain('en')
            self.assertRegex(ar, '[؀-ۿ]')
            self.assertNotRegex(en, '[؀-ۿ]')
            self.assertNotIn('{', ar + en)
            for word in ('Fedora', 'Red Hat', 'fedora'):
                self.assertNotIn(word, ar + en)
        self.assertIn('أساسية', cases[1].explain('ar'))
        self.assertIn('essential', cases[1].explain('en'))

    def test_as_dict_carries_the_derived_answers(self):
        self.home.state({'tier': 'balanced'})
        data = self.home.policy().as_dict()
        self.assertEqual({k: data[k] for k in ('level', 'tier', 'still', 'owner_off', 'scale')},
                         {'level': 'reduced', 'tier': 'balanced', 'still': False, 'owner_off': False,
                          'scale': 0.85})
        json.dumps(data)


# ── the still face ─────────────────────────────────────────────────────
# Run in a child process, so the backend is chosen before Qt starts and nothing leaks into the
# suites that share this interpreter. It lays MiraCore (the stage) and Avatar (top bar, nav rail,
# Settings) on a plain window of the portal's own background colour and reads the pixels back.
FACE_BG = (7, 6, 17)
FACE_PROBE = r'''
import json, math, sys
from pathlib import Path
app_dir, out, hide = Path(sys.argv[1]), sys.argv[2], sys.argv[3] == "hide"
sys.path.insert(0, str(app_dir))
from PySide6.QtCore import Property, QObject, QTimer, QUrl
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QSGRendererInterface

class Stub(QObject):                    # the two words the components may read from the controller
    def _style(self): return "rose"
    def _phase(self): return "idle"
    faceStyle = Property(str, _style, constant=True)
    phase = Property(str, _phase, constant=True)

app = QGuiApplication(sys.argv[:1])
from faces import FaceProvider
engine = QQmlEngine()
engine.addImageProvider("mira", FaceProvider())
engine.addImportPath(str(app_dir / "qml"))
stub = Stub()
engine.rootContext().setContextProperty("mira", stub)
qml = """
import QtQuick
import QtQuick.Window
import Mira
Window {
    width: 600; height: 420; visible: true; color: "#070611"
    MiraCore { x: 0; y: 10; width: 400; height: 400; motion: false; faceStyle: "rose"; phase: "idle"; visible: SHOWN }
    Avatar { x: 440; y: 150; width: 120; height: 120; style: "rose"; visible: SHOWN }
}
""".replace("SHOWN", "false" if hide else "true")
component = QQmlComponent(engine)
component.setData(qml.encode(), QUrl.fromLocalFile(str(app_dir / "qml" / "face-probe.qml")))
window = component.create()
if window is None:
    print(json.dumps({"error": " | ".join(e.toString() for e in component.errors())}))
    sys.exit(3)

def region(image, cx, cy, half, step=3):
    bg = QColor(7, 6, 17)
    lum, differs = [], 0
    for y in range(cy - half, cy + half + 1, step):
        for x in range(cx - half, cx + half + 1, step):
            c = image.pixelColor(x, y)
            lum.append(0.2126 * c.red() + 0.7152 * c.green() + 0.0722 * c.blue())
            if max(abs(c.red() - bg.red()), abs(c.green() - bg.green()), abs(c.blue() - bg.blue())) > 40:
                differs += 1
    mean = sum(lum) / len(lum)
    spread = math.sqrt(sum((v - mean) ** 2 for v in lum) / len(lum))
    return {"drawn": round(differs / len(lum), 3), "spread": round(spread, 1)}

def ring(image, cx, cy, radius):
    bg, lit = QColor(7, 6, 17), 0
    for step in range(72):
        a = step * math.pi / 36
        c = image.pixelColor(round(cx + radius * math.cos(a)), round(cy + radius * math.sin(a)))
        lit += max(abs(c.red() - bg.red()), abs(c.green() - bg.green()), abs(c.blue() - bg.blue())) > 40
    return round(lit / 72, 3)

def grab():
    api = window.rendererInterface().graphicsApi()
    image = window.grabWindow()
    image.save(out)
    portal = round(400 * 0.66)
    print(json.dumps({
        "software": api == QSGRendererInterface.GraphicsApi.Software,
        "face": region(image, 200, 210, round(portal * 0.26)),
        "ring": ring(image, 200, 210, round(portal * 0.47)),
        "avatar": region(image, 500, 210, 30, 2),
    }), flush=True)
    app.quit()

QTimer.singleShot(1500, grab)
app.exec()
'''


def face_probe(app_dir, save=None, hide=False):
    """Draw MiraCore and Avatar from APP_DIR on the software scene graph; return what is there."""
    with tempfile.TemporaryDirectory() as home:
        out = save or str(Path(home) / 'face-probe.png')
        env = {key: value for key, value in os.environ.items()
               if key not in ('QT_QUICK_BACKEND', 'QSG_RHI_BACKEND', 'MIRA_STILL', 'WAYLAND_DISPLAY',
                              'DISPLAY', 'DBUS_SESSION_BUS_ADDRESS', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME')}
        env.update(HOME=home, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software',
                   PYTHONDONTWRITEBYTECODE='1', QT_FORCE_STDERR_LOGGING='1')
        run = subprocess.run([sys.executable, '-s', '-c', FACE_PROBE, str(app_dir), out,
                              'hide' if hide else 'show'],
                             env=env, cwd=home, capture_output=True, text=True, timeout=180)
    lines = [line for line in run.stdout.splitlines() if line.startswith('{')]
    result = json.loads(lines[-1]) if lines else {'error': 'no result'}
    result['log'] = (run.stdout + run.stderr).strip()
    result['returncode'] = run.returncode
    return result


def face_verdict(result):
    """'' when the still face is on screen, else why not (the words a failed gate prints)."""
    if 'error' in result:
        return f"the face probe did not run: {result['error']}\n{result.get('log', '')}"
    if not result.get('software'):
        return 'the probe did not draw on the software scene graph, so it proved nothing'
    face, avatar = result['face'], result['avatar']
    if face['drawn'] < 0.6 or face['spread'] < 10:
        return f'her face portal is empty on the software scene graph (drawn {face["drawn"]}, spread {face["spread"]})'
    if result['ring'] < 0.8:
        return f'the portal ring is missing on the software scene graph (lit {result["ring"]})'
    if avatar['drawn'] < 0.6 or avatar['spread'] < 10:
        return f'her avatar is a hollow circle on the software scene graph (drawn {avatar["drawn"]}, spread {avatar["spread"]})'
    return ''


class StillFaceIsDrawn(unittest.TestCase):
    """Where she is still (Qt's software scene graph: every ARM session, any machine without a real
    GPU), she is still HERE: the face portal, its ring and the avatar all carry her face."""

    def test_the_software_scene_graph_draws_her_face_ring_and_avatar(self):
        result = face_probe(ROOT)
        self.assertEqual(face_verdict(result), '', result.get('log', ''))

    def test_the_probe_sees_an_empty_portal(self):
        # The same probe with both components hidden: it must call the stage empty, or it could
        # never fail (the way a blank ShaderEffect once passed a PNG-is-not-empty gate).
        result = face_probe(ROOT, hide=True)
        self.assertTrue(result.get('software'), result.get('log', ''))
        self.assertIn('empty', face_verdict(result))


@unittest.skipUnless(TOOL.is_file(), 'moos-visual-tier is not in this tree (the image build stage copies only Mira)')
class AgreesWithMoosVisualTier(unittest.TestCase):
    """Mira's reading of the tool's files must stay the tool's own contract."""

    @classmethod
    def setUpClass(cls):
        loader = importlib.machinery.SourceFileLoader('moos_visual_tier_under_test', str(TOOL))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        cls.tool = importlib.util.module_from_spec(spec)
        before = sys.dont_write_bytecode
        sys.dont_write_bytecode = True      # never leave a __pycache__ inside system_files
        try:
            loader.exec_module(cls.tool)
        finally:
            sys.dont_write_bytecode = before

    def test_the_tiers_and_their_speeds_match(self):
        self.assertEqual(tuple(self.tool.TIERS), vt.TIERS)
        for tier, profile in self.tool.PROFILES.items():
            with self.subTest(tier=tier):
                self.assertEqual(float(profile['kdeglobals']['KDE/AnimationDurationFactor']), vt.TIER_FACTOR[tier])
                self.assertEqual(vt.MOTION_TIER[profile['motion']], tier)

    def test_the_state_and_pin_paths_match(self):
        with tempfile.TemporaryDirectory() as folder:
            env = {'MOOS_TIER_STATE_HOME': folder + '/state', 'MOOS_TIER_CONFIG_HOME': folder + '/config'}
            with mock.patch.dict('os.environ', env):
                state, pin = self.tool.state_path(), self.tool.override_path()
            self.assertEqual(state, Path(folder) / 'state' / vt.STATE_FILE)
            self.assertEqual(pin, Path(folder) / 'config' / vt.PIN_FILE)
            state.parent.mkdir()
            pin.parent.mkdir()
            record = {'tier': 'essential', 'motion': self.tool.PROFILES['essential']['motion']}
            state.write_text(json.dumps(record))
            pin.write_text('balanced\n')
            self.assertEqual(vt.recorded_tier(env, Path(folder)), 'essential')
            self.assertEqual(vt.pinned_tier(env, Path(folder)), 'balanced')


def _face_gate(app_dir, save=None):
    result = face_probe(Path(app_dir), save)
    verdict = face_verdict(result)
    if verdict:
        print(f'GATE FAIL: {verdict} ({app_dir})', file=sys.stderr)
        print(result.get('log', ''), file=sys.stderr)
        return 1
    print(f"Mira's still face is drawn ({app_dir}): face {result['face']}, ring {result['ring']}, "
          f"avatar {result['avatar']}")
    return 0


if __name__ == '__main__':
    if len(sys.argv) >= 3 and sys.argv[1] == '--face-probe':
        sys.exit(_face_gate(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None))
    unittest.main()
