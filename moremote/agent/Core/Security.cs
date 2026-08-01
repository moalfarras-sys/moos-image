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

public sealed record TrustedDevice(
    string Id, string Name, string TokenHash,
    long CreatedUnix, long LastUsedUnix, long ExpiresUnix);

public sealed record TrustedDeviceView(
    string Id, string Name, long CreatedUnix, long LastUsedUnix, long ExpiresUnix, bool Current);

public sealed record AuthGrant(string Token, string? DeviceId = null, string? DeviceToken = null);

public sealed record Session(string Token, DateTimeOffset Created, string? DeviceId = null)
{
    public DateTimeOffset ExpiresAt { get; set; }
}

/// <summary>
/// Authentication, short-lived in-memory session tokens, opt-in trusted-device credentials,
/// and brute-force lockout. A restart discards access bearers; a still-valid trusted device may
/// exchange its persisted hashed credential for a new one without weakening the PIN boundary.
/// </summary>
public sealed class SessionManager
{
    private const int MaxAttempts = 5;
    private const int MaxTrustedDevices = 16;
    private static readonly TimeSpan LockoutDuration = TimeSpan.FromMinutes(2);
    private static readonly TimeSpan TrustedDeviceLifetime = TimeSpan.FromDays(30);

    private readonly AppConfig _cfg;
    private readonly object _authGate = new();
    private readonly ConcurrentDictionary<string, Session> _tokens = new();

    public SessionManager(AppConfig cfg)
    {
        _cfg = cfg;
        _cfg.TrustedDevices ??= [];
        lock (_authGate) PruneTrustedDevices(save: true);
    }

    public bool FirstRun => _cfg.FirstRun;

    public int LockoutRemainingSeconds()
    {
        var until = DateTimeOffset.FromUnixTimeSeconds(_cfg.LockoutUntilUnix);
        var rem = (until - DateTimeOffset.UtcNow).TotalSeconds;
        return rem > 0 ? (int)Math.Ceiling(rem) : 0;
    }

    /// <summary>First-run PIN creation. Returns a fresh session token.</summary>
    public string SetupPin(string pin) => SetupPin(pin, null).Token;

    public AuthGrant SetupPin(string pin, string? deviceName)
    {
        lock (_authGate)
        {
            if (!_cfg.FirstRun)
                throw new InvalidOperationException("Remote PIN is already configured.");
            _cfg.PinHash = PinHasher.Hash(pin);
            _cfg.FailedAttempts = 0;
            _cfg.LockoutUntilUnix = 0;
            _cfg.Save();
            Log.Info("PIN created (first run).");
            return IssueGrant(deviceName);
        }
    }

    public LoginResult Login(string pin, out string token)
    {
        var result = Login(pin, null, out var grant);
        token = grant.Token;
        return result;
    }

    public LoginResult Login(string pin, string? deviceName, out AuthGrant grant)
    {
        grant = new AuthGrant("");
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
            grant = IssueGrant(deviceName);
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
            _cfg.TrustedDevices.Clear();
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
            _cfg.TrustedDevices.Clear();
            _cfg.Save();
            _tokens.Clear();
            Log.Info("PIN set from tray — all sessions invalidated.");
        }
    }

    public bool ResumeTrustedDevice(string? deviceId, string? deviceToken, out string token)
    {
        token = "";
        if (string.IsNullOrWhiteSpace(deviceId) || string.IsNullOrWhiteSpace(deviceToken)) return false;
        lock (_authGate)
        {
            PruneTrustedDevices(save: false);
            var index = _cfg.TrustedDevices.FindIndex(d => d.Id == deviceId);
            if (index < 0) { _cfg.Save(); return false; }
            var device = _cfg.TrustedDevices[index];
            if (!FixedTimeHexEquals(device.TokenHash, HashDeviceToken(deviceToken))) return false;
            _cfg.TrustedDevices[index] = device with {
                LastUsedUnix = DateTimeOffset.UtcNow.ToUnixTimeSeconds()
            };
            _cfg.Save();
            token = IssueToken(device.Id);
            Log.Info($"Trusted device resumed: {device.Name} ({device.Id}).");
            return true;
        }
    }

    public IReadOnlyList<TrustedDeviceView> ListTrustedDevices(string? accessToken)
    {
        if (!ValidateAndTouch(accessToken)) return [];
        var currentId = _tokens.TryGetValue(accessToken!, out var current) ? current.DeviceId : null;
        lock (_authGate)
        {
            PruneTrustedDevices(save: true);
            return _cfg.TrustedDevices.OrderByDescending(d => d.LastUsedUnix)
                .Select(d => new TrustedDeviceView(d.Id, d.Name, d.CreatedUnix,
                    d.LastUsedUnix, d.ExpiresUnix, d.Id == currentId)).ToArray();
        }
    }

    public bool RevokeTrustedDevice(string? accessToken, string? deviceId)
    {
        if (!ValidateAndTouch(accessToken) || string.IsNullOrWhiteSpace(deviceId)) return false;
        lock (_authGate)
        {
            if (_cfg.TrustedDevices.RemoveAll(d => d.Id == deviceId) == 0) return false;
            foreach (var pair in _tokens)
                if (pair.Value.DeviceId == deviceId) _tokens.TryRemove(pair.Key, out _);
            _cfg.Save();
            Log.Warn($"Trusted device revoked: {deviceId}.");
            return true;
        }
    }

    public string? DeviceIdFor(string? accessToken)
        => !string.IsNullOrEmpty(accessToken) && _tokens.TryGetValue(accessToken, out var session)
            ? session.DeviceId : null;

    private AuthGrant IssueGrant(string? deviceName)
    {
        if (string.IsNullOrWhiteSpace(deviceName)) return new AuthGrant(IssueToken());
        PruneTrustedDevices(save: false);
        while (_cfg.TrustedDevices.Count >= MaxTrustedDevices)
        {
            var evicted = _cfg.TrustedDevices.OrderBy(d => d.LastUsedUnix).First();
            _cfg.TrustedDevices.Remove(evicted);
            foreach (var pair in _tokens)
                if (pair.Value.DeviceId == evicted.Id) _tokens.TryRemove(pair.Key, out _);
        }
        var secret = RandomToken();
        var id = RandomToken()[..16];
        var now = DateTimeOffset.UtcNow;
        var name = NormalizeDeviceName(deviceName);
        _cfg.TrustedDevices.Add(new TrustedDevice(id, name, HashDeviceToken(secret),
            now.ToUnixTimeSeconds(), now.ToUnixTimeSeconds(),
            now.Add(TrustedDeviceLifetime).ToUnixTimeSeconds()));
        _cfg.Save();
        return new AuthGrant(IssueToken(id), id, secret);
    }

    private string IssueToken(string? deviceId = null)
    {
        var token = RandomToken();
        var ttl = TimeSpan.FromMinutes(Math.Max(5, _cfg.TokenTtlMinutes));
        _tokens[token] = new Session(token, DateTimeOffset.UtcNow, deviceId) {
            ExpiresAt = DateTimeOffset.UtcNow.Add(ttl)
        };
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

    private static string RandomToken() => Convert.ToBase64String(RandomNumberGenerator.GetBytes(32))
        .Replace('+', '-').Replace('/', '_').TrimEnd('=');

    private static string HashDeviceToken(string token)
        => Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(token)));

    private static bool FixedTimeHexEquals(string expected, string actual)
    {
        try
        {
            return CryptographicOperations.FixedTimeEquals(
                Convert.FromHexString(expected), Convert.FromHexString(actual));
        }
        catch (FormatException) { return false; }
    }

    private static string NormalizeDeviceName(string value)
    {
        var clean = new string(value.Trim().Where(c => !char.IsControl(c)).ToArray());
        if (clean.Length > 64) clean = clean[..64];
        return string.IsNullOrWhiteSpace(clean) ? "Trusted device" : clean;
    }

    private void PruneTrustedDevices(bool save)
    {
        var now = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
        var changed = _cfg.TrustedDevices.RemoveAll(d => d.ExpiresUnix <= now) > 0;
        if (changed && save) _cfg.Save();
    }

    private void PruneExpired()
    {
        var now = DateTimeOffset.UtcNow;
        foreach (var kv in _tokens)
            if (kv.Value.ExpiresAt <= now)
                _tokens.TryRemove(kv.Key, out _);
    }
}
