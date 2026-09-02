#!/usr/bin/env bash
# Shared host-side VirGL display setup for x86 graphical release proofs.
# The guest must render through virtio-gpu's 3D path; recent Plasma/Mesa builds
# are not stable when their entire compositor runs in nested TCG llvmpipe.

moos_start_virgl_display() {
    local work="$1"
    local evidence="$2"
    local display_file="$work/xvfb-display"
    local tool=""

    for tool in Xvfb xdpyinfo glxinfo; do
        command -v "$tool" >/dev/null || {
            echo "QEMU VIRGL FATAL: required host tool is missing: $tool" >&2
            return 1
        }
    done

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

moos_stop_virgl_display() {
    if [ -n "${xvfb_pid:-}" ] && kill -0 "$xvfb_pid" 2>/dev/null; then
        kill "$xvfb_pid" 2>/dev/null || true
        wait "$xvfb_pid" 2>/dev/null || true
    fi
    xvfb_pid=""
}
