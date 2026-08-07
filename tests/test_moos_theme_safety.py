#!/usr/bin/env python3
"""Behavioural/static safety gate for MoOS theme transitions."""

from __future__ import annotations

import configparser
import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
APPLY = ROOT / "system_files/usr/bin/moos-apply-theme"
SWITCH = ROOT / "system_files/usr/bin/moos-theme"
PATH_UNIT = ROOT / "system_files/usr/lib/systemd/user/moos-theme-sync.path"
SERVICE_UNIT = ROOT / "system_files/usr/lib/systemd/user/moos-theme-sync.service"
MIGRATE = ROOT / "system_files/usr/bin/moos-ui-migrate"

# The two migration tests below EXECUTE moos-ui-migrate, which rewrites KConfig
# files with the real kwriteconfig6 (KF6). That tool exists on any MoOS/KDE
# machine — so `just check` and the image build both run these for real — but not
# on the bare ubuntu-latest CI repo-gates runner, where the transform would
# silently no-op and the exact-output assertions (Arabic display names, comma
# variant lists) could never match. Skip there instead of failing; the real
# transform stays gated pre-push by `just check` and live on every login.
_HAS_KWRITECONFIG6 = shutil.which("kwriteconfig6") is not None
_KWRITE_REASON = "kwriteconfig6 (KF6 kconfig CLI) not on PATH — migration cannot be executed here"
INPUT_DEFAULTS = ROOT / "system_files/etc/xdg/kcminputrc"
INPUT_MIGRATE_SERVICE = (
    ROOT / "system_files/usr/lib/systemd/user/moos-input-migrate.service"
)
USER_KWIN_DROPIN = (
    ROOT / "system_files/usr/lib/systemd/user/"
    "plasma-kwin_wayland.service.d/10-moos-input-migrate.conf"
)
LOGIN_KWIN_DROPIN = (
    ROOT / "system_files/usr/lib/systemd/user/"
    "plasma-login-kwin_wayland.service.d/10-moos-input-migrate.conf"
)


def bash_executable() -> str:
    """Use real Git Bash on Windows instead of the WSL app-execution alias."""
    override = os.environ.get("MOOS_TEST_BASH")
    if override:
        return override
    if os.name == "nt":
        candidate = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git/bin/bash.exe"
        if candidate.is_file():
            return str(candidate)
    return shutil.which("bash") or "bash"


BASH = bash_executable()


def bash_executable() -> str:
    """Use real Git Bash on Windows instead of the WSL app-execution alias."""
    override = os.environ.get("MOOS_TEST_BASH")
    if override:
        return override
    if os.name == "nt":
        candidate = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git/bin/bash.exe"
        if candidate.is_file():
            return str(candidate)
    return shutil.which("bash") or "bash"


BASH = bash_executable()


def function(text: str, name: str) -> str:
    match = re.search(rf"(?ms)^{re.escape(name)}\(\) \{{.*?^\}}$", text)
    if not match:
        raise AssertionError(f"could not extract {name}()")
    return match.group(0)


class TestMoOSThemeSafety(unittest.TestCase):
    def test_runtime_supplements_follow_konsole_profiles_and_gsettings(self) -> None:
        """A renamed Konsole profile and GTK identity must follow every theme live."""
        switch = SWITCH.read_text(encoding="utf-8")
        loader = function(switch, "load_profile")
        supplements = function(switch, "apply_supplements")
        complete = function(switch, "automatic_supplements_complete")
        profile_root = ROOT / "system_files/usr/share/konsole"

        # Run the real profile selector for every installed MoOS look, but point
        # its read-only system path at this checkout. This catches the exact bug
        # where profile metadata was renamed while 16 hard-coded D-Bus names
        # stayed on the previous generation.
        constant_block = switch[
            switch.index('DARK_LNF="'):switch.index("\nusage()")
        ]
        loader_in_tree = loader.replace(
            "/usr/share/konsole", str(profile_root)
        )
        harness = f"""
set -euo pipefail
{constant_block}
{loader_in_tree}
load_profile "$1"
printf '%s\\t%s\\t%s\\t%s\\n' \
    "$konsole_profile" "$konsole_profile_name" "$style" "$icons"
"""
        lnfs = re.findall(r'^[A-Z_]+_LNF="([^"]+)"', constant_block, re.M)
        self.assertEqual(len(lnfs), 16, "the gate must exercise all MoOS looks")
        for lnf in lnfs:
            with self.subTest(look_and_feel=lnf):
                selected = subprocess.run(
                    [BASH, "-c", harness, "test", lnf],
                    check=True,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                ).stdout.rstrip("\n").split("\t")
                self.assertEqual(len(selected), 4)
                profile_file, selected_name, selected_style, selected_icons = selected
                parser = configparser.ConfigParser(interpolation=None)
                parser.optionxform = str
                self.assertTrue(
                    parser.read(profile_root / profile_file, encoding="utf-8"),
                    f"{lnf}: missing Konsole profile {profile_file}",
                )
                self.assertEqual(
                    selected_name,
                    parser["General"]["Name"],
                    f"{lnf}: D-Bus retint must use the profile's live Name value",
                )
                self.assertEqual(
                    selected_icons,
                    selected_style,
                    f"{lnf}: moos-theme must apply the palette-specific symbolic "
                    "overlay named after its Plasma style",
                )

        self.assertEqual(
            len(re.findall(r"(?m)^\s*konsole_profile_name=", loader)),
            1,
            "derive the Konsole name once from its profile; do not duplicate "
            "user-visible names across 16 case arms",
        )

        # GSettings is the Wayland/Flatpak source. Synchronising only its
        # light/dark bit leaves apps on stale icons, cursor and fonts.
        expected_sets = {
            "color-scheme": '"$([ "$prefer_dark" = true ] && echo prefer-dark || echo prefer-light)"',
            "icon-theme": '"$icons"',
            "cursor-theme": '"$cursor"',
            "font-name": "'IBM Plex Sans 10'",
            "monospace-font-name": "'JetBrains Mono 10'",
        }
        for key, value in expected_sets.items():
            with self.subTest(gsettings_key=key):
                self.assertRegex(
                    supplements,
                    rf"gsettings set org\.gnome\.desktop\.interface {re.escape(key)}\s+"
                    rf"(?:\\\s*)?"
                    rf"{re.escape(value)}",
                )
                self.assertRegex(
                    complete,
                    rf"gsettings get org\.gnome\.desktop\.interface {re.escape(key)}",
                )
        # Plasma's gtkconfig rewrites these GSettings font keys from the KDE font
        # description and renders them DOUBLE-SPACED — measured live on this
        # image: 'IBM Plex Sans  10', 'JetBrains Mono  10'. An exact string
        # compare therefore never matched, so automatic_supplements_complete()
        # could not return true at all: `moos-theme auto` exited 1 with the
        # desktop already correct and every reconcile paid the full ~13s pass.
        self.assertIn('same_font "$font_actual" "IBM Plex Sans 10"', complete)
        self.assertIn(
            'same_font "$monospace_actual" "JetBrains Mono 10"', complete
        )
        self.assertNotRegex(
            complete, r'\[ "\$font_actual" = "IBM Plex Sans 10" \]',
            "font comparison must normalise whitespace, or gtkconfig's double "
            "space makes the completeness check permanently false",
        )

    def test_portal_preferences_keep_kde_session_services(self) -> None:
        """The /etc override must extend the stock KDE map, not erase services."""
        portal = ROOT / "system_files/etc/xdg-desktop-portal/kde-portals.conf"
        parser = configparser.ConfigParser(interpolation=None, strict=True)
        parser.optionxform = str
        self.assertTrue(parser.read(portal, encoding="utf-8"))
        self.assertIn("preferred", parser)
        preferred = dict(parser["preferred"])
        self.assertEqual(
            preferred,
            {
                "default": "kde",
                "org.freedesktop.impl.portal.Settings": "kde;gtk;",
                "org.freedesktop.impl.portal.Notification": "plasmanotify",
                "org.freedesktop.impl.portal.FileChooser": "kde",
            },
        )

    @unittest.skipUnless(_HAS_KWRITECONFIG6, _KWRITE_REASON)
    def test_numlock_default_migrates_before_user_and_greeter_kwin(self) -> None:
        migration = MIGRATE.read_text(encoding="utf-8")
        migrator = function(migration, "migrate_startup_numlock")
        defaults = INPUT_DEFAULTS.read_text(encoding="utf-8")
        service = INPUT_MIGRATE_SERVICE.read_text(encoding="utf-8")
        user_dropin = USER_KWIN_DROPIN.read_text(encoding="utf-8")
        login_dropin = LOGIN_KWIN_DROPIN.read_text(encoding="utf-8")
        build = (ROOT / "build_files/build.sh").read_text(encoding="utf-8")

        self.assertRegex(defaults, r"(?ms)^\[Keyboard\]\s*$.*?^NumLock=0$")
        self.assertIn(
            "ExecStart=/usr/bin/moos-ui-migrate --input-only", service
        )
        self.assertIn(
            "/usr/lib/systemd/user/moos-input-migrate.service", build,
            "the image build must run systemd-analyze over the pre-KWin unit",
        )
        for unit_name, dropin in (
            ("user-session KWin", user_dropin),
            ("Plasma Login Manager KWin", login_dropin),
        ):
            with self.subTest(unit=unit_name):
                self.assertIn("Wants=moos-input-migrate.service", dropin)
                self.assertIn("After=moos-input-migrate.service", dropin)

        input_only = '[ "${1:-}" = "--input-only" ] && exit 0'
        self.assertIn(input_only, migration)
        self.assertLess(
            migration.index(input_only),
            migration.index("# --- GStreamer registry:"),
            "the pre-KWin input-only path must not run the rest of the UI migration",
        )
        for unsafe in (
            "KWIN_FORCE_NUM_LOCK_EVALUATION",
            "ydotool",
            "numlockx",
            "xset",
        ):
            self.assertNotIn(
                unsafe, migrator + service + user_dropin + login_dropin,
                f"NumLock startup must not use persistent/key-injection forcing: {unsafe}",
            )

        def run_profile(
            contents: str | None,
            already_migrated: bool = False,
        ) -> tuple[str | None, bool]:
            import tempfile

            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                config = root / "config"
                state = root / "state/moos"
                logs = state / "migrations"
                config.mkdir()
                logs.mkdir(parents=True)
                profile = config / "kcminputrc"
                if contents is not None:
                    profile.write_text(contents, encoding="utf-8")
                marker = state / "numlock-startup-v1.done"
                if already_migrated:
                    marker.touch()
                harness = f"""
set -euo pipefail
state_dir={shlex.quote(str(state))}
log_dir={shlex.quote(str(logs))}
{migrator}
migrate_startup_numlock
"""
                env = dict(os.environ)
                env["HOME"] = str(root / "home")
                env["XDG_CONFIG_HOME"] = str(config)
                subprocess.run(
                    [BASH, "-c", harness],
                    check=True,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=env,
                )
                migrated = (
                    profile.read_text(encoding="utf-8")
                    if profile.exists()
                    else None
                )
                return migrated, marker.exists()

        fresh_profile, fresh_marked = run_profile(None)
        self.assertIsNone(
            fresh_profile,
            "fresh users should inherit /etc/xdg, not receive a needless local pin",
        )
        self.assertTrue(fresh_marked)
        for legacy_value in ("1", "2"):
            with self.subTest(legacy_value=legacy_value):
                migrated, marked = run_profile(
                    "[Keyboard]\n"
                    f"NumLock={legacy_value}\n"
                    "[Mouse]\n"
                    "cursorTheme=PersonalCursor\n"
                )
                self.assertIn("NumLock=0", migrated)
                self.assertIn("cursorTheme=PersonalCursor", migrated)
                self.assertTrue(marked)

        custom = "[Keyboard]\nNumLock=7\n[Mouse]\ncursorTheme=PersonalCursor\n"
        self.assertEqual(run_profile(custom)[0], custom)
        no_key = "[Mouse]\ncursorTheme=PersonalCursor\n"
        self.assertEqual(run_profile(no_key)[0], no_key)

        # The marker makes this a repair, not a policy daemon: a preference the
        # user chooses after migration remains theirs on every later login.
        post_migration_choice = "[Keyboard]\nNumLock=1\n"
        self.assertEqual(
            run_profile(post_migration_choice, already_migrated=True)[0],
            post_migration_choice,
        )

    @unittest.skipUnless(_HAS_KWRITECONFIG6, _KWRITE_REASON)
    def test_keyboard_migration_is_exact_and_preserves_custom_profiles(self) -> None:
        migration = MIGRATE.read_text(encoding="utf-8")
        migrator = function(migration, "migrate_legacy_keyboard")

        def run_profile(contents: str) -> str:
            with self.subTest(profile=contents):
                import tempfile

                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    config = root / "config"
                    state = root / "state/moos"
                    logs = state / "migrations"
                    config.mkdir()
                    logs.mkdir(parents=True)
                    profile = config / "kxkbrc"
                    profile.write_text(contents, encoding="utf-8")
                    harness = f"""
set -euo pipefail
state_dir={shlex.quote(str(state))}
log_dir={shlex.quote(str(logs))}
gdbus() {{ return 0; }}
{migrator}
migrate_legacy_keyboard
"""
                    env = dict(os.environ)
                    env["HOME"] = str(root / "home")
                    env["XDG_CONFIG_HOME"] = str(config)
                    subprocess.run(
                        [BASH, "-c", harness],
                        check=True,
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        env=env,
                    )
                    return profile.read_text(encoding="utf-8")

        legacy = "[Layout]\nDisplayNames=DE,ع\nLayoutList=de,ara\nVariantList=,\n"
        migrated = run_profile(legacy)
        self.assertIn("LayoutList=de,us,ara", migrated)
        self.assertIn("VariantList=,,", migrated)
        self.assertIn("DisplayNames=DE,,ع", migrated)

        customised = legacy + "Options=grp:alt_shift_toggle\n"
        self.assertEqual(run_profile(customised), customised)

    @unittest.skipUnless(_HAS_KWRITECONFIG6, _KWRITE_REASON)
    def test_wallet_migration_disables_existing_profiles_once(self) -> None:
        migration = MIGRATE.read_text(encoding="utf-8")
        migrator = function(migration, "disable_wallet_v2")

        def run_profile(
            contents: str | None,
            already_migrated: bool = False,
        ) -> tuple[str | None, bool]:
            import tempfile

            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                config = root / "config"
                state = root / "state/moos"
                logs = state / "migrations"
                config.mkdir()
                logs.mkdir(parents=True)
                profile = config / "kwalletrc"
                if contents is not None:
                    profile.write_text(contents, encoding="utf-8")
                marker = state / "wallet-disabled-v2.done"
                if already_migrated:
                    marker.touch()
                harness = f"""
set -euo pipefail
state_dir={shlex.quote(str(state))}
log_dir={shlex.quote(str(logs))}
systemctl() {{ return 0; }}
pkill() {{ return 0; }}
gdbus() {{ return 1; }}
secret-tool() {{ return 1; }}
{migrator}
disable_wallet_v2
"""
                env = dict(os.environ)
                env["HOME"] = str(root / "home")
                env["XDG_CONFIG_HOME"] = str(config)
                subprocess.run(
                    [BASH, "-c", harness],
                    check=True,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=env,
                )
                migrated = (
                    profile.read_text(encoding="utf-8")
                    if profile.exists()
                    else None
                )
                return migrated, marker.exists()

        fresh, fresh_marked = run_profile(None)
        self.assertIn("Enabled=false", fresh)
        self.assertIn("First Use=false", fresh)
        self.assertTrue(fresh_marked)

        legacy = "[Wallet]\nEnabled=false\nFirst Use=false\n"
        migrated, marked = run_profile(legacy)
        self.assertIn("Enabled=false", migrated)
        self.assertIn("First Use=false", migrated)
        self.assertTrue(marked)

        custom_disabled = legacy + "Close When Idle=true\n"
        self.assertIn("Close When Idle=true", run_profile(custom_disabled)[0])
        enabled = "[Wallet]\nEnabled=true\nFirst Use=false\n"
        self.assertIn("Enabled=false", run_profile(enabled)[0])

        # A choice made after the one-time migration remains the user's choice.
        self.assertEqual(
            run_profile(enabled, already_migrated=True)[0],
            enabled,
        )

    def test_any_foreign_look_resolves_to_the_one_moos_look(self) -> None:
        """MoOS now ships a FAMILY of looks on one engine: the Graphite/Tidal base pair plus
        the org.moos.ui2.* members (Nova, Amethyst, Midnight, Aurora). A member the user picked
        is a durable choice and is PRESERVED. Everything that is NOT a current MoOS look — the
        DELETED old generations (org.moos.nova, org.moos.ui, which are a different, top-level
        namespace), Breeze, any foreign theme — must still resolve to the dark half, because
        Plasma does not error on a missing Global Theme, it silently serves Breeze.
        """
        text = APPLY.read_text(encoding="utf-8")
        resolver = function(text, "target_lnf")
        # Point the resolver's on-disk check at the in-tree packages, so the gate
        # tests the ACTUAL installed set of MoOS looks — the single source of truth
        # for "is this a real theme" — instead of a hand-kept list. (This is the
        # gap that let the self-heal quietly reset 10 of 16 looks to Dark.)
        lnf_root = ROOT / "system_files/usr/share/plasma/look-and-feel"
        harness = f"""
set -uo pipefail
DARK_LNF=org.moos.ui2
LIGHT_LNF=org.moos.ui2.light
NOVA_LNF=org.moos.ui2.nova
AMETHYST_LNF=org.moos.ui2.amethyst
MIDNIGHT_LNF=org.moos.ui2.midnight
AURORA_LNF=org.moos.ui2.aurora
LNF_ROOT={shlex.quote(str(lnf_root))}
marker=/definitely/not/present
current_lookandfeel() {{ printf '%s\\n' "$CURRENT"; }}
{resolver}
target_lnf "$1" "$2"
"""
        installed = sorted(p.name for p in lnf_root.glob("org.moos.ui2*") if p.is_dir())
        self.assertGreaterEqual(
            len(installed), 16,
            f"expected all 16 MoOS looks in-tree, found {len(installed)}")
        # EVERY installed MoOS look is a durable choice and must be PRESERVED, at
        # both migration states. This asserts the resolver never silently downgrades
        # gaming/dev/study/daylight/any *-light back to Dark again.
        cases = {}
        for lnf in installed:
            cases[(lnf, "true")] = lnf
            cases[(lnf, "false")] = lnf
        # The DELETED old generations (top-level namespace) and anything not on disk
        # land on the dark half — never on a theme that is no longer installed.
        cases.update({
            ("org.moos.ui", "true"): "org.moos.ui2",
            ("org.moos.ui.light", "true"): "org.moos.ui2",
            ("org.moos.nova", "true"): "org.moos.ui2",
            ("org.kde.breezedark.desktop", "true"): "org.moos.ui2",
            ("org.example.foreign", "true"): "org.moos.ui2",
        })
        for (current, completed), expected in cases.items():
            with self.subTest(current=current, completed=completed):
                result = subprocess.run(
                    [BASH, "-c", harness, "test", current, completed],
                    check=True,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                self.assertEqual(result.stdout.strip(), expected)

        self.assertIn("migration_completed=true", text)
        self.assertIn(
            'target_lnf "$(current_lookandfeel)" "$migration_completed"', text
        )
        # No generation but this one may be a TARGET…
        self.assertNotIn("UI1_DARK_LNF", text)
        self.assertNotIn("UI1_LIGHT_LNF", text)
        # …but the widget-era dashboards must still be REMOVABLE, or a user who has
        # one keeps it forever, drawing on top of the icons, on a desktop whose bento
        # now lives inside the wallpaper scene.
        self.assertIn('"org.moos.nova.deskclock"', text)
        self.assertIn('"org.moos.ui2.dashboard"', text)
        self.assertIn('d.wallpaperPlugin = "org.moos.ui2.wallpaper"', text)
        # Hero Clock is the one allowed desktop applet (THEME_REV 43). The retired
        # bento/deskclock must still never be placed — they fight Folder View icons.
        self.assertIn("seed_heroclock_once", text)
        self.assertIn('addWidget("org.moos.heroclock")', text)
        self.assertIn("moos-heroclock-seeded.v1", text)
        self.assertNotIn('addWidget("org.moos.ui2.dashboard")', text)
        self.assertNotIn('addWidget("org.moos.nova.deskclock")', text)
        add_hits = [
            line for line in text.splitlines()
            if "addWidget(" in line and not line.lstrip().startswith("#")
        ]
        self.assertEqual(
            len(add_hits), 1,
            f"exactly one addWidget site (heroclock); found {add_hits!r}",
        )
        # The icons grow from the RIGHT, opposite the bento's top-left corner of the scene.
        self.assertIn('d.writeConfig("alignment", "1")', text)

    def test_automatic_switch_has_bounded_non_recursive_supplement_sync(self) -> None:
        switch = SWITCH.read_text(encoding="utf-8")
        path = PATH_UNIT.read_text(encoding="utf-8")
        service = SERVICE_UNIT.read_text(encoding="utf-8")
        build = (ROOT / "build_files/build.sh").read_text(encoding="utf-8")

        self.assertIn("PathChanged=%h/.config/kdeglobals", path)
        self.assertIn("WantedBy=plasma-workspace.target", path)
        self.assertIn("PartOf=plasma-workspace.target", path)
        # `reconcile`, not the old `sync-auto`: kdeglobals changes on EVERY Global
        # Theme Apply, not only the sunrise/sunset switch. LookAndFeelManager carries
        # colours and decoration but never the MoOS wallpaper scene, Konsole, GTK or
        # the lock screen, so a GUI pick of e.g. "MoOS Nova" stranded Nova's colours on
        # the OLD wallpaper (measured live). `reconcile` delegates to sync_auto in
        # automatic mode and otherwise applies those missing supplements.
        self.assertIn("ExecStart=/usr/bin/moos-theme reconcile-service", service)
        self.assertIn("reconcile()", switch)
        # It must carry the MANUAL family, not only the two auto halves, or a GUI pick
        # of Nova/Amethyst/Midnight/Aurora still strands the wallpaper.
        reconcile_body = switch.split("reconcile() {", 1)[1].split("\n}\n", 1)[0]
        for fam in ("NOVA_LNF", "AMETHYST_LNF", "MIDNIGHT_LNF", "AURORA_LNF"):
            self.assertIn(fam, reconcile_body)
        self.assertNotRegex(service, r"(?m)^Restart=")
        bounded = function(switch, "reconcile_service")
        self.assertIn("for attempt in 1 2 3", bounded)
        self.assertIn("reconcile && return 0", bounded)
        self.assertIn('[ "$attempt" -eq 3 ] && break', bounded)
        self.assertIn('sleep "$delay"', bounded)
        # The bound that matters is on the RUN (TimeoutStartSec), never on the RATE.
        # A path-triggered unit must not be rate-limited: Plasma rewrites kdeglobals
        # several times in the first seconds of a session, so the old 5-per-60s limit
        # turned an ordinary login into failed(start-limit-hit) — and systemd fails the
        # .path unit along with it, so the watch was dead for the rest of the session
        # and the sunrise/sunset supplements stopped following the theme. Reproduced on
        # the maintainer's machine with eight touches of kdeglobals. Failure retries are
        # bounded INSIDE one service run: rate limiting counts successful path activations
        # too, while Restart=on-failure with the limiter disabled would loop forever.
        self.assertIn("StartLimitIntervalSec=0", service)
        self.assertNotIn("StartLimitBurst", service)
        self.assertIn("TimeoutStartSec=45s", service)
        self.assertIn("systemctl --global enable moos-theme-sync.path", build)
        self.assertIn("systemd-analyze verify", build)

        # `auto` must ARRIVE on UI2, not merely arm the switch. sync_auto refuses to touch a
        # look that is not already a UI2 half (by design — see below), so without a bootstrap
        # the command pins the targets, prints "auto", and leaves a UI1 desktop on UI1 until
        # the next sunrise: success reported for doing nothing. It did exactly that on the
        # maintainer's machine.
        # The branch ends at a ';;' on its own line at the case-arm indent; the ';;' inside
        # the bootstrap's own case statement are deeper and inline, so they do not match.
        auto_branch = switch.split("\n    auto)")[1].split("\n        ;;")[0]
        self.assertIn('apply "$DARK_LNF"', auto_branch)

        # …and it must arm the switch AFTER that bootstrap, never before. plasma-apply-
        # lookandfeel CLEARS AutomaticLookAndFeel — applying a Global Theme by hand is
        # Plasma's own signal that the user took manual control — so arming first arms
        # nothing: the bootstrap disarms it one line later and `auto` leaves the switch OFF
        # while printing success. Measured exactly that way on the maintainer's machine.
        # Ordering is invisible to a "does the file contain X" gate, so assert the order.
        self.assertLess(
            auto_branch.index('apply "$DARK_LNF"'),
            auto_branch.index("AutomaticLookAndFeel true"),
            "moos-theme auto arms the day/night switch before its bootstrap apply, "
            "which clears it — the switch ends up off",
        )

        sync = function(switch, "sync_auto")
        supplements = function(switch, "apply_supplements")
        self.assertNotIn("plasma-apply-lookandfeel", sync)
        self.assertNotIn("kwriteconfig6 --file kdeglobals", sync)
        self.assertIn('apply_supplements', sync)
        self.assertIn('AutomaticLookAndFeel', sync)
        self.assertIn('automatic_after', sync)
        self.assertIn('automatic_supplements_complete', sync)
        self.assertIn('[ -d "/usr/share/plasma/look-and-feel/$lnf" ]', sync)

        # reconcile is the path unit's entry point and fires on Plasma's burst of
        # kdeglobals writes at login. It MUST NOT write kdeglobals itself or it
        # would re-arm the very watch that triggered it — an unbounded loop. It is
        # loop-safe structurally: it only reads, delegates to sync_auto, and calls
        # apply_supplements (both already proven kdeglobals-clean above).
        recon = function(switch, "reconcile")
        self.assertNotIn("kwriteconfig6 --file kdeglobals", recon)
        self.assertIn("apply_supplements", recon)
        self.assertIn("automatic_supplements_complete", recon)
        self.assertIn("sync_auto", recon)
        self.assertIn('[ -d "/usr/share/plasma/look-and-feel/$lnf" ]', recon)

        for token in (
            # The desktop wallpaper is the MoOS scene plugin, applied per
            # containment; plasma-apply-wallpaperimage is FORBIDDEN because it
            # forces org.kde.image back and erases the dashboard bento.
            "apply_desktop_scene",
            "DefaultProfile",
            "gtk-application-prefer-dark-theme",
            "org.gnome.desktop.interface color-scheme",
            "WallpaperPlugin",
        ):
            self.assertIn(token, supplements)
        self.assertIn(
            '[ "$lock_image" = "$wallpaper_package" ] || return 1',
            function(switch, "automatic_supplements_complete"),
            "NovaLight must not satisfy Nova lockscreen readback by prefix",
        )
        self.assertNotIn("plasma-apply-wallpaperimage", supplements)
        self.assertNotIn("kdeglobals", supplements)

        auto_case = switch[switch.index("    auto)"):switch.index("    sync-auto)")]
        self.assertIn("systemctl --user start moos-theme-sync.path", auto_case)
        self.assertIn("sync_auto", auto_case)
        self.assertIn("moos-theme.lock", switch)
        self.assertIn("moos-theme.lock", APPLY.read_text(encoding="utf-8"))
        # A theme write that fails must be reported, and a plasmashell that is
        # merely SLOW must not be read as "the theme did not apply": a supplement
        # failure propagates to apply_manual, which REVERTS the look the user just
        # chose. `timeout` reports 124 when the child was still running, so that
        # one status is a verdict of UNKNOWN and is left to the reconciler.
        apply_body = re.search(r"(?ms)^apply\(\) \{.*?^\}$", switch).group(0)
        self.assertIn(
            "write_failed=1", apply_body,
            "a failing kwriteconfig6 must be reported, not swallowed — the "
            "desktop is left half-switched while moos-theme prints success",
        )
        scene = function(switch, "apply_desktop_scene")
        self.assertIn(
            '[ "$status" -eq 124 ] && return 2', scene,
            "an 8s plasmashell timeout is not a failed apply",
        )
        self.assertIn('[ "$scene_status" -eq 2 ]', supplements)

    @unittest.skipIf(os.name == "nt", "theme service retry harness requires POSIX shims")
    def test_theme_service_failure_stops_after_three_attempts(self) -> None:
        """A persistent desktop failure must become failed, not a five-second forever loop."""
        import tempfile

        with tempfile.TemporaryDirectory(prefix="moos-theme-retry-") as temporary:
            root = Path(temporary)
            bindir = root / "bin"
            bindir.mkdir()
            log = root / "reads"
            kread = bindir / "kreadconfig6"
            kread.write_text(
                """#!/bin/sh
case "$*" in
  *AutomaticLookAndFeel*) printf 'attempt\\n' >>"$MOOS_THEME_RETRY_LOG"; echo true ;;
  *LookAndFeelPackage*) echo org.moos.ui2 ;;
esac
""",
                encoding="utf-8",
            )
            kread.chmod(0o755)
            sleep = bindir / "sleep"
            sleep.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            sleep.chmod(0o755)
            env = {
                **os.environ,
                "HOME": str(root / "home"),
                "XDG_RUNTIME_DIR": str(root / "run"),
                "MOOS_THEME_RETRY_LOG": str(log),
                "PATH": f"{bindir}:{os.environ.get('PATH', '')}",
            }
            result = subprocess.run(
                [BASH, str(SWITCH), "reconcile-service"],
                env=env,
                text=True,
                capture_output=True,
                timeout=10,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            # reconcile + sync_auto's before/after stability read = three reads per
            # attempt. Nine proves exactly three attempts, neither one nor forever.
            self.assertEqual(log.read_text(encoding="utf-8").splitlines(), ["attempt"] * 9)
            self.assertIn("reconcile failed after 3 attempts", result.stderr)

    def test_wallpaper_motion_policy_is_atomic_and_picker_verifies_live_state(self) -> None:
        switch = SWITCH.read_text(encoding="utf-8")
        picker = (
            ROOT / "system_files/usr/share/moos/theme-picker/main.qml"
        ).read_text(encoding="utf-8")

        query = function(switch, "query_motion_mode")
        mutation = function(switch, "set_motion_mode")
        for token in (
            "desktops()",
            'wallpaperPlugin != "org.moos.ui2.wallpaper"',
            '["Wallpaper", "org.moos.ui2.wallpaper", "General"]',
            'readConfig("MotionMode", "1")',
            "moos-motion-error:mixed",
        ):
            self.assertIn(token, query)
        for mode, value in (("still", "0"), ("gentle", "1"), ("alive", "2")):
            self.assertRegex(
                mutation,
                rf"(?m)^\s*{mode}\)\s+value={value};\s+ambient=(?:false|true)\s+;;$",
            )
        self.assertRegex(
            mutation,
            r"(?m)^\s*still\)\s+value=0;\s+ambient=false\s+;;$",
        )
        self.assertRegex(
            mutation,
            r"(?m)^\s*(?:gentle|alive)\)\s+value=[12];\s+ambient=true\s+;;$",
        )
        self.assertIn('writeConfig("MotionMode", TARGET)', mutation)
        self.assertIn('writeConfig("AmbientMotion", AMBIENT)', mutation)
        self.assertIn("reloadConfig()", mutation)
        self.assertIn('actual="$(query_motion_mode)"', mutation)
        self.assertIn('[ "$actual" != "$requested" ]', mutation)
        self.assertRegex(
            switch,
            r"(?m)^\s*dark\|.*\|apply-lnf\)\s*$",
            "every command that MUTATES the desktop must enter the transaction lock",
        )
        self.assertIn(
            '[ "$#" -gt 1 ] && needs_theme_lock=1',
            switch,
            "a motion WRITE must take the same transaction lock as a theme change "
            "and a read-only motion QUERY must take nothing: the Theme Picker "
            "fires that query the moment it opens, so behind the exclusive write "
            "lock merely opening the picker waited out a whole theme transition "
            "(or made the next one wait on it)",
        )

        self.assertIn(
            'readonly property string currentMotionQuery: "moos-theme motion"',
            picker,
        )
        for mode in ("still", "gentle", "alive"):
            self.assertIn(f'cmd = "moos-theme motion {mode}"', picker)
            self.assertIn(f'onClicked: root.setMotion("{mode}")', picker)
            self.assertIn(f'root.currentMotion === "{mode}"', picker)
        self.assertNotRegex(
            picker,
            r'"moos-theme motion "\s*\+',
            "mutable QML values must never be concatenated into a shell command",
        )
        self.assertNotIn("id: motionExec", picker)
        self.assertIn("themeExec.run(cmd)", picker)
        self.assertIn('root.local("حركة الخلفية", "Wallpaper motion")', picker)
        self.assertNotIn("حركة الخلفية  ·  Wallpaper motion", picker)
        for icon in (
            "moos-ui-symbolic",
            "moos-refresh-symbolic",
            "moos-orbit-symbolic",
            "moos-close-symbolic",
            "moos-check-symbolic",
            "moos-sun-symbolic",
            "moos-moon-symbolic",
        ):
            self.assertIn(f'"{icon}"', picker)
        for inherited in (
            "preferences-desktop-theme-global",
            "edit-undo",
            "preferences-desktop-effects",
            "dialog-close",
            "checkmark",
            "weather-clear",
            "weather-clear-night",
        ):
            self.assertNotIn(f'"{inherited}"', picker)

        motion_completion = picker[
            picker.index("if (cmd === pendingMotionCommand)"):
            picker.index("if (cmd !== pendingThemeCommand)")
        ]
        self.assertLess(
            motion_completion.index("normalExit(data)"),
            motion_completion.index("awaitingMotionReadback = true"),
        )
        self.assertLess(
            motion_completion.index("awaitingMotionReadback = true"),
            motion_completion.index("refreshMotion()"),
            "motion readback must start only after the mutation process exits",
        )
        motion_readback = picker[
            picker.index("} else if (cmd === currentMotionQuery)"):
            picker.index("} else if (cmd === currentQuery)")
        ]
        self.assertIn("activeMotion !== pendingExpectedMotion", motion_readback)
        self.assertIn("clearOperationState()", motion_readback)

    @unittest.skipIf(os.name == "nt", "motion CLI harness requires POSIX executable shims")
    def test_wallpaper_motion_cli_maps_and_validates_exact_values(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory(prefix="moos-motion-test-") as temporary:
            temp = Path(temporary)
            state = temp / "motion-state"
            state.write_text("1\n", encoding="utf-8")

            tools = {
                "timeout": """#!/usr/bin/env bash
shift
exec "$@"
""",
                "flock": """#!/usr/bin/env bash
printf '%s\n' locked >>"$MOOS_MOTION_TEST_LOCK_LOG"
exit 0
""",
                "gdbus": """#!/usr/bin/env bash
if [[ "${MOOS_MOTION_TEST_FAIL:-}" == "mixed" ]]; then
    printf "%s\n" "(true, 'moos-motion-error:mixed\\n')"
    exit 0
fi
if [[ "$*" == *'writeConfig("MotionMode", TARGET)'* ]]; then
    if [[ "$*" == *'var TARGET = 0;'* ]]; then mode=0
    elif [[ "$*" == *'var TARGET = 1;'* ]]; then mode=1
    elif [[ "$*" == *'var TARGET = 2;'* ]]; then mode=2
    else exit 9
    fi
    printf '%s\n' "$mode" >"$MOOS_MOTION_TEST_STATE"
    printf "%s\n" "(true, 'moos-motion-set:2\\n')"
else
    mode="$(sed -n '1p' "$MOOS_MOTION_TEST_STATE")"
    printf "%s\n" "(true, 'moos-motion-value:${mode}\\n')"
fi
""",
            }
            for name, source in tools.items():
                path = temp / name
                path.write_text(source, encoding="utf-8")
                path.chmod(0o755)

            runtime = temp / "runtime"
            runtime.mkdir()
            lock_log = temp / "lock-log"
            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{temp}{os.pathsep}{env.get('PATH', '')}",
                    "XDG_RUNTIME_DIR": str(runtime),
                    "MOOS_MOTION_TEST_STATE": str(state),
                    "MOOS_MOTION_TEST_LOCK_LOG": str(lock_log),
                }
            )

            for requested, stored in (
                ("still", "0"),
                ("gentle", "1"),
                ("alive", "2"),
            ):
                with self.subTest(requested=requested):
                    changed = subprocess.run(
                        [BASH, str(SWITCH), "motion", requested],
                        env=env,
                        check=True,
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                    self.assertEqual(changed.stdout, f"{requested}\n")
                    self.assertEqual(state.read_text(encoding="utf-8"), f"{stored}\n")

                    queried = subprocess.run(
                        [BASH, str(SWITCH), "motion"],
                        env=env,
                        check=True,
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                    self.assertEqual(queried.stdout, f"{requested}\n")

            invalid = subprocess.run(
                [BASH, str(SWITCH), "motion", "cinematic"],
                env=env,
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertEqual(invalid.returncode, 2)
            self.assertIn("expected still, gentle, or alive", invalid.stderr)

            mixed_env = env | {"MOOS_MOTION_TEST_FAIL": "mixed"}
            mixed = subprocess.run(
                [BASH, str(SWITCH), "motion"],
                env=mixed_env,
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertNotEqual(mixed.returncode, 0)
            self.assertEqual(mixed.stdout, "")
            self.assertIn("inconsistent motion modes", mixed.stderr)
            self.assertEqual(
                len(lock_log.read_text(encoding="utf-8").splitlines()),
                4,
                "the four motion WRITES above (still, gentle, alive and the "
                "rejected 'cinematic') must each hold the transaction lock, and "
                "the four READS must take nothing at all — a read-only query "
                "behind the exclusive write lock is what made opening the Theme "
                "Picker block on, and block, a real theme transition",
            )

    def test_every_family_has_a_matched_light_and_dark_sibling(self) -> None:
        """The owner's rule: every theme is a light+dark pair. Assert each family
        ships BOTH complete look-and-feel package sets, that the light scheme is
        genuinely light and the dark scheme genuinely dark (a light theme whose
        window is dark is the "no light theme" bug), and that moos-theme can drive
        each light id and toggle any family by the ".light" suffix rule."""
        share = ROOT / "system_files/usr/share"
        switch = SWITCH.read_text(encoding="utf-8")

        def window_bg_sum(scheme_style: str) -> int:
            text = (share / "color-schemes" / f"{scheme_style}.colors").read_text(encoding="utf-8")
            m = re.search(r"\[Colors:Window\][^\[]*?BackgroundNormal=(\d+),(\d+),(\d+)", text, re.S)
            self.assertIsNotNone(m, f"{scheme_style}: no [Colors:Window] BackgroundNormal")
            return sum(int(g) for g in m.groups())

        # base pair + four accent families, each (dark_lnf, dark_style, light_lnf, light_style)
        families = {
            "base":     ("org.moos.ui2",          "MoOSUI2Dark",     "org.moos.ui2.light",          "MoOSUI2Light"),
            "nova":     ("org.moos.ui2.nova",      "MoOSUI2Nova",     "org.moos.ui2.nova.light",     "MoOSUI2NovaLight"),
            "amethyst": ("org.moos.ui2.amethyst",  "MoOSUI2Amethyst", "org.moos.ui2.amethyst.light", "MoOSUI2AmethystLight"),
            "aurora":   ("org.moos.ui2.aurora",    "MoOSUI2Aurora",   "org.moos.ui2.aurora.light",   "MoOSUI2AuroraLight"),
            "midnight": ("org.moos.ui2.midnight",  "MoOSUI2Midnight", "org.moos.ui2.midnight.light", "MoOSUI2Daylight"),
            "gaming":   ("org.moos.ui2.gaming",    "MoOSUI2Arena",    "org.moos.ui2.gaming.light",   "MoOSUI2ArenaLight"),
            "dev":      ("org.moos.ui2.dev",       "MoOSUI2Forge",    "org.moos.ui2.dev.light",      "MoOSUI2ForgeLight"),
            "study":    ("org.moos.ui2.study",     "MoOSUI2Scholar",  "org.moos.ui2.study.light",    "MoOSUI2ScholarLight"),
        }
        for fam, (dark_lnf, dark_style, light_lnf, light_style) in families.items():
            for lnf in (dark_lnf, light_lnf):
                self.assertTrue((share / "plasma/look-and-feel" / lnf / "contents/defaults").is_file(),
                                f"{fam}: missing look-and-feel package {lnf}")
            for style in (dark_style, light_style):
                self.assertTrue((share / "color-schemes" / f"{style}.colors").is_file(),
                                f"{fam}: missing color scheme {style}")
            # light must read light, dark must read dark — the actual parity property
            self.assertGreater(window_bg_sum(light_style), 540,
                               f"{light_style} is not a LIGHT scheme (window bg too dark)")
            self.assertLess(window_bg_sum(dark_style), 320,
                            f"{dark_style} is not a DARK scheme (window bg too light)")
            # the accent families also ship desktoptheme/aurorae/wallpaper for both halves
            if fam not in ("base",):
                for style in (dark_style, light_style):
                    self.assertTrue((share / "plasma/desktoptheme" / style).is_dir(),
                                    f"{fam}: missing desktoptheme {style}")
                    self.assertTrue((share / "aurorae/themes" / style).is_dir(),
                                    f"{fam}: missing aurorae {style}")
                    self.assertTrue((share / "wallpapers" / style / "contents/screenshot.png").is_file(),
                                    f"{fam}: missing wallpaper {style}")
            # moos-theme must be able to apply the light id (a load_profile arm)
            self.assertIn(light_lnf, switch, f"moos-theme cannot drive {light_lnf}")
            # Live verification and login self-heal must agree with the switcher.
            # A family member is not healthy if our own diagnostics call it foreign,
            # or if every login needlessly reapplies it despite intact selectors.
            for checker_name in ("moos-selfcheck", "post-update-check.sh"):
                checker_path = (ROOT / "system_files/usr/bin/moos-selfcheck"
                                if checker_name == "moos-selfcheck"
                                else ROOT / "tests/post-update-check.sh")
                checker = checker_path.read_text(encoding="utf-8")
                self.assertIn(dark_lnf, checker, f"{checker_name} rejects {dark_lnf}")
                self.assertIn(light_lnf, checker, f"{checker_name} rejects {light_lnf}")
            apply_theme = (ROOT / "system_files/usr/bin/moos-apply-theme").read_text(encoding="utf-8")
            self.assertIn(dark_lnf, apply_theme, f"login self-heal rejects {dark_lnf}")
            self.assertIn(light_lnf, apply_theme, f"login self-heal rejects {light_lnf}")
        # toggle flips ANY family by the ".light" suffix rule, in both directions
        self.assertIn('target="${cur%.light}"', switch)
        self.assertIn('target="${cur}.light"', switch)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class SteadyStateWallpaperReconcileTests(unittest.TestCase):
    """The steady-state guard: a green marker must not keep a drifted wallpaper.

    Plasma flushes its in-memory config on shutdown, so a lost race can put
    ANOTHER MoOS package back on a themed desktop (seen live 2026-08-02: a
    Scholar-Light session rebooted into a Graphite desktop wallpaper with every
    marker green). moos-apply-theme now reconciles package-level drift on every
    login while never touching a custom image file the user picked on purpose.
    """

    APPLY = ROOT / "system_files/usr/bin/moos-apply-theme"

    def test_marker_exit_reconciles_first(self) -> None:
        text = self.APPLY.read_text(encoding="utf-8")
        self.assertIn('reconcile_wallpaper_drift "$lnf"\n        exit 0', text,
                      "the theme_intact early exit must reconcile wallpaper "
                      "drift before trusting the marker")

    def test_only_moos_packages_are_healed(self) -> None:
        text = self.APPLY.read_text(encoding="utf-8")
        body = text.split("reconcile_wallpaper_drift() {", 1)[1].split("\n}", 1)[0]
        # Desktop heal keys on MoOSUI2* OR empty (unread); lock heal keys on
        # MoOSUI2* alone. A custom image path must match neither arm.
        self.assertIn('/usr/share/wallpapers/MoOSUI2*|"")', body,
                      "desktop heal must key on the MoOSUI2 package prefix "
                      "(plus empty = unread), never a custom image path")
        self.assertIn("/usr/share/wallpapers/MoOSUI2*)", body,
                      "lock heal must key on the MoOSUI2 package prefix")
        self.assertIn('"$pkg"|"") ;;', body,
                      "a matching package and an unreadable value must both be "
                      "left alone")

    def test_family_mapping_matches_the_shipped_packages(self) -> None:
        """Run the real lnf_wallpaper_package for all 16 looks."""
        text = self.APPLY.read_text(encoding="utf-8")
        fn = "lnf_wallpaper_package() {" + text.split(
            "lnf_wallpaper_package() {", 1)[1].split("\n}\n", 1)[0] + "\n}"
        expected = {
            "org.moos.ui2": "MoOSUI2Graphite",
            "org.moos.ui2.light": "MoOSUI2Tide",
            "org.moos.ui2.nova": "MoOSUI2Nova",
            "org.moos.ui2.nova.light": "MoOSUI2NovaLight",
            "org.moos.ui2.amethyst": "MoOSUI2Amethyst",
            "org.moos.ui2.amethyst.light": "MoOSUI2AmethystLight",
            "org.moos.ui2.midnight": "MoOSUI2Midnight",
            "org.moos.ui2.midnight.light": "MoOSUI2MidnightLight",
            "org.moos.ui2.aurora": "MoOSUI2Aurora",
            "org.moos.ui2.aurora.light": "MoOSUI2AuroraLight",
            "org.moos.ui2.daylight": "MoOSUI2Daylight",
            "org.moos.ui2.gaming": "MoOSUI2Arena",
            "org.moos.ui2.gaming.light": "MoOSUI2ArenaLight",
            "org.moos.ui2.dev": "MoOSUI2Forge",
            "org.moos.ui2.dev.light": "MoOSUI2ForgeLight",
            "org.moos.ui2.study": "MoOSUI2Scholar",
            "org.moos.ui2.study.light": "MoOSUI2ScholarLight",
        }
        for lnf, package in expected.items():
            with self.subTest(lnf=lnf):
                out = subprocess.run(
                    ["bash", "-c", fn + f'\nlnf_wallpaper_package "{lnf}"'],
                    capture_output=True, text=True)
                self.assertEqual(out.returncode, 0, out.stderr)
                self.assertEqual(out.stdout.strip(),
                                 f"/usr/share/wallpapers/{package}")
        out = subprocess.run(
            ["bash", "-c", fn + '\nlnf_wallpaper_package "org.kde.breeze"'],
            capture_output=True, text=True)
        self.assertNotEqual(out.returncode, 0,
                            "a non-MoOS look must never map to a package")
