#!/usr/bin/bash
# The bootc account database lives in /usr/lib/{passwd,group}; /etc contains only
# the mutable overlay. Dracut's generated /etc files therefore know just a few
# initrd users, while udev/tmpfiles rules reference audio, video, render, kvm,
# disk, input, tss and others. Install the vendor database as the initrd's
# ephemeral /etc database so those permissions resolve before switch-root.

check() {
    return 0
}

depends() {
    echo systemd
    return 0
}

install() {
    # systemd and base create small /etc databases before this module runs, so
    # inst_simple would deliberately refuse to replace them. Merge the vendor
    # database first (it owns static IDs and memberships), then retain initrd-
    # specific entries such as root that are not present in /usr/lib.
    local name vendor current merged
    for name in passwd group; do
        vendor="${dracutsysrootdir-}/usr/lib/${name}"
        current="${initdir}/etc/${name}"
        merged="${initdir}/etc/.${name}.moos"
        [ -r "$vendor" ] || return 1
        mkdir -p "${initdir}/etc"
        awk -F: '!seen[$1]++' "$vendor" "$current" > "$merged"
        chmod 0644 "$merged"
        mv -f "$merged" "$current"
    done
}
