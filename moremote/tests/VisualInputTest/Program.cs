using MoRemote;

using var portal=new PortalBridge();
using var capture=new ScreenCapture(portal);
using var input=new InputInjector(portal,capture);
var readyUntil=DateTime.UtcNow.AddSeconds(10);
while(!input.IsReady&&DateTime.UtcNow<readyUntil)Thread.Sleep(100);
if(!input.IsReady)throw new Exception(input.LastError);
void Pause(int ms=180)=>Thread.Sleep(ms);
if(args.Contains("--launcher")){input.KeyTap("Meta");Thread.Sleep(5000);input.KeyTap("Escape");Console.WriteLine("LAUNCHER_TEST=PASS");return;}
if(args.Contains("--firefox")){
 input.KeyTap("Meta");Pause(500);input.TypeText("firefox");Pause(500);input.KeyTap("Enter");Thread.Sleep(3500);
 input.Combo(["Control","L"]);input.TypeText("https://example.com");input.KeyTap("Enter");Thread.Sleep(5000);
 Console.WriteLine("FIREFOX_URL_TEST=PASS");return;
}
if(args.Contains("--context")){input.MouseMove(.5,.5);input.ClickCurrent("right");Thread.Sleep(5000);input.KeyTap("Escape");Console.WriteLine("RIGHT_CLICK_TEST=PASS");return;}
if(args.Contains("--click-firefox")){
 input.Combo(["Alt","Tab"]);Thread.Sleep(900);
 // Firefox's navigation toolbar is near the top of the maximized desktop.
 // Do not use Ctrl+L: reaching the requested page must depend on the click.
 input.MouseMove(.48,.045);input.ClickCurrent("left");Pause(250);
 input.Combo(["Control","A"]);input.TypeText("https://example.org");input.KeyTap("Enter");Thread.Sleep(4500);
 Console.WriteLine("CLICK_NAVIGATION_TEST=PASS");return;
}
if(args.Contains("--drag")){input.MouseMove(.5,.075);input.MouseButtonCurrent("left",true);for(int i=0;i<12;i++){input.MouseMoveRelative(8,5);Pause(20);}input.MouseButtonCurrent("left",false);Thread.Sleep(4000);Console.WriteLine("WINDOW_DRAG_TEST=PASS");return;}
if(args.Contains("--unicode")){input.KeyTap("Meta");Pause(500);input.TypeText("kwrite");Pause(400);input.KeyTap("Enter");Thread.Sleep(2500);input.Combo(["Control","N"]);Pause(400);input.TypeText("مرحباً Grüße English");Thread.Sleep(2500);Console.WriteLine("UNICODE_TYPING_TEST=PASS");return;}
if(args.Contains("--unicode-file")){
 const string path="/tmp/moremote-unicode-input.txt";
const string expected="مرحبا بالعالم — Grüße € 👩🏽‍💻 1️⃣ English @#:/?_−";
 File.Delete(path);
 var start=new System.Diagnostics.ProcessStartInfo("/usr/bin/moai-open") { UseShellExecute=false };
 foreach(var arg in new[]{"konsole","-e","sh","-c",$"cat > {path}"})start.ArgumentList.Add(arg);
 using var terminal=System.Diagnostics.Process.Start(start);
 Thread.Sleep(2200);
 input.TypeText(expected);
 input.Combo(["Control","D"]);Thread.Sleep(1200);
 var actual=File.Exists(path)?File.ReadAllText(path):"";
 if(actual!=expected)throw new Exception($"Unicode input mismatch: expected '{expected}', got '{actual}'");
 Console.WriteLine("UNICODE_FILE_TEST=PASS");return;
}

// Corners and return paths.
foreach(var p in new[]{(0d,0d),(1d,0d),(1d,1d),(0d,1d),(.5,.5)}){input.MouseMove(p.Item1,p.Item2);Pause();}
// Slow and fast circles around the center.
foreach(var delay in new[]{35,5})for(int i=0;i<=48;i++){double a=i*Math.PI*2/48;input.MouseMove(.5+.22*Math.Cos(a),.5+.22*Math.Sin(a));Pause(delay);}
input.MouseMove(.5,.5);Pause();
// Button paths, including guaranteed release. Center is the already-focused terminal content.
input.ClickCurrent("left");input.ClickCurrent("right");Pause();input.KeyTap("Escape");
input.MouseButtonCurrent("left",true);input.MouseMoveRelative(12,8);input.MouseButtonCurrent("left",false);
input.Scroll(0,2);input.Scroll(2,0);
// Real desktop shortcuts and release recovery.
input.KeyTap("Meta");Pause(700);input.KeyTap("Escape");
input.Combo(["Alt","Tab"]);Pause(500);input.Combo(["Alt","Tab"]);
input.ReleaseAll();
Console.WriteLine($"VISIBLE_INPUT_PATHS=PASS backend={input.BackendName} geometry={capture.InputBounds}");
