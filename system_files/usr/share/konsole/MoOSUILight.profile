# MoOS — default Konsole profile (MoOSUIDark colors + JetBrains Mono).
# Key names verified against KDE/konsole master src/profile/Profile.cpp
# ([General] Name, [Appearance] ColorScheme / Font). Parent=FALLBACK/ is the
# stock "inherit built-in defaults" parent used by shipped profiles.
# Font uses the legacy 10-field QFont::toString() form
# (family,pointsize,pixelsize,styleHint,weight,italic,underline,strikeout,
# fixedpitch,rawmode) — accepted by QFont::fromString in both Qt5 and Qt6.
# JetBrains Mono is installed by build.sh section (c4).

# Beautified, solid — the light twin of MoOS.profile. Same premium chrome, with a blue
# cursor (#7C3AED) that reads on a light background where the cyan would wash out.
# Group names are Konsole's real ones — [Cursor Options] / [Interaction Options]; see the
# note in MoOS.profile for what happens when they are shortened.
[Appearance]
ColorScheme=MoOSUILight
Font=JetBrains Mono,11,-1,5,50,0,0,0,0,0
LineSpacing=2
BoldIntense=true
UseFontLineChararacters=true

[General]
Name=MoOS UI Light
Parent=FALLBACK/
TerminalMargin=14
TerminalCenter=false
ShowTerminalSizeHint=false

[Scrolling]
ScrollBarPosition=2
HistoryMode=1
HistorySize=20000

[Cursor Options]
CursorShape=0
UseCustomCursorColor=true
CustomCursorColor=124,58,237

[Terminal Features]
BlinkingCursorEnabled=true
BellMode=3

[Interaction Options]
AutoCopySelectedText=true
TrimTrailingSpacesInSelectedText=true
UnderlineLinksEnabled=true
UnderlineFilesEnabled=true
