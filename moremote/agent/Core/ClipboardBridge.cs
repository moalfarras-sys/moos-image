using System.Drawing;
using System.Drawing.Imaging;
using System.Windows.Forms;

namespace MoRemote;

/// <summary>One snapshot of the Windows clipboard (text or image).</summary>
public sealed record ClipContent(string Kind, string? Text, byte[]? ImagePng);

/// <summary>
/// Reads/writes the Windows clipboard (text + images). The OLE clipboard requires an STA
/// thread, so each call runs on a short-lived STA thread. Only ever invoked on an explicit
/// user button press from the phone — never polled or read in the background.
/// </summary>
public static class ClipboardBridge
{
    public static bool IsReady => true;
    public static ClipContent GetContent()
    {
        ClipContent result = new("empty", null, null);
        RunSta(() =>
        {
            try
            {
                if (Clipboard.ContainsImage())
                {
                    using var img = Clipboard.GetImage();
                    if (img != null)
                    {
                        using var ms = new MemoryStream();
                        img.Save(ms, ImageFormat.Png);
                        result = new ClipContent("image", null, ms.ToArray());
                    }
                }
                else if (Clipboard.ContainsText())
                {
                    result = new ClipContent("text", Clipboard.GetText() ?? "", null);
                }
            }
            catch (Exception ex) { Log.Warn("Clipboard read failed: " + ex.Message); }
        });
        return result;
    }

    public static string GetText() => GetContent() is { Kind: "text", Text: { } t } ? t : "";

    public static bool SetText(string text)
    {
        return RunSta(() =>
        {
            try
            {
                if (string.IsNullOrEmpty(text)) Clipboard.Clear();
                else Clipboard.SetText(text);
                return true;
            }
            catch (Exception ex)
            {
                Log.Warn("Clipboard write failed: " + ex.Message);
                return false;
            }
        });
    }

    public static bool SetImagePng(byte[] data)
    {
        return RunSta(() =>
        {
            try
            {
                using var ms = new MemoryStream(data);
                using var img = Image.FromStream(ms);
                // SetImage serialises a copy onto the clipboard, so disposing after is safe.
                Clipboard.SetImage(img);
                return true;
            }
            catch (Exception ex)
            {
                Log.Warn("Clipboard image write failed: " + ex.Message);
                return false;
            }
        });
    }

    private static bool RunSta(Func<bool> action)
    {
        var result = false;
        var t = new Thread(() => result = action()) { IsBackground = true };
        t.SetApartmentState(ApartmentState.STA);
        t.Start();
        return t.Join(5000) && result;
    }

    private static void RunSta(Action action)
    {
        var t = new Thread(() => action()) { IsBackground = true };
        t.SetApartmentState(ApartmentState.STA);
        t.Start();
        t.Join(5000);
    }
}
