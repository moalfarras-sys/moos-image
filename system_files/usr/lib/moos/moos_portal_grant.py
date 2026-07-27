#!/usr/bin/python3
"""Copy a working RemoteDesktop grant onto an account that cannot click for one.

THE PROBLEM THIS SOLVES

Mo PC Remote injects input through xdg-desktop-portal's RemoteDesktop interface.
The portal wants one interactive approval, and it remembers it afterwards:
mo-remote-portal.py asks for `persist_mode = 2` and saves the returned
`restore_token`, so the dialog appears exactly once per account, ever.

"Once" is one time too many for MoOS Cloud's second desktop. That session runs on
`kwin_wayland --virtual` with nobody in front of it, and the only way to click the
dialog is through Mo PC Remote — which is the thing waiting on the grant. The
seat-owning account never hit this because it HAS a seat: ydotoold works there,
so it could click its own prompt. A virtual session has no such route.

WHAT A REAL GRANT ACTUALLY LOOKS LIKE

Read off a working account rather than guessed at:

    table       remote-desktop
    id          tan02ApTgIYasWH2ZZPc1w      <- the RESTORE TOKEN, random per grant
    app-id      ""                          <- empty: Mo PC Remote is not sandboxed
    permission  yes
    data        ('KDE', uint32 1, <bytes>)  <- KDE's session state: clipboardEnabled,
                                               devices (pointer|keyboard), screenShareEnabled

That id is the whole trick, and it is why `flatpak permission-set remote-desktop
... moos-pc-remote` appeared to do nothing. It DID write an entry — under the key
`moos-pc-remote`, with empty data. The portal only ever looks up the key the app
hands it in `restore_token`, so an entry under any other name is never read and
`permission-show` looking "empty" was never the problem.

So a grant is two halves that must agree, and seeding one without the other is
what makes this look impossible:

    1. an entry in the permission store, keyed by a token, carrying KDE's data
    2. that same token in ~/.config/MoRemote/portal-restore-token

WHY THIS IS NOT A PRIVILEGE ESCALATION

It grants an account's own Mo PC Remote the right to drive that account's own
desktop — precisely what the dialog would have granted had anyone been able to
click it. Nothing crosses between users: the data blob carries device flags, not
identity, and each account's token lands in its own store and its own home. Mo PC
Remote still refuses every connection that does not arrive over Tailscale.

TWO STEPS, BECAUSE ONE PROCESS CANNOT REACH BOTH BUSES

A user's session bus lives in /run/user/<uid>, mode 0700, and dbus-broker
authenticates the peer's uid — so the donor must dump and the target must apply,
each as themselves. `dump` serialises the data variant; `apply` writes it back.
"""
import argparse
import pathlib
import sys

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib

BUS = "org.freedesktop.impl.portal.PermissionStore"
OBJ = "/org/freedesktop/impl/portal/PermissionStore"
TABLE = "remote-desktop"
# The serialised GVariant is stored with its type string on the first line so
# `apply` can rebuild it exactly; guessing the signature is how this silently
# writes an entry the portal cannot read.
SIGNATURE = "v"


def session_bus():
    """The caller's own bus. Never an address passed in — see the header."""
    return Gio.bus_get_sync(Gio.BusType.SESSION, None)


def call(conn, method, params, reply_type):
    return conn.call_sync(
        BUS, OBJ, BUS, method, params,
        GLib.VariantType(reply_type) if reply_type else None,
        Gio.DBusCallFlags.NONE, 5000, None)


def cmd_dump(args):
    conn = session_bus()
    try:
        ids = call(conn, "List", GLib.Variant("(s)", (TABLE,)), "(as)").unpack()[0]
    except GLib.Error as exc:
        raise SystemExit(f"cannot read the permission store: {exc.message}")

    for entry in ids:
        reply = call(conn, "Lookup", GLib.Variant("(ss)", (TABLE, entry)), "(a{sas}v)")
        perms, data = reply.get_child_value(0), reply.get_child_value(1)
        # An entry with no data is the broken shape this whole file exists to
        # replace — it is not a donor, it is the symptom.
        if data.get_type_string() == "()":
            continue
        if not any("yes" in v for v in perms.unpack().values()):
            continue
        pathlib.Path(args.file).write_bytes(data.get_data_as_bytes().get_data())
        print(f"dumped a working grant from id {entry}")
        return 0

    raise SystemExit(
        "this account has no RemoteDesktop grant to copy. Approve Mo PC Remote's\n"
        "prompt once on an account that HAS a seat, then run this again.")


def cmd_apply(args):
    raw = pathlib.Path(args.file).read_bytes()
    data = GLib.Variant.new_from_bytes(GLib.VariantType(SIGNATURE),
                                       GLib.Bytes.new(raw), False)
    conn = session_bus()
    try:
        call(conn, "Set",
             GLib.Variant("(sbsva{sas})", (TABLE, True, args.token, data, {"": ["yes"]})),
             None)
    except GLib.Error as exc:
        raise SystemExit(f"cannot write the permission store: {exc.message}")

    # Prove it landed, and prove it landed WITH its data. An entry that reads
    # back empty is the failure this is meant to make impossible.
    check = call(conn, "Lookup", GLib.Variant("(ss)", (TABLE, args.token)), "(a{sas}v)")
    if check.get_child_value(1).get_type_string() == "()":
        raise SystemExit("the entry was written without its session data — the portal "
                         "would ignore it and prompt anyway")
    perms = check.get_child_value(0).unpack()
    if not any("yes" in v for v in perms.values()):
        raise SystemExit(f"the entry was written without a 'yes' permission: {perms}")

    # The other half. Without this the portal has a grant nobody asks for.
    token_file = pathlib.Path(args.token_file).expanduser()
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(args.token + "\n", encoding="utf-8")
    token_file.chmod(0o600)
    print(f"grant applied: {args.token}")
    print(f"  permissions : {perms}")
    print(f"  token file  : {token_file}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("dump", help="read this account's working grant into a file")
    d.add_argument("file")
    d.set_defaults(func=cmd_dump)

    a = sub.add_parser("apply", help="write a dumped grant into this account")
    a.add_argument("file")
    a.add_argument("token")
    a.add_argument("--token-file", default="~/.config/MoRemote/portal-restore-token")
    a.set_defaults(func=cmd_apply)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
