using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using MoRemote;

Log.Init();
using var mutex = new Mutex(true, "MoRemotePersonal_Linux", out var first);
if (!first) return;
var config=AppConfig.Load(); UserSettings.Apply(config);
var tls=TlsManager.TryLoad();
// One portal session backs both the video stream and input injection.
using var portal=new PortalBridge();
using var capture=new ScreenCapture(portal); using var input=new InputInjector(portal,capture);
var svc=new AgentServices{Config=config,Sessions=new SessionManager(config),State=new SessionState(),Capture=capture,Input=input,HttpsHost=tls?.Host};
var builder=WebApplication.CreateBuilder(new WebApplicationOptions{ContentRootPath=AppContext.BaseDirectory,Args=args});
builder.Logging.ClearProviders(); builder.Services.AddSingleton(svc);
builder.WebHost.ConfigureKestrel(o=>o.ListenAnyIP(config.Port,lo=>{if(tls!=null)lo.UseHttps(tls.Certificate);}));
var app=builder.Build(); WebApi.UseNetworkGuard(app,svc); // Both values, because the interval alone is another gate that never fires. KeepAliveTimeout defaults
// to InfiniteTimeSpan, so ASP.NET sent a keep-alive ping every two minutes and then waited forever for
// a reply that a wedged peer was never going to send — the connection stayed "open" indefinitely, which
// is the server-side half of the stall the client watchdog was added to catch.
app.UseWebSockets(new WebSocketOptions {
    KeepAliveInterval = TimeSpan.FromSeconds(15),
    KeepAliveTimeout  = TimeSpan.FromSeconds(20),
}); app.UseDefaultFiles(); app.UseStaticFiles(); WebApi.Map(app,svc); app.MapFallbackToFile("index.html");
Log.Info($"Linux server listening: {svc.AccessUrl}");
await app.RunAsync();
