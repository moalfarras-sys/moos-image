# Meyar Form

Meyar Form Arabic and Meyar Form Sans are selectable regular-weight studies based on the corresponding OFL Meyar fonts. The OpenType contextual alternates draw faceted opening glyphs and rounded closing glyphs. For an odd number of shaped letters the opening gets the middle one. A native ligature stays together. Marks retain their positions, numerals and punctuation keep their outlines, and uncovered scripts use the application's normal fallback. The split covers up to 64 shaped letters per word. Longer unprocessed centres retain the source outlines. Applications must support contextual alternates.

Use the pinned Meyar font-tools environment and system PySide6 for the builder. When they are installed in separate Python environments, add the compatible font environment's site-packages directory to the system Python path. On V3 both runtimes use Python 3.14.

    python3 build.py OUTPUT
    python3 verify.py OUTPUT
    python3 editor.py OUTPUT

Distribute the original OFL-Arabic.txt and OFL-LGC.txt from system_files/usr/share/fonts/meyar with their respective fonts. The editor loads the requested files for its own process. A reviewer can select the distinctly named fonts without changing system defaults. Retire a user-local review copy when the identical signed font is available and the native editor accepts it.
