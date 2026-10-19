using System.Net.Sockets;
using Microsoft.Extensions.Hosting;

namespace MoRemote;

/// <summary>One bind attempt; systemd owns the bounded restart policy.</summary>
public static class ListenerStartup
{
    public static async Task<bool> TryStartAsync(IHost host, CancellationToken cancellation = default)
    {
        try
        {
            await host.StartAsync(cancellation);
            return true;
        }
        catch (IOException error) when (AddressInUse(error))
        {
            // Another account's retiring greeter can still own this listener.
            // Never stop it, switch ports, retry a failed host, or publish ready.
            return false;
        }
    }

    private static bool AddressInUse(Exception error)
    {
        for (Exception? current = error; current is not null; current = current.InnerException)
            if (current is SocketException socket && socket.SocketErrorCode == SocketError.AddressAlreadyInUse)
                return true;
        return false;
    }
}
