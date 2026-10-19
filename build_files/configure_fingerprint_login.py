#!/usr/bin/env python3
"""Use authselect's local-authentication stack for the local login greeter.

The vendor greeter uses password-auth (deliberately without fingerprint), while
the locker uses fingerprint-auth. Keep the vendor conversation/session code and
every account/password/session rule; change only the local auth substack.
Never overwrite a site's PAM customization or regenerate PAM by hand.
"""
import argparse
import os
from pathlib import Path
import re
import subprocess
import tempfile


AUTH = re.compile(r"^(auth\s+substack\s+)password-auth([ \t]*)$", re.MULTILINE)


def local_login(vendor: str) -> str:
    if len(AUTH.findall(vendor)) != 1:
        raise ValueError("unrecognized vendor login authentication stack")
    for facility in ("account", "password", "session"):
        if not re.search(rf"^{facility}\s+include\s+password-auth\s*$", vendor, re.MULTILINE):
            raise ValueError(f"missing vendor {facility} stack")
    return AUTH.sub(r"\1system-auth\2", vendor)


def plan(root: Path) -> tuple[Path, str]:
    vendor = (root / "usr/lib/pam.d/plasmalogin").read_text()
    configured = local_login(vendor)
    target = root / "etc/pam.d/plasmalogin"
    if target.is_symlink():
        raise ValueError("refusing a local PAM symlink")
    if target.exists() and target.read_text() not in (vendor, configured):
        raise ValueError("preserving customized local PAM configuration; review required")
    return target, configured


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
    if not target.exists() or target.read_text() != configured:
        fd, temporary = tempfile.mkstemp(prefix=".moos-login-", dir=target.parent)
        try:
            with os.fdopen(fd, "w") as out:
                out.write(configured)
                out.flush()
                os.fsync(out.fileno())
                os.fchmod(out.fileno(), 0o644)
            os.replace(temporary, target)
        finally:
            Path(temporary).unlink(missing_ok=True)
    if Path("/usr/sbin/restorecon").exists():
        run(["/usr/sbin/restorecon", str(target)], check=True)
    run(["authselect", "check"], check=True)
    print("MoOS: local login uses authselect system-auth; password fallback retained")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--image", action="store_true")
    args = parser.parse_args()
    if args.apply:
        if os.geteuid() != 0:
            parser.error("administrator authentication is required")
        if args.image and (not Path("/run/.containerenv").exists() or Path("/run/ostree-booted").exists()):
            parser.error("--image requires an unbooted build container")
        apply(Path("/"), image=args.image)
    else:
        print(local_login(Path("/usr/lib/pam.d/plasmalogin").read_text()), end="")


if __name__ == "__main__":
    main()
