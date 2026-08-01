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
