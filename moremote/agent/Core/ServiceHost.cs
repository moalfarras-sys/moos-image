using System.Diagnostics;
using System.Runtime.InteropServices;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;

namespace MoRemote;

/// <summary>
/// EXPERIMENTAL "full SYSTEM service" mode. A LocalSystem Windows Service (Session 0) supervises
/// a worker that it launches **as SYSTEM in the active console session**, targeting whichever
/// desktop currently has input (Default when logged in, Winlogon at the lock / login / UAC screen).
/// That worker runs the normal web + capture + input pipeline headless, so the phone can see and
/// control even the login screen. Tradeoff: no on-screen "control active" banner in this mode.
/// Strictly opt-in; installed / removed via scripts\install-service.ps1 / uninstall-service.ps1.
/// </summary>
public static class ServiceHost
{
    /// <summary>Entry point when started by the SCM with --service. Blocks until the service stops.</summary>
    public static void Run()
    {
        Log.Info("Starting as Windows Service (supervisor).");
        var builder = Host.CreateApplicationBuilder();
        builder.Services.AddWindowsService(o => o.ServiceName = "MoRemotePersonal");
        builder.Services.AddHostedService<SessionSupervisor>();
        builder.Build().Run();
    }
}

/// <summary>Keeps exactly one worker alive in the active console session, on the current input desktop.</summary>
internal sealed class SessionSupervisor : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stop)
    {
        Log.Info("Session supervisor running.");
        var exe = Environment.ProcessPath ?? "";
        int workerPid = -1;
        uint lastSession = 0xFFFFFFFF;
        string lastDesktop = "";

        while (!stop.IsCancellationRequested)
        {
            try
            {
                uint session = SessionLauncher.WTSGetActiveConsoleSessionId();
                if (session != 0xFFFFFFFF)
                {
                    // A user session → its interactive desktop; otherwise the secure login desktop.
                    string desktop = SessionLauncher.HasUserSession(session) ? @"winsta0\default" : @"winsta0\winlogon";
                    bool workerDead = workerPid < 0 || !IsAlive(workerPid);

                    if (workerDead || session != lastSession || desktop != lastDesktop)
                    {
                        if (workerPid > 0 && IsAlive(workerPid)) TryKill(workerPid);
                        workerPid = SessionLauncher.LaunchAsSystem(exe, "--worker", session, desktop);
                        lastSession = session; lastDesktop = desktop;
                        Log.Info($"Worker launched in session {session} on {desktop} (pid {workerPid}).");
                    }
                }
            }
            catch (Exception ex) { Log.Error("Supervisor loop error.", ex); }

            try { await Task.Delay(2000, stop); } catch { }
        }

        if (workerPid > 0 && IsAlive(workerPid)) TryKill(workerPid);
    }

    private static bool IsAlive(int pid)
    {
        try { using var p = Process.GetProcessById(pid); return !p.HasExited; }
        catch { return false; }
    }

    private static void TryKill(int pid)
    {
        try { using var p = Process.GetProcessById(pid); p.Kill(); }
        catch { }
    }
}

/// <summary>Launches a process as SYSTEM inside a given session, on a given desktop (CreateProcessAsUser).</summary>
internal static class SessionLauncher
{
    public static bool HasUserSession(uint sessionId)
    {
        if (WTSQueryUserToken(sessionId, out IntPtr tok))
        {
            CloseHandle(tok);
            return true;
        }
        return false;
    }

    public static int LaunchAsSystem(string exePath, string args, uint sessionId, string desktop)
    {
        // Duplicate winlogon.exe's token (SYSTEM in that session) into a primary token.
        var winlogon = Process.GetProcessesByName("winlogon")
            .FirstOrDefault(p => { try { return (uint)p.SessionId == sessionId; } catch { return false; } });
        if (winlogon == null) { Log.Warn($"No winlogon in session {sessionId}."); return -1; }

        IntPtr hProc = OpenProcess(PROCESS_QUERY_INFORMATION, false, winlogon.Id);
        if (hProc == IntPtr.Zero) { Log.Warn("OpenProcess(winlogon) failed: " + Marshal.GetLastWin32Error()); return -1; }
        try
        {
            if (!OpenProcessToken(hProc, TOKEN_DUPLICATE | TOKEN_QUERY | TOKEN_ASSIGN_PRIMARY | TOKEN_ADJUST_DEFAULT | TOKEN_ADJUST_SESSIONID, out IntPtr hTok))
            { Log.Warn("OpenProcessToken failed: " + Marshal.GetLastWin32Error()); return -1; }
            try
            {
                if (!DuplicateTokenEx(hTok, MAXIMUM_ALLOWED, IntPtr.Zero, SecurityImpersonation, TokenPrimary, out IntPtr hDup))
                { Log.Warn("DuplicateTokenEx failed: " + Marshal.GetLastWin32Error()); return -1; }
                try
                {
                    uint sid = sessionId;
                    SetTokenInformation(hDup, TokenSessionId, ref sid, sizeof(uint));

                    IntPtr env = IntPtr.Zero;
                    CreateEnvironmentBlock(out env, hDup, false);

                    var si = new STARTUPINFO();
                    si.cb = Marshal.SizeOf<STARTUPINFO>();
                    si.lpDesktop = desktop;

                    uint flags = CREATE_UNICODE_ENVIRONMENT | CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP;
                    string cmd = $"\"{exePath}\" {args}";

                    bool ok = CreateProcessAsUser(hDup, exePath, cmd, IntPtr.Zero, IntPtr.Zero, false,
                        flags, env, Path.GetDirectoryName(exePath), ref si, out PROCESS_INFORMATION pi);
                    if (env != IntPtr.Zero) DestroyEnvironmentBlock(env);
                    if (!ok) { Log.Warn("CreateProcessAsUser failed: " + Marshal.GetLastWin32Error()); return -1; }

                    CloseHandle(pi.hThread);
                    CloseHandle(pi.hProcess);
                    return (int)pi.dwProcessId;
                }
                finally { CloseHandle(hDup); }
            }
            finally { CloseHandle(hTok); }
        }
        finally { CloseHandle(hProc); }
    }

    // ---------------- Win32 ----------------
    private const uint MAXIMUM_ALLOWED = 0x02000000;
    private const uint PROCESS_QUERY_INFORMATION = 0x0400;
    private const uint TOKEN_DUPLICATE = 0x0002, TOKEN_QUERY = 0x0008, TOKEN_ASSIGN_PRIMARY = 0x0001,
                       TOKEN_ADJUST_DEFAULT = 0x0080, TOKEN_ADJUST_SESSIONID = 0x0100;
    private const uint CREATE_UNICODE_ENVIRONMENT = 0x00000400, CREATE_NO_WINDOW = 0x08000000,
                       CREATE_NEW_PROCESS_GROUP = 0x00000200;
    private const int TokenSessionId = 12;

    private enum SECURITY_IMPERSONATION_LEVEL { SecurityAnonymous, SecurityIdentification, SecurityImpersonation, SecurityDelegation }
    private enum TOKEN_TYPE { TokenPrimary = 1, TokenImpersonation }
    private const SECURITY_IMPERSONATION_LEVEL SecurityImpersonation = SECURITY_IMPERSONATION_LEVEL.SecurityImpersonation;
    private const TOKEN_TYPE TokenPrimary = TOKEN_TYPE.TokenPrimary;

    [StructLayout(LayoutKind.Sequential)]
    private struct PROCESS_INFORMATION { public IntPtr hProcess; public IntPtr hThread; public uint dwProcessId; public uint dwThreadId; }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct STARTUPINFO
    {
        public int cb; public string lpReserved; public string lpDesktop; public string lpTitle;
        public int dwX, dwY, dwXSize, dwYSize, dwXCountChars, dwYCountChars, dwFillAttribute, dwFlags;
        public short wShowWindow, cbReserved2; public IntPtr lpReserved2, hStdInput, hStdOutput, hStdError;
    }

    [DllImport("kernel32.dll")] public static extern uint WTSGetActiveConsoleSessionId();
    [DllImport("wtsapi32.dll", SetLastError = true)] public static extern bool WTSQueryUserToken(uint sessionId, out IntPtr phToken);
    [DllImport("kernel32.dll", SetLastError = true)] public static extern IntPtr OpenProcess(uint access, bool inherit, int pid);
    [DllImport("advapi32.dll", SetLastError = true)] private static extern bool OpenProcessToken(IntPtr hProcess, uint access, out IntPtr hToken);
    [DllImport("advapi32.dll", SetLastError = true)]
    private static extern bool DuplicateTokenEx(IntPtr hExisting, uint access, IntPtr attrs,
        SECURITY_IMPERSONATION_LEVEL level, TOKEN_TYPE type, out IntPtr hNew);
    [DllImport("advapi32.dll", SetLastError = true)]
    private static extern bool SetTokenInformation(IntPtr hToken, int tokenInfoClass, ref uint info, int len);
    [DllImport("userenv.dll", SetLastError = true)] private static extern bool CreateEnvironmentBlock(out IntPtr env, IntPtr hToken, bool inherit);
    [DllImport("userenv.dll", SetLastError = true)] private static extern bool DestroyEnvironmentBlock(IntPtr env);
    [DllImport("advapi32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    private static extern bool CreateProcessAsUser(IntPtr hToken, string? appName, string cmdLine,
        IntPtr procAttrs, IntPtr threadAttrs, bool inherit, uint flags, IntPtr env, string? curDir,
        ref STARTUPINFO si, out PROCESS_INFORMATION pi);
    [DllImport("kernel32.dll", SetLastError = true)] public static extern bool CloseHandle(IntPtr h);
}
