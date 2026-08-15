namespace MoRemote;

/// <summary>One maximal committed-text run and the native mechanism which can preserve it.</summary>
public readonly record struct PlannedTextRun(string Text, bool Arabic, bool UnicodePaste);

/// <summary>
/// Splits committed browser text without breaking Unicode grapheme clusters into separate paste
/// transactions. ASCII stays on the normal Latin/US key paths, Arabic uses its measured keymap,
/// and codepoints no installed built-in map carries take the exact Unicode compatibility path.
/// </summary>
public static class TextRunPlanner
{
    /// <summary>
    /// One unsupported grapheme makes the complete gathered browser commit an exact clipboard
    /// transaction. Splitting one commit into several clipboard owners is not safe: Wayland
    /// clients may fetch an earlier Paste asynchronously after the next selection was published.
    /// </summary>
    public static bool RequiresAtomicPaste(IReadOnlyList<PlannedTextRun> parts) =>
        parts.Any(part => part.UnicodePaste);

    public static List<PlannedTextRun> Split(string run)
    {
        var parts = new List<PlannedTextRun>();
        var buf = new System.Text.StringBuilder();
        // 0 Latin/US, 1 Arabic keymap, 2 exact Unicode paste, -1 not chosen yet.
        int mode = -1;
        var elements = System.Globalization.StringInfo.GetTextElementEnumerator(run);
        while (elements.MoveNext())
        {
            var element = elements.GetTextElement();
            int want = Classify(element);
            // ASCII punctuation common to both maps stays with its surrounding run. Consecutive
            // unsupported graphemes stay together so emoji ZWJ, skin-tone and keycap sequences are
            // one clipboard transaction rather than independently scheduled pieces.
            if (mode >= 0 && want != mode && !(mode != 2 && want != 2 && Ambiguous(element)))
            {
                parts.Add(new(buf.ToString(), mode == 1, mode == 2));
                buf.Clear();
                mode = want;
            }
            else if (mode < 0) mode = want;
            buf.Append(element);
        }
        if (buf.Length > 0) parts.Add(new(buf.ToString(), mode == 1, mode == 2));
        return parts;
    }

    private static int Classify(string element)
    {
        bool arabic = false;
        foreach (var rune in element.EnumerateRunes())
        {
            if (AraKeymap.NeedsArabicGroup(rune.Value)) arabic = true;
            else if (!IsLatinTypable(rune.Value)) return 2;
        }
        return arabic ? 1 : 0;
    }

    private static bool Ambiguous(string element)
    {
        foreach (var rune in element.EnumerateRunes())
            if (rune.Value > 0x7f || !AraKeymap.Has(rune.Value) || !IsLatinTypable(rune.Value))
                return false;
        return true;
    }

    private static bool IsLatinTypable(int c) => c is >= 0x20 and <= 0x7e;
}
