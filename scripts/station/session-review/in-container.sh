#!/usr/bin/env bash
# Runs INSIDE the review container (see review.sh). Lays the worktree's session surfaces over a
# stock Plasma, then renders each requested shot under Xvfb with the real greeter binaries:
#   lock    /usr/libexec/kscreenlocker_greet --testing
#   logout  /usr/libexec/ksmserver-logout-greeter --windowed
#   login   /usr/libexec/plasma-login-greeter --test
#   loginscene  /usr/bin/plasma-login-wallpaper   (the scene a compositor stacks under it)
#
# One line of /work/shots.txt per shot:  <surface> <name> [key=value ...]
# (or `probe <name>`: plasma_seams.py's real-greeter load test, with its negative control)
#   lang=ar|en|de        session language (default ar)
#   size=1536x864        LOGICAL size; the X screen is size*scale device pixels
#   scale=1              QT_SCALE_FACTOR (2.5 is the station's 4K panel)
#   theme=org.moos.ui2.aurora   a MoOS family: its colour scheme, Plasma style and wallpaper
#                        are read from theme-profiles.tsv (the session surfaces take their
#                        colours from the PLASMA STYLE, so a scheme alone proves nothing)
#   wallpaper=MoOSUI2Graphite   override the family's wallpaper
#   state=idle|active|typed|failed      (lock/login) what the capture shows
#   mode=all|shutdown|reboot|logout     (logout) which prompt
#   motion=1|0           0 writes AnimationDurationFactor=0
#   face=0|1             1 gives the review user a photo
#   wait=8 after=2.5     seconds before input / before capture
#   xi="move 10 10 ..."  extra xinput.py commands (logical pixels) before the capture
set -uo pipefail
SRC=/src
OUT=/out
HERE="$SRC/scripts/station/session-review"

overlay() {
    local share="$SRC/system_files/usr/share"
    cp -a "$share/pixmaps/." /usr/share/pixmaps/
    cp -a "$share/color-schemes/." /usr/share/color-schemes/
    cp -a "$share/plasma/." /usr/share/plasma/
    cp -a "$share/wallpapers/." /usr/share/wallpapers/
    cp -a "$SRC/system_files/usr/lib64/qt6/qml/." /usr/lib64/qt6/qml/
    # What build.sh does: without this the compiled-in Breeze copies win over MoOS's files.
    sed -i '/^prefer /d' /usr/lib64/qt6/qml/org/kde/breeze/components/qmldir
    cp -a "$SRC/system_files/etc/xdg/." /etc/xdg/
    install -D -m 0644 "$SRC/system_files/usr/lib/plasmalogin/defaults.conf" \
        /usr/lib/plasmalogin/defaults.conf
    if [ -n "${SEAM_SET:-}" ]; then
        # Review a Plasma-next seam variant's text on this Plasma. It only LOADS when the
        # container's Plasma is the one the set was derived for.
        cp -a "$SRC/build_files/plasma-seams/$SEAM_SET/usr/." /usr/
    fi
    fc-cache -f >/dev/null 2>&1
    # The review user is the HOST user's uid (podman --userns=keep-id), so every PNG and log
    # it writes into the mounted out/work directories belongs to the person who ran this.
    local uid="${REVIEW_UID:-1000}"
    grep -v -E "^[^:]*:[^:]*:${uid}:" /etc/passwd > /etc/passwd.review
    printf 'mo:x:%s:%s:Mo:/work:/bin/bash\n' "$uid" "$uid" >> /etc/passwd.review
    cat /etc/passwd.review > /etc/passwd
    grep -q -E "^[^:]*:[^:]*:${uid}:" /etc/group || printf 'mo:x:%s:\n' "$uid" >> /etc/group
    if [ "${REVIEW_USERS:-1}" -gt 1 ]; then
        # More accounts for the login greeter's user list (it shows every uid >= 1000).
        printf 'sara:x:%s:%s:سارة:/home/sara:/bin/bash\n' $((uid + 1)) "$uid" >> /etc/passwd
        printf 'omar:x:%s:%s:Omar Khalil:/home/omar:/bin/bash\n' $((uid + 2)) "$uid" >> /etc/passwd
    fi
}

shot() {
    local surface="$1" name="$2"; shift 2
    local lang=ar size=1536x864 scale=1 theme=org.moos.ui2.aurora wallpaper=""
    local state=idle mode=all motion=1 face=0 wait=8 after=2.5 xi=""
    local kv
    for kv in "$@"; do
        case "$kv" in
            lang=*|size=*|scale=*|theme=*|wallpaper=*|state=*|mode=*|motion=*|face=*|wait=*|after=*|xi=*)
                printf -v "${kv%%=*}" '%s' "${kv#*=}" ;;
            *) echo "unknown option: $kv" >&2; return 2 ;;
        esac
    done
    local lnf="$theme" family style profile_wallpaper
    IFS=$'\t' read -r _ family style _ _ _ _ _ profile_wallpaper _ < <(
        awk -F'\t' -v id="$theme" '$1 == id' "$SRC/system_files/usr/share/moos/theme-profiles.tsv")
    [ -n "${family:-}" ] || { echo "unknown theme: $theme" >&2; return 2; }
    [ -n "$wallpaper" ] || wallpaper="$profile_wallpaper"
    local locale
    case "$lang" in
        ar) locale=ar_SA.UTF-8 ;;
        de) locale=de_DE.UTF-8 ;;
        *) locale=en_US.UTF-8 ;;
    esac
    local w="${size%x*}" h="${size#*x}"
    local pw ph
    pw="$(awk -v v="$w" -v s="$scale" 'BEGIN{printf "%d", v*s+0.5}')"
    ph="$(awk -v v="$h" -v s="$scale" 'BEGIN{printf "%d", v*s+0.5}')"

    local work; work="$(mktemp -d /work/shot.XXXXXX)"
    local home="$work/home"
    mkdir -p "$home/.config" "$home/.local/share" "$home/.cache" "$work/run"
    chmod 700 "$work/run"

    # A .colors file IS a kdeglobals: applying a scheme copies these groups.
    cp "/usr/share/color-schemes/$family.colors" "$home/.config/kdeglobals" || return 2
    {
        printf '\n[KDE]\nLookAndFeelPackage=%s\n' "$lnf"
        [ "$motion" = 0 ] && printf 'AnimationDurationFactor=0\n'
    } >> "$home/.config/kdeglobals"
    printf '[Theme]\nname=%s\n' "$style" > "$home/.config/plasmarc"
    cat > "$home/.config/kscreenlockerrc" <<EOF
[Greeter]
WallpaperPlugin=org.kde.image

[Greeter][Wallpaper][org.kde.image][General]
Image=/usr/share/wallpapers/$wallpaper
EOF
    if [ "$face" = 1 ]; then
        magick -size 512x512 radial-gradient:'#F2C9A0-#7A4B2A' "$home/.face.icon" 2>/dev/null
        ln -sf .face.icon "$home/.face"
    fi

    local actions=""
    case "$surface:$state" in
        *:idle) ;;
        *:active) actions="move $((w*4/5)) $((h*4/5)) move $((w*4/5+8)) $((h*4/5+6)) sleep 0.4 move $((w*4/5+2)) $((h*4/5+2))" ;;
        *:typed) actions="move $((w*4/5)) $((h*4/5)) move $((w*4/5+8)) $((h*4/5+6)) sleep 1.2 focus type moos2026" ;;
        *:failed) actions="move $((w*4/5)) $((h*4/5)) move $((w*4/5+8)) $((h*4/5+6)) sleep 1.2 focus type wrongpass key Return" ;;
        *) echo "unknown state: $state" >&2; return 2 ;;
    esac

    local command
    case "$surface" in
        lock) command="/usr/libexec/kscreenlocker_greet --testing" ;;
        logout)
            command="/usr/libexec/ksmserver-logout-greeter --windowed --lookandfeel $lnf"
            case "$mode" in
                shutdown) command="$command --shutdown" ;;
                reboot) command="$command --reboot" ;;
                logout) command="$command --logout" ;;
            esac ;;
        login) command="$HERE/login-greeter.sh $wallpaper" ;;
        # The login SCENE alone: the wallpaper process that a compositor stacks under the
        # greeter. It reads the image's own /usr/lib/plasmalogin/defaults.conf.
        loginscene) command="/usr/bin/plasma-login-wallpaper" ;;
        *) echo "unknown surface: $surface" >&2; return 2 ;;
    esac

    cat > "$work/session.sh" <<EOF
#!/usr/bin/env bash
$command >"$work/surface.log" 2>&1 &
sleep "$wait"
python3 "$HERE/xinput.py" scale "$scale" $actions $xi 2>>"$work/input.log"
sleep "$after"
import -silent -window root "$OUT/$name.png" 2>>"$work/shot.log"
EOF
    chmod +x "$work/session.sh"

    env -i PATH=/usr/bin:/usr/sbin:/bin HOME="$home" USER=mo LOGNAME=mo \
        XDG_CONFIG_HOME="$home/.config" XDG_DATA_HOME="$home/.local/share" \
        XDG_CACHE_HOME="$home/.cache" XDG_RUNTIME_DIR="$work/run" \
        XDG_CURRENT_DESKTOP=KDE KDE_FULL_SESSION=true KDE_SESSION_VERSION=6 XDG_SESSION_TYPE=x11 \
        LANG="$locale" LC_ALL="$locale" LANGUAGE="$lang" \
        LIBGL_ALWAYS_SOFTWARE=1 QT_QPA_PLATFORM=xcb QML_DISABLE_DISK_CACHE=1 \
        LOGIN_WALLPAPER="${LOGIN_WALLPAPER:-0}" \
        QT_SCALE_FACTOR="$scale" QT_FORCE_STDERR_LOGGING=1 \
        timeout 90 dbus-run-session -- \
        xvfb-run -a -s "-screen 0 ${pw}x${ph}x24 -nolisten tcp" "$work/session.sh" \
        >"$work/session.out" 2>&1
    if [ -s "$OUT/$name.png" ]; then
        echo "rendered $name.png (${pw}x${ph} device, scale $scale) at ${SECONDS}s"
    else
        echo "NO FRAME for $name"; tail -n 5 "$work/session.out" "$work/shot.log" 2>/dev/null
    fi
    # The QML engine's own verdict, minus the noise every offscreen Plasma process prints.
    grep -E "qml|QML|Error|error|ReferenceError|TypeError|Unable to assign|is not a type|not installed|Cannot" \
        "$work/surface.log" 2>/dev/null \
        | grep -v -E "kf.windowsystem|kf.plasma.quick|org.kde.plasma.workspace.keyboardlayout|qt.qpa|Qt Quick Layouts: Detected recursive|xkbcommon|DBus|dbus|kscreen|qt.dbus|ksmserver|PowerDevil|org.freedesktop|portal|Solid|UPower|QSocketNotifier|kf.kio|kf.config|kf.coreaddons|kf.i18n|pulse|PipeWire|canberra|battery" \
        | sed -E "s#file://##" | sort | uniq -c | sort -rn | head -14
    cp "$work/surface.log" "$OUT/$name.log" 2>/dev/null
    return 0
}

# `probe <name>` in shots.txt: the build's own verdict on this overlay — the real greeter,
# offscreen, no session bus (build_files/plasma_seams.py probe-lockscreen) — and then the
# same probe against a copy with one type renamed, which MUST fail. A probe that cannot go
# red proves nothing about the run that went green.
probe() {
    local name="$1" log="$OUT/$1.log"
    {
        echo "== plasma: $(rpm -q plasma-workspace plasma-desktop kscreenlocker | tr '\n' ' ')"
        echo "== probe: the overlay as installed"
        python3 "$SRC/build_files/plasma_seams.py" probe-lockscreen; echo "exit=$?"
        echo "== negative control: SessionManagementScreen instantiates a type that does not exist"
        local dir=/usr/lib64/qt6/qml/org/kde/breeze/components
        cp "$dir/SessionManagementScreen.qml" /tmp/sms.keep
        sed -i 's/^    UserList {$/    UserListRemovedUpstream {/' "$dir/SessionManagementScreen.qml"
        python3 "$SRC/build_files/plasma_seams.py" probe-lockscreen; echo "exit=$?"
        cp /tmp/sms.keep "$dir/SessionManagementScreen.qml"
    } > "$log" 2>&1
    grep -E "^== |^exit=|is not a type|Failed to load|loaded|OK|FAIL" "$log" | cut -c1-200
}

if [ "${1:-}" = "--shots" ]; then
    # Second entry, as the review user.
    while IFS= read -r line || [ -n "$line" ]; do
        case "$line" in ''|'#'*|probe\ *) continue ;; esac
        eval "set -- $line"
        shot "$@"
    done < /work/shots.txt
    exit 0
fi

SECONDS=0
overlay
echo "overlay ready in ${SECONDS}s ($(rpm -q plasma-workspace))"
# Probes edit the overlay to prove they can fail, so they run here, as root, before the shots.
while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in probe\ *) eval "set -- $line"; shift; probe "$@" ;; esac
done < /work/shots.txt
exec runuser -u mo -- bash "$HERE/in-container.sh" --shots
