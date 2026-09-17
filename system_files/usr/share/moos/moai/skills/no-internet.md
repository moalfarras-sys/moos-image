---
id: no-internet
title_en: No internet, or an unstable connection
title_ar: لا يوجد إنترنت، أو الاتصال غير مستقر
use_when: Pages do not load, Wi-Fi does not connect, the connection drops, or only some names fail to resolve.
---
## Look first
1. `get_system_status` — is Wi-Fi on?
2. `network_status` — which device is connected, does it have an address, is there a default route, which DNS servers answer.

## Steps
1. Wi-Fi is off and the person uses Wi-Fi → `toggle_wifi` value=`on`.
2. No device is connected → `open_settings` page=`network` so the person can choose a network and type its password. You cannot type a password for them and must not ask for it.
3. Connected with an address, but no default route or no DNS → `net_doctor`. It checks devices, route, DNS, reachability and Tailscale; read its verdict before anything else.
4. Addresses and route are right but names do not resolve → `unit_status` name=`systemd-resolved.service`, then `read_journal` unit=`systemd-resolved.service` priority=`warning` since=`1h` lines=60.
5. No device is managed at all → `unit_status` name=`NetworkManager.service`, then `read_journal` unit=`NetworkManager.service` priority=`warning` since=`boot` lines=80 and look for the reason: authentication failed, no carrier, or a DHCP timeout.
6. Authentication failed → the saved password is wrong: `open_settings` page=`network`.
7. "No carrier" on a cable → the cable or the router port. A DHCP timeout on every network → restart the router.

## Never
- Never use `toggle_wifi` value=`off` to "reset" the connection when the person may be reaching this computer over the network (Mo PC Remote): it cuts them off. The system asks them first for exactly that reason.

## Stop and tell the person when
- This computer has an address, a route and working DNS, and only some sites fail: the problem is not on this machine. Say so.
