---
id: oracle-cloud-workstation
title_en: Oracle cloud development workstation and Mo PC Remote
title_ar: محطة تطوير Oracle السحابية وMo PC Remote
use_when: The owner uses an Oracle A1 or another always-on cloud MoOS computer for development, especially through Mo PC Remote from a phone or browser.
---
## Know this first
- This computer may draw the desktop in software. A smooth remote session matters more than
  desktop effects, and sustained memory pressure matters more than a high used-memory number.
- Swap here is compressed memory, used on purpose for pages nobody is touching. A few gigabytes
  in swap with plenty of memory available is a healthy machine, not a slow one.
- While someone watches a busy screen the compositor is the largest cost, larger than the video
  encoder; with nobody watching both rest. A lower picture size helps the network, not that cost.
- A computer with no monitor draws a desktop of a size its owner chose. A phone-sized desktop
  reaches the phone pixel for pixel, so text is sharper and the picture smoother; the larger one
  gives a computer's browser more room. The owner changes it from a terminal with the cloud
  desktop tool's display setting, and it applies the next time they sign in, never at once.
- `/var` is the real writable disk. Do not diagnose the small read-only `/` view as a full disk.
- Mo PC Remote should stay private through the paired network path. Never recommend exposing its
  local port directly to the public internet.

## Steps
1. Read `os_state`, then `device_report`, so the advice matches the running architecture, edition,
   signed origin, staged update and measured resources.
2. Read `memory_status`, `top_processes` by=`memory`, then `top_processes` by=`cpu`. Available memory
   and pressure are the decision: swap use alone can be old and harmless. If one graphical app owns
   more than half of RAM or a core while idle, name it and suggest closing that app; do not suggest a
   restart as the first repair.
3. If that list shows `pipewire` holding hundreds of megabytes, the remote has left old screen
   connections open, a fault a later update fixes. Say so, and offer
   `remote_control` value=`restart`: the picture drops for a few seconds and comes back, so ask
   first if the owner is watching through the remote.
4. Read `disk_status`. Keep useful headroom on `/var` for repositories, containers and updates. If it
   is below 10% free, read skill `disk-full`.
5. Read `list_failed_units`. For a failed user application, call `unit_status`
   name=<listed_unit> user=`true`, passing the exact listed unit name. A recent out-of-memory failure
   plus a dominant process is evidence, not a reason to tune the kernel blindly.
6. For phone or browser access, read `unit_status` name=`mo-remote-personal.service` user=`true`,
   `read_moos_log` name=`remote`, and `network_status`. Report whether the service is healthy and the
   private path exists. If the picture is laggy but connected, offer `fast_remote` value=`on`; it asks
   first and temporarily reduces visual effects. Do not turn the remote off while the owner may be
   using it.
7. If `os_state` says a signed update is already staged, explain that a later owner-chosen restart
   applies it. Never restart an always-on development station for the owner.

## Stop and tell the person when
- Memory pressure is low, `/var` has headroom, no service is failed and Remote is healthy: the host
  is ready; ask which development workload or remote action feels slow rather than applying generic
  tuning.
- Remote is not paired or its private network path is absent: say what is missing. Do not replace it
  with a public port.
