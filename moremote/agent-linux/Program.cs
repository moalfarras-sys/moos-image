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
using var capture=new ScreenCapture(); using var input=new InputInjector(capture);
var svc=new AgentServices{Config=config,Sessions=new SessionManager(config),State=new SessionState(),Capture=capture,Input=input,HttpsHost=tls?.Host};
var builder=WebApplication.CreateBuilder(new WebApplicationOptions{ContentRootPath=AppContext.BaseDirectory,Args=args});
builder.Logging.ClearProviders(); builder.Services.AddSingleton(svc);
builder.WebHost.ConfigureKestrel(o=>o.ListenAnyIP(config.Port,lo=>{if(tls!=null)lo.UseHttps(tls.Certificate);}));
var app=builder.Build(); WebApi.UseNetworkGuard(app,svc); app.UseWebSockets(); app.UseDefaultFiles(); app.UseStaticFiles(); WebApi.Map(app,svc); app.MapFallbackToFile("index.html");
Log.Info($"Linux server listening: {svc.AccessUrl}");
await app.RunAsync();
