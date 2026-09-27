using System.Net;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Hosting.Server;
using Microsoft.AspNetCore.Hosting.Server.Features;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using MoRemote;

static class ShellFreshnessTests
{
    public static async Task<int> Run()
    {
        var directory = Path.Combine(Path.GetTempPath(), "moos-shell-http-" + Guid.NewGuid());
        Directory.CreateDirectory(directory);
        var worker = Path.Combine(directory, "sw.js");
        await File.WriteAllTextAsync(worker, "version-one");
        File.SetLastWriteTimeUtc(worker, DateTime.UnixEpoch);
        var builder = WebApplication.CreateSlimBuilder(new WebApplicationOptions { WebRootPath = directory });
        builder.Logging.ClearProviders();
        builder.WebHost.ConfigureKestrel(server => server.Listen(IPAddress.Loopback, 0));
        await using var app = builder.Build();
        ShellFreshness.Use(app);
        app.UseStaticFiles();
        app.UseRouting();
        app.MapGet("/{**path}", (HttpContext ctx) => ctx.Response.WriteAsync("fixture"));
        await app.StartAsync();
        try
        {
            var address = app.Services.GetRequiredService<IServer>().Features
                .Get<IServerAddressesFeature>()!.Addresses.Single();
            using var client = new HttpClient { BaseAddress = new Uri(address), Timeout = TimeSpan.FromSeconds(3) };
            foreach (var path in new[] { "/", "/index.html", "/sw.js", "/notification-sw.js", "/manifest.webmanifest" })
            {
                using var response = await client.GetAsync(path);
                if (!response.IsSuccessStatusCode || response.Headers.CacheControl is not { NoStore: true, NoCache: true, MustRevalidate: true })
                    throw new Exception($"entry shell was cacheable: {path}: {response.Headers.CacheControl}");
            }
            foreach (var path in new[] { "/assets/index-hashed.js", "/api/status" })
            {
                using var response = await client.GetAsync(path);
                if (response.Headers.CacheControl is not null)
                    throw new Exception($"shell middleware changed unrelated route: {path}");
            }
            // Immutable deployments preserve mtime and can preserve byte count.
            // StaticFiles alone would return 304 to this old validator forever.
            await File.WriteAllTextAsync(worker, "version-two");
            File.SetLastWriteTimeUtc(worker, DateTime.UnixEpoch);
            using var request = new HttpRequestMessage(HttpMethod.Get, "/sw.js");
            request.Headers.IfModifiedSince = DateTimeOffset.UnixEpoch;
            request.Headers.TryAddWithoutValidation("If-None-Match", "*");
            using var updated = await client.SendAsync(request);
            if (updated.StatusCode != HttpStatusCode.OK || await updated.Content.ReadAsStringAsync() != "version-two"
                || updated.Headers.ETag is not null || updated.Content.Headers.LastModified is not null)
                throw new Exception("frozen-mtime worker update did not arrive as fresh bytes");
            return 8;
        }
        finally { await app.StopAsync(); Directory.Delete(directory, recursive: true); }
    }
}
