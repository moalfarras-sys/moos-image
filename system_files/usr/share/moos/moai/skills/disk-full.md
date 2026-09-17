---
id: disk-full
title_en: The disk is full, or space is running out
title_ar: القرص ممتلئ أو المساحة تنفد
use_when: An install or update fails for lack of space, the person sees a low-space warning, or asks what takes up the disk.
---
## Know this first
MoOS is delivered as a read-only system image. `/` always reads 100% full — that is the image, not the disk. The space that matters is `/var`, which holds the person's home folder, their apps and containers.

## Look first
1. `disk_status` — read the `/var` line: size, used, free.
2. `list_installed_apps` — large apps and games the person may no longer use.

## Steps
1. `optimize_system`. It asks first, then removes unused app runtimes, unused container images and old logs. It never touches personal files.
2. For each app the person names as unused → `uninstall_app` app_id=<the id from list_installed_apps>. It asks first.
3. Run `disk_status` again and report the difference in GB.
4. Still full → what remains is personal files: Downloads, videos, game libraries, the Trash. Tell the person where to look. You have no tool that deletes personal files, by design, and must not suggest a command that does.

## Stop and tell the person when
- `/var` has plenty of free space and an install still fails: the cause is not disk space → `read_moos_log` name=`store`.
