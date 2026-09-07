#!/usr/bin/env bash
# Measure the things this branch claims to improve, so before/after is evidence
# rather than opinion. Run identically on both sides; diff the two outputs.
#
#   bash tests/measure_oracle_baseline.sh > /var/home/moos/measure-before.txt
#   ... change something, reboot ...
#   bash tests/measure_oracle_baseline.sh > /var/home/moos/measure-after.txt
#
# Everything here is read-only. Nothing is inferred: each number names the
# command that produced it.

echo "MoOS Oracle measurement — $(date -Is)"
echo "boot id: $(cat /proc/sys/kernel/random/boot_id 2>/dev/null)"
echo "uptime : $(uptime -p 2>/dev/null)"
echo "deployment: $(rpm-ostree status --json 2>/dev/null | python3 -c 'import json,sys
d=json.load(sys.stdin)
b=[x for x in d["deployments"] if x.get("booted")]
print(b[0].get("version","?") if b else "?")' 2>/dev/null)"

echo
echo "== memory =="
free -m | awk '/^Mem:/ {printf "  total=%s MiB  used=%s MiB  available=%s MiB\n", $2, $3, $7}'
free -m | awk '/^Swap:/ {printf "  swap_used=%s MiB of %s MiB\n", $3, $2}'
printf '  psi_memory_some_avg60: %s\n' "$(awk '/^some/{print $3}' /proc/pressure/memory 2>/dev/null)"
printf '  psi_cpu_some_avg60   : %s\n' "$(awk '/^some/{print $3}' /proc/pressure/cpu 2>/dev/null)"
printf '  psi_io_some_avg60    : %s\n' "$(awk '/^some/{print $3}' /proc/pressure/io 2>/dev/null)"

echo
echo "== the MoOS-owned desktop processes (RSS MiB) =="
for c in kwin_wayland plasmashell baloo_file kded6 xdg-desktop-portal-kde \
         kactivitymanagerd plasma-keyboard MoRemotePersona moai-control; do
    pids=$(pgrep -x "$c" 2>/dev/null | paste -sd, -)
    if [ -n "$pids" ]; then
        rss=$(ps -o rss= -p "$pids" 2>/dev/null | awk '{s+=$1} END {printf "%.1f", s/1024}')
        printf '  %-24s %8s MiB   (pid %s)\n' "$c" "$rss" "$pids"
    else
        printf '  %-24s %8s\n' "$c" "not running"
    fi
done

echo
echo "== cgroup accounting for the session's heaviest units =="
for u in plasma-kwin_wayland.service plasma-plasmashell.service \
         plasma-baloorunner.service app-baloo_file@autostart.service; do
    cur=$(systemctl --user show "$u" -p MemoryCurrent --value 2>/dev/null)
    case "$cur" in
        ''|'[not set]'|18446744073709551615) printf '  %-38s -\n' "$u" ;;
        *) printf '  %-38s %.1f MiB\n' "$u" "$(echo "$cur" | awk '{print $1/1048576}')" ;;
    esac
done

echo
echo "== file indexing =="
printf '  budget says      : %s\n' "$(moos-visual-tier --json 2>/dev/null | python3 -c 'import json,sys;print(json.load(sys.stdin)["budget"]["file_indexing"])' 2>/dev/null)"
printf '  only basic index : %s\n' "$(grep -h '^only basic indexing' /etc/xdg/baloofilerc "$HOME/.config/baloofilerc" 2>/dev/null | tail -1)"
printf '  index db size    : %s\n' "$(du -sh "$HOME/.local/share/baloo" 2>/dev/null | cut -f1)"
balooctl6 status 2>/dev/null | sed 's/^/  /' | head -5

echo
echo "== adaptive budget (the one authority) =="
moos-visual-tier --json 2>/dev/null | python3 -c 'import json,sys
d = json.load(sys.stdin)
print("  tier:", d.get("tier"), "  cores:", d["facts"]["cores"], "  mem:", d["facts"]["memory_gib"], "GiB")
for k, v in sorted(d.get("budget", {}).items()):
    print(f"  budget.{k:20} {v}")' 2>/dev/null

echo
echo "== boot =="
systemd-analyze 2>/dev/null | sed 's/^/  /'
echo "  --- slowest units ---"
systemd-analyze blame 2>/dev/null | head -8 | sed 's/^/  /'

echo
echo "== health =="
printf '  failed system units: %s\n' "$(systemctl --failed --no-legend --no-pager 2>/dev/null | wc -l)"
systemctl --failed --no-legend --no-pager 2>/dev/null | sed 's/^/      /'
printf '  failed user units  : %s\n' "$(systemctl --user --failed --no-legend --no-pager 2>/dev/null | wc -l)"
systemctl --user --failed --no-legend --no-pager 2>/dev/null | sed 's/^/      /'
printf '  OOM kills this boot: %s\n' "$(journalctl -b --no-pager 2>/dev/null | grep -ciE 'oom-kill|Killed process|out of memory')"
printf '  journal errors     : %s\n' "$(journalctl -b -p err --no-pager 2>/dev/null | wc -l)"
