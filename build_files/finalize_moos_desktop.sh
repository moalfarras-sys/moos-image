#!/usr/bin/env bash
# Finalize architecture-independent MoOS desktop assets after the last package
# transaction.  system_files is the source authority, but three runtime pieces
# are intentionally generated at image-build time: the broad Colloid-backed
# icon themes, the Bibata-backed pointer themes, and the plasma-login-manager
# account state.  Every desktop architecture must run this file; otherwise a
# source-tree identity gate can be green while the installed desktop falls back.
set -euo pipefail

readonly COLLOID_COMMIT=c9e702beb96f731e2b3bea2fa1c619fa94e79a9f
readonly BIBATA_VERSION=2.0.7

need() {
    command -v "$1" >/dev/null 2>&1 || {
        echo "FATAL: MoOS desktop finalizer requires '$1'" >&2
        exit 1
    }
}

for tool in git curl tar gtk-update-icon-cache; do
    need "${tool}"
done

recolor_symbols() {
    local directory="$1" text="$2" accent="$3" warning="$4" danger="$5" file
    for file in "${directory}"/moos-*-symbolic.svg; do
        [ -f "${file}" ] || continue
        sed -i \
            -e "s/#243238/${text}/gI" \
            -e "s/#147d72/${accent}/gI" \
            -e "s/#8a5a00/${warning}/gI" \
            -e "s/#a9364b/${danger}/gI" \
            "${file}"
    done
}

recolor_apps() {
    local directory="$1" text="$2" background="$3" highlight="$4"
    local selected="$5" positive="$6" neutral="$7" negative="$8" file
    for file in "${directory}"/moos-*.svg; do
        [ -f "${file}" ] || continue
        grep -q 'id="current-color-scheme"' "${file}" || continue
        sed -i \
            -e "s/#e8f1ef/${text}/gI" \
            -e "s/#1d2529/${background}/gI" \
            -e "s/#4ed7c8/${highlight}/gI" \
            -e "s/#142220/${selected}/gI" \
            -e "s/#69d9a5/${positive}/gI" \
            -e "s/#f4c56a/${neutral}/gI" \
            -e "s/#ff7d88/${negative}/gI" \
            "${file}"
    done
}

install_icons() {
    rm -rf /tmp/moos-colloid
    git clone --depth 1 https://github.com/vinceliuice/Colloid-icon-theme.git \
        /tmp/moos-colloid
    git -C /tmp/moos-colloid fetch --depth 1 origin "${COLLOID_COMMIT}"
    git -C /tmp/moos-colloid checkout "${COLLOID_COMMIT}"
    bash /tmp/moos-colloid/install.sh -d /usr/share/icons -t teal -s default
    rm -rf /tmp/moos-colloid

    local theme base label comment inherited directory
    for theme in MoOSUI2 MoOSUI2Light; do
        case "${theme}" in
            MoOSUI2)
                base=Colloid-Teal-Dark
                label='MoOS UI'
                comment='MoOS icons — mineral teal on graphite'
                inherited='Colloid-Teal-Dark,Papirus-Dark,breeze-dark,hicolor'
                ;;
            *)
                base=Colloid-Teal-Light
                label='MoOS UI Light'
                comment='MoOS icons — mineral teal on tidal mist'
                inherited='Colloid-Teal-Light,Papirus,breeze,hicolor'
                ;;
        esac
        test -d "/usr/share/icons/${base}/apps"
        rm -rf "/usr/share/icons/${theme}"
        mkdir -p "/usr/share/icons/${theme}"
        cp "/usr/share/icons/${base}/index.theme" "/usr/share/icons/${theme}/index.theme"
        sed -i \
            -e "s|^Name=.*|Name=${label}|" \
            -e "s|^Comment=.*|Comment=${comment}|" \
            -e "s|^Inherits=.*|Inherits=${inherited}|" \
            -e 's|^FollowsColorScheme=.*|FollowsColorScheme=false|' \
            -e 's|^Directories=|Directories=moos/actions/scalable,moos/apps/scalable,|' \
            "/usr/share/icons/${theme}/index.theme"
        for directory in /usr/share/icons/${base}/*/; do
            ln -snf "../${base}/$(basename "${directory}")" \
                "/usr/share/icons/${theme}/$(basename "${directory}")"
        done
        mkdir -p "/usr/share/icons/${theme}/moos/actions/scalable" \
                 "/usr/share/icons/${theme}/moos/apps/scalable"
        cp /usr/share/icons/hicolor/scalable/actions/moos-*-symbolic.svg \
            "/usr/share/icons/${theme}/moos/actions/scalable/"
        cp /usr/share/icons/hicolor/scalable/apps/moos-*.svg \
            "/usr/share/icons/${theme}/moos/apps/scalable/"
        if [ "${theme}" = MoOSUI2 ]; then
            recolor_symbols "/usr/share/icons/${theme}/moos/actions/scalable" \
                '#E8F1EF' '#4ED7C8' '#F4C56A' '#FF7D88'
            recolor_apps "/usr/share/icons/${theme}/moos/apps/scalable" \
                '#E8F1EF' '#1D2529' '#4ED7C8' '#142220' \
                '#69D9A5' '#F4C56A' '#FF7D88'
        else
            recolor_symbols "/usr/share/icons/${theme}/moos/actions/scalable" \
                '#17302E' '#006D67' '#7B520F' '#A52F3F'
            recolor_apps "/usr/share/icons/${theme}/moos/apps/scalable" \
                '#17302E' '#C9E2DD' '#006D67' '#E1F0EC' \
                '#086B4B' '#7B520F' '#A52F3F'
        fi
        cat >> "/usr/share/icons/${theme}/index.theme" <<'EOF'

[moos/actions/scalable]
Size=24
Context=Actions
Type=Scalable
MinSize=16
MaxSize=512

[moos/apps/scalable]
Size=64
Context=Applications
Type=Scalable
MinSize=16
MaxSize=512
EOF
        gtk-update-icon-cache -f "/usr/share/icons/${theme}" || true
    done
}

install_cursor() {
    local upstream="$1" target="$2" label="$3" archive
    archive="/tmp/${upstream}.tar.xz"
    curl -Lf --retry 5 --retry-all-errors --retry-delay 2 --connect-timeout 30 \
        -o "${archive}" \
        "https://github.com/ful1e5/Bibata_Cursor/releases/download/v${BIBATA_VERSION}/${upstream}.tar.xz"
    tar -xJf "${archive}" -C /usr/share/icons/
    rm -f "${archive}"
    test -d "/usr/share/icons/${upstream}/cursors"
    rm -rf "/usr/share/icons/${target}"
    cp -a "/usr/share/icons/${upstream}" "/usr/share/icons/${target}"
    sed -i "s|^Name=.*|Name=${label}|" "/usr/share/icons/${target}/index.theme"
    sed -i "s|^Name=.*|Name=${label}|" "/usr/share/icons/${target}/cursor.theme"
    cat > "/usr/share/icons/${target}/MOOS-NOTICE.txt" <<EOF
${target} is a renamed, otherwise unmodified build of ${upstream} v${BIBATA_VERSION}
by Abdulkaiz Khatri (ful1e5) and contributors.
Source: https://github.com/ful1e5/Bibata_Cursor
License: GNU General Public License v3.0 (GPL-3.0).
EOF
}

finalize_login() {
    local qmldir=/usr/lib64/qt6/qml/org/kde/breeze/components/qmldir
    test -f "${qmldir}" || { echo "FATAL: Plasma Breeze QML module is missing"; exit 1; }
    for component in ActionButton Clock UserDelegate; do
        test -f "/usr/lib64/qt6/qml/org/kde/breeze/components/${component}.qml" || {
            echo "FATAL: MoOS login component is missing: ${component}.qml"
            exit 1
        }
    done
    sed -i '/^prefer /d' "${qmldir}"
    ! grep -q '^prefer ' "${qmldir}" || {
        echo "FATAL: Plasma Login Manager still prefers compiled foreign controls"
        exit 1
    }

    test -f /usr/share/color-schemes/MoOSUI2Dark.colors || {
        echo "FATAL: the greeter palette is missing"
        exit 1
    }
    install -d -m 0755 /usr/share/moos/plasmalogin
    {
        cat /usr/share/color-schemes/MoOSUI2Dark.colors
        printf '\n[General]\nColorScheme=MoOSUI2Dark\n'
        printf '\n[Icons]\nTheme=MoOSUI2\n'
        printf '\n[KDE]\nwidgetStyle=Breeze\nLookAndFeelPackage=org.moos.ui2\n'
    } > /usr/share/moos/plasmalogin/kdeglobals
    printf '[Theme]\nname=MoOSUI2\n' > /usr/share/moos/plasmalogin/plasmarc
    cat > /usr/lib/tmpfiles.d/moos-plasmalogin-greeter.conf <<'EOF'
r! /var/lib/plasmalogin/.config/kdeglobals
r! /var/lib/plasmalogin/.config/plasmarc
d  /var/lib/plasmalogin/.config             0700 plasmalogin plasmalogin -
C+ /var/lib/plasmalogin/.config/kdeglobals  0600 plasmalogin plasmalogin - /usr/share/moos/plasmalogin/kdeglobals
C+ /var/lib/plasmalogin/.config/plasmarc    0600 plasmalogin plasmalogin - /usr/share/moos/plasmalogin/plasmarc
EOF
}

if [ ! -f /usr/share/icons/MoOSUI2/index.theme ] \
   || [ ! -d /usr/share/icons/MoOSUI2/apps ] \
   || [ ! -f /usr/share/icons/MoOSUI2Light/index.theme ] \
   || [ ! -d /usr/share/icons/MoOSUI2Light/apps ]; then
    install_icons
fi

if [ ! -d /usr/share/icons/MoOS/cursors ]; then
    install_cursor Bibata-Modern-Ice MoOS 'MoOS Pointer'
fi
if [ ! -d /usr/share/icons/MoOSDark/cursors ]; then
    install_cursor Bibata-Modern-Classic MoOSDark 'MoOS Pointer Dark'
fi
rm -rf /usr/share/icons/default
mkdir -p /usr/share/icons/default
printf '[Icon Theme]\nName=MoOS Default Pointer\nInherits=MoOS\n' \
    > /usr/share/icons/default/index.theme

finalize_login

for required in \
    /usr/share/icons/MoOSUI2/index.theme \
    /usr/share/icons/MoOSUI2Light/index.theme \
    /usr/share/icons/MoOS/cursors/left_ptr \
    /usr/share/icons/MoOSDark/cursors/left_ptr \
    /usr/share/moos/plasmalogin/kdeglobals \
    /usr/lib/tmpfiles.d/moos-plasmalogin-greeter.conf; do
    test -e "${required}" || { echo "FATAL: missing finalized desktop asset ${required}"; exit 1; }
done

echo "MoOS desktop finalization OK: icons, pointers and interactive login chrome"
