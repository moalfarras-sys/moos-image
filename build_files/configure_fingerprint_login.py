#!/usr/bin/env python3
"""Use authselect's local-authentication stack for the local login greeter.

The vendor greeter collects its password before starting PAM. A fingerprint-first
stack therefore scans even when the owner already supplied a valid password.
Derive a greeter-only stack from authselect's generated system-auth, swapping only
the adjacent sufficient password/fingerprint alternatives. Blank input reaches
the reader; a valid supplied password finishes without starting it. Preserve the
vendor conversation, other services and every account/password/session rule.
"""
import argparse
import os
from pathlib import Path
import re
import subprocess
import tempfile


AUTH = re.compile(r"^(auth\s+substack\s+)password-auth([ \t]*)$", re.MULTILINE)
GREETER_STACK = "moos-local-login-auth"
PAIR = re.compile(
    r"^(auth[ \t]+sufficient[ \t]+pam_fprintd\.so[^\n]*\n)"
    r"(auth[ \t]+sufficient[ \t]+pam_unix\.so[^\n]*(?:\n|$))", re.MULTILINE)


def local_login(vendor: str) -> str:
    if len(AUTH.findall(vendor)) != 1:
        raise ValueError("unrecognized vendor login authentication stack")
    for facility in ("account", "password", "session"):
        if not re.search(rf"^{facility}\s+include\s+password-auth\s*$", vendor, re.MULTILINE):
            raise ValueError(f"missing vendor {facility} stack")
    return AUTH.sub(r"\g<1>" + GREETER_STACK + r"\2", vendor)


def greeter_auth(stack: str, *, bounded: bool = True) -> str:
    """Keep the generated policy; refuse stacks requiring a different review."""
    if not stack.endswith("\n"):
        raise ValueError("incomplete generated authentication stack")
    for name in ("pam_fprintd", "pam_unix"):
        if len(re.findall(rf"^-?auth[ \t]+[^\n]*\b{name}\.so(?:[ \t]|$)", stack, re.MULTILINE)) != 1:
            raise ValueError("ambiguous generated authentication alternatives")
    if len(PAIR.findall(stack)) != 1:
        raise ValueError("unrecognized generated authentication order; review required")
    fingerprint = PAIR.search(stack)[1]
    if bounded and not re.fullmatch(r"auth[ \t]+sufficient[ \t]+pam_fprintd\.so[ \t]*\n", fingerprint):
        raise ValueError("preserving custom fingerprint options; review required")
    # A site with lockout/other authentication policy needs its own integration
    # review: never run an empty password attempt through its failure counters.
    if re.search(r"^auth\s+.*\bpam_(?:faillock|tally2|sss|u2f|pkcs11)\.so", stack, re.MULTILINE):
        raise ValueError("preserving additional authentication policy; review required")
    def alternatives(match):
        reader = match[1]
        if bounded:
            reader = reader.replace("pam_fprintd.so", "pam_fprintd.so max_tries=1 timeout=8")
        return match[2] + reader
    return ("# MoOS greeter-only derivative of authselect system-auth.\n"
            "# Only the adjacent sufficient alternatives are reordered.\n"
            "# Refresh with configure_fingerprint_login.py; other services are unchanged.\n"
            + ("# The reader has one attempt and an eight-second timeout.\n" if bounded else "")
            + PAIR.sub(alternatives, stack))


def plan(root: Path) -> tuple[Path, str]:
    vendor = (root / "usr/lib/pam.d/plasmalogin").read_text()
    configured = local_login(vendor)
    target = root / "etc/pam.d/plasmalogin"
    if target.is_symlink():
        raise ValueError("refusing a local PAM symlink")
    legacy = AUTH.sub(r"\1system-auth\2", vendor)
    if target.exists() and target.read_text() not in (vendor, legacy, configured):
        raise ValueError("preserving customized local PAM configuration; review required")
    return target, configured


def atomic_write(target: Path, contents: str) -> None:
    fd, temporary = tempfile.mkstemp(prefix=".moos-login-", dir=target.parent)
    try:
        with os.fdopen(fd, "w") as out:
            out.write(contents)
            out.flush()
            os.fsync(out.fileno())
            os.fchmod(out.fileno(), 0o644)
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)


def stack_plan(root: Path) -> tuple[Path, str]:
    stack = (root / "etc/pam.d/system-auth").read_text()
    derived = greeter_auth(stack)
    target = root / "etc/pam.d" / GREETER_STACK
    if target.is_symlink():
        raise ValueError("refusing a local greeter-auth symlink")
    if target.exists() and target.read_text() not in (derived, greeter_auth(stack, bounded=False)):
        raise ValueError("preserving customized greeter authentication; review required")
    return target, derived


def check_configuration(root: Path) -> None:
    target, configured = plan(root)
    auth_target, derived = stack_plan(root)
    if not target.is_file() or target.read_text() != configured:
        raise ValueError("greeter does not use the reviewed local authentication stack")
    if not auth_target.is_file() or auth_target.read_text() != derived:
        raise ValueError("greeter authentication requires the reviewed reader limits")


def apply(root: Path, *, image: bool = False, run=subprocess.run) -> None:
    target, configured = plan(root)
    # Private fixtures may inspect a plan, never run host authselect.
    if root != Path("/"):
        raise ValueError("apply requires the actual OS root")
    run(["authselect", "check"], check=True)
    current = run(["authselect", "current", "--raw"], check=True,
                  capture_output=True, text=True).stdout.split()
    if "with-fingerprint" not in current:
        command = ["authselect", "enable-feature", "with-fingerprint"]
        if not image:
            command.append("--backup=moos-before-fingerprint-login")
        run(command, check=True)
    stack = (root / "etc/pam.d/system-auth").read_text()
    if not re.search(r"^auth\s+sufficient\s+pam_fprintd\.so(?:\s|$)", stack, re.MULTILINE):
        raise ValueError("authselect did not provide fingerprint authentication")
    if not re.search(r"^auth\s+sufficient\s+pam_unix\.so(?:\s|$)", stack, re.MULTILINE):
        raise ValueError("authselect password fallback is absent")
    auth_target, derived = stack_plan(root)
    # Publish the referenced stack before the greeter starts referring to it.
    if not auth_target.exists() or auth_target.read_text() != derived:
        atomic_write(auth_target, derived)
    if not target.exists() or target.read_text() != configured:
        atomic_write(target, configured)
    if Path("/usr/sbin/restorecon").exists():
        run(["/usr/sbin/restorecon", str(auth_target), str(target)], check=True)
    run(["authselect", "check"], check=True)
    print("MoOS: greeter accepts supplied password or fingerprint; authselect policy and password fallback retained")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--image", action="store_true")
    args = parser.parse_args()
    if args.check:
        check_configuration(Path("/"))
        subprocess.run(["authselect", "check"], check=True)
    elif args.apply:
        if os.geteuid() != 0:
            parser.error("administrator authentication is required")
        if args.image and (not Path("/run/.containerenv").exists() or Path("/run/ostree-booted").exists()):
            parser.error("--image requires an unbooted build container")
        apply(Path("/"), image=args.image)
    else:
        print(local_login(Path("/usr/lib/pam.d/plasmalogin").read_text()), end="")


if __name__ == "__main__":
    main()
