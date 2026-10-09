namespace MoRemote;

/// <summary>A private, uniquely allocated directory for one fallback capture.</summary>
public sealed class CaptureScratch : IDisposable
{
    private readonly DirectoryInfo _directory = Directory.CreateTempSubdirectory("mo-remote-capture-");
    public string FilePath => Path.Combine(_directory.FullName, "capture.png");

    public void Dispose()
    {
        try { _directory.Delete(recursive: true); }
        catch (DirectoryNotFoundException) { }
        catch (IOException) { }
        catch (UnauthorizedAccessException) { }
    }
}
