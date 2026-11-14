# V3 motion-sensor backport packet

The physical V3 enumerates its LSM6DS3TR-C as `SMOCF05`. The installed
7.2.15 transport and reviewed signed 7.3.3/7.3.4 vendor inputs do not match
that ACPI ID. The sensor therefore remains unbound and SensorProxy exposes
no accelerometer. Adding a modprobe alias cannot supply the driver's match data.

The accepted upstream change is
[53c677faa471be1ebfdbbea87dfa3dbe5b0fa2fb](https://kernel.googlesource.com/pub/scm/linux/kernel/git/jic23/iio/+/53c677faa471be1ebfdbbea87dfa3dbe5b0fa2fb).
The first patch preserves its author, review and sign-off chain. The second
adapts that change and the C99 table prerequisite to the reviewed stock
transport context. `manifest.json` pins both patches, the source fixture and
the complete accepted result. These Linux-derived files retain GPL-2.0-only.

`python3 tests/test_rotation_backport.py` applies the real patch privately with
Git's context checks, compares the entire resulting transport against the accepted source
digest, preserves both existing ACPI identities and refuses reapplication.
This is source preparation, not a compiled or signed kernel payload.

Delivery must use a signed kernel/module admitted by the existing trusted kernel
path, exact RPM provenance, architecture/vermagic and full image/boot checks.
The repository's OCI signing secret does not grant the vendor's kernel-signing
authority. No vendor private kernel key or generic sensor-module signing lane
exists in this project. A new project kernel trust chain would need its own
reviewed signing, enrollment, build and recovery implementation; merely bundling
a self-signed certificate does not make Secure Boot trust it.

The already installed systemd matrix is `-1,0,0;0,-1,0;0,0,1`. Keep its owner;
the earlier firmware SLA0 convention negates Z incorrectly for SensorProxy tilt.
Native KWin owns internal-panel orientation and transforms touch coordinates
using the output transform and scale. Do not add an independent rotation loop,
force-bind a firmware client or change the external-monitor configuration.

After signed delivery, require actual IIO probe/readings, four physical
orientations, tilt, pointer/touch corners, portrait logical dimensions, rotation
lock/tablet policy, external-monitor stability and suspend/reboot durability.
Current native acceptance remains blocked before the first driver probe.
