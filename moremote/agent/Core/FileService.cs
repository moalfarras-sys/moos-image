namespace MoRemote;

public sealed record FileEntry(string name, string path, bool isDir, long size);
public sealed record FileListing(string title, string? path, string? parent, FileEntry[] entries);

/// <summary>
/// Browses the local filesystem for the file-transfer feature. The user owns this PC, so
/// any readable path is allowed; we just skip hidden/system entries and swallow access errors.
/// </summary>
public static class FileService
{
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
