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

    /// <summary>Publish text and acknowledge only after the STA clipboard returns it exactly.</summary>
    public static bool SetTextConfirmed(string text)
    {
        return RunSta(() =>
        {
            try
            {
                if (string.IsNullOrEmpty(text)) Clipboard.Clear();
                else Clipboard.SetText(text);
                for (var attempt = 0; attempt < 12; attempt++)
                {
                    var actual = Clipboard.ContainsText() ? Clipboard.GetText() ?? "" : "";
                    if (string.Equals(actual, text, StringComparison.Ordinal)) return true;
                    if (attempt < 11) Thread.Sleep(25);
                }
                Log.Warn("Windows clipboard did not return the requested text within the confirmation budget.");
                return false;
            }
            catch (Exception ex)
            {
                Log.Warn("Clipboard text confirmation failed: " + ex.Message);
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

    /// <summary>Publish an image and confirm its decoded pixels before acknowledging it.</summary>
    public static bool SetImagePngConfirmed(byte[] data)
    {
        if (data.Length == 0) return false;
        return RunSta(() =>
        {
            try
            {
                using var stream = new MemoryStream(data);
                using var expected = Image.FromStream(stream);
                var expectedPng = CanonicalPng(expected);
                Clipboard.SetImage(expected);
                for (var attempt = 0; attempt < 12; attempt++)
                {
                    using var actual = Clipboard.ContainsImage() ? Clipboard.GetImage() : null;
                    if (actual is not null
                        && expectedPng.AsSpan().SequenceEqual(CanonicalPng(actual)))
                        return true;
                    if (attempt < 11) Thread.Sleep(25);
                }
                Log.Warn("Windows clipboard did not return the requested image within the confirmation budget.");
                return false;
            }
            catch (Exception ex)
            {
                Log.Warn("Clipboard image confirmation failed: " + ex.Message);
                return false;
            }
        });
    }

    private static byte[] CanonicalPng(Image image)
    {
        using var bitmap = new Bitmap(image.Width, image.Height, PixelFormat.Format32bppArgb);
        using (var graphics = Graphics.FromImage(bitmap))
            graphics.DrawImageUnscaled(image, 0, 0);
        using var output = new MemoryStream();
        bitmap.Save(output, ImageFormat.Png);
        return output.ToArray();
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
