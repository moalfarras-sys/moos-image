using System.Buffers.Binary;
using System.Diagnostics;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;

namespace MoRemote;

/// <summary>
/// Persistent KDE Wayland input backend. It writes Linux input_event datagrams directly to the
/// already-running ydotoold uinput device; no process is spawned per pointer event.
/// </summary>
public sealed class InputInjector : IDisposable
{
    private const ushort EvSyn=0, EvKey=1, EvRel=2;
    private const ushort SynReport=0, RelX=0, RelY=1, RelHWheel=6, RelWheel=8;
    private const ushort BtnLeft=0x110, BtnRight=0x111, BtnMiddle=0x112;
    private readonly ScreenCapture _capture;
    private readonly object _gate = new();
    private readonly HashSet<ushort> _pressed = [];
    private Socket? _socket;
    private string _lastError="";
    private DateTimeOffset _lastConnectAttempt;
    private bool _cursorKnown;
    private int _cursorX,_cursorY;
    private Process? _portal;
    private StreamWriter? _portalInput;
    private bool _portalReady;

    private static readonly Dictionary<string,ushort> Keys = new(StringComparer.OrdinalIgnoreCase) {
        ["Control"]=29,["Ctrl"]=29,["Alt"]=56,["Shift"]=42,["Meta"]=125,["Super"]=125,["Win"]=125,
        ["Enter"]=28,["Escape"]=1,["Esc"]=1,["Tab"]=15,["Backspace"]=14,["Delete"]=111,
        ["ArrowUp"]=103,["ArrowDown"]=108,["ArrowLeft"]=105,["ArrowRight"]=106,
        ["Home"]=102,["End"]=107,["PageUp"]=104,["PageDown"]=109,["Insert"]=110,["Space"]=57,
        ["a"]=30,["c"]=46,["v"]=47,["x"]=45,["z"]=44,
        ["F1"]=59,["F2"]=60,["F3"]=61,["F4"]=62,["F5"]=63,["F6"]=64,
        ["F7"]=65,["F8"]=66,["F9"]=67,["F10"]=68,["F11"]=87,["F12"]=88
    };

    public InputInjector(ScreenCapture capture) { _capture=capture; StartPortal(); ConfigureKwinPointer(); EnsureConnected(force:true); }
    public bool IsReady { get { lock(_gate) return _portalReady||EnsureConnected(); } }
    public string BackendName => _portalReady?"KDE RemoteDesktop portal + ydotoold absolute fallback":"ydotoold/uinput fallback";
    public string LastError { get { lock(_gate) return _lastError; } }

    private static string SocketPath => Environment.GetEnvironmentVariable("YDOTOOL_SOCKET")
        ?? Path.Combine(Environment.GetEnvironmentVariable("XDG_RUNTIME_DIR") ?? "/tmp", ".ydotool_socket");

    private void StartPortal()
    {
        try{
            var helper=Path.Combine(AppContext.BaseDirectory,"mo-remote-input-portal.py");if(!File.Exists(helper))return;
            var psi=new ProcessStartInfo("python3"){UseShellExecute=false,RedirectStandardInput=true,RedirectStandardOutput=true,RedirectStandardError=true};psi.ArgumentList.Add(helper);
            _portal=Process.Start(psi);if(_portal==null)return;
            var read=_portal.StandardOutput.ReadLineAsync();if(!read.Wait(8000)||string.IsNullOrEmpty(read.Result))throw new IOException("portal helper startup timed out");
            using var doc=JsonDocument.Parse(read.Result);_portalReady=doc.RootElement.GetProperty("type").GetString()=="ready";
            _portalInput=_portal.StandardInput;_portalInput.AutoFlush=true;if(_portalReady)Log.Info("Input backend ready: KDE RemoteDesktop portal.");
        }catch(Exception ex){_portalReady=false;Log.Warn("KDE input portal unavailable, using ydotoold fallback: "+ex.Message);try{_portal?.Kill(true);}catch{}}
    }
    private bool Portal(object message){lock(_gate){if(!_portalReady||_portalInput==null)return false;try{_portalInput.WriteLine(JsonSerializer.Serialize(message));return true;}catch(Exception ex){_portalReady=false;_lastError=ex.Message;Log.Warn("KDE input portal failed: "+ex.Message);return false;}}}

    private bool EnsureConnected(bool force=false)
    {
        if (_socket != null) return true;
        if (!force && DateTimeOffset.UtcNow-_lastConnectAttempt < TimeSpan.FromSeconds(1)) return false;
        _lastConnectAttempt=DateTimeOffset.UtcNow;
        try {
            if (!File.Exists(SocketPath)) throw new IOException($"ydotoold socket not found: {SocketPath}");
            var socket=new Socket(AddressFamily.Unix,SocketType.Dgram,ProtocolType.Unspecified);
            socket.Connect(new UnixDomainSocketEndPoint(SocketPath));
            _socket=socket; _lastError=""; Log.Info($"Input backend ready: ydotoold socket {SocketPath}."); return true;
        } catch(Exception ex) { _lastError=ex.Message; Log.Warn("Input backend unavailable: "+ex.Message); return false; }
    }

    private bool Emit(ushort type,ushort code,int value,bool sync=true)
    {
        lock(_gate) {
            if(!EnsureConnected()) return false;
            try { SendEvent(type,code,value); if(sync) SendEvent(EvSyn,SynReport,0); return true; }
            catch(Exception ex) { _lastError=ex.Message; try{_socket?.Dispose();}catch{} _socket=null; Log.Warn("Input socket failed: "+ex.Message); return false; }
        }
    }
    private void SendEvent(ushort type,ushort code,int value)
    {
        Span<byte> data=stackalloc byte[24]; // timeval(16), type(2), code(2), value(4), little-endian Linux x64
        BinaryPrimitives.WriteUInt16LittleEndian(data[16..],type);
        BinaryPrimitives.WriteUInt16LittleEndian(data[18..],code);
        BinaryPrimitives.WriteInt32LittleEndian(data[20..],value);
        if(_socket!.Send(data)!=data.Length) throw new IOException("short ydotoold datagram write");
    }

    private (int x,int y) Pos(double x,double y) {var b=_capture.InputBounds;var p=CoordinateMapper.NormalizedToDesktop(x,y,new(b.Left,b.Top,b.Width,b.Height));return(p.X-b.Left,p.Y-b.Top);}
    private static ushort Button(string b)=>b.Equals("right",StringComparison.OrdinalIgnoreCase)?BtnRight:b.Equals("middle",StringComparison.OrdinalIgnoreCase)?BtnMiddle:BtnLeft;

    private static void ConfigureKwinPointer()
    {
        try {
            var eventName=Directory.EnumerateFiles("/sys/class/input","event*").Select(Path.GetFileName)
                .FirstOrDefault(e=>File.ReadAllText($"/sys/class/input/{e}/device/name").Trim()=="ydotoold virtual device");
            if(eventName==null)return;var path=$"/org/kde/KWin/InputDevice/{eventName}";
            foreach(var (property,value) in new[]{("pointerAccelerationProfileFlat","true"),("pointerAccelerationProfileAdaptive","false")}){
                var psi=new ProcessStartInfo("busctl"){UseShellExecute=false,RedirectStandardError=true};
                foreach(var a in new[]{"--user","set-property","org.kde.KWin",path,"org.kde.KWin.InputDevice",property,"b",value})psi.ArgumentList.Add(a);
                using var p=Process.Start(psi);p?.WaitForExit(2000);
            }
            Log.Info("Configured KWin flat acceleration for the ydotoold virtual pointer.");
        } catch(Exception ex){Log.Warn("Could not configure KWin virtual pointer: "+ex.Message);}
    }

    public void MouseMove(double x,double y)=>MoveTo(x,y,false);
    private void MoveTo(double x,double y,bool recalibrate) { var p=Pos(x,y); lock(_gate) { if(!EnsureConnected())return; try {
        var b=_capture.InputBounds;
        if(recalibrate||!_cursorKnown){SendEvent(EvRel,RelX,4096);SendEvent(EvRel,RelY,4096);SendEvent(EvSyn,SynReport,0);_cursorX=Math.Max(0,b.Width-1);_cursorY=Math.Max(0,b.Height-1);_cursorKnown=true;}
        int dx=p.x-_cursorX,dy=p.y-_cursorY;if(dx!=0)SendEvent(EvRel,RelX,dx);if(dy!=0)SendEvent(EvRel,RelY,dy);if(dx!=0||dy!=0)SendEvent(EvSyn,SynReport,0);_cursorX=p.x;_cursorY=p.y;
    } catch(Exception ex){_lastError=ex.Message;_socket?.Dispose();_socket=null;_cursorKnown=false;} } }
    public void MouseMoveRelative(double dx,double dy,double sensitivity=1) {
        int x=(int)Math.Round(Math.Clamp(dx*sensitivity,-500,500)), y=(int)Math.Round(Math.Clamp(dy*sensitivity,-500,500));
        if(x!=0||y!=0)if(Portal(new{type="relative",dx=x,dy=y})){lock(_gate){if(_cursorKnown){var b=_capture.InputBounds;_cursorX=Math.Clamp(_cursorX+x,0,Math.Max(0,b.Width-1));_cursorY=Math.Clamp(_cursorY+y,0,Math.Max(0,b.Height-1));}}return;}
        if(x==0&&y==0)return; lock(_gate){if(!EnsureConnected())return;try{SendEvent(EvRel,RelX,x);SendEvent(EvRel,RelY,y);SendEvent(EvSyn,SynReport,0);if(_cursorKnown){var b=_capture.InputBounds;_cursorX=Math.Clamp(_cursorX+x,0,Math.Max(0,b.Width-1));_cursorY=Math.Clamp(_cursorY+y,0,Math.Max(0,b.Height-1));}}catch(Exception ex){_lastError=ex.Message;_socket?.Dispose();_socket=null;_cursorKnown=false;}}
    }
    public void Click(string b,double x,double y) { MoveTo(x,y,true); ClickCode(Button(b)); }
    public void ClickCurrent(string b) => ClickCode(Button(b));
    private void ClickCode(ushort c){Set(c,true);Thread.Sleep(35);Set(c,false);}
    public void DoubleClick(double x,double y) { MoveTo(x,y,true); DoubleClickCurrent(); }
    public void DoubleClickCurrent() { ClickCode(BtnLeft);Thread.Sleep(50);ClickCode(BtnLeft); }
    public void MouseButton(string b,bool down,double x,double y) { MoveTo(x,y,down); Set(Button(b),down); }
    public void MouseButtonCurrent(string b,bool down) => Set(Button(b),down);
    public void Scroll(double dx,double dy,double sensitivity=1) { double x=Math.Clamp(dx*sensitivity,-20,20),y=Math.Clamp(dy*sensitivity,-20,20);if(Portal(new{type="axis",dx=x,dy=y}))return;int ix=(int)Math.Round(x),iy=(int)Math.Round(-y);lock(_gate){if(!EnsureConnected())return;try{if(ix!=0)SendEvent(EvRel,RelHWheel,ix);if(iy!=0)SendEvent(EvRel,RelWheel,iy);if(ix!=0||iy!=0)SendEvent(EvSyn,SynReport,0);}catch(Exception ex){_lastError=ex.Message;_socket?.Dispose();_socket=null;}} }
    private void Set(ushort code,bool down){lock(_gate){if(down){if(!_pressed.Add(code))return;}else{if(!_pressed.Remove(code))return;}if(!Portal(new{type=code>=BtnLeft?"button":"key",button=(int)code,code=(int)code,down}))Emit(EvKey,code,down?1:0);}}
    public void KeyTap(string k){if(Keys.TryGetValue(k,out var c)){Set(c,true);Thread.Sleep(12);Set(c,false);}else if(k.Length==1)TypeText(k);}
    public void KeyDown(string k){if(Keys.TryGetValue(k,out var c))Set(c,true);}
    public void KeyUp(string k){if(Keys.TryGetValue(k,out var c))Set(c,false);}
    public void Combo(IReadOnlyList<string> keys){var codes=keys.Select(k=>Keys.TryGetValue(k,out var c)?c:(ushort)0).Where(c=>c>0).ToArray();foreach(var c in codes)Set(c,true);foreach(var c in codes.Reverse())Set(c,false);}
    public void TypeText(string text){if(string.IsNullOrEmpty(text))return;ClipboardBridge.SetText(text);Combo(["Control","V"]);}
    public void ReleaseAll(){ushort[] pressed;lock(_gate)pressed=_pressed.ToArray();foreach(var code in pressed)Set(code,false);}
    public void Dispose(){ReleaseAll();lock(_gate){try{_portalInput?.Close();}catch{}try{if(_portal is{HasExited:false})_portal.Kill(true);}catch{} _socket?.Dispose();_socket=null;}}
}
