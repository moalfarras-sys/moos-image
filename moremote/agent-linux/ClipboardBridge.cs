using System.Diagnostics;
namespace MoRemote;
public sealed record ClipContent(string Kind, string? Text, byte[]? ImagePng);
public static class ClipboardBridge
{
    public static bool IsReady => File.Exists("/usr/bin/wl-copy") && File.Exists("/usr/bin/wl-paste") && !string.IsNullOrEmpty(Environment.GetEnvironmentVariable("WAYLAND_DISPLAY"));
    private static byte[] RunRead(string file,string args) { using var p=Process.Start(new ProcessStartInfo(file,args){UseShellExecute=false,RedirectStandardOutput=true}); if(p==null)return []; using var m=new MemoryStream(); p.StandardOutput.BaseStream.CopyTo(m); p.WaitForExit(3000); return m.ToArray(); }
    public static ClipContent GetContent() { try { var types=System.Text.Encoding.UTF8.GetString(RunRead("wl-paste","--list-types")); if(types.Contains("image/png")) return new("image",null,RunRead("wl-paste","--type image/png")); var t=System.Text.Encoding.UTF8.GetString(RunRead("wl-paste","--no-newline")); return string.IsNullOrEmpty(t)?new("empty",null,null):new("text",t,null); } catch { return new("empty",null,null); } }
    public static string GetText()=>GetContent().Text??"";
    // Pass NO text argument: wl-copy given positional text copies THAT (after .NET's
    // argv splitting/quote-mangling) and ignores stdin, corrupting spaces/quotes and
    // Arabic. Empty args => argv is just [wl-copy], so it copies stdin verbatim —
    // exactly like SetImagePng (options in argv, payload on stdin).
    public static void SetText(string text)=>Write("wl-copy","",System.Text.Encoding.UTF8.GetBytes(text));
    public static void SetImagePng(byte[] data)=>Write("wl-copy","--type image/png",data);
    private static void Write(string file,string args,byte[] data){using var p=Process.Start(new ProcessStartInfo(file,args){UseShellExecute=false,RedirectStandardInput=true});if(p==null)return;p.StandardInput.BaseStream.Write(data);p.StandardInput.Close();p.WaitForExit(3000);}
}
