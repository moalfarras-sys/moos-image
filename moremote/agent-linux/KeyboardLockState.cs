using System.Diagnostics;
using System.Net.Sockets;
using System.Text;

namespace MoRemote;

/// <summary>
/// Read KWin's seat state through its version-1 keystate protocol. Keyboard LEDs
/// can be absent on a cloud host and XWayland can retain a previous focus state.
/// This short-lived connection creates no surface and never changes a lock.
/// Protocol: KDE/plasma-wayland-protocols, src/protocols/keystate.xml.
/// </summary>
public static class KeyboardLockState
{
    public static bool? ReadCapsLock()
    {
        var display = Environment.GetEnvironmentVariable("WAYLAND_DISPLAY");
        var runtime = Environment.GetEnvironmentVariable("XDG_RUNTIME_DIR");
        if (string.IsNullOrEmpty(display)) return null;
        if (!Path.IsPathRooted(display))
        {
            if (string.IsNullOrEmpty(runtime)) return null;
            display = Path.Combine(runtime, display);
        }
        return ReadCapsLock(display);
    }

    internal static bool? ReadCapsLock(string socketPath)
    {
        try
        {
            using var socket = new Socket(AddressFamily.Unix, SocketType.Stream, ProtocolType.Unspecified);
            socket.ReceiveTimeout = socket.SendTimeout = 250;
            socket.ConnectAsync(new UnixDomainSocketEndPoint(socketPath))
                .WaitAsync(TimeSpan.FromMilliseconds(250)).GetAwaiter().GetResult();
            var deadline = Stopwatch.StartNew();
            void Send(uint id, ushort opcode, byte[] payload)
            {
                // Wayland uses the local machine's native byte order; never a network endian.
                var bytes = BitConverter.GetBytes(id)
                    .Concat(BitConverter.GetBytes((uint)((payload.Length + 8) << 16) | opcode))
                    .Concat(payload).ToArray();
                for (int sent = 0; sent < bytes.Length;)
                {
                    int n = socket.Send(bytes.AsSpan(sent));
                    if (n == 0) throw new IOException("Wayland closed");
                    sent += n;
                }
            }
            byte[] Read(int count)
            {
                var bytes = new byte[count];
                for (int got = 0; got < count;)
                {
                    if (deadline.ElapsedMilliseconds > 500) throw new IOException("Wayland state timeout");
                    int n = socket.Receive(bytes.AsSpan(got));
                    if (n == 0) throw new IOException("Wayland closed");
                    got += n;
                }
                return bytes;
            }
            uint global = 0;
            bool? caps = null;
            void UntilSync(uint callback)
            {
                for (int messages = 0; messages < 4096; messages++)
                {
                    var header = Read(8);
                    uint id = BitConverter.ToUInt32(header);
                    uint word = BitConverter.ToUInt32(header, 4);
                    int size = (int)(word >> 16);
                    if (size < 8 || size % 4 != 0) throw new IOException("Invalid Wayland frame");
                    var body = Read(size - 8);
                    uint opcode = word & 0xffff;
                    if (id == 1 && opcode == 0) throw new IOException("Wayland protocol error");
                    if (id == callback && opcode == 0) return;
                    if (id == 2 && opcode == 0 && body.Length >= 12)
                    {
                        int length = checked((int)BitConverter.ToUInt32(body, 4));
                        int padded = checked((length + 3) & ~3);
                        if (length < 1 || padded > body.Length - 12 || body[8 + length - 1] != 0)
                            throw new IOException("Invalid Wayland interface");
                        if (Encoding.UTF8.GetString(body, 8, length - 1) == "org_kde_kwin_keystate"
                            && BitConverter.ToUInt32(body, 8 + padded) >= 1)
                            global = BitConverter.ToUInt32(body);
                    }
                    if (id == 4 && opcode == 0 && body.Length == 8 && BitConverter.ToUInt32(body) == 0)
                    {
                        uint state = BitConverter.ToUInt32(body, 4);
                        caps = state <= 2 ? state != 0 : null;
                    }
                }
                throw new IOException("Wayland state message limit");
            }
            Send(1, 1, BitConverter.GetBytes(2u)); // wl_display.get_registry
            Send(1, 0, BitConverter.GetBytes(3u)); // wl_display.sync
            UntilSync(3);
            if (global == 0) return null;
            var name = Encoding.UTF8.GetBytes("org_kde_kwin_keystate\0");
            var paddedName = new byte[(name.Length + 3) & ~3];
            name.CopyTo(paddedName, 0);
            Send(2, 0, BitConverter.GetBytes(global).Concat(BitConverter.GetBytes((uint)name.Length))
                .Concat(paddedName).Concat(BitConverter.GetBytes(1u)).Concat(BitConverter.GetBytes(4u)).ToArray());
            Send(4, 0, []); // fetchStates
            Send(1, 0, BitConverter.GetBytes(5u));
            UntilSync(5);
            return caps;
        }
        catch (Exception ex) when (ex is SocketException or IOException or ArgumentException or OverflowException or TimeoutException)
        {
            return null; // unknown is never treated as unlocked by the text injector
        }
    }
}
