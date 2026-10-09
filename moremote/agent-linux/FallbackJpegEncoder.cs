using SkiaSharp;

namespace MoRemote;

/// <summary>Bounded PNG/JPEG conversion for Spectacle's private capture file.</summary>
public static class FallbackJpegEncoder
{
    public const long MaxPixels = 64L * 1024 * 1024;
    public const long MaxInputBytes = 128L * 1024 * 1024;

    public static byte[] Encode(string path, int quality, double scale)
    {
        var length = new FileInfo(path).Length;
        if (length <= 0 || length > MaxInputBytes || !double.IsFinite(scale))
            throw new InvalidDataException("Invalid fallback capture size or scale.");

        using var file = File.OpenRead(path);
        if (file.Length <= 0 || file.Length > MaxInputBytes)
            throw new InvalidDataException("Fallback capture changed outside the input budget.");
        using var data = SKData.Create(file, checked((int)file.Length));
        using var codec = SKCodec.Create(data)
            ?? throw new InvalidDataException("Fallback capture cannot be decoded.");
        if (codec.EncodedFormat is not (SKEncodedImageFormat.Png or SKEncodedImageFormat.Jpeg))
            throw new InvalidDataException("Fallback capture must be PNG or JPEG.");
        var info = codec.Info;
        if (info.Width <= 0 || info.Height <= 0 || (long)info.Width * info.Height > MaxPixels)
            throw new InvalidDataException("Fallback capture dimensions exceed the budget.");

        using var original = new SKBitmap(info.WithColorType(SKColorType.Bgra8888)
            .WithAlphaType(SKAlphaType.Premul));
        if (codec.GetPixels(original.Info, original.GetPixels()) != SKCodecResult.Success)
            throw new InvalidDataException("Fallback capture pixels are incomplete or invalid.");
        scale = Math.Clamp(scale, .2, 1);
        if (scale >= .995) scale = 1; // Preserve the capture path's near-original size policy.
        var width = Math.Max(1, (int)(info.Width * scale));
        var height = Math.Max(1, (int)(info.Height * scale));
        using var resized = new SKBitmap(width, height);
        using (var canvas = new SKCanvas(resized))
        {
            // JPEG has no alpha: use a defined matte instead of uninitialized pixels.
            canvas.Clear(SKColors.Black);
            canvas.DrawBitmap(original, new SKRect(0, 0, width, height),
                new SKSamplingOptions(SKFilterMode.Linear, SKMipmapMode.None));
        }
        using var image = SKImage.FromBitmap(resized);
        using var encoded = image.Encode(SKEncodedImageFormat.Jpeg, Math.Clamp(quality, 10, 95))
            ?? throw new InvalidDataException("Fallback JPEG encoding failed.");
        return encoded.ToArray();
    }
}
