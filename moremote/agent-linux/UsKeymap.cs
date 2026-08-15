namespace MoRemote;

/// <summary>
/// Where every printable ASCII character physically sits on the `us` keymap group.
///
/// WHY THIS EXISTS, AND WHY IT IS POSITIONS RATHER THAN KEYSYMS
///
/// The fast path for Latin text is <see cref="InputInjector.TryDirectStrokes"/>, which injects
/// KEYSYMS and lets the compositor find the key on whatever layout the user actually has. That is
/// the right default and it stays the default — but it can only reach SHIFT LEVEL ONE, because
/// KWin resolves an injected keysym against the active group at level one only (the same fact that
/// forced <see cref="AraKeymap"/> to exist). So it handles a-z, 0-9 and space, plus A-Z by pressing
/// Shift explicitly — uppercase being the one level-two case that is the same on every Latin
/// layout.
///
/// EVERY SYMBOL IS LEVEL TWO OR HIGHER, AND ITS POSITION IS NOT LAYOUT-INVARIANT.
///
/// `@` is Shift+2 on US and AltGr+Q on German; `#` is Shift+3 on US and a dead key on French. So
/// TryDirectStrokes returned false for any run containing a symbol, and Deliver logged
/// "Typing skipped N character(s) with no key on the available layouts; nothing was typed for that
/// run" — the whole run, silently dropped. The owner reported it as symbols not surviving a copy
/// and paste, which is exactly what it looks like from the other end: paste a URL, a password or an
/// email address into the remote and the symbols are missing or the line never arrives at all.
///
/// The fix is the one AraKeymap already proved. Selecting a KNOWN group makes positions
/// deterministic, and a position plus a shift state is not a request for the compositor to go
/// looking — it is what a real keyboard sends, and it reaches every level. `us` is present in the
/// session's layout list on this machine (`de, us, ara`), and select_group falls back cleanly if it
/// ever is not, so a run is skipped rather than mistyped.
///
/// THE TABLE IS US QWERTY, WHICH IS A STANDARD AND NOT A GUESS. Codes are evdev scancodes, the
/// same ones InputInjector.PhysicalCodes carries for the browser's KeyboardEvent.code values, so
/// the two tables can be checked against each other — tests/test_remote_us_keymap.py does exactly
/// that, and also asserts every printable ASCII character is reachable.
/// </summary>
public static class UsKeymap
{
    private const ushort Shift = 42;

    public readonly record struct Key(ushort Code, bool Shift);

    /// <summary>char -> (evdev code, shift level two). US QWERTY, alphanumeric block only.</summary>
    private static readonly Dictionary<int, Key> ByChar = Build();

    private static Dictionary<int, Key> Build()
    {
        // Unshifted and shifted faces of each key, paired by position. Digit row, then the three
        // letter rows' punctuation, in the order they sit on the board.
        (ushort Code, char Low, char High)[] table =
        {
            (41, '`', '~'),
            (2, '1', '!'), (3, '2', '@'), (4, '3', '#'), (5, '4', '$'), (6, '5', '%'),
            (7, '6', '^'), (8, '7', '&'), (9, '8', '*'), (10, '9', '('), (11, '0', ')'),
            (12, '-', '_'), (13, '=', '+'),
            (26, '[', '{'), (27, ']', '}'), (43, '\\', '|'),
            (39, ';', ':'), (40, '\'', '"'),
            (51, ',', '<'), (52, '.', '>'), (53, '/', '?'),
        };

        var map = new Dictionary<int, Key>();
        foreach (var (code, low, high) in table)
        {
            map[low] = new Key(code, false);
            map[high] = new Key(code, true);
        }

        // Letters: unshifted lowercase, shifted uppercase. Same evdev codes as PhysicalCodes.
        (ushort Code, char Letter)[] letters =
        {
            (30, 'a'), (48, 'b'), (46, 'c'), (32, 'd'), (18, 'e'), (33, 'f'), (34, 'g'),
            (35, 'h'), (23, 'i'), (36, 'j'), (37, 'k'), (38, 'l'), (50, 'm'), (49, 'n'),
            (24, 'o'), (25, 'p'), (16, 'q'), (19, 'r'), (31, 's'), (20, 't'), (22, 'u'),
            (47, 'v'), (17, 'w'), (45, 'x'), (21, 'y'), (44, 'z'),
        };
        foreach (var (code, letter) in letters)
        {
            map[letter] = new Key(code, false);
            map[char.ToUpperInvariant(letter)] = new Key(code, true);
        }

        // Digits sit on the same keys as the digit-row symbols above, unshifted.
        (ushort Code, char Digit)[] digits =
        {
            (2, '1'), (3, '2'), (4, '3'), (5, '4'), (6, '5'),
            (7, '6'), (8, '7'), (9, '8'), (10, '9'), (11, '0'),
        };
        foreach (var (code, digit) in digits) map[digit] = new Key(code, false);

        map[' '] = new Key(57, false);   // Space
        return map;
    }

    /// <summary>Is every character of this run reachable on the US group?</summary>
    public static bool Covers(string text)
    {
        foreach (var rune in text.EnumerateRunes())
            if (!ByChar.ContainsKey(rune.Value)) return false;
        return true;
    }

    /// <summary>
    /// Append an ordered press/release batch for `text` on the US group, or return false if any
    /// character is not on it. Shape matches AraKeymap.TryStrokes exactly, because the portal
    /// consumes one event stream and must not care which table built it.
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
