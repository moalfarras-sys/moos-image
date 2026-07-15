#!/usr/bin/env bash
# Did the update actually land, and does the thing it shipped actually work?
#
# Run this on the LIVE machine after a `bootc upgrade` + reboot. Everything else in
# tests/ checks the image; this checks the *desktop the user is sitting in front
# of*, which is the only place several of this project's bugs have ever been
# visible (see PROJECT_STATE.md — "the shadowed-config trap": the image was right
# and the user still could not type Arabic).
#
#   ./tests/post-update-check.sh
#
# Exits non-zero if any check fails. Every line says what it is checking and, when
# it fails, what that means for the person using the machine.

set -uo pipefail

pass=0
fail=0

ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; pass=$((pass + 1)); }
bad()  { printf '  \033[31m✗\033[0m %s\n' "$1"; fail=$((fail + 1)); }
head_() { printf '\n\033[1m%s\033[0m\n' "$1"; }

head_ "The deployment"

# `bootc status` needs root — as a normal user it prints "This command must be
# executed as the root user" and exits, which made this check report "could not
# read bootc status" on a machine that had booted the right image. `rpm-ostree
# status --json` answers the same question without a password prompt, so ask it
# first and keep bootc as the fallback for a machine that has no rpm-ostree.
booted_digest="$(rpm-ostree status --json 2>/dev/null \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); b=[x for x in d["deployments"] if x.get("booted")]; print(b[0].get("container-image-reference-digest","") if b else "")' 2>/dev/null)"
[ -n "$booted_digest" ] || booted_digest="$(sudo -n bootc status --format json 2>/dev/null \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["status"]["booted"]["image"].get("imageDigest",""))' 2>/dev/null)"
published_digest="$(skopeo inspect docker://ghcr.io/moalfarras-sys/moos-nvidia:latest 2>/dev/null \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["Digest"])' 2>/dev/null)"

if [ -n "$booted_digest" ] && [ "$booted_digest" = "$published_digest" ]; then
    ok "booted image IS the published one ($booted_digest)"
elif [ -n "$booted_digest" ]; then
    bad "booted $booted_digest but the registry publishes $published_digest — the reboot did not take, or a newer build landed since"
else
    bad "could not read bootc status"
fi

# The signature policy is the reason a locally-built image must never be forced on
# to this machine: it is what stops an unsigned one from booting.
if grep -q sigstoreSigned /etc/containers/policy.json 2>/dev/null; then
    ok "signature enforcement is still on (sigstoreSigned)"
else
    bad "signature enforcement is GONE from /etc/containers/policy.json"
fi

head_ "Identity"

. /etc/os-release 2>/dev/null || true
[ "${ID:-}" = "moos" ] && ok "os-release says MoOS (ID=moos, ${VERSION:-?})" \
                       || bad "os-release is not MoOS — it says ID=${ID:-?}"

head_ "MoOS UI2 — the live theme, its pair, and its dashboard"

# Read the selectors Plasma is actually using.  A package under /usr can be
# perfect while ~/.config or ~/.config/kdedefaults keeps the running desktop on
# another theme, so file-presence checks alone cannot prove this section.
theme_lnf="$(kreadconfig6 --file kdeglobals --group KDE --key LookAndFeelPackage 2>/dev/null)"
theme_deco="$(kreadconfig6 --file kwinrc --group org.kde.kdecoration2 --key theme 2>/dev/null)"
theme_scheme="$(kreadconfig6 --file kdeglobals --group General --key ColorScheme 2>/dev/null)"
theme_icons="$(kreadconfig6 --file kdeglobals --group Icons --key Theme 2>/dev/null)"
theme_style="$(kreadconfig6 --file plasmarc --group Theme --key name 2>/dev/null)"

# There is ONE MoOS look (UI2, dark + light halves). The UI1 generation no
# longer ships — the image build gates its ABSENCE — so a UI1 selector here is
# drift, not a rollback. (Version rollback is `bootc rollback`, a separate thing.)
case "$theme_lnf" in
    org.moos.ui2)
        theme_family=ui2; theme_name="UI2 Graphite Dark"
        want_deco=__aurorae__svg__MoOSUI2; want_scheme=MoOSUI2Dark
        want_icons=MoOSUI2; want_style=MoOSUI2; want_wallpaper=MoOSUI2Graphite
        pair_dark=org.moos.ui2; pair_light=org.moos.ui2.light
        ;;
    org.moos.ui2.light)
        theme_family=ui2; theme_name="UI2 Tidal Light"
        want_deco=__aurorae__svg__MoOSUI2Light; want_scheme=MoOSUI2Light
        want_icons=MoOSUI2Light; want_style=MoOSUI2Light; want_wallpaper=MoOSUI2Tide
        pair_dark=org.moos.ui2; pair_light=org.moos.ui2.light
        ;;
    *)
        theme_family=""; theme_name=""; want_deco=""; want_scheme=""; want_icons=""
        want_style=""; want_wallpaper=""; pair_dark=""; pair_light=""
        bad "active LookAndFeelPackage is '${theme_lnf:-unset}', not a MoOS UI2 half"
        ;;
esac

if [ -n "$theme_family" ]; then
    ok "active theme is ${theme_name} (${theme_lnf})"
    [ "$theme_deco" = "$want_deco" ] \
        && ok "window decoration matches ${theme_name}" \
        || bad "decoration is '${theme_deco:-unset}', expected ${want_deco}"
    [ "$theme_scheme" = "$want_scheme" ] \
        && ok "colour scheme matches ${theme_name}" \
        || bad "colour scheme is '${theme_scheme:-unset}', expected ${want_scheme}"
    [ "$theme_icons" = "$want_icons" ] \
        && ok "icon theme matches ${theme_name}" \
        || bad "icon theme is '${theme_icons:-unset}', expected ${want_icons}"
    [ "$theme_style" = "$want_style" ] \
        && ok "Plasma style matches ${theme_name}" \
        || bad "Plasma style is '${theme_style:-unset}', expected ${want_style}"

    default_dark="$(kreadconfig6 --file kdeglobals --group KDE --key DefaultDarkLookAndFeel 2>/dev/null)"
    default_light="$(kreadconfig6 --file kdeglobals --group KDE --key DefaultLightLookAndFeel 2>/dev/null)"
    [ "$default_dark" = "$pair_dark" ] \
        && ok "automatic dark target is the UI2 Graphite half" \
        || bad "dark target is '${default_dark:-unset}', expected ${pair_dark}"
    [ "$default_light" = "$pair_light" ] \
        && ok "automatic light target is the UI2 Tidal half" \
        || bad "light target is '${default_light:-unset}', expected ${pair_light}"
    if [ -d "/usr/share/plasma/look-and-feel/$pair_dark" ] && \
       [ -d "/usr/share/plasma/look-and-feel/$pair_light" ]; then
        ok "UI2 Graphite/Tidal automatic pair is installed"
    else
        bad "the UI2 automatic dark/light pair is incomplete"
    fi
    # Validate every live desktop containment. Exactly-one global counts reject a
    # correct two-monitor setup and a first-Image grep can inspect a panel instead
    # of a desktop, so the running Plasma shell is the authority here. The valid
    # state is the MoOS SCENE: wallpaper plugin org.moos.ui2.wallpaper (which
    # paints the dashboard bento BELOW the icons) with the matching image, and
    # ZERO leftover widget-era dashboard applets.
    desktop_state="$(timeout 5s gdbus call --session -d org.kde.plasmashell -o /PlasmaShell \
        -m org.kde.PlasmaShell.evaluateScript '
            var expected = "'"$want_wallpaper"'";
            var ds = desktops();
            var scenes = 0, wallpapers = 0, staleTotal = 0;
            for (var i = 0; i < ds.length; i++) {
                if (ds[i].wallpaperPlugin == "org.moos.ui2.wallpaper") { scenes++; }
                ds[i].currentConfigGroup = ["Wallpaper", "org.moos.ui2.wallpaper", "General"];
                if (String(ds[i].readConfig("Image", "")).indexOf(expected) >= 0) {
                    wallpapers++;
                }
                var ws = ds[i].widgets();
                for (var j = 0; j < ws.length; j++) {
                    if (ws[j].type == "org.moos.ui2.dashboard"
                            || ws[j].type == "org.moos.nova.deskclock") { staleTotal++; }
                }
            }
            print("desktops=" + ds.length + ";scenes=" + scenes
                + ";wallpapers=" + wallpapers + ";stale=" + staleTotal);
        ' 2>/dev/null \
        | grep -oE 'desktops=[1-9][0-9]*;scenes=[0-9]+;wallpapers=[0-9]+;stale=[0-9]+' \
        | head -n1)" || desktop_state=""
    if [ -n "$desktop_state" ]; then
        desktop_count="$(printf '%s\n' "$desktop_state" | tr ';' '\n' | sed -n 's/^desktops=//p')"
        scene_count="$(printf '%s\n' "$desktop_state" | tr ';' '\n' | sed -n 's/^scenes=//p')"
        wallpaper_count="$(printf '%s\n' "$desktop_state" | tr ';' '\n' | sed -n 's/^wallpapers=//p')"
        stale_count="$(printf '%s\n' "$desktop_state" | tr ';' '\n' | sed -n 's/^stale=//p')"
        [ "$scene_count" = "$desktop_count" ] \
            && ok "all ${desktop_count} live desktop(s) run the MoOS scene wallpaper" \
            || bad "only ${scene_count}/${desktop_count} desktop(s) run org.moos.ui2.wallpaper — no dashboard there"
        [ "$wallpaper_count" = "$desktop_count" ] \
            && ok "all ${desktop_count} live desktop wallpaper(s) match ${want_wallpaper}" \
            || bad "only ${wallpaper_count}/${desktop_count} live wallpaper(s) match ${want_wallpaper}"
        [ "${stale_count:-0}" = "0" ] \
            && ok "no leftover widget-era dashboard applets" \
            || bad "${stale_count} stale dashboard applet(s) still draw over the icons"
    else
        bad "could not inspect every live desktop's scene state through Plasma"
    fi
fi

# Both UI2 variants, their wallpapers, and the scene plugin (the wallpaper that
# carries the dashboard bento) must have shipped.
ui2_missing=""
for asset in \
    /usr/share/plasma/look-and-feel/org.moos.ui2/contents/defaults \
    /usr/share/plasma/look-and-feel/org.moos.ui2.light/contents/defaults \
    /usr/share/plasma/desktoptheme/MoOSUI2/widgets/panel-background.svg \
    /usr/share/plasma/desktoptheme/MoOSUI2Light/widgets/panel-background.svg \
    /usr/share/color-schemes/MoOSUI2Dark.colors \
    /usr/share/color-schemes/MoOSUI2Light.colors \
    /usr/share/aurorae/themes/MoOSUI2/MoOSUI2rc \
    /usr/share/aurorae/themes/MoOSUI2Light/MoOSUI2Lightrc \
    /usr/share/konsole/MoOSUI2.profile \
    /usr/share/konsole/MoOSUI2Light.profile \
    /usr/share/wallpapers/MoOSUI2Graphite/contents/images/3840x2160.jpg \
    /usr/share/wallpapers/MoOSUI2Tide/contents/images/3840x2160.jpg \
    /usr/share/plasma/wallpapers/org.moos.ui2.wallpaper/metadata.json \
    /usr/share/plasma/wallpapers/org.moos.ui2.wallpaper/contents/ui/main.qml \
    /usr/share/plasma/wallpapers/org.moos.ui2.wallpaper/contents/ui/DashboardBento.qml \
    /usr/share/plasma/wallpapers/org.moos.ui2.wallpaper/contents/images/weather/storm.png; do
    [ -e "$asset" ] || ui2_missing="${ui2_missing} ${asset}"
done
[ -z "$ui2_missing" ] \
    && ok "UI2 themes, wallpapers, dashboard and weather art all shipped" \
    || bad "UI2 asset set is incomplete:${ui2_missing}"

head_ "Keyboard — the one that silently broke"

# fcitx5 rewrote ~/.config/kxkbrc to `LayoutList=us` and took Arabic and German
# with it. It is removed from the image; this is the check that says so.
if rpm -q fcitx5 >/dev/null 2>&1; then
    bad "fcitx5 is INSTALLED again — one launch and the Arabic layout is gone"
else
    ok "fcitx5 is not in the image"
fi

layouts="$(busctl --user call org.kde.KWin /Layouts org.kde.KeyboardLayouts getLayoutsList 2>/dev/null || true)"
if printf '%s' "$layouts" | grep -q '"ara"'; then
    ok "the live session has the Arabic layout"
elif [ -z "$layouts" ]; then
    bad "could not ask KWin for its layouts (not in a Plasma session?)"
else
    bad "the live session's layouts do not include Arabic — you cannot type it"
fi

[ -f "$HOME/.config/kxkbrc" ] \
    && bad "~/.config/kxkbrc exists — it SHADOWS the image's layout defaults" \
    || ok "no ~/.config/kxkbrc shadowing the image"

head_ "MoPlayer"

test -x /usr/lib/moplayer/moplayer && ok "the Flutter bundle shipped" \
                                   || bad "/usr/lib/moplayer/moplayer is missing"
test -x /usr/bin/moplayer && ok "the launcher shipped" \
                          || bad "/usr/bin/moplayer is missing"
grep -q moos-gpu-headroom /usr/bin/moplayer 2>/dev/null \
    && ok "the launcher asks for GPU headroom (without it, it aborts while the brain holds the card)" \
    || bad "the GPU-headroom guard is GONE from the launcher"
test -x /usr/bin/moos-gpu-headroom && ok "moos-gpu-headroom shipped" \
                                   || bad "moos-gpu-headroom is missing"

for size in 128x128 256x256; do
    test -f "/usr/share/icons/hicolor/${size}/apps/moos-moplayer.png" \
        && ok "icon ${size}" \
        || bad "icon ${size} missing — Plasma will draw a generic tile"
done
test -f /usr/share/applications/org.moos.moplayer.desktop \
    && ok "the launcher entry shipped" \
    || bad "no .desktop — MoPlayer will not appear in Kickoff"

head_ "Mo AI"

grep -q KNOWN_GOOD /usr/bin/moai-control 2>/dev/null \
    && ok "the decision layer is there (answers the need, not the keyword)" \
    || bad "moai-control lost its KNOWN_GOOD table"
grep -q install-opencode /usr/bin/moai-do 2>/dev/null \
    && ok "OpenCode — the agent that runs on the local brain" \
    || bad "moai-do lost install-opencode"
# The diagnosis lives in moai-gateway (commit 3928b61), not moai-control — this
# gate used to grep the wrong file and went red against a working system. And it
# greps for `cudamalloc`, a string that only exists in the code that classifies
# llama-server's death, with comments stripped first: every file in this repo
# names the bug it prevents, so "VRAM" appears in comments beside fixes that have
# nothing to do with this one, and a gate that matched those would stay green
# after the code was deleted.
#
# Read the stripped file into a variable rather than piping it into `grep -q`: under
# `set -o pipefail` (line 15) that pipeline is FLAKY. `grep -q` exits on its first
# match, the upstream grep dies of SIGPIPE, and pipefail hands the pipeline 141 —
# so the gate goes red on a healthy system whenever the writer loses that race.
moai_code="$(grep -vE '^[[:space:]]*#' /usr/bin/moai-gateway 2>/dev/null)"
case "$moai_code" in
    *cudamalloc*) ok "the brain can say WHY it failed to start (it reads llama-server's own error)" ;;
    *)            bad "moai-gateway lost its failure diagnosis — a dead brain will just 502" ;;
esac

head_ "Nothing in \$HOME is shadowing the image"

# The bug family this repo keeps losing to: the image ships the fix, and the user
# still does not get it, because a file under $HOME outranks it. Every check above
# reads /usr — none of them would notice.
#
# It is not hypothetical. On 2026-07-13, an hour after this image shipped MoPlayer
# with a GPU-headroom guard, clicking MoPlayer in Kickoff still core-dumped: a
# ~/.local/share/applications/org.moos.moplayer.desktop left over from a hand-install
# pointed at ~/.local/bin/moplayer, which had no guard, and Plasma reads $HOME first.
# ~/.local/bin also comes BEFORE /usr/bin on PATH, so the same trick hides a launcher
# from the terminal. A second one pointed at a script that exec'd the *working tree* —
# so the app in the menu was whatever an agent had half-finished editing.
#
# Staging a fix into $HOME is still the right way to prove it on the running desktop.
# Just delete the copy afterwards — that is what this check is here to remind you of.

# Shadowing something MoOS itself ships is a bug — the image's fix is what $HOME is
# hiding. Shadowing a third-party tool usually is not: ~/.local/bin/gh is a newer gh
# than the image carries, deliberately installed, and failing the run over it would
# teach the maintainer to ignore this section. So: first-party shadows are red,
# everything else is a line you can read and dismiss.
is_first_party() {
    case "$1" in
        org.moos.*|moos-*|moos|moai*|moplayer|mo-pc-remote) return 0 ;;
        *) return 1 ;;
    esac
}

shadow_first=""; shadow_other=""
for f in "$HOME"/.local/share/applications/*.desktop; do
    [ -e "$f" ] || continue
    b="$(basename "$f")"
    [ -e "/usr/share/applications/$b" ] || continue
    if is_first_party "${b%.desktop}"; then shadow_first="$shadow_first $b"
    else shadow_other="$shadow_other $b"; fi
done
for f in "$HOME"/.local/bin/*; do
    [ -x "$f" ] || continue
    b="$(basename "$f")"
    [ -x "/usr/bin/$b" ] || continue
    if is_first_party "$b"; then shadow_first="$shadow_first $b"
    else shadow_other="$shadow_other $b"; fi
done

if [ -z "$shadow_first" ]; then
    ok "no copy in \$HOME is overriding a MoOS app the image ships"
else
    bad "\$HOME overrides these MoOS apps — Kickoff and PATH run the copy, NOT the image:"
    for b in $shadow_first; do printf '      %s\n' "$b"; done
    printf '      \033[2m(delete it: the image is the one that gets fixed)\033[0m\n'
fi
for b in $shadow_other; do
    printf '  · %s in $HOME shadows the image'"'"'s copy — fine if you meant it\n' "$b"
done

head_ "The image is not carrying the build machine's litter"

stray="$(find /usr/bin /usr/share/moos -type d -name __pycache__ 2>/dev/null | head -3)"
[ -z "$stray" ] && ok "no Python bytecode cache in /usr/bin or /usr/share/moos" \
                || bad "shipped bytecode cache: $stray"

head_ "Boot"

if command -v systemd-analyze >/dev/null 2>&1; then
    printf '  · %s\n' "$(systemd-analyze 2>/dev/null | head -1)"
    slow="$(systemd-analyze blame 2>/dev/null | head -3 | sed 's/^/    /')"
    printf '%s\n' "$slow"
fi

# The app-store index was 3.5 s inside the critical path. It is a timer now.
if systemctl is-enabled moos-appstream-refresh.timer >/dev/null 2>&1; then
    ok "the app-store index is a timer, not a boot-blocker"
else
    bad "moos-appstream-refresh.timer is not enabled — the index may be back on the critical path"
fi

head_ "The dock actually has MoOS's apps in it"

# The image has pinned MoPlayer and Mo PC Remote in layout.js for a long time, and the
# maintainer's dock still did not have them: a layout template only runs for a user with no
# panel. So ask the dock the user is looking at, not the file we shipped.
dock="$(kreadconfig6 --file plasma-org.kde.plasma.desktop-appletsrc \
        --group Containments --group 52 --group Applets --group 54 \
        --group Configuration --group General --key launchers 2>/dev/null)"
[ -n "$dock" ] || dock="$(grep -m1 '^launchers=' "${XDG_CONFIG_HOME:-$HOME/.config}/plasma-org.kde.plasma.desktop-appletsrc" 2>/dev/null)"
if [ -z "$dock" ]; then
    printf '  · could not read the dock (no panel config?) — skipped\n'
else
    for app in org.moos.moai org.moos.moplayer org.moos.remote; do
        case "$dock" in
            *"${app}.desktop"*) ok "${app} is pinned in the dock" ;;
            *) bad "${app} is NOT in the dock — moos-apply-theme's reconcile did not reach this user (a THEME_REV bump + relogin is what applies it)" ;;
        esac
    done
fi

head_ "The disk cannot fill itself"

# Every one of these was an unbounded leak on this machine: 125 GB of podman build layers,
# 4.2 GB of core dumps in a night, and a journal heading for 10 % of a 475 GB disk. Read the
# EFFECTIVE config, not the file we shipped — /etc outranks /usr/lib, and a stale /etc
# drop-in would silently restore the default.
journal_cap="$(systemd-analyze cat-config systemd/journald.conf 2>/dev/null \
               | grep -v '^\s*#' | grep -m1 '^SystemMaxUse=')"
[ -n "$journal_cap" ] && ok "the journal is capped ($journal_cap)" \
                      || bad "no SystemMaxUse in the effective journald config — the journal grows to 10 % of the disk"

coredump_cap="$(systemd-analyze cat-config systemd/coredump.conf 2>/dev/null \
                | grep -v '^\s*#' | grep -m1 '^MaxUse=')"
[ -n "$coredump_cap" ] && ok "core dumps are capped ($coredump_cap)" \
                       || bad "no MaxUse in the effective coredump config — one bad GPU night wrote 4.2 GB of dumps"

if systemctl --user is-enabled moos-reclaim-disk.timer >/dev/null 2>&1; then
    ok "the weekly build-litter sweep is enabled"
else
    bad "moos-reclaim-disk.timer is not enabled — podman's dangling build layers grow without limit (125 GB in days)"
fi

head_ "Failed units"

failed="$(systemctl --failed --no-legend 2>/dev/null | grep -v drkonqi-coredump | wc -l)"
failed_user="$(systemctl --user --failed --no-legend 2>/dev/null | grep -v drkonqi-coredump | wc -l)"
[ "$failed" -eq 0 ] && ok "no failed system units" || {
    bad "$failed failed system unit(s):"
    systemctl --failed --no-legend | grep -v drkonqi-coredump | sed 's/^/      /' | head -5
}
[ "$failed_user" -eq 0 ] && ok "no failed user units" || {
    bad "$failed_user failed user unit(s):"
    systemctl --user --failed --no-legend | grep -v drkonqi-coredump | sed 's/^/      /' | head -5
}

printf '\n\033[1m%d passed, %d failed\033[0m\n' "$pass" "$fail"
[ "$fail" -eq 0 ] || exit 1
