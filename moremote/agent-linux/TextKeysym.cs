namespace MoRemote;

/// <summary>Maps Unicode text to keysyms accepted by KWin's RemoteDesktop portal.</summary>
public static class TextKeysym
{
    public static int ForCodepoint(int codepoint)
    {
        // XKB represents the core Arabic block with legacy 0x05xx keysyms. The generic
        // 0x01000000+Unicode form is accepted by D-Bus but silently produces no key event.
        if (codepoint == 0x060c) return 0x05ac;
        if (codepoint == 0x061b) return 0x05bb;
        if (codepoint == 0x061f) return 0x05bf;
        if (codepoint is >= 0x0621 and <= 0x063a) return 0x05c1 + (codepoint - 0x0621);
        if (codepoint is >= 0x0640 and <= 0x0652) return 0x05e0 + (codepoint - 0x0640);
        return codepoint is >= 0x20 and <= 0x7e or >= 0xa0 and <= 0xff
            ? codepoint
            : 0x01000000 + codepoint;
    }
}
