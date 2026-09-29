#!/bin/busybox.static sh
# shellcheck shell=sh
# Mira's on-device voice client, supervised by busybox init through one inittab line:
#
#     ::respawn:/data/mira/run.sh
#
# This script stays in the foreground for as long as it lives and is never setsid'd or
# daemonized: under busybox init a respawn that forks away looks like an exit and init starts
# another. It runs the agent as its own child and waits for it, so a crash never reaches init;
# restarts are paced here with exponential backoff (2 s doubling to 60 s, back to 2 s once a run
# has stayed up for 5 minutes). A TERM (shutdown, or a rollback's kill) is passed on to the agent,
# which closes its Live session and the device API cleanly before exiting.
#
# Maintenance: while /run/mira/hold exists the agent is not started.
BB=/bin/busybox.static
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
DIR=/data/mira
LOG=$DIR/agent.log
MAX=262144                      # rotate agent.log to agent.log.1 above ~256 KB
LAN=${MIRA_LAN:-192.168.3.0/24} # the only network the desktop heartbeat/sync may come from
STATE=/run/mira
HEALTHY=300
child=

log() { echo "$($BB date -u +%Y-%m-%dT%H:%M:%SZ) run.sh: $*" >> $LOG; }

stop() {
	[ -n "$child" ] && kill -TERM "$child" 2>/dev/null && wait "$child"
	log "stopped by signal"
	exit 0
}
trap stop TERM INT
trap '' HUP

while [ ! -e /run/techo5/ready ]; do $BB sleep 1; done

# TECHO5's boot leaves the loopback interface down (measured 2026-09-29: lo DOWN, no 127.0.0.1).
# This client reaches echod's API on the unit's own address, which the kernel routes through lo,
# so without it every takeover connection times out. Bringing lo up changes nothing else.
case "$(ip link show lo 2>/dev/null)" in
	*UP*) ;;
	*) ip link set lo up && log "loopback: lo brought up" ;;
esac
ip -4 addr show dev lo 2>/dev/null | grep -q 127.0.0.1 || ip addr add 127.0.0.1/8 dev lo 2>/dev/null
while [ ! -e $DIR/agent.py ] || [ ! -x $DIR/venv/bin/python ]; do $BB sleep 5; done
$BB mkdir -p $STATE
umask 077

# Survives a respawn of this script within one boot; /run is a tmpfs, so every boot starts at 2 s.
delay=$($BB cat $STATE/backoff 2>/dev/null)
case "$delay" in ''|*[!0-9]*) delay=2 ;; esac

while true; do
	while [ -e $STATE/hold ]; do $BB sleep 5; done

	# techo5-firewall rebuilds INPUT (policy DROP) at every boot without this port.
	if ! iptables-legacy -C INPUT -p tcp --dport 8765 -s "$LAN" -j ACCEPT 2>/dev/null; then
		iptables-legacy -I INPUT -p tcp --dport 8765 -s "$LAN" -j ACCEPT && log "firewall: 8765 open to $LAN"
	fi

	size=$($BB stat -c %s $LOG 2>/dev/null || echo 0)
	if [ "$size" -gt $MAX ]; then
		$BB cp -f $LOG $LOG.1 && : > $LOG
		$BB chmod 600 $LOG.1
	fi

	start=$($BB date +%s)
	echo "$start" > $STATE/started
	log "starting agent (restart delay now ${delay}s)"
	cd "$DIR" || exit 1
	# shellcheck disable=SC2094 # python appends to the log it is told about; nothing reads it here
	MIRA_LOG=$LOG $DIR/venv/bin/python -u -X faulthandler $DIR/agent.py >> $LOG 2>&1 &
	child=$!
	wait "$child"
	rc=$?
	child=
	ran=$(( $($BB date +%s) - start ))
	if [ $ran -ge $HEALTHY ]; then
		delay=2
	fi
	log "agent exited rc=$rc after ${ran}s; restarting in ${delay}s"
	$BB sleep $delay
	delay=$(( delay * 2 ))
	[ $delay -gt 60 ] && delay=60
	echo "$delay" > $STATE/backoff
done
