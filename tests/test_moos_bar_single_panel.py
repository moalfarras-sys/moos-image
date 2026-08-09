#!/usr/bin/env python3
"""The MoOS Horizon Bar is ONE panel — proven by running the real merge.

Rev 30 split the bar into a centred dock capsule and a corner system capsule so
the task area could hold the true screen centre. On the real machine that reads
as two detached pieces of glass with a wide gap, the clock and tray marooned in
the corner; the owner rejected it on sight, having already removed that layout
once before. Rev 33 merges them back.

A string gate over moos-bar-apply would only prove the file mentions merging.
This extracts the actual Python surgery out of the shipped script and runs it
against real appletsrc fixtures, so the invariant tested is the behaviour a user
gets: one bottom panel, carrying the whole bar, in the configured order, no
matter what the profile looked like going in.
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(os.environ.get("MOOS_TEST_ROOT", Path(__file__).resolve().parents[1])).resolve()
BAR_APPLY = ROOT / "system_files/usr/bin/moos-bar-apply"
BAR_CONF = ROOT / "system_files/usr/share/moos/moos-bar.conf"
LAYOUT = (ROOT / "system_files/usr/share/plasma/layout-templates"
          / "org.kde.plasma.desktop.defaultPanel/contents/layout.js")

BRAND = "org.moos.brand"
ISLAND = "org.moos.island"


def merge_program() -> str:
    """The python heredoc inside merge_appletsrc(), verbatim."""
    text = BAR_APPLY.read_text(encoding="utf-8")
    body = text.split("merge_appletsrc() {", 1)[1]
    # The heredoc line carries redirections after <<'PY'; the program starts on
    # the next line.
    after = body.split("<<'PY'", 1)[1].split("\n", 1)[1]
    return after.split("\nPY\n", 1)[0]


def panel(cid: str, applets: dict[str, str], *, location: str = "4",
          order: list[str] | None = None, immutability: str = "0") -> str:
    out = [f"[Containments][{cid}]", "activityId=", "formfactor=2",
           f"immutability={immutability}", "lastScreen=0", f"location={location}",
           "plugin=org.kde.panel", "wallpaperplugin=org.kde.image", ""]
    out += [f"[Containments][{cid}][General]",
            "AppletOrder=" + ";".join(order if order is not None else applets), ""]
    for aid, plugin in applets.items():
        out += [f"[Containments][{cid}][Applets][{aid}]", f"plugin={plugin}", ""]
    return "\n".join(out)


class SinglePanelMerge(unittest.TestCase):
    def run_merge(self, appletsrc: str, shellrc: str = "") -> tuple[str, str, str]:
        with tempfile.TemporaryDirectory() as tmp:
            rc = Path(tmp) / "appletsrc"
            views = Path(tmp) / "plasmashellrc"
            rc.write_text(appletsrc, encoding="utf-8")
            views.write_text(shellrc, encoding="utf-8")
            applets = ""
            section = None
            for line in BAR_CONF.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if re.match(r"^\[(.+)\]$", line):
                    section = line[1:-1]
                elif section == "bar" and line.startswith("applets="):
                    applets = line.split("=", 1)[1]
            proc = subprocess.run(
                [sys.executable, "-", str(rc), BRAND, applets, str(BAR_CONF), str(views)],
                input=merge_program(), capture_output=True, text=True, check=True,
            )
            return proc.stdout.strip(), rc.read_text(encoding="utf-8"), views.read_text(encoding="utf-8")

    @staticmethod
    def bottom_panels(text: str) -> list[str]:
        found, cur = [], None
        for line in text.splitlines():
            m = re.fullmatch(r"\[Containments\]\[(\d+)\]", line)
            if m:
                cur = m.group(1)
                continue
            if cur and line == "location=4":
                found.append(cur)
        return found

    @staticmethod
    def order_of(text: str, cid: str) -> list[str]:
        block = text.split(f"[Containments][{cid}][General]", 1)[1]
        for line in block.splitlines():
            if line.startswith("AppletOrder="):
                return [a for a in line.split("=", 1)[1].split(";") if a]
        return []

    def test_the_rev30_two_slab_profile_becomes_one_capsule(self) -> None:
        """The exact shape the owner was left with after 44.20260806.546."""
        src = "\n".join((
            panel("398", {"400": "org.kde.plasma.icontasks", "424": BRAND,
                          "425": ISLAND},
                  order=["424", "400", "425"]),
            panel("417", {}, location="0"),
            panel("430", {"401": "org.kde.plasma.marginsseparator",
                          "402": "org.kde.plasma.systemtray",
                          "421": "org.moos.nova.clock"},
                  order=["402", "401", "421"]),
        ))
        views = ("[PlasmaViews][Panel 398]\nalignment=132\nfloating=1\n\n"
                 "[PlasmaViews][Panel 430]\nalignment=2\nfloating=1\n")
        verdict, merged, shellrc = self.run_merge(src, views)

        self.assertEqual(verdict, "merged")
        self.assertEqual(self.bottom_panels(merged), ["398"],
                         "the bar must end as exactly ONE bottom panel")
        self.assertNotIn("[Containments][430]", merged,
                         "the absorbed panel must be gone, not emptied")
        self.assertEqual(self.order_of(merged, "398"),
                         ["424", "425", "400", "401", "402", "421"],
                         "applets must land in moos-bar.conf order: "
                         "brand, island, tasks, separator, tray, clock")
        for aid in ("401", "402", "421"):
            self.assertIn(f"[Containments][398][Applets][{aid}]", merged,
                          f"applet {aid} must be re-homed, never dropped")
        self.assertNotIn("[PlasmaViews][Panel 430]", shellrc,
                         "the dead panel's geometry must not survive to be flushed back")
        self.assertIn("[PlasmaViews][Panel 398]", shellrc,
                      "the surviving panel keeps its geometry")

    def test_merging_is_idempotent(self) -> None:
        src = "\n".join((
            panel("398", {"400": "org.kde.plasma.icontasks", "424": BRAND},
                  order=["424", "400"]),
            panel("430", {"402": "org.kde.plasma.systemtray",
                          "421": "org.moos.nova.clock"},
                  order=["402", "421"]),
        ))
        _, once, _ = self.run_merge(src)
        self.assertIn(
            f"plugin={ISLAND}", once,
            "the stopped-shell merge must create the direct island for stale profiles",
        )
        verdict, twice, _ = self.run_merge(once)
        self.assertEqual(verdict, "no-change",
                         "a merged bar must be left alone, not rewritten every login")
        self.assertEqual(once, twice)
        self.assertEqual(len(self.bottom_panels(twice)), 1)

    def test_three_stray_panels_all_collapse_into_the_launcher_s_panel(self) -> None:
        src = "\n".join((
            panel("10", {"11": "org.kde.plasma.systemtray"}, order=["11"]),
            panel("20", {"21": "org.kde.plasma.icontasks", "22": BRAND},
                  order=["21", "22"]),
            panel("30", {"31": "org.moos.nova.clock"}, order=["31"]),
        ))
        verdict, merged, _ = self.run_merge(src)
        self.assertEqual(verdict, "merged")
        self.assertEqual(self.bottom_panels(merged), ["20"],
                         "the panel holding the MoOS launcher is the one that survives")
        self.assertEqual(self.order_of(merged, "20"), ["22", "32", "21", "11", "31"])

    def test_a_locked_desktop_is_handed_back_to_its_owner(self) -> None:
        """immutability=1 is Plasma's "Widgets are locked".

        It does not merely stop a drag: it removes Add Widgets, Configure and
        every applet's own settings from the context menus, so the desk goes
        read-only with nothing on screen explaining why. Found live on this
        machine on BOTH the panel and the folder containment, with nothing in
        this repo setting it — a stray lock from an earlier session that had
        been in force ever since. MoOS does not ship a desktop its owner cannot
        arrange.
        """
        src = "\n".join((
            panel("398", {"400": "org.kde.plasma.icontasks", "424": BRAND},
                  order=["424", "400"], immutability="1"),
            panel("417", {}, location="0", immutability="1"),
        ))
        _, out, _ = self.run_merge(src)
        self.assertNotIn("immutability=1", out,
                         "every containment must come back mutable")
        self.assertEqual(out.count("immutability=0"), 2,
                         "the folder containment counts too — a locked desktop "
                         "is exactly where 'I cannot add widgets' comes from")

    def test_a_users_own_top_or_side_panel_is_never_absorbed(self) -> None:
        src = "\n".join((
            panel("398", {"400": "org.kde.plasma.icontasks", "424": BRAND},
                  order=["424", "400"]),
            panel("500", {"501": "org.kde.plasma.systemtray"},
                  location="3", order=["501"]),
        ))
        verdict, merged, _ = self.run_merge(src)
        self.assertIn("[Containments][500]", merged,
                      "MoOS owns the bottom edge only; a top panel is the user's")
        self.assertNotIn("[Containments][398][Applets][501]", merged)
        self.assertEqual(verdict, "reordered",
                         "adding the required direct island may repair the MoOS panel")

    def test_an_applet_missing_from_every_appletorder_still_survives(self) -> None:
        """A widget absent from AppletOrder is drawn but unlisted; dropping it
        on merge would silently delete something the user placed."""
        src = "\n".join((
            panel("398", {"400": "org.kde.plasma.icontasks", "424": BRAND},
                  order=["424"]),
            panel("430", {"402": "org.kde.plasma.systemtray"}, order=[]),
        ))
        _, merged, _ = self.run_merge(src)
        order = self.order_of(merged, "398")
        self.assertIn("400", order, "the unlisted task manager must be swept in")
        self.assertIn("402", order, "the unlisted tray must be swept in")


class SingleSourceAgreement(unittest.TestCase):
    """The conf, the seed template and the migration must state one bar."""

    def test_the_conf_defines_exactly_one_panel(self) -> None:
        conf = BAR_CONF.read_text(encoding="utf-8")
        self.assertIn("[bar]", conf)
        for retired in ("[dock]", "[system]"):
            self.assertNotIn(f"\n{retired}\n", conf,
                             f"{retired} is the retired two-slab definition")
        for key in ("lengthMode=fit", "alignment=center", "floating=true"):
            self.assertIn(key, conf, "the capsule geometry lives in the conf")
        self.assertIn("applets=brand;island;tasks;separator;tray;clock", conf,
                      "one order, mirrored by Plasma for RTL")

    def test_the_seed_template_creates_exactly_one_panel(self) -> None:
        layout = LAYOUT.read_text(encoding="utf-8")
        code = re.sub(r"/\*.*?\*/", "", layout, flags=re.S)
        self.assertEqual(len(re.findall(r"\bnew Panel\b", code)), 1,
                         "a new profile must be seeded with ONE panel")
        for applet in ("org.moos.brand", "org.moos.island",
                       "org.kde.plasma.icontasks",
                       "org.kde.plasma.marginsseparator",
                       "org.kde.plasma.systemtray", "org.moos.nova.clock"):
            self.assertIn(applet, layout,
                          f"{applet} belongs on the one panel, not a second one")

    def test_the_migration_can_never_create_a_panel(self) -> None:
        apply = BAR_APPLY.read_text(encoding="utf-8")
        self.assertNotIn("split_appletsrc", apply,
                         "the splitter is what produced two capsules")
        self.assertIn("merge_appletsrc", apply)
        # The rev-30 splitter built a panel by appending a containment block.
        self.assertNotIn('"plugin=org.kde.panel' + chr(92) + "n", apply,
                         "moos-bar-apply must never write a new panel containment")
        self.assertIn('*bar=ok*)', apply,
                      "the success sentinel must be the single-capsule one")
        self.assertNotIn("sys=ok", apply,
                         "the two-slab readback must be gone")

    def test_live_bar_pass_unlocks_runtime_desktop(self) -> None:
        apply = BAR_APPLY.read_text(encoding="utf-8")
        self.assertIn("ds[d].locked = false", apply,
                      "the live shell must clear Plasma's runtime desktop lock")
        self.assertIn("appletsrc immutability key", apply.lower(),
                      "the runtime lock and saved applet lock must stay distinct")
        self.assertIn("len(parts) >= 2", apply,
                      "applet sections must be repaired along with containments")
        self.assertIn("systemctl --user start plasma-plasmashell.service", apply,
                      "bar restart must remain managed by the user systemd unit")
        self.assertNotIn("setsid kstart plasmashell", apply,
                         "bar restart must not create an orphan plasmashell")
        self.assertIn("org.kde.PlasmaShell.evaluateScript", apply,
                      "readiness must wait for Plasma scripting, not only D-Bus ping")
        self.assertIn("sleep 8", apply,
                      "readback must allow Plasma containment restore to finish")
        self.assertIn("for _ in $(seq 1 12)", apply,
                      "transient Plasma scripting startup must be retried")
        self.assertIn("dock.addWidget(ISLAND_APPLET)", apply,
                      "existing profiles must receive the direct adaptive island")
        self.assertIn("island_plugin = zone_plugin.get(\"island\"", apply,
                      "the stopped-shell merge must create the direct island")
        self.assertIn('dock.readConfig("AppletOrder", "")', apply,
                      "live order checks must read Plasma's saved visual order")
        self.assertIn('ps[i].readConfig("AppletOrder", "")', apply,
                      "the non-destructive check must read the visual order")
        self.assertIn("directIslandPosition == directBrandPosition + 1", apply,
                      "live success must prove the island follows the launcher")
        self.assertIn("e != ISLAND_APPLET", apply,
                      "the retired tray copy must be removed during migration")
        live_script = apply.split(
            "-m org.kde.PlasmaShell.evaluateScript '", 1
        )[1].split("' 2>>", 1)[0]
        js_comments = "\n".join(re.findall(r"//[^\n]*", live_script))
        self.assertNotIn(
            "'", js_comments,
            "an apostrophe in the shell-single-quoted live JavaScript splits "
            "evaluateScript into multiple D-Bus parameters",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
