---
id: slow-system
title_en: The computer is slow or freezes
title_ar: الجهاز بطيء أو يتجمّد
use_when: Everything feels slow, the fans run constantly, apps freeze, or the person asks what is using the machine.
---
## Look first
1. `top_processes` by=`cpu`, then `top_processes` by=`memory`.
2. `memory_status` — read "available" and the pressure lines. A memory "some avg10" above 10 means the machine is short of memory right now; a full swap confirms it.
3. `disk_status` — less than 10% free on `/var` slows updates and apps.
4. `list_failed_units` — a service restarting in a loop burns processor time.

## Steps
1. One app uses most of the processor or memory → name it and suggest closing it. You have no tool that ends a process; say so if asked.
2. Memory pressure is high and swap is full → closing the largest app is the repair. Browser tabs are the usual cause.
3. The disk is nearly full → read skill `disk-full`.
4. A service is failed or looping → read skill `failed-service`.
5. Nothing stands out, and the complaint is stutter in games or video → `gpu_report`, then skill `graphics-and-nvidia`.
6. `os_state` shows a staged version and the computer has been on for weeks → a restart applies the update and clears leaked memory. Suggest it; never restart for the person.

## Stop and tell the person when
- Processor, memory, disk and services all look normal: say the measurements are healthy, and ask what exactly is slow (one app, the network, startup) instead of guessing a repair.
