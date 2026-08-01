using System.Collections.Concurrent;
using System.Security.Cryptography;
using System.Text;

namespace MoRemote;

public sealed record UploadStart(string Id, long Offset, long TotalBytes);
public sealed record UploadProgress(long Offset, long TotalBytes);

/// <summary>Bounded, sequential chunk uploads with atomic visibility at commit.</summary>
public sealed class UploadSessionStore
{
    public const int MaxChunkBytes = 4 * 1024 * 1024;
    private const int MaxSessions = 64;
    private static readonly TimeSpan Lifetime = TimeSpan.FromMinutes(30);

    private sealed class Session
    {
        public required string Id { get; init; }
        public required string OwnerHash { get; init; }
        public required string Directory { get; init; }
        public required string Name { get; init; }
        public required string TempPath { get; init; }
        public required long TotalBytes { get; init; }
        public required DateTimeOffset Expires { get; set; }
        public long Offset;
        public object Gate { get; } = new();
    }

    private readonly ConcurrentDictionary<string, Session> _sessions = new();
    private readonly ConcurrentQueue<string> _order = new();
    private readonly TimeProvider _clock;

    public UploadSessionStore(TimeProvider? clock = null) => _clock = clock ?? TimeProvider.System;

    public UploadStart Start(string ownerToken, string directory, string name, long totalBytes)
    {
        if (string.IsNullOrWhiteSpace(ownerToken)) throw new UnauthorizedAccessException();
        if (totalBytes is < 0 or > FileService.MaxUploadBytes)
            throw new InvalidDataException("Upload size is outside the supported range");
        var dir = Path.GetFullPath(directory);
        Directory.CreateDirectory(dir);
        CleanupExpired();
        while (_sessions.Count >= MaxSessions && _order.TryDequeue(out var oldest))
        {
            if (_sessions.TryGetValue(oldest, out var oldSession))
                lock (oldSession.Gate) Remove(oldest);
        }

        var id = RandomToken();
        var safeName = Path.GetFileName(name);
        if (string.IsNullOrWhiteSpace(safeName)) safeName = "upload.bin";
        var temp = Path.Combine(dir, $".moremote-upload-session-{id}.part");
        using (new FileStream(temp, FileMode.CreateNew, FileAccess.Write, FileShare.None)) { }
        var session = new Session {
            Id = id,
            OwnerHash = Hash(ownerToken),
            Directory = dir,
            Name = safeName,
            TempPath = temp,
            TotalBytes = totalBytes,
            Expires = _clock.GetUtcNow() + Lifetime,
        };
        _sessions[id] = session;
        _order.Enqueue(id);
        CleanupAbandonedFiles(dir, temp);
        return new UploadStart(id, 0, totalBytes);
    }

    public UploadProgress Status(string ownerToken, string? id)
    {
        var session = Require(ownerToken, id);
        lock (session.Gate)
        {
            EnsureLive(session);
            return new UploadProgress(session.Offset, session.TotalBytes);
        }
    }

    public async Task<UploadProgress> AppendAsync(string ownerToken, string? id, long offset,
        Stream body, CancellationToken cancellationToken)
    {
        var session = Require(ownerToken, id);
        // Read before taking the per-session lock so a slow sender cannot block Status/Cancel.
        var chunk = await FileService.ReadBoundedAsync(body, MaxChunkBytes, cancellationToken);
        if (chunk.Length == 0) throw new InvalidDataException("Chunk is empty");
        lock (session.Gate)
        {
            EnsureLive(session);
            if (offset != session.Offset) throw new InvalidOperationException($"Offset mismatch:{session.Offset}");
            if (session.Offset + chunk.Length > session.TotalBytes)
                throw new InvalidDataException("Chunk exceeds declared upload size");
            using var output = new FileStream(session.TempPath, FileMode.Open, FileAccess.Write, FileShare.None);
            output.Position = session.Offset;
            output.Write(chunk);
            output.Flush(flushToDisk: false);
            session.Offset += chunk.Length;
            session.Expires = _clock.GetUtcNow() + Lifetime;
            return new UploadProgress(session.Offset, session.TotalBytes);
        }
    }

    public string Commit(string ownerToken, string? id)
    {
        var session = Require(ownerToken, id);
        lock (session.Gate)
        {
            EnsureLive(session);
            if (session.Offset != session.TotalBytes)
                throw new InvalidOperationException($"Upload incomplete:{session.Offset}");
            using (var output = new FileStream(session.TempPath, FileMode.Open, FileAccess.Write, FileShare.None))
                output.Flush(flushToDisk: true);
            var target = FileService.UniquePath(session.Directory, session.Name);
            File.Move(session.TempPath, target);
            _sessions.TryRemove(session.Id, out _);
            return target;
        }
    }

    public bool Cancel(string ownerToken, string? id)
    {
        if (string.IsNullOrEmpty(id) || !_sessions.TryGetValue(id, out var session)
            || !SameHash(session.OwnerHash, Hash(ownerToken))) return false;
        lock (session.Gate) return Remove(id);
    }

    private Session Require(string ownerToken, string? id)
    {
        if (string.IsNullOrEmpty(id) || !_sessions.TryGetValue(id, out var session)
            || !SameHash(session.OwnerHash, Hash(ownerToken))) throw new UnauthorizedAccessException();
        return session;
    }

    private void EnsureLive(Session session)
    {
        if (!_sessions.TryGetValue(session.Id, out var current) || !ReferenceEquals(current, session))
            throw new UnauthorizedAccessException();
        if (session.Expires >= _clock.GetUtcNow()) return;
        Remove(session.Id);
        throw new TimeoutException("Upload session expired");
    }

    private bool Remove(string id)
    {
        if (!_sessions.TryRemove(id, out var session)) return false;
        try { File.Delete(session.TempPath); } catch { }
        return true;
    }

    private void CleanupExpired()
    {
        var now = _clock.GetUtcNow();
        foreach (var pair in _sessions)
            if (pair.Value.Expires < now)
                lock (pair.Value.Gate)
                    if (pair.Value.Expires < now) Remove(pair.Key);
    }

    private static void CleanupAbandonedFiles(string directory, string current)
    {
        try
        {
            foreach (var path in Directory.EnumerateFiles(directory, ".moremote-upload-session-*.part"))
                if (path != current && File.GetLastWriteTimeUtc(path) < DateTime.UtcNow.AddDays(-1))
                    try { File.Delete(path); } catch { }
        }
        catch { }
    }

    private static string RandomToken() => Convert.ToBase64String(RandomNumberGenerator.GetBytes(24))
        .TrimEnd('=').Replace('+', '-').Replace('/', '_');
    private static string Hash(string value)
        => Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(value)));
    private static bool SameHash(string expected, string actual)
        => CryptographicOperations.FixedTimeEquals(Convert.FromHexString(expected), Convert.FromHexString(actual));
}
