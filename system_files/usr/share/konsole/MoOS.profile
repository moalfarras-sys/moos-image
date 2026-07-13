# MoOS — default Konsole profile (NovaDark colors + JetBrains Mono).
# Key names verified against KDE/konsole master src/profile/Profile.cpp
# ([General] Name, [Appearance] ColorScheme / Font). Parent=FALLBACK/ is the
# stock "inherit built-in defaults" parent used by shipped profiles.
# Font uses the legacy 10-field QFont::toString() form
# (family,pointsize,pixelsize,styleHint,weight,italic,underline,strikeout,
# fixedpitch,rawmode) — accepted by QFont::fromString in both Qt5 and Qt6.
# JetBrains Mono is installed by build.sh section (c4).

# Beautified, and SOLID by design (the colour scheme is fully opaque). Every key below
# is a real Konsole profile key (KDE/konsole master src/profile/Profile.cpp):
#   LineSpacing / BoldIntense / UseFontLineChararacters (yes, that misspelling is the
#   actual key), TerminalMargin, ShowTerminalSizeHint, ScrollBarPosition (2 = hidden),
#   HistoryMode (1 = fixed), Cursor{Shape,CustomColor}, BellMode (3 = none), and the
#   smart-selection keys.
#
# THE GROUP NAMES MATTER. Konsole reads the cursor keys from **[Cursor Options]** and the
# selection keys from **[Interaction Options]** — not from [Cursor]/[Interaction]. Written
# under the short names the file parses, the gate passes, and the keys do nothing: a live
# terminal was verified showing a WHITE cursor with CustomCursorColor set. The eight group
# names Konsole knows are in the binary (`strings libkonsoleprivate.so`): Appearance,
# Cursor Options, Encoding Options, General, Interaction Options, Keyboard, Scrolling,
# Terminal Features.
[Appearance]
ColorScheme=NovaDark
Font=JetBrains Mono,11,-1,5,50,0,0,0,0,0
LineSpacing=2
BoldIntense=true
UseFontLineChararacters=true

[General]
Name=MoOS
Parent=FALLBACK/
# Generous inner padding + no resize popup = a calm, premium canvas.
TerminalMargin=14
TerminalCenter=false
ShowTerminalSizeHint=false

[Scrolling]
# Hidden scrollbar for a clean edge; 20k lines of bounded history.
ScrollBarPosition=2
HistoryMode=1
HistorySize=20000

[Cursor Options]
# A steady-blinking block cursor in the Nova cyan accent (#22D3EE).
CursorShape=0
UseCustomCursorColor=true
CustomCursorColor=34,211,238

[Terminal Features]
BlinkingCursorEnabled=true
BellMode=3

[Interaction Options]
# Smart defaults: copy on select, keep links/paths clickable, never copy trailing spaces.
AutoCopySelectedText=true
TrimTrailingSpacesInSelectedText=true
UnderlineLinksEnabled=true
UnderlineFilesEnabled=true
