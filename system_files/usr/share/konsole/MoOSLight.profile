# MoOS — default Konsole profile (NovaDark colors + JetBrains Mono).
# Key names verified against KDE/konsole master src/profile/Profile.cpp
# ([General] Name, [Appearance] ColorScheme / Font). Parent=FALLBACK/ is the
# stock "inherit built-in defaults" parent used by shipped profiles.
# Font uses the legacy 10-field QFont::toString() form
# (family,pointsize,pixelsize,styleHint,weight,italic,underline,strikeout,
# fixedpitch,rawmode) — accepted by QFont::fromString in both Qt5 and Qt6.
# JetBrains Mono is installed by build.sh section (c4).

[Appearance]
ColorScheme=NovaLight
Font=JetBrains Mono,11,-1,5,50,0,0,0,0,0

[General]
Name=MoOS Light
Parent=FALLBACK/
