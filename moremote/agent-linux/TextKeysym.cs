namespace MoRemote;

/// <summary>
/// Maps Unicode to X keysyms for the portal's NotifyKeyboardKeysym.
///
/// This is only used for characters that are reachable on the ACTIVE keymap group at shift level
/// one — in practice ASCII. It deliberately no longer tries to reach Arabic: KWin resolves a
/// keysym against the active group only, so on a `de,ara` keymap sitting in the German group an
/// Arabic keysym (legacy 0x05xx or the 0x01000000+Unicode form alike) resolves to no real key.
/// Measured: 'م' arrived as keycode 247 / keyval 0x1008ffb5 — a key that types nothing. Arabic is
/// typed on its real keymap group; characters no installed group carries use the explicitly
/// ordered, byte-confirmed fallback in InputInjector.
/// </summary>
public static class TextKeysym
{
    public static int ForCodepoint(int codepoint) =>
        codepoint is >= 0x20 and <= 0x7e or >= 0xa0 and <= 0xff
            ? codepoint
            : 0x01000000 + codepoint;
}
