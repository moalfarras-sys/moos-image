namespace MoRemote;

/// <summary>
/// Where every character of the Arabic keymap physically sits.
///
/// WHY A TABLE OF POSITIONS AND NOT A TABLE OF KEYSYMS
///
/// KWin resolves an injected keysym against the ACTIVE keymap group only, and only at shift
/// level one. That is the whole reason Arabic used to type through the clipboard. Selecting the
/// Arabic group with org.kde.KeyboardLayouts.setLayout fixes the group — but a keysym is still
/// a request for the compositor to go looking, and level two (the Arabic comma, the question
/// mark, every diacritic) is not reachable that way. A POSITION plus a shift state is not a
/// request; it is exactly what a real keyboard sends, and it reaches every level.
///
/// HOW THIS TABLE WAS BUILT
///
/// Measured, not transcribed. Every key in the alphanumeric block was pressed on the live
/// session with the `ara` group active, at level one and level two, one character per line into
/// a real editor, and the saved file is what this table records. Parsing
/// /usr/share/X11/xkb/symbols/ara would have meant trusting a keysym-name-to-character mapping
/// that nothing here can check; pressing the key and reading the character back cannot be wrong
/// about what the key does. tests/test_remote_ara_keymap.py re-derives the same table from the
/// shipped xkb file where one is available, so drift between the two is a build failure rather
/// than a typo nobody notices.
///
/// The lam-alef ligature keys (لا لأ لإ لآ) are deliberately absent: they emit two codepoints
/// from one key, and the same text is produced by typing lam and then alef, which the reverse
/// map already covers. A ligature entry would only ever be a second way to say the same thing.
/// </summary>
public static class AraKeymap
{
    private const ushort Shift = 42;

    /// <summary>Level 1 — the character the unmodified key produces on the `ara` group.</summary>
    private static readonly (ushort Code, string Ch)[] Level1 =
    [
        (2, "1"), (3, "2"), (4, "3"), (5, "4"), (6, "5"), (7, "6"), (8, "7"), (9, "8"),
        (10, "9"), (11, "0"), (12, "-"), (13, "="),
        (16, "ض"), (17, "ص"), (18, "ث"), (19, "ق"), (20, "ف"), (21, "غ"), (22, "ع"),
        (23, "ه"), (24, "خ"), (25, "ح"), (26, "ج"), (27, "د"),
        (30, "ش"), (31, "س"), (32, "ي"), (33, "ب"), (34, "ل"), (35, "ا"), (36, "ت"),
        (37, "ن"), (38, "م"), (39, "ك"), (40, "ط"), (41, "ذ"),
        (43, "\\"),
        (44, "ئ"), (45, "ء"), (46, "ؤ"), (47, "ر"), (49, "ى"), (50, "ة"), (51, "و"),
        (52, "ز"), (53, "ظ"),
        (86, "|"), (57, " "),
    ];

    /// <summary>Level 2 — the character the key produces with Shift held.</summary>
    private static readonly (ushort Code, string Ch)[] Level2 =
    [
        (2, "!"), (3, "@"), (4, "#"), (5, "$"), (6, "%"), (7, "^"), (8, "&"), (9, "*"),
        (10, ")"), (11, "("), (12, "_"), (13, "+"),
        (16, "َ"), (17, "ً"), (18, "ُ"), (19, "ٌ"), (21, "إ"),
        (22, "`"), (23, "÷"), (24, "×"), (25, "؛"), (26, "<"), (27, ">"),
        (30, "ِ"), (31, "ٍ"), (32, "]"), (33, "["), (35, "أ"), (36, "ـ"),
        (37, "،"), (38, "/"), (39, ":"), (40, "\""), (41, "ّ"),
        (43, "|"),
        (44, "~"), (45, "ْ"), (46, "}"), (47, "{"), (49, "آ"), (50, "'"), (51, ","),
        (52, "."), (53, "؟"),
        (86, "…"),
    ];

    private static readonly Dictionary<int, (ushort Code, bool Shift)> ByChar = Build();

    private static Dictionary<int, (ushort, bool)> Build()
    {
        var map = new Dictionary<int, (ushort, bool)>();
        // Level 1 first, so a character reachable without Shift is never given the shifted key.
        foreach (var (code, ch) in Level1)
            map.TryAdd(char.ConvertToUtf32(ch, 0), (code, false));
        foreach (var (code, ch) in Level2)
            map.TryAdd(char.ConvertToUtf32(ch, 0), (code, true));
        return map;
    }

    /// <summary>True when this character has a key on the Arabic layout.</summary>
    public static bool Has(int codepoint) => ByChar.ContainsKey(codepoint);

    /// <summary>
    /// True when this character is one only the Arabic group can produce — i.e. typing it
    /// REQUIRES the switch. Digits, Latin punctuation and space live on both layouts, so they
    /// must not drag the group across on their own: a full stop between two Arabic words would
    /// otherwise cost two switches and two OSD flashes for a character either group can type.
    /// </summary>
    public static bool NeedsArabicGroup(int codepoint) =>
        codepoint > 0x7F && ByChar.ContainsKey(codepoint);

    /// <summary>
    /// The ordered press/release events that type <paramref name="text"/> on the Arabic group,
    /// or false if any character has no key there — a partial run must never be typed, because
    /// half a word delivered is worse than a word the caller can report as undeliverable.
    /// </summary>
    public static bool TryStrokes(string text, List<object> events)
    {
        foreach (var rune in text.EnumerateRunes())
        {
            if (!ByChar.TryGetValue(rune.Value, out var k)) return false;
            if (k.Shift) events.Add(new { code = (int)Shift, down = true });
            events.Add(new { code = (int)k.Code, down = true });
            events.Add(new { code = (int)k.Code, down = false });
            if (k.Shift) events.Add(new { code = (int)Shift, down = false });
        }
        return true;
    }
}
