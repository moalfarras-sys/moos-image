namespace MoRemote;

public sealed record FileEntry(string name, string path, bool isDir, long size);
public sealed record FileListing(string title, string? path, string? parent, FileEntry[] entries);

/// <summary>
/// Browses the local filesystem for the file-transfer feature. The user owns this PC, so
/// any readable path is allowed; we just skip hidden/system entries and swallow access errors.
/// </summary>
public static class FileService
{
    public const long MaxUploadBytes = 1_073_741_824; // 1 GiB per file
    private const long FreeSpaceReserve = 536_870_912; // keep 512 MiB for the OS and logs
    public static FileListing List(string? path)
    {
        if (string.IsNullOrWhiteSpace(path)) return Roots();

        var dir = new DirectoryInfo(path);
        if (!dir.Exists) throw new DirectoryNotFoundException("Folder not found");

        var entries = new List<FileEntry>();
        foreach (var d in SafeDirs(dir)) entries.Add(new FileEntry(d.Name, d.FullName, true, 0));
        foreach (var f in SafeFiles(dir)) entries.Add(new FileEntry(f.Name, f.FullName, false, f.Length));

        var title = string.IsNullOrEmpty(dir.Name) ? dir.FullName : dir.Name;
        return new FileListing(title, dir.FullName, dir.Parent?.FullName, entries.ToArray());
    }

    public static string UniquePath(string dir, string name)
    {
        name = Path.GetFileName(name);
        if (string.IsNullOrWhiteSpace(name)) name = "upload.bin";
        var target = Path.Combine(dir, name);
        int i = 1;
        while (File.Exists(target))
        {
            var stem = Path.GetFileNameWithoutExtension(name);
            var ext = Path.GetExtension(name);
            target = Path.Combine(dir, $"{stem} ({i}){ext}");
            i++;
        }
        return target;
    }

    public static async Task<string> SaveUploadAsync(Stream source, string dir, string name,
        CancellationToken cancellationToken)
    {
        Directory.CreateDirectory(dir);
        var target = UniquePath(dir, name);
        var temp = Path.Combine(dir, $".moremote-upload-{Guid.NewGuid():N}.part");
        var buffer = new byte[128 * 1024];
        long written = 0;
        long nextSpaceCheck = 0;
        try
        {
            await using (var output = new FileStream(temp, FileMode.CreateNew, FileAccess.Write,
                FileShare.None, buffer.Length, FileOptions.Asynchronous))
            {
                while (true)
                {
                    var read = await source.ReadAsync(buffer, cancellationToken);
                    if (read == 0) break;
                    written += read;
                    if (written > MaxUploadBytes)
                        throw new InvalidDataException("File exceeds the 1 GiB upload limit");
                    // DriveInfo can be a filesystem query. Refresh every 64 MiB, not for every
                    // 128 KiB network chunk (8,192 stat calls for a 1 GiB file).
                    if (written >= nextSpaceCheck)
                    {
                        if (AvailableSpaceFor(dir) < FreeSpaceReserve + buffer.Length)
                            throw new IOException("Not enough free space to finish the upload safely");
                        nextSpaceCheck = written + 64L * 1024 * 1024;
                    }
                    await output.WriteAsync(buffer.AsMemory(0, read), cancellationToken);
                }
                await output.FlushAsync(cancellationToken);
            }
            File.Move(temp, target);
            return target;
        }
        catch
        {
            try { File.Delete(temp); } catch { }
            throw;
        }
    }

    private static long AvailableSpaceFor(string path)
    {
        var full = Path.GetFullPath(path);
        var drive = DriveInfo.GetDrives()
            .Where(d => d.IsReady && full.StartsWith(d.RootDirectory.FullName,
                OperatingSystem.IsWindows() ? StringComparison.OrdinalIgnoreCase : StringComparison.Ordinal))
            .OrderByDescending(d => d.RootDirectory.FullName.Length)
            .FirstOrDefault();
        return drive?.AvailableFreeSpace ?? long.MaxValue;
    }

    private static IEnumerable<DirectoryInfo> SafeDirs(DirectoryInfo d)
    {
        try { return d.EnumerateDirectories().Where(x => !Hidden(x.Attributes)).OrderBy(x => x.Name, StringComparer.OrdinalIgnoreCase); }
        catch { return Array.Empty<DirectoryInfo>(); }
    }
    private static IEnumerable<FileInfo> SafeFiles(DirectoryInfo d)
    {
        try { return d.EnumerateFiles().Where(x => !Hidden(x.Attributes)).OrderBy(x => x.Name, StringComparer.OrdinalIgnoreCase); }
        catch { return Array.Empty<FileInfo>(); }
    }
    private static bool Hidden(FileAttributes a) => (a & (FileAttributes.Hidden | FileAttributes.System)) != 0;

    private static FileListing Roots()
    {
        var e = new List<FileEntry>();
        void Add(string label, string p) { try { if (Directory.Exists(p)) e.Add(new FileEntry(label, p, true, 0)); } catch { } }
        Add("Desktop", Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory));
        Add("Downloads", Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), "Downloads"));
        Add("Documents", Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments));
        Add("Pictures", Environment.GetFolderPath(Environment.SpecialFolder.MyPictures));
        Add("Music", Environment.GetFolderPath(Environment.SpecialFolder.MyMusic));
        Add("Videos", Environment.GetFolderPath(Environment.SpecialFolder.MyVideos));
        foreach (var dr in DriveInfo.GetDrives())
            try { if (dr.IsReady) e.Add(new FileEntry(dr.Name, dr.RootDirectory.FullName, true, 0)); } catch { }
        return new FileListing("This PC", null, null, e.ToArray());
    }
}
