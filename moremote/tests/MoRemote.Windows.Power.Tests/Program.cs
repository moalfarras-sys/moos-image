using MoRemote;

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
