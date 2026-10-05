#!/usr/bin/env bash
# The login greeter in its own --test mode. plasma-login-manager draws the wallpaper in a
# SEPARATE process (plasma-login-wallpaper) that a Wayland compositor stacks under the greeter;
# Xvfb has no compositor, so this starts the greeter alone unless LOGIN_WALLPAPER=1.
wallpaper="${1:-MoOSUI2Graphite}"
mkdir -p "$XDG_CONFIG_HOME"
cat > "$XDG_CONFIG_HOME/plasmalogin.conf" <<EOC
[Greeter]
WallpaperPluginId=org.moos.ui2.greeter
ShowClock=true

[Greeter][Wallpaper][org.moos.ui2.greeter][General]
Image=/usr/share/wallpapers/$wallpaper/
EOC
if [ "${LOGIN_WALLPAPER:-0}" = 1 ]; then
    /usr/bin/plasma-login-wallpaper &
    sleep 2
fi
exec /usr/libexec/plasma-login-greeter --test
