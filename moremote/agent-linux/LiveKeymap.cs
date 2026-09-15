using System.Globalization;
using System.Text;
using System.Text.Json;

namespace MoRemote;

/// <summary>A key position plus the level modifiers that must be held while it is pressed.</summary>
public readonly record struct KeyStroke(ushort Code, bool Shift, bool Level3)
{
    /// <summary>Press/release events this stroke puts on the wire.</summary>
    public int Cost => 2 + (Shift ? 2 : 0) + (Level3 ? 2 : 0);
}

/// <summary>
/// One keymap group exactly as the portal helper compiled it from KWin's own kxkbrc names with
/// libxkbcommon — the library and data the compositor uses. See build_keymaps in
/// mo-remote-portal.py for why positions come from the running keymap, not from tables here.
/// </summary>
public sealed class GroupKeymap
{
    private readonly Dictionary<int, KeyStroke> _chars = new();
    private readonly Dictionary<int, KeyStroke> _dead = new();
    private readonly Dictionary<ushort, HashSet<int>> _byPosition = new();
    private readonly Dictionary<ushort, int> _level1 = new();

    private GroupKeymap(string code, int group, ushort? shift, ushort? level3)
    {
        Code = code;
        Group = group;
        ShiftCode = shift;
        Level3Code = level3;
    }

    /// <summary>The layout code KWin reports for this group, e.g. `ara` or `de`.</summary>
    public string Code { get; }
    /// <summary>The group's index in KWin's layout ring when the helper compiled it.</summary>
    public int Group { get; }
    public ushort? ShiftCode { get; }
    public ushort? Level3Code { get; }

    /// <summary>The cheapest stroke producing this character on this group.</summary>
    public bool TryChar(int codepoint, out KeyStroke stroke) => _chars.TryGetValue(codepoint, out stroke);

    /// <summary>The dead key that applies this combining mark to the next base character.</summary>
    public bool TryDead(int mark, out KeyStroke stroke) => _dead.TryGetValue(mark, out stroke);

    /// <summary>Does this physical key produce the character at any level this group can reach?</summary>
    public bool Produces(ushort code, int codepoint) =>
        _byPosition.TryGetValue(code, out var produced) && produced.Contains(codepoint);

    /// <summary>The unmodified character at a position, or -1 when it has none.</summary>
    public int Level1At(ushort code) => _level1.TryGetValue(code, out var codepoint) ? codepoint : -1;

    /// <summary>Parses one helper group, or null when any part is malformed — a partly trusted
    /// keymap would type confidently wrong text, and exact paste is always available instead.</summary>
    internal static GroupKeymap? Parse(JsonElement element)
    {
        if (element.ValueKind != JsonValueKind.Object) return null;
        if (!element.TryGetProperty("code", out var codeElement) || codeElement.ValueKind != JsonValueKind.String
            || codeElement.GetString() is not { Length: > 0 and <= 64 } code) return null;
        if (!TryInt(element, "group", out var group) || group is < 0 or > 31) return null;
        var map = new GroupKeymap(code, group, OptionalCode(element, "shift"), OptionalCode(element, "level3"));

        if (!element.TryGetProperty("levels", out var levels) || levels.ValueKind != JsonValueKind.Array) return null;
        foreach (var entry in levels.EnumerateArray())
        {
            if (!TryTriple(entry, out var key, out var mods, out var codepoint) || !IsScalar(codepoint)
                || codepoint < 0x20) return null;
            if (!map.TryStroke(key, mods, out var stroke)) continue;
            if (!map._byPosition.TryGetValue(stroke.Code, out var produced))
                map._byPosition[stroke.Code] = produced = [];
            produced.Add(codepoint);
            if (mods == 0) map._level1.TryAdd(stroke.Code, codepoint);
            if (!map._chars.TryGetValue(codepoint, out var existing) || stroke.Cost < existing.Cost)
                map._chars[codepoint] = stroke;
        }

        if (element.TryGetProperty("dead", out var dead) && dead.ValueKind == JsonValueKind.Array)
        {
            foreach (var entry in dead.EnumerateArray())
            {
                if (!TryTriple(entry, out var key, out var mods, out var mark) || mark is < 0x0300 or > 0x036F)
                    return null;
                if (!map.TryStroke(key, mods, out var stroke)) continue;
                if (!map._dead.TryGetValue(mark, out var existing) || stroke.Cost < existing.Cost)
                    map._dead[mark] = stroke;
            }
        }
        return map;
    }

    private bool TryStroke(int key, int mods, out KeyStroke stroke)
    {
        bool shift = (mods & 1) != 0, level3 = (mods & 2) != 0;
        stroke = new KeyStroke((ushort)key, shift, level3);
        return (!shift || ShiftCode is not null) && (!level3 || Level3Code is not null);
    }

    private static ushort? OptionalCode(JsonElement element, string name) =>
        TryInt(element, name, out var value) && value is > 0 and <= 255 ? (ushort)value : null;

    private static bool TryInt(JsonElement element, string name, out int value)
    {
        value = 0;
        return element.TryGetProperty(name, out var property) && property.ValueKind == JsonValueKind.Number
            && property.TryGetInt32(out value);
    }

    internal static bool TryTriple(JsonElement entry, out int first, out int second, out int third)
    {
        first = second = third = 0;
        if (entry.ValueKind != JsonValueKind.Array || entry.GetArrayLength() != 3) return false;
        var values = new int[3];
        int i = 0;
        foreach (var item in entry.EnumerateArray())
        {
            if (item.ValueKind != JsonValueKind.Number || !item.TryGetInt32(out values[i++])) return false;
        }
        (first, second, third) = (values[0], values[1], values[2]);
        return first is > 0 and <= 255 && second is >= 0 and <= 3;
    }

    internal static bool IsScalar(int codepoint) =>
        codepoint is >= 0 and < 0x110000 && codepoint is < 0xD800 or > 0xDFFF;
}

/// <summary>What to do with a desktop viewer's physical key before pressing it.</summary>
public enum PhysicalKeyPlan
{
    /// <summary>The active group already puts the viewer's character on this key (or nothing can).</summary>
    AsIs,
    /// <summary>Another loaded group puts the viewer's character on this key: select it first.</summary>
    SelectGroup,
    /// <summary>No group has the character on this key, but some group can type it.</summary>
    TypeText,
}

/// <summary>Every loaded group, which one is active, and the Unicode composition the planner needs.</summary>
public sealed class LiveKeymap
{
    private readonly IReadOnlyDictionary<(int Base, int Mark), int> _compose;
    private readonly IReadOnlyDictionary<int, (int Base, int Mark)> _decompose;

    public LiveKeymap(IReadOnlyList<GroupKeymap> groups, int current,
        IReadOnlyDictionary<(int Base, int Mark), int>? compose = null)
    {
        Groups = groups;
        Current = current;
        _compose = compose ?? new Dictionary<(int, int), int>();
        var decompose = new Dictionary<int, (int, int)>();
        foreach (var (pair, composed) in _compose) decompose.TryAdd(composed, pair);
        _decompose = decompose;
    }

    private LiveKeymap(LiveKeymap source, int current)
    {
        Groups = source.Groups;
        Current = current;
        _compose = source._compose;
        _decompose = source._decompose;
    }

    public IReadOnlyList<GroupKeymap> Groups { get; }

    /// <summary>The active group index as last reported by KWin, or -1 when unknown.</summary>
    public int Current { get; }

    public GroupKeymap? CurrentGroup => (uint)Current < (uint)Groups.Count ? Groups[Current] : null;

    public LiveKeymap WithCurrent(int current) => new(this, current);

    public bool TryCompose(int baseCodepoint, int mark, out int composed) =>
        _compose.TryGetValue((baseCodepoint, mark), out composed);

    public bool TryDecompose(int composed, out int baseCodepoint, out int mark)
    {
        var found = _decompose.TryGetValue(composed, out var pair);
        (baseCodepoint, mark) = pair;
        return found;
    }

    /// <summary>
    /// Parses the helper's `keymaps` and `compose` fields. Groups must arrive complete and in ring
    /// order; anything else yields null so the caller takes the exact paste path.
    /// </summary>
    public static LiveKeymap? Parse(JsonElement keymaps, JsonElement compose, int current)
    {
        if (keymaps.ValueKind != JsonValueKind.Array) return null;
        var groups = new List<GroupKeymap>();
        foreach (var item in keymaps.EnumerateArray())
        {
            var group = GroupKeymap.Parse(item);
            if (group is null || group.Group != groups.Count) return null;
            groups.Add(group);
        }
        if (groups.Count == 0) return null;

        var table = new Dictionary<(int, int), int>();
        if (compose.ValueKind == JsonValueKind.Array)
        {
            foreach (var entry in compose.EnumerateArray())
            {
                if (entry.ValueKind != JsonValueKind.Array || entry.GetArrayLength() != 3) return null;
                var values = entry.EnumerateArray().Select(v => v.ValueKind == JsonValueKind.Number
                    && v.TryGetInt32(out var n) ? n : -1).ToArray();
                if (values.Any(v => !GroupKeymap.IsScalar(v))) return null;
                table.TryAdd((values[1], values[2]), values[0]);
            }
        }
        return new LiveKeymap(groups, current, table);
    }

    /// <summary>
    /// The physical key for Ctrl/Alt+letter, following the rule Qt applies when matching shortcuts:
    /// a Latin symbol on the active group wins; on a non-Latin active group, the key's symbol is
    /// taken from the FIRST other group (in configured order) that has a Latin one there. So on
    /// `ara,de` with Arabic active, Ctrl+Z is the German Z position (evdev 21), which Qt, KDE and
    /// Firefox resolve to Ctrl+Z — not the US position that would read as Ctrl+غ or Ctrl+Y.
    /// </summary>
    public ushort? ShortcutPosition(char letter)
    {
        int codepoint = letter;
        var current = CurrentGroup;
        if (current is not null && current.TryChar(codepoint, out var own) && !own.Shift && !own.Level3)
            return own.Code;
        foreach (var group in Groups)
        {
            if (ReferenceEquals(group, current) || !group.TryChar(codepoint, out var stroke)
                || stroke.Shift || stroke.Level3) continue;
            if (current is not null && IsLatin1(current.Level1At(stroke.Code))) continue;
            var fallback = Groups.FirstOrDefault(other =>
                !ReferenceEquals(other, current) && IsLatin1(other.Level1At(stroke.Code)));
            if (fallback is not null && fallback.Level1At(stroke.Code) == codepoint) return stroke.Code;
        }
        return null;
    }

    /// <summary>
    /// A desktop viewer pressed a physical key that produced `produced` on THEIR keyboard. The remote
    /// must produce the same character, which the active group may not: with Arabic active, a German
    /// or US keyboard's A key would type ش.
    /// </summary>
    public PhysicalKeyPlan PlanPhysical(ushort code, string produced, out GroupKeymap? group)
    {
        group = null;
        int codepoint = -1, count = 0;
        foreach (var rune in produced.EnumerateRunes())
        {
            codepoint = rune.Value;
            if (++count > 1) return PhysicalKeyPlan.AsIs;
        }
        if (count != 1) return PhysicalKeyPlan.AsIs;
        if (CurrentGroup is { } current && current.Produces(code, codepoint)) return PhysicalKeyPlan.AsIs;
        foreach (var candidate in Groups)
        {
            if (!candidate.Produces(code, codepoint)) continue;
            group = candidate;
            return PhysicalKeyPlan.SelectGroup;
        }
        return KeymapPlanner.TryPlan(produced, this, out _) ? PhysicalKeyPlan.TypeText : PhysicalKeyPlan.AsIs;
    }

    private static bool IsLatin1(int codepoint) => codepoint is >= 0x20 and <= 0xFF;
}

/// <summary>A maximal stretch of text typed on one group.</summary>
public readonly record struct PlannedRun(GroupKeymap Group, string Text, IReadOnlyList<KeyStroke> Strokes);

/// <summary>
/// Turns committed text into ordered key strokes on the loaded groups.
///
/// Every grapheme is resolved on every group (direct level, precomposed form, dead key, or dead
/// key + space for a spacing accent). A dynamic program then picks the group per grapheme with the
/// fewest group changes and, after that, the fewest events. Characters several groups carry — space,
/// digits, most punctuation — therefore join the stretch around them instead of forcing a switch,
/// because every switch is an Alt+Shift chord plus a Plasma layout OSD re-encoded into the picture.
/// A grapheme no group can produce fails the whole plan: the caller preserves the complete commit
/// with one exact paste, never a partly typed prefix.
/// </summary>
public static class KeymapPlanner
{
    /// <summary>Larger than any single grapheme's strokes, so a switch is only taken when needed.</summary>
    private const int SwitchCost = 64;
    private const int Unreachable = int.MaxValue / 4;

    public static bool TryPlan(string text, LiveKeymap keymap, out List<PlannedRun> plan)
    {
        plan = [];
        var groups = keymap.Groups;
        if (string.IsNullOrEmpty(text) || groups.Count == 0) return false;

        var elements = new List<string>();
        var enumerator = StringInfo.GetTextElementEnumerator(text);
        while (enumerator.MoveNext()) elements.Add(enumerator.GetTextElement());

        int n = elements.Count, g = groups.Count;
        var strokes = new List<KeyStroke>?[n, g];
        for (int i = 0; i < n; i++)
        {
            bool reachable = false;
            for (int j = 0; j < g; j++)
            {
                strokes[i, j] = Resolve(elements[i], groups[j], keymap);
                reachable |= strokes[i, j] is not null;
            }
            if (!reachable) return false;
        }

        var cost = new int[n, g];
        var from = new int[n, g];
        for (int j = 0; j < g; j++)
        {
            cost[0, j] = strokes[0, j] is { } first
                ? Sum(first) + (j == keymap.Current ? 0 : SwitchCost)
                : Unreachable;
            from[0, j] = -1;
        }
        for (int i = 1; i < n; i++)
        {
            for (int j = 0; j < g; j++)
            {
                cost[i, j] = Unreachable;
                from[i, j] = -1;
                if (strokes[i, j] is not { } own) continue;
                // Staying is considered first, so an equal-cost switch is never taken.
                int best = cost[i - 1, j], bestFrom = j;
                for (int k = 0; k < g; k++)
                {
                    if (k == j) continue;
                    int via = cost[i - 1, k] + SwitchCost;
                    if (via < best) { best = via; bestFrom = k; }
                }
                if (best >= Unreachable) continue;
                cost[i, j] = best + Sum(own);
                from[i, j] = bestFrom;
            }
        }

        int end = -1;
        for (int j = 0; j < g; j++)
        {
            if (cost[n - 1, j] >= Unreachable) continue;
            if (end < 0 || cost[n - 1, j] < cost[n - 1, end]
                || (cost[n - 1, j] == cost[n - 1, end] && j == keymap.Current)) end = j;
        }
        if (end < 0) return false;

        var chosen = new int[n];
        for (int i = n - 1, j = end; i >= 0; i--)
        {
            chosen[i] = j;
            j = from[i, j];
        }

        int start = 0;
        for (int i = 1; i <= n; i++)
        {
            if (i < n && chosen[i] == chosen[start]) continue;
            int group = chosen[start];
            var runStrokes = new List<KeyStroke>();
            var runText = new StringBuilder();
            for (int k = start; k < i; k++)
            {
                runStrokes.AddRange(strokes[k, group]!);
                runText.Append(elements[k]);
            }
            plan.Add(new PlannedRun(groups[group], runText.ToString(), runStrokes));
            start = i;
        }
        return true;
    }

    /// <summary>Appends the press/release events for a run, modifiers wrapped around each key.</summary>
    public static void AppendEvents(PlannedRun run, List<object> events)
    {
        foreach (var stroke in run.Strokes)
        {
            if (stroke.Shift) events.Add(new { code = (int)run.Group.ShiftCode!.Value, down = true });
            if (stroke.Level3) events.Add(new { code = (int)run.Group.Level3Code!.Value, down = true });
            events.Add(new { code = (int)stroke.Code, down = true });
            events.Add(new { code = (int)stroke.Code, down = false });
            if (stroke.Level3) events.Add(new { code = (int)run.Group.Level3Code!.Value, down = false });
            if (stroke.Shift) events.Add(new { code = (int)run.Group.ShiftCode!.Value, down = false });
        }
    }

    /// <summary>The strokes that type one grapheme on one group, or null when it cannot.</summary>
    internal static List<KeyStroke>? Resolve(string element, GroupKeymap group, LiveKeymap keymap)
    {
        var runes = new List<int>();
        foreach (var rune in element.EnumerateRunes()) runes.Add(rune.Value);
        var result = new List<KeyStroke>(runes.Count);
        for (int i = 0; i < runes.Count; i++)
        {
            int codepoint = runes[i];
            int mark = i + 1 < runes.Count && IsCombiningMark(runes[i + 1]) ? runes[i + 1] : -1;
            if (mark >= 0)
            {
                // Decomposed input (a + U+0308) uses the precomposed key when this group has one.
                if (keymap.TryCompose(codepoint, mark, out var composed) && group.TryChar(composed, out var precomposed))
                {
                    result.Add(precomposed);
                    i++;
                    continue;
                }
                // Otherwise a dead key applies the mark — unless the mark is a key of its own, as
                // Arabic harakat are, in which case letter and mark are typed in sequence below.
                if (!group.TryChar(mark, out _) && group.TryDead(mark, out var deadForMark)
                    && group.TryChar(codepoint, out var baseForMark))
                {
                    result.Add(deadForMark);
                    result.Add(baseForMark);
                    i++;
                    continue;
                }
            }
            if (group.TryChar(codepoint, out var direct))
            {
                result.Add(direct);
                continue;
            }
            // Precomposed text (é from a French phone keyboard) on a group with the dead key.
            if (keymap.TryDecompose(codepoint, out var baseCodepoint, out var accent)
                && group.TryDead(accent, out var dead) && group.TryChar(baseCodepoint, out var baseKey))
            {
                result.Add(dead);
                result.Add(baseKey);
                continue;
            }
            // German has ^ and ` only as dead keys; dead key + space yields them in every shipped
            // compose table (`<dead_circumflex> <space> : "^"`). Other accents map to different
            // characters there (dead_acute + space is an apostrophe), so they are not guessed.
            if (SpacingAccentMark(codepoint) is int spacing && group.TryDead(spacing, out var spacingDead)
                && group.TryChar(' ', out var space))
            {
                result.Add(spacingDead);
                result.Add(space);
                continue;
            }
            return null;
        }
        return result;
    }

    private static int? SpacingAccentMark(int codepoint) => codepoint switch
    {
        '^' => 0x0302,
        '`' => 0x0300,
        '~' => 0x0303,
        _ => null,
    };

    private static bool IsCombiningMark(int codepoint) =>
        CharUnicodeInfo.GetUnicodeCategory(codepoint) is UnicodeCategory.NonSpacingMark
            or UnicodeCategory.SpacingCombiningMark or UnicodeCategory.EnclosingMark;

    private static int Sum(List<KeyStroke> strokes)
    {
        int total = 0;
        foreach (var stroke in strokes) total += stroke.Cost;
        return total;
    }
}
