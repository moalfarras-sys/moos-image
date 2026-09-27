using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;

namespace MoRemote;

public static class ShellFreshness
{
    // Shared by both hosts. OSTree mtimes are frozen: a cached Last-Modified
    // value cannot tell the browser that the entry page or worker changed.
    public static void Use(WebApplication app) => app.Use(async (ctx, next) =>
    {
        var path = ctx.Request.Path.Value ?? "";
        var entry = path == "/" || path.EndsWith(".html", StringComparison.OrdinalIgnoreCase)
            || path.EndsWith("manifest.webmanifest", StringComparison.OrdinalIgnoreCase)
            || path.EndsWith("sw.js", StringComparison.OrdinalIgnoreCase);
        // StaticFiles derives both validators from mtime/length. Both can stay
        // identical between immutable releases even when the bytes changed.
        if (entry)
        {
            ctx.Request.Headers.Remove("If-None-Match");
            ctx.Request.Headers.Remove("If-Modified-Since");
        }
        ctx.Response.OnStarting(() =>
        {
            if (entry)
            {
                ctx.Response.Headers.CacheControl = "no-cache, no-store, must-revalidate";
                ctx.Response.Headers.Remove("ETag");
                ctx.Response.Headers.Remove("Last-Modified");
            }
            return Task.CompletedTask;
        });
        await next();
    });
}
