#!/usr/bin/env python3
"""Gate: MoPlayer exports its MPRIS object BEFORE it takes the bus name.

WHAT WAS MEASURED, ON THE STATION, 2026-09-18

Playing a video changed nothing on the desktop: the MoOS Island stayed empty, no
media controls appeared and no title was shown — but the same video DID appear if
the shell was restarted while it was already playing. `dbus-monitor` explained it
in one line:

    method call  sender=:1.2 -> destination=org.mpris.MediaPlayer2.moplayer
                 path=/org/mpris/MediaPlayer2 member=GetAll
    error        sender=:1.2067 -> destination=:1.2
                 error_name=org.freedesktop.DBus.Error.UnknownObject

A desktop watches for the MPRIS bus NAME and asks the new owner for its
properties the moment the name appears — 2 ms later here. MoPlayer took the name
first and exported `/org/mpris/MediaPlayer2` one `await` afterwards, so that first
question hit an empty connection, and Plasma's player model drops a player that
answers `UnknownObject`; it never asks again. A model created later enumerates the
bus and finds it, which is why a shell restart "fixed" it.

Exporting the object first closes the window for every MPRIS consumer, not only
Plasma's. This gate keeps the order, because the two calls read as interchangeable
and a future edit could swap them back without anything failing in CI.
"""

from __future__ import annotations

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
MPRIS = ROOT / "moplayer/lib/services/system/mpris.dart"


class MprisRegistrationOrder(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = MPRIS.read_text(encoding="utf-8")
        start = cls.source.index("Future<void> _connect(")
        end = cls.source.index("\n  }\n", start)
        cls.connect = cls.source[start:end]

    def test_the_object_is_exported_before_the_name_is_requested(self):
        register = self.connect.index("registerObject(")
        request = self.connect.index("requestName(")
        self.assertLess(
            register, request,
            "a client that reacts to the bus name must find the object already "
            "exported; taking the name first answers UnknownObject and the player "
            "is dropped for the life of that shell")

    def test_the_reason_is_written_where_the_order_lives(self):
        self.assertIn("UnknownObject", self.connect,
                      "the next reader must see why the order matters")

    def test_a_lost_name_race_still_closes_the_connection(self):
        tail = self.connect[self.connect.index("requestName("):]
        self.assertIn("primaryOwner", tail)
        self.assertIn("client.close()", tail,
                      "losing the name must not leave an exported object behind")

    def test_nothing_else_requests_the_name(self):
        requests = re.findall(r"requestName\(", self.source)
        self.assertEqual(len(requests), 1,
                         "one place owns the registration order")


class MetadataIsSingleWrapped(unittest.TestCase):
    """`a{sv}` carries ONE variant per value, and MoPlayer used to send two.

    Measured on the station on 2026-09-18, reading MoPlayer's own Metadata off
    the bus:

        dict entry(string "xesam:title"
                   variant variant string "…")

    `DBusDict.stringVariant` wraps each value in the variant the signature asks
    for, so the values passed to it must be raw. Wrapping them again put a
    variant inside a variant: every MPRIS reader takes the outer one, asks for a
    string and gets nothing. The title, length, artwork and artist were all
    invisible — the MoOS Island showed "وسائط قيد التشغيل" with a placeholder
    cover while the player was healthy and playing.
    """

    @classmethod
    def setUpClass(cls):
        source = MPRIS.read_text(encoding="utf-8")
        start = source.index("DBusValue _metadataValue()")
        cls.metadata = source[start:source.index("\n  }\n", start)]

    def test_no_value_is_wrapped_in_a_variant_by_hand(self):
        self.assertNotIn("DBusVariant(", self.metadata,
                         "stringVariant already adds the variant a{sv} requires; "
                         "a second one makes every reader see an empty value")

    def test_the_fields_a_desktop_reads_are_still_published(self):
        for field in ("mpris:trackid", "mpris:length", "mpris:artUrl",
                      "xesam:title", "xesam:artist", "xesam:album"):
            self.assertIn(field, self.metadata)

    def test_the_measurement_is_written_down(self):
        self.assertIn("variant", self.metadata.lower(),
                      "the next reader must find out why the values are raw")


if __name__ == "__main__":
    loader = unittest.defaultTestLoader
    suite = unittest.TestSuite([loader.loadTestsFromTestCase(MprisRegistrationOrder),
                                loader.loadTestsFromTestCase(MetadataIsSingleWrapped)])
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
