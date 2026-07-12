# Mo PC Remote security

- SELinux remains enforcing; no allow rule has been added because no observed AVC requires one.
- firewalld remains enabled. Never use a catch-all port range as the application's policy; Sunshine ports must be a dedicated service limited to the trusted LAN zone when the package is integrated.
- No daemon runs permanently as root. No `cap_sys_admin` is granted.
- uinput is `0660 root:input` plus logind `uaccess`; the ydotool socket is mode 0600 in `%t`, restricting it to the logged-in user.
- Streaming is disabled by default in the image. The user explicitly starts it.
- The legacy PIN/token scheme lacks device identity and approval and is not sufficient for the selected final design.
- Production pairing must use Sunshine/Moonlight certificate-backed PIN pairing, show the connecting device, allow first-use acceptance, enumerate paired clients and revoke them.
- Bind/discovery is LAN-only by default. Internet exposure requires an explicit VPN configuration; no UPnP or router port forwarding is enabled by MoOS.
- Sensitive power actions should be removed from the legacy API or gated by a narrowly defined polkit action before production use.
