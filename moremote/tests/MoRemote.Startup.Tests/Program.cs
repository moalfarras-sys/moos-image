using System.Net;
using System.Net.Sockets;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using MoRemote;

try
{
var directory = Path.Combine(Path.GetTempPath(), "moos-bind-proof-" + Guid.NewGuid());
Directory.CreateDirectory(directory);
var endpoint = Path.Combine(directory, "endpoint.json");
using var deadline = new CancellationTokenSource(TimeSpan.FromSeconds(20));
var cancellation = deadline.Token;
int passed = 0;
void Check(bool value, string name)
{
    if (!value) throw new Exception(name);
    Console.WriteLine("PASS: " + name);
    passed++;
}
WebApplication Application(int port, Exception? failure = null)
{
    var builder = WebApplication.CreateSlimBuilder();
    builder.Logging.ClearProviders();
    // Same ListenLocalhost boundary as production; no portal or account state.
    builder.WebHost.ConfigureKestrel(server => server.ListenLocalhost(port));
    if (failure is not null) builder.Services.AddSingleton<IHostedService>(new FailedStart(failure));
    var app = builder.Build();
    app.MapGet("/", () => "bound");
    return app;
}
async Task<int> Attempt(int port)
{
    await using var app = Application(port);
    if (!await ListenerStartup.TryStartAsync(app, cancellation)) return 75;
    await File.WriteAllTextAsync(endpoint, "bound", cancellation);
    try
    {
        using var http = new HttpClient { Timeout = TimeSpan.FromSeconds(2) };
        Check(await http.GetStringAsync($"http://127.0.0.1:{port}/", cancellation) == "bound", "real HTTP after bind");
        Check(File.Exists(endpoint), "endpoint exists only on successful path");
    }
    finally
    {
        File.Delete(endpoint);
        await app.StopAsync(cancellation);
    }
    return 0;
}
try
{
    using var occupied = new TcpListener(IPAddress.Loopback, 0);
    occupied.Start();
    int port = ((IPEndPoint)occupied.LocalEndpoint).Port;
    // Execute the old real Kestrel call; catch its failure here to avoid creating
    // the very unhandled-exception core dump this repair prevents.
    await using (var old = Application(port))
    {
        bool threw = false;
        try { await old.StartAsync(cancellation); }
        catch (IOException) { threw = true; }
        Check(threw && !File.Exists(endpoint), "old startup throws on occupied actual socket");
    }
    for (int attempt = 0; attempt < 3; attempt++)
    {
        Check(await Attempt(port) == 75, "occupied attempt returns ordinary failure " + attempt);
        Check(!File.Exists(endpoint), "occupied attempt does not publish endpoint " + attempt);
    }
    Check(occupied.Server.IsBound, "foreign fixture listener stays owned and bound");
    occupied.Stop();
    Check(await Attempt(port) == 0, "new attempt binds after previous owner releases");
    Check(!File.Exists(endpoint), "successful stop removes endpoint");
    Check(await Attempt(port) == 0, "ordinary unoccupied startup still works");

    using var cancelled = new CancellationTokenSource();
    cancelled.Cancel();
    await using (var app = Application(port))
    {
        bool threw = false;
        try { await ListenerStartup.TryStartAsync(app, cancelled.Token); }
        catch (OperationCanceledException) { threw = true; }
        Check(threw && !File.Exists(endpoint), "cancelled startup stays cancellation without endpoint");
    }
    foreach (var failure in new Exception[] { new IOException("private disk failure"), new InvalidOperationException("private configuration failure") })
    {
        await using var app = Application(port, failure);
        bool same = false;
        try { await ListenerStartup.TryStartAsync(app, cancellation); }
        catch (Exception caught) { same = ReferenceEquals(caught, failure); }
        Check(same && !File.Exists(endpoint), "unrelated failure propagates: " + failure.GetType().Name);
    }
    Console.WriteLine($"Native Kestrel startup controls passed ({passed})");
}
finally { Directory.Delete(directory, recursive: true); }
}
catch (Exception error)
{
    Console.Error.WriteLine("Startup controls failed: " + error);
    return 1;
}
return 0;

sealed class FailedStart(Exception failure) : IHostedService
{
    public Task StartAsync(CancellationToken cancellation) => Task.FromException(failure);
    public Task StopAsync(CancellationToken cancellation) => Task.CompletedTask;
}
