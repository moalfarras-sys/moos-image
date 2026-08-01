using System.Collections.Concurrent;
using System.Security.Cryptography;

namespace MoRemote;

/// <summary>Single-use URL capabilities for elements that cannot send an Authorization header.</summary>
public sealed class AccessTicketStore
{
    private sealed record Entry(string Purpose, string Resource, DateTimeOffset Expires);
    private readonly ConcurrentDictionary<string, Entry> _tickets = new();
    private readonly TimeProvider _clock;

    public AccessTicketStore(TimeProvider? clock = null) => _clock = clock ?? TimeProvider.System;

    public string Issue(string purpose, string resource = "", TimeSpan? lifetime = null)
    {
        Prune();
        var token = Convert.ToBase64String(RandomNumberGenerator.GetBytes(32))
            .TrimEnd('=').Replace('+', '-').Replace('/', '_');
        _tickets[token] = new Entry(purpose, resource,
            _clock.GetUtcNow() + (lifetime ?? TimeSpan.FromSeconds(45)));
        return token;
    }

    public bool Consume(string? token, string purpose, out string resource)
    {
        resource = "";
        if (string.IsNullOrEmpty(token) || !_tickets.TryRemove(token, out var entry)) return false;
        if (!CryptographicOperations.FixedTimeEquals(
                System.Text.Encoding.UTF8.GetBytes(entry.Purpose),
                System.Text.Encoding.UTF8.GetBytes(purpose))
            || entry.Expires < _clock.GetUtcNow()) return false;
        resource = entry.Resource;
        return true;
    }

    private void Prune()
    {
        var now = _clock.GetUtcNow();
        foreach (var pair in _tickets)
            if (pair.Value.Expires < now) _tickets.TryRemove(pair.Key, out _);
    }
}
