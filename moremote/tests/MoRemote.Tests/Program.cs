using MoRemote;

var trustDir = Path.Combine(Path.GetTempPath(), "moremote-tests-" + Guid.NewGuid());
Environment.SetEnvironmentVariable("MOREMOTE_DATA_DIR", trustDir);

int passed=0;
void Eq<T>(T expected,T actual,string name){if(!EqualityComparer<T>.Default.Equals(expected,actual))throw new Exception($"{name}: expected {expected}, got {actual}");passed++;}
void Throws(Action a,string name){try{a();throw new Exception(name+": did not reject");}catch(ArgumentOutOfRangeException){passed++;}}
(double x,double y) Client(double px,double py,double left,double top,double width,double height)=>(Math.Clamp((px-left)/width,0,1),Math.Clamp((py-top)/height,0,1));

var normal=new LogicalRect(0,0,1397,786);
Eq((0,0),CoordinateMapper.NormalizedToDesktop(0,0,normal),"top-left");
Eq((1396,785),CoordinateMapper.NormalizedToDesktop(1,1,normal),"bottom-right");
Eq((698,392),CoordinateMapper.NormalizedToDesktop(.5,.5,normal),"scaled center");
var neg=new LogicalRect(-1920,-200,3840,1280);
Eq((-1920,-200),CoordinateMapper.NormalizedToDesktop(0,0,neg),"negative origin");
Eq((1919,1079),CoordinateMapper.NormalizedToDesktop(1,1,neg),"multi-monitor extent");
var portrait=Client(195,422,0,300,390,219.375);Eq((.5,Math.Clamp((422d-300)/219.375,0,1)),portrait,"portrait letterbox");
var landscape=Client(422,195,120,0,600,390);Eq((302d/600,.5),landscape,"landscape crop/content rect");
Eq((0d,1d),Client(-50,999,20,30,300,200),"out-of-content clamp");
Throws(()=>CoordinateMapper.NormalizedToDesktop(double.NaN,.5,normal),"NaN");
Throws(()=>CoordinateMapper.NormalizedToDesktop(double.PositiveInfinity,.5,normal),"infinity");
Throws(()=>CoordinateMapper.NormalizedToDesktop(.5,.5,new(0,0,0,10)),"empty geometry");
Eq((0,785),CoordinateMapper.NormalizedToDesktop(-5,9,normal),"out-of-range clamp");
var guard=new InputSequenceGuard();Eq(true,guard.Accept(1,1000,1000,out _),"sequence first");Eq(false,guard.Accept(1,1001,1001,out _),"sequence duplicate");Eq(false,guard.Accept(0,1002,1002,out _),"sequence reordered");Eq(true,new InputSequenceGuard().Accept(1,0,40000,out _),"a large now-vs-timestamp gap is deliberately ACCEPTED: freshness is sequence-only, not wall-clock (see InputSequenceGuard)");

var unicode="مرحباً Grüße English";Eq(unicode,System.Text.Encoding.UTF8.GetString(System.Text.Encoding.UTF8.GetBytes(unicode)),"clipboard unicode");
var clipboardClock = System.Diagnostics.Stopwatch.StartNew();
var timedOutClipboard = ClipboardBridge.RunReadCommand(
    "/bin/sh", ["-c", "sleep 20"], TimeSpan.FromMilliseconds(120), 1024);
clipboardClock.Stop();
Eq(0, timedOutClipboard.Length, "hung clipboard helper returns an empty result");
Eq(true, clipboardClock.Elapsed < TimeSpan.FromSeconds(2), "clipboard timeout is real and bounded");
var oversizedClipboard = ClipboardBridge.RunReadCommand(
    "/bin/sh", ["-c", "printf 123456"], TimeSpan.FromSeconds(1), 5);
Eq(0, oversizedClipboard.Length, "oversized clipboard output is rejected before retention");
var exactClipboard = ClipboardBridge.RunReadCommand(
    "/bin/sh", ["-c", "printf 12345"], TimeSpan.FromSeconds(1), 5);
Eq("12345", System.Text.Encoding.UTF8.GetString(exactClipboard), "clipboard accepts its exact size limit");
Eq(false, ClipboardBridge.WriteCommand(
    "/bin/sh", ["-c", "exit 7"], "payload"u8.ToArray(), TimeSpan.FromSeconds(1)),
    "clipboard write reports a rejected helper instead of fake success");
Eq(true, ClipboardBridge.WriteCommand(
    "/bin/sh", ["-c", "cat >/dev/null"], "مرحباً"u8.ToArray(), TimeSpan.FromSeconds(1)),
    "clipboard write reports a completed Unicode payload");
// ASCII is the only thing the keysym path is allowed to carry: KWin resolves a keysym against the
// ACTIVE keymap group only, so on a `de,ara` keymap in the German group an Arabic keysym — legacy
// 0x05xx or 0x01000000+Unicode alike — resolves to no real key. Measured on a live KWin 6.7
// session: 'م' arrived as keycode 247 / keyval 0x1008ffb5, which types nothing. Arabic therefore
// goes through the clipboard, and this asserts we no longer pretend otherwise.
Eq((int)'a',TextKeysym.ForCodepoint('a'),"ASCII keysym is the codepoint");
Eq((int)'Z',TextKeysym.ForCodepoint('Z'),"ASCII capital keysym is the codepoint");
Eq(0x010020ac,TextKeysym.ForCodepoint('€'),"non-ASCII Unicode keysym form");
Eq(0x01000645,TextKeysym.ForCodepoint('م'),"Arabic no longer claims a legacy keysym");
Eq("/usr/bin/qdbus-qt6", PowerActions.Resolve("lock")?.FileName, "lock uses the Plasma session bus");
Eq("Lock", PowerActions.Resolve("lock")?.Arguments[^1], "lock invokes the real ScreenSaver method");
Eq("logout", PowerActions.Resolve("signout")?.Arguments[^1], "signout invokes Plasma logout");
Eq("--no-block", PowerActions.Resolve("sleep")?.Arguments[0], "sleep is queued without hanging HTTP");
Eq("suspend", PowerActions.Resolve("sleep")?.Arguments[1], "sleep maps to system suspend");
Eq("reboot", PowerActions.Resolve("restart")?.Arguments[1], "restart maps to reboot");
Eq("poweroff", PowerActions.Resolve("shutdown")?.Arguments[1], "shutdown maps to poweroff");
Eq(null, PowerActions.Resolve("hibernate"), "unknown power actions fail closed");
var editionDir = Path.Combine(Path.GetTempPath(), "moremote-edition-" + Guid.NewGuid());
Directory.CreateDirectory(editionDir);
var editionFile = Path.Combine(editionDir, "edition");
File.WriteAllText(editionFile, "moos-cloud\n");
Eq(false, PowerActions.HostPowerAllowedAt(editionFile), "cloud users cannot power off the shared host");
Eq(false, PowerActions.CanRunAt("lock", editionFile), "passwordless cloud session cannot be irrecoverably locked");
Eq(false, PowerActions.CanRunAt("signout", editionFile), "cloud signout cannot permanently stop its private desktop");
Eq(false, PowerActions.CanRunAt("restart", editionFile), "cloud user cannot reboot the shared host");
File.WriteAllText(editionFile, "moos\n");
Eq(true, PowerActions.HostPowerAllowedAt(editionFile), "desktop owners retain host power controls");
Eq(true, PowerActions.CanRunAt("lock", editionFile), "desktop owner retains lock");
Directory.Delete(editionDir, true);
Eq(true, PowerActions.Execute(new("/usr/bin/true", []), "test"), "accepted command succeeds");
Eq(false, PowerActions.Execute(new("/usr/bin/false", []), "test"), "rejected command is not fake success");
Eq(false, PowerActions.Execute(new("/usr/bin/sleep", ["1"]), "test", 5), "hung command times out");
var tickets = new AccessTicketStore();
var downloadTicket = tickets.Issue("download", "/tmp/report.pdf");
Eq(true, tickets.Consume(downloadTicket, "download", out var ticketPath), "download ticket works once");
Eq("/tmp/report.pdf", ticketPath, "download ticket carries only its fixed resource");
Eq(false, tickets.Consume(downloadTicket, "download", out _), "download ticket cannot be replayed");
var downloadLease = tickets.IssueLease("download", "/tmp/large.iso", maxUses: 3);
Eq(true, tickets.UseLease(downloadLease, "download", out var leasedPath), "download lease accepts first range");
Eq("/tmp/large.iso", leasedPath, "download lease is bound to one resource");
Eq(true, tickets.UseLease(downloadLease, "download", out _), "download lease accepts retry");
Eq(true, tickets.UseLease(downloadLease, "download", out _), "download lease accepts final range");
Eq(false, tickets.UseLease(downloadLease, "download", out _), "download lease expires by use count");
var confusedLease = tickets.IssueLease("download", "/tmp/private.bin");
Eq(false, tickets.UseLease(confusedLease, "audio", out _), "wrong purpose burns the download lease");
Eq(false, tickets.UseLease(confusedLease, "download", out _), "burned lease cannot be retried correctly");
var audioTicket = tickets.Issue("audio");
Eq(false, tickets.Consume(audioTicket, "download", out _), "ticket purpose cannot be confused");
Eq(false, tickets.Consume(audioTicket, "audio", out _), "wrong-purpose attempt consumes the capability");
for (var i = 0; i < 1100; i++) tickets.Issue("pressure", i.ToString());
Eq(true, tickets.Count <= 1024, "ticket pressure remains memory bounded");
var uploadDir = Path.Combine(Path.GetTempPath(), "moremote-upload-" + Guid.NewGuid());
Directory.CreateDirectory(uploadDir);
var savedUpload = await FileService.SaveUploadAsync(
    new MemoryStream("complete"u8.ToArray()), uploadDir, "../safe.txt", CancellationToken.None);
Eq("safe.txt", Path.GetFileName(savedUpload), "upload strips path traversal from the name");
Eq("complete", File.ReadAllText(savedUpload), "upload becomes visible only when complete");
try
{
    await FileService.SaveUploadAsync(new FailingReadStream(), uploadDir, "broken.bin", CancellationToken.None);
    throw new Exception("interrupted upload did not fail");
}
catch (IOException) { passed++; }
Eq(0, Directory.GetFiles(uploadDir, ".moremote-upload-*.part").Length,
    "interrupted upload removes its partial file");
Directory.Delete(uploadDir, true);
var chunkDir = Path.Combine(Path.GetTempPath(), "moremote-chunks-" + Guid.NewGuid());
Directory.CreateDirectory(chunkDir);
File.WriteAllText(Path.Combine(chunkDir, "report.bin"), "existing");
using var uploads = new UploadSessionStore();
var upload = uploads.Start("owner-token", chunkDir, "../report.bin", 6);
var firstChunk = await uploads.AppendAsync("owner-token", upload.Id, 0,
    new MemoryStream("abc"u8.ToArray()), CancellationToken.None);
Eq(3L, firstChunk.Offset, "chunk upload records authoritative offset");
Eq(3L, uploads.Status("owner-token", upload.Id).Offset, "upload status resumes after interruption");
try { uploads.Status("different-device", upload.Id); throw new Exception("upload session crossed owners"); }
catch (UnauthorizedAccessException) { passed++; }
try
{
    await uploads.AppendAsync("owner-token", upload.Id, 0,
        new MemoryStream("abc"u8.ToArray()), CancellationToken.None);
    throw new Exception("duplicate offset was accepted");
}
catch (InvalidOperationException) { passed++; }
await uploads.AppendAsync("owner-token", upload.Id, 3,
    new MemoryStream("def"u8.ToArray()), CancellationToken.None);
var committed = uploads.Commit("owner-token", upload.Id);
Eq("report (1).bin", Path.GetFileName(committed), "atomic commit never overwrites a conflict");
Eq("abcdef", File.ReadAllText(committed), "committed chunks preserve byte order");
var partial = uploads.Start("owner-token", chunkDir, "partial.bin", 4);
await uploads.AppendAsync("owner-token", partial.Id, 0,
    new MemoryStream("ab"u8.ToArray()), CancellationToken.None);
try { uploads.Commit("owner-token", partial.Id); throw new Exception("partial upload became visible"); }
catch (InvalidOperationException) { passed++; }
Eq(false, File.Exists(Path.Combine(chunkDir, "partial.bin")), "partial target remains invisible");
Eq(true, uploads.Cancel("owner-token", partial.Id), "cancel removes a partial upload");
Eq(0, Directory.GetFiles(chunkDir, ".moremote-upload-session-*.part").Length,
    "cancel leaves no chunk-session temporary file");
var uploadClock = new ManualTimeProvider(DateTimeOffset.Parse("2026-08-01T00:00:00Z"));
using (var expiringUploads = new UploadSessionStore(uploadClock))
{
    var expiring = expiringUploads.Start("owner-token", chunkDir, "expired.bin", 4);
    await expiringUploads.AppendAsync("owner-token", expiring.Id, 0,
        new MemoryStream("ab"u8.ToArray()), CancellationToken.None);
    uploadClock.Advance(TimeSpan.FromMinutes(31));
    Eq(1, expiringUploads.SweepExpired(), "idle expiry sweep removes the abandoned session");
    Eq(false, File.Exists(Path.Combine(chunkDir, $".moremote-upload-session-{expiring.Id}.part")),
        "idle expiry sweep deletes the abandoned partial file");
}
Directory.Delete(chunkDir, true);
var bounded = await FileService.ReadBoundedAsync(
    new MemoryStream("exact"u8.ToArray()), 5, CancellationToken.None);
Eq("exact", System.Text.Encoding.UTF8.GetString(bounded), "bounded body accepts its exact limit");
try
{
    await FileService.ReadBoundedAsync(
        new MemoryStream("one-byte-too-many"u8.ToArray()), 16, CancellationToken.None);
    throw new Exception("bounded body retained data beyond its limit");
}
catch (InvalidDataException) { passed++; }
var listingDir = Path.Combine(Path.GetTempPath(), "moremote-listing-" + Guid.NewGuid());
Directory.CreateDirectory(listingDir);
for (var i = 0; i < FileService.MaxListingEntries + 20; i++)
    File.WriteAllText(Path.Combine(listingDir, $"item-{i:D4}.txt"), "x");
var listing = FileService.List(listingDir);
Eq(FileService.MaxListingEntries, listing.entries.Length, "large directory listing is bounded");
Eq(true, listing.truncated, "large directory reports truncation instead of pretending complete");
Directory.Delete(listingDir, true);

var trustConfig = new AppConfig { PinHash = PinHasher.Hash("246810") };
trustConfig.Save();
var auth = new SessionManager(trustConfig);
try { auth.SetupPin("135790", "Racing browser"); throw new Exception("second setup replaced the PIN"); }
catch (InvalidOperationException) { passed++; }
Eq(LoginResult.Ok, auth.Login("246810", "  Pixel 9\n", out var grant), "trusted login succeeds");
Eq(true, !string.IsNullOrEmpty(grant.Token), "trusted login returns access token");
Eq(true, !string.IsNullOrEmpty(grant.DeviceId), "trusted login returns device id");
Eq(true, !string.IsNullOrEmpty(grant.DeviceToken), "trusted login returns device secret once");
Eq(false, File.ReadAllText(Paths.ConfigFile).Contains(grant.DeviceToken!), "persisted config never stores raw device secret");
var restartedAuth = new SessionManager(AppConfig.Load());
Eq(false, restartedAuth.ResumeTrustedDevice(grant.DeviceId, "wrong", out _), "wrong device secret is rejected");
Eq(true, restartedAuth.ResumeTrustedDevice(grant.DeviceId, grant.DeviceToken, out var resumed), "trusted device survives agent restart");
var devices = restartedAuth.ListTrustedDevices(resumed);
Eq(1, devices.Count, "trusted device appears in owner-visible inventory");
Eq("Pixel 9", devices[0].Name, "device name strips control characters");
Eq(true, devices[0].Current, "inventory marks the current device");
Eq(true, restartedAuth.RevokeTrustedDevice(resumed, grant.DeviceId), "device can revoke itself");
Eq(false, restartedAuth.ResumeTrustedDevice(grant.DeviceId, grant.DeviceToken, out _), "revoked device cannot resume");
Directory.Delete(trustDir, true);
// ── Clipboard typing: the copy must be CONFIRMED before the paste ───────────
// Live-proven on the Cloud session (2026-08-03): wl-copy returns before the
// selection is servable, so an immediate Shift+Insert pasted the previous
// clipboard. Three Arabic words injected that way lost the first one entirely
// (" في مشكلة "); with the read-back they arrived intact ("لسى في مشكلة ").
// This asserts the SOURCE contract so the racy call can never come back.
{
    var injector = File.ReadAllText(Path.Combine(RepoRoot(), "agent-linux/InputInjector.cs"));
    var bridge = File.ReadAllText(Path.Combine(RepoRoot(), "agent-linux/ClipboardBridge.cs"));
    if (!injector.Contains("ClipboardBridge.SetTextConfirmed(text)"))
        throw new Exception("clipboard typing must use the confirmed write");
    if (injector.Contains("if (!ClipboardBridge.SetText(text))"))
        throw new Exception("the unconfirmed SetText must not be used to type");
    if (!bridge.Contains("GetText()") || !bridge.Contains("ConfirmAttempts"))
        throw new Exception("SetTextConfirmed must read the clipboard back, bounded");
    passed++;

    // Ordering: nothing may overtake text already gathering for a paste — a
    // space IS on the fast keysym path, which is how spaces landed one letter
    // early inside Arabic ("لسى في" -> "لس ىف").
    var typeText = injector[injector.IndexOf("public void TypeText")..];
    typeText = typeText[..typeText.IndexOf("private const int BulkPasteThreshold")];
    var guardAt = typeText.IndexOf("_pending.Length > 0");
    var fastAt = typeText.IndexOf("TryDirectStrokes");
    if (guardAt < 0 || fastAt < 0 || guardAt > fastAt)
        throw new Exception("the pending-paste guard must precede the fast keysym path");
    passed++;

    foreach (var m in new[] { "public void KeyTap", "public void KeyDown", "public void Combo" })
    {
        var body = injector[injector.IndexOf(m)..];
        body = body[..Math.Min(body.Length, 420)];
        if (!body.Contains("FlushPendingText"))
            throw new Exception(m + " must flush pending text so keys cannot reorder an edit");
        passed++;
    }

    // ── Session lifetime honesty (2026-08-03, each broken once) ────────────
    // 1. Cancelling WebSocket.SendAsync ABORTS the socket — there is no "drop
    //    one frame and carry on". The old catch claimed to continue and the
    //    session then died of the next send with nothing connecting the two.
    // 2. A gathered word must never wait for the agent's own 140 ms window on
    //    top of the client's — only single letters wait for company.
    // 3. A viewer actively WATCHING (pings flowing, page visible) is not idle;
    //    a pocketed phone reports watching=false and still times out.
    var session = File.ReadAllText(Path.Combine(RepoRoot(), "agent/Web/StreamSession.cs"));
    if (!session.Contains("_socket.Abort();"))
        throw new Exception("a frame-send timeout must abort the socket honestly");
    if (session.Contains("was abandoned; the viewer's link is saturated"))
        throw new Exception("the send-timeout 'carry on' claim must not return");
    passed++;
    if (injector.IndexOf("text.Length > 1 ||") < 0 ||
        !injector.Contains("PasteMaxHoldMs = 700"))
        throw new Exception("multi-character chunks must flush at once, bounded by the 700 ms age cap");
    passed++;
    if (!session.Contains("if (_watching) _lastInput = DateTimeOffset.UtcNow;"))
        throw new Exception("a watching viewer's pings must count against the idle timeout");
    passed++;
}

static string RepoRoot()
{
    var dir = AppContext.BaseDirectory;
    while (dir is not null && !Directory.Exists(Path.Combine(dir, "agent-linux")))
        dir = Path.GetDirectoryName(dir);
    return dir ?? throw new Exception("could not locate the moremote tree");
}

Console.WriteLine($"PASS: {passed} mapping/validation/Unicode tests");

sealed class FailingReadStream : Stream
{
    private bool _first = true;
    public override async ValueTask<int> ReadAsync(Memory<byte> buffer,
        CancellationToken cancellationToken = default)
    {
        if (!_first) throw new IOException("simulated disconnect");
        _first = false;
        buffer.Span[0] = 1;
        await Task.Yield();
        return 1;
    }
    public override bool CanRead => true;
    public override bool CanSeek => false;
    public override bool CanWrite => false;
    public override long Length => throw new NotSupportedException();
    public override long Position { get => throw new NotSupportedException(); set => throw new NotSupportedException(); }
    public override void Flush() => throw new NotSupportedException();
    public override int Read(byte[] buffer, int offset, int count) => throw new NotSupportedException();
    public override long Seek(long offset, SeekOrigin origin) => throw new NotSupportedException();
    public override void SetLength(long value) => throw new NotSupportedException();
    public override void Write(byte[] buffer, int offset, int count) => throw new NotSupportedException();
}

sealed class ManualTimeProvider(DateTimeOffset now) : TimeProvider
{
    private DateTimeOffset _now = now;
    public override DateTimeOffset GetUtcNow() => _now;
    public void Advance(TimeSpan amount) => _now += amount;
}
