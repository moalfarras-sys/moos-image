#!/usr/bin/env bash
# Shared host-side VirGL display setup for x86 graphical release proofs.
# The guest must render through virtio-gpu's 3D path; recent Plasma/Mesa builds
# are not stable when their entire compositor runs in nested TCG llvmpipe.

MOOS_QEMU_WINDOW_TITLE="${MOOS_QEMU_WINDOW_TITLE:-MoOS release proof}"
export MOOS_QEMU_WINDOW_TITLE

moos_start_virgl_display() {
    local work="$1"
    local evidence="$2"
    local display_file="$work/xvfb-display"
    local tool=""

    for tool in Xvfb xdpyinfo glxinfo import xwininfo; do
        command -v "$tool" >/dev/null || {
            echo "QEMU VIRGL FATAL: required host tool is missing: $tool" >&2
            return 1
        }
    done

    # A full Plasma boot under TCG is not a valid health measurement. Run
    # 33686491949 reached the real greeter through VirGL, then system services
    # timed out because software CPU emulation took minutes of wall clock for
    # seconds of guest work. Require Linux's hardware accelerator so unit
    # deadlines, animations and reboot timing are measured on a real clock.
    {
        printf 'accelerator=kvm\n'
        printf 'host-arch=%s\n' "$(uname -m)"
        qemu-system-x86_64 -accel help
        ls -l /dev/kvm 2>&1 || true
    } > "$evidence/host-kvm.txt"
    [ -c /dev/kvm ] || {
        echo "QEMU KVM FATAL: the x86 release runner has no /dev/kvm" >&2
        return 1
    }
    grep -Fxq kvm < <(qemu-system-x86_64 -accel help) || {
        echo "QEMU KVM FATAL: this QEMU build has no KVM accelerator" >&2
        return 1
    }
    if [ ! -r /dev/kvm ] || [ ! -w /dev/kvm ]; then
        sudo chmod a+rw /dev/kvm
    fi
    [ -r /dev/kvm ] && [ -w /dev/kvm ] || {
        echo "QEMU KVM FATAL: the runner cannot access /dev/kvm" >&2
        return 1
    }
    stat -c 'device=%n mode=%a owner=%U group=%G' /dev/kvm \
        >> "$evidence/host-kvm.txt"

    : > "$display_file"
    exec 3>"$display_file"
    Xvfb -displayfd 3 -screen 0 1600x1000x24 -nolisten tcp \
        >"$evidence/xvfb.log" 2>&1 &
    xvfb_pid=$!
    exec 3>&-

    for _ in $(seq 1 100); do
        if ! kill -0 "$xvfb_pid" 2>/dev/null; then
            echo "QEMU VIRGL FATAL: Xvfb exited during startup" >&2
            tail -80 "$evidence/xvfb.log" >&2 || true
            return 1
        fi
        if [ -s "$display_file" ]; then
            export DISPLAY=":$(tr -d '\r\n' < "$display_file")"
            if xdpyinfo -display "$DISPLAY" >/dev/null 2>&1; then
                break
            fi
        fi
        sleep 0.1
    done
    [ -n "${DISPLAY:-}" ] && xdpyinfo -display "$DISPLAY" >/dev/null 2>&1 || {
        echo "QEMU VIRGL FATAL: Xvfb display did not become ready" >&2
        return 1
    }

    # qemu-system-gui creates the accelerated virtio-vga-gl context through
    # this X display. Keep the renderer report with the boot evidence so a
    # runner image change cannot silently turn graphical proof into guesswork.
    LIBGL_ALWAYS_SOFTWARE=1 glxinfo -B > "$evidence/host-opengl.txt" 2>&1 || {
        echo "QEMU VIRGL FATAL: the CI host cannot create an OpenGL context" >&2
        tail -80 "$evidence/host-opengl.txt" >&2 || true
        return 1
    }
    grep -Fq "OpenGL renderer string:" "$evidence/host-opengl.txt" || {
        echo "QEMU VIRGL FATAL: OpenGL renderer identity is unavailable" >&2
        return 1
    }
}

moos_capture_virgl_display() {
    local output="$1"
    local log="${output%.*}-capture.log"
    local window_id=""

    # QEMU's monitor screendump cannot read a virtio-vga-gl dmabuf scanout on
    # current hosted runners. Capture the mapped GTK display instead: these are
    # the actual pixels a person sees, including any host-side presentation
    # failure that an internal guest framebuffer dump would miss.
    xwininfo -display "$DISPLAY" -root -tree > "${output%.*}-windows.txt" 2>&1 || true
    : > "$log"
    for _ in $(seq 1 20); do
        window_id="$(xwininfo -display "$DISPLAY" -name "$MOOS_QEMU_WINDOW_TITLE" -int \
            2>>"$log" | awk '/Window id:/ {print $4; exit}')"
        [ -n "$window_id" ] || { sleep 0.5; continue; }
        rm -f -- "$output"
        if import -silent -display "$DISPLAY" -window "$window_id" "$output" \
                >>"$log" 2>&1 && [ -s "$output" ]; then
            return 0
        fi
        sleep 0.5
    done
    echo "QEMU VIRGL FATAL: the mapped GTK window could not be captured" >&2
    tail -40 "$log" >&2 || true
    return 1
}

moos_stop_virgl_display() {
    if [ -n "${xvfb_pid:-}" ] && kill -0 "$xvfb_pid" 2>/dev/null; then
        kill "$xvfb_pid" 2>/dev/null || true
        wait "$xvfb_pid" 2>/dev/null || true
    fi
    xvfb_pid=""
}
