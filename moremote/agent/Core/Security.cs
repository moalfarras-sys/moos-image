using System.Collections.Concurrent;
using System.Security.Cryptography;
using System.Text;
using Konscious.Security.Cryptography;

namespace MoRemote;

/// <summary>Argon2id password/PIN hashing in a self-describing PHC-style string.</summary>
public static class PinHasher
{
    // Tuned for an interactive desktop: ~64 MB, fast enough for a login, costly to brute force.
    private const int MemoryKiB = 65536; // 64 MB
    private const int Iterations = 3;
    private const int Parallelism = 2;
    private const int SaltLen = 16;
    private const int HashLen = 32;

    public static string Hash(string pin)
    {
        var salt = RandomNumberGenerator.GetBytes(SaltLen);
        var hash = Derive(pin, salt, MemoryKiB, Iterations, Parallelism, HashLen);
        return $"$argon2id$v=19$m={MemoryKiB},t={Iterations},p={Parallelism}$" +
               $"{Convert.ToBase64String(salt)}${Convert.ToBase64String(hash)}";
    }

    public static bool Verify(string pin, string encoded)
    {
        try
        {
            // $argon2id$v=19$m=..,t=..,p=..$saltB64$hashB64
            var parts = encoded.Split('$', StringSplitOptions.RemoveEmptyEntries);
            if (parts.Length != 5 || parts[0] != "argon2id") return false;

            int m = 0, t = 0, p = 0;
            foreach (var kv in parts[2].Split(','))
            {
                var s = kv.Split('=');
                if (s.Length != 2) continue;
                if (s[0] == "m") m = int.Parse(s[1]);
                else if (s[0] == "t") t = int.Parse(s[1]);
                else if (s[0] == "p") p = int.Parse(s[1]);
            }
            var salt = Convert.FromBase64String(parts[3]);
            var expected = Convert.FromBase64String(parts[4]);
            var actual = Derive(pin, salt, m, t, p, expected.Length);
            return CryptographicOperations.FixedTimeEquals(actual, expected);
        }
        catch
        {
            return false;
        }
    }

    private static byte[] Derive(string pin, byte[] salt, int memKiB, int iters, int par, int len)
    {
        using var argon = new Argon2id(Encoding.UTF8.GetBytes(pin))
        {
            Salt = salt,
            MemorySize = memKiB,
            Iterations = iters,
            DegreeOfParallelism = par,
        };
        return argon.GetBytes(len);
    }
}

public enum LoginResult { Ok, InvalidPin, LockedOut }

public sealed record Session(string Token, DateTimeOffset Created)
{
    public DateTimeOffset ExpiresAt { get; set; }
}

/// <summary>
/// Authentication, short-lived session tokens (sliding expiry), and brute-force lockout.
/// Tokens live in memory only, so a restart forces re-login (by design).
/// </summary>
public sealed class SessionManager
{
    private const int MaxAttempts = 5;
    private static readonly TimeSpan LockoutDuration = TimeSpan.FromMinutes(2);

    private readonly AppConfig _cfg;
    private readonly object _authGate = new();
    private readonly ConcurrentDictionary<string, Session> _tokens = new();

    public SessionManager(AppConfig cfg) => _cfg = cfg;

    public bool FirstRun => _cfg.FirstRun;

    public int LockoutRemainingSeconds()
    {
        var until = DateTimeOffset.FromUnixTimeSeconds(_cfg.LockoutUntilUnix);
        var rem = (until - DateTimeOffset.UtcNow).TotalSeconds;
        return rem > 0 ? (int)Math.Ceiling(rem) : 0;
    }

    /// <summary>First-run PIN creation. Returns a fresh session token.</summary>
    public string SetupPin(string pin)
    {
        lock (_authGate)
        {
            _cfg.PinHash = PinHasher.Hash(pin);
            _cfg.FailedAttempts = 0;
            _cfg.LockoutUntilUnix = 0;
            _cfg.Save();
            Log.Info("PIN created (first run).");
            return IssueToken();
        }
    }

    public LoginResult Login(string pin, out string token)
    {
        token = "";
        lock (_authGate)
        {
            if (LockoutRemainingSeconds() > 0)
                return LoginResult.LockedOut;

            if (!PinHasher.Verify(pin, _cfg.PinHash))
            {
                _cfg.FailedAttempts++;
                if (_cfg.FailedAttempts >= MaxAttempts)
                {
                    _cfg.LockoutUntilUnix = DateTimeOffset.UtcNow.Add(LockoutDuration).ToUnixTimeSeconds();
                    _cfg.FailedAttempts = 0;
                    _cfg.Save();
                    Log.Warn($"Too many failed PIN attempts — locked out for {LockoutDuration.TotalMinutes} min.");
                    return LoginResult.LockedOut;
                }
                _cfg.Save();
                Log.Warn($"Failed PIN attempt ({_cfg.FailedAttempts}/{MaxAttempts}).");
                return LoginResult.InvalidPin;
            }

            _cfg.FailedAttempts = 0;
            _cfg.LockoutUntilUnix = 0;
            _cfg.Save();
            token = IssueToken();
            Log.Info("Login OK — token issued.");
            return LoginResult.Ok;
        }
    }

    public bool ChangePin(string currentPin, string newPin)
    {
        lock (_authGate)
        {
            if (!PinHasher.Verify(currentPin, _cfg.PinHash)) return false;
            _cfg.PinHash = PinHasher.Hash(newPin);
            _cfg.Save();
            _tokens.Clear(); // force re-login everywhere after a PIN change
            Log.Info("PIN changed — all sessions invalidated.");
            return true;
        }
    }

    /// <summary>Owner-side change (from the tray) without knowing the current PIN.</summary>
    public void ForceSetPin(string newPin)
    {
        lock (_authGate)
        {
            _cfg.PinHash = PinHasher.Hash(newPin);
            _cfg.FailedAttempts = 0;
            _cfg.LockoutUntilUnix = 0;
            _cfg.Save();
            _tokens.Clear();
            Log.Info("PIN set from tray — all sessions invalidated.");
        }
    }

    private string IssueToken()
    {
        var token = Convert.ToBase64String(RandomNumberGenerator.GetBytes(32))
            .Replace('+', '-').Replace('/', '_').TrimEnd('=');
        var ttl = TimeSpan.FromMinutes(Math.Max(5, _cfg.TokenTtlMinutes));
        _tokens[token] = new Session(token, DateTimeOffset.UtcNow) { ExpiresAt = DateTimeOffset.UtcNow.Add(ttl) };
        PruneExpired();
        return token;
    }

    /// <summary>Validate a token and slide its expiry forward. Returns false if missing/expired.</summary>
    public bool ValidateAndTouch(string? token)
    {
        if (string.IsNullOrEmpty(token)) return false;
        if (!_tokens.TryGetValue(token, out var s)) return false;
        if (s.ExpiresAt <= DateTimeOffset.UtcNow)
        {
            _tokens.TryRemove(token, out _);
            return false;
        }
        s.ExpiresAt = DateTimeOffset.UtcNow.Add(TimeSpan.FromMinutes(Math.Max(5, _cfg.TokenTtlMinutes)));
        return true;
    }

    public void Revoke(string? token)
    {
        if (!string.IsNullOrEmpty(token)) _tokens.TryRemove(token!, out _);
    }

    public void RevokeAll() => _tokens.Clear();

    /// <summary>Loopback-only integration testing; WebApi exposes this only when an explicit
    /// process environment flag is enabled. Never used by the installed service normally.</summary>
    public string IssueLocalDiagnosticToken() => IssueToken();

    private void PruneExpired()
    {
        var now = DateTimeOffset.UtcNow;
        foreach (var kv in _tokens)
            if (kv.Value.ExpiresAt <= now)
                _tokens.TryRemove(kv.Key, out _);
    }
}
