using SkiaSharp;
using MoRemote;

static class FallbackJpegEncoderTests
{
    public static void Run()
    {
        var first = new CaptureScratch();
        using (var second = new CaptureScratch())
        {
            if (first.FilePath == second.FilePath || File.Exists(first.FilePath))
                throw new Exception("fallback capture paths are reused or contain an old picture");
            if (OperatingSystem.IsLinux())
            {
                var parent = Path.GetDirectoryName(first.FilePath)!;
                var mode = File.GetUnixFileMode(parent);
                if (mode != (UnixFileMode.UserRead | UnixFileMode.UserWrite | UnixFileMode.UserExecute))
                    throw new Exception("fallback capture directory permits another user's access");
            }
            File.WriteAllText(first.FilePath, "synthetic picture");
            first.Dispose();
            if (Directory.Exists(Path.GetDirectoryName(first.FilePath)))
                throw new Exception("fallback capture files survived disposal");
        }
        var directory = Path.Combine(Path.GetTempPath(), "moos-codec-" + Guid.NewGuid());
        Directory.CreateDirectory(directory);
        try
        {
            var path = Path.Combine(directory, "capture.png");
            using var bitmap = new SKBitmap(320, 180);
            using (var canvas = new SKCanvas(bitmap)) canvas.Clear(SKColors.Red);
            using (var image = SKImage.FromBitmap(bitmap))
            using (var png = image.Encode(SKEncodedImageFormat.Png, 100))
            using (var file = File.Create(path)) png.SaveTo(file);
            foreach (var (scale, width, height) in new[] { (1d, 320, 180), (.998, 320, 180), (.5, 160, 90), (.01, 64, 36), (2d, 320, 180) })
            {
                var bytes = FallbackJpegEncoder.Encode(path, 75, scale);
                if (bytes.Length < 3 || bytes[0] != 0xff || bytes[1] != 0xd8)
                    throw new Exception("fallback output is not a JPEG");
                using var decoded = SKBitmap.Decode(bytes);
                if (decoded is null || decoded.Width != width || decoded.Height != height)
                    throw new Exception("fallback changed the expected aspect ratio or scale");
                var pixel = decoded.GetPixel(width / 2, height / 2);
                if (pixel.Red < 220 || pixel.Green > 25 || pixel.Blue > 25)
                    throw new Exception("fallback lost actual captured pixel colors");
            }
            foreach (var quality in new[] { -10, 200 })
            {
                using var decoded = SKBitmap.Decode(FallbackJpegEncoder.Encode(path, quality, 1));
                if (decoded is null) throw new Exception("clamped quality failed");
            }
            var complete = File.ReadAllBytes(path);
            File.WriteAllBytes(path, complete[..(complete.Length / 2)]);
            Refuse(() => FallbackJpegEncoder.Encode(path, 75, 1));
            using (var image = SKImage.FromBitmap(bitmap))
            using (var jpeg = image.Encode(SKEncodedImageFormat.Jpeg, 90))
            using (var file = File.Create(path)) jpeg.SaveTo(file);
            using (var decoded = SKBitmap.Decode(FallbackJpegEncoder.Encode(path, 75, .5)))
            {
                if (decoded is null || decoded.Width != 160 || decoded.Height != 90 ||
                    decoded.GetPixel(80, 45).Red < 220)
                    throw new Exception("JPEG input lost captured pixels or scaling");
            }
            using (var canvas = new SKCanvas(bitmap)) canvas.Clear(SKColors.Transparent);
            using (var image = SKImage.FromBitmap(bitmap))
            using (var png = image.Encode(SKEncodedImageFormat.Png, 100))
            using (var file = File.Create(path)) png.SaveTo(file);
            using (var decoded = SKBitmap.Decode(FallbackJpegEncoder.Encode(path, 75, 1)))
            {
                if (decoded is null || decoded.GetPixel(160, 90).Red > 5 ||
                    decoded.GetPixel(160, 90).Green > 5 || decoded.GetPixel(160, 90).Blue > 5)
                    throw new Exception("transparent pixels did not use the defined black JPEG matte");
            }
            Refuse(() => FallbackJpegEncoder.Encode(path, 75, double.NaN));
            Refuse(() => FallbackJpegEncoder.Encode(path, 75, double.PositiveInfinity));
            File.WriteAllText(path, "not image pixels");
            Refuse(() => FallbackJpegEncoder.Encode(path, 75, 1));
            File.WriteAllBytes(path, []);
            Refuse(() => FallbackJpegEncoder.Encode(path, 75, 1));
            using (var file = File.Create(path)) file.SetLength(FallbackJpegEncoder.MaxInputBytes + 1);
            Refuse(() => FallbackJpegEncoder.Encode(path, 75, 1));
            Console.WriteLine("PASS: native PNG/JPEG pixels, dimensions, scaling, alpha matte, quality and invalid/truncated-input budgets");
        }
        finally { Directory.Delete(directory, true); }
    }

    private static void Refuse(Action action)
    {
        try { action(); }
        catch (InvalidDataException) { return; }
        throw new Exception("fallback accepted invalid or oversized input");
    }
}
