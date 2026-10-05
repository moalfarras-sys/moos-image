using MoRemote;

var dataDir = Path.Combine(Path.GetTempPath(), "moremote-power-tests-" + Guid.NewGuid());
Environment.SetEnvironmentVariable("MOREMOTE_DATA_DIR", dataDir);
Directory.CreateDirectory(dataDir);
try
{
var passed = 0;
void Eq(bool expected, bool actual, string name)
{
    if (expected != actual) throw new Exception($"{name}: expected {expected}, got {actual}");
    passed++;
}

Eq(true, PowerActions.Execute(new("/usr/bin/true", []), "test"),
    "an accepted command reports success");
Eq(false, PowerActions.Execute(new("/usr/bin/false", []), "test"),
    "a rejected command cannot report success");
Eq(false, PowerActions.Execute(new("/usr/bin/sleep", ["1"]), "test", 5),
    "a hung command is bounded and cannot report success");
Eq(false, PowerActions.Execute(new("/path/that/does/not/exist", []), "test"),
    "a command that never started cannot report success");

Console.WriteLine($"PASS: {passed} Windows power acceptance tests");
}
catch (Exception ex) { Console.Error.WriteLine("FAIL: " + ex.Message); Environment.ExitCode = 1; }
finally { Directory.Delete(dataDir, true); }
