using System.Threading.Channels;
using MoRemote;

static class AudioLeaseTests
{
    public static async Task Run(SessionManager auth, Action<bool, bool, string> eq)
    {
        string Login()
        {
            if (auth.Login("246810", null, out var grant) != LoginResult.Ok)
                throw new Exception("audio fixture login failed");
            return grant.Token;
        }

        var token = Login();
        var tickets = new AccessTicketStore();
        var ticket = tickets.Issue("audio", token);
        auth.Revoke(token);
        eq(true, tickets.Consume(ticket, "audio", out var owner), "audio ticket retains its issuing session");
        eq(false, auth.IsValid(owner), "a ticket issued before logout cannot reopen audio");

        token = Login();
        await using (var lease = new SessionStreamLease(() => auth.IsValid(token), CancellationToken.None))
        {
            using var input = new AudioInput();
            using var output = new MemoryStream();
            input.Packets.Writer.TryWrite([1, 2, 3]);
            var copying = lease.CopyAsync(input, output);
            using var deadline = new CancellationTokenSource(TimeSpan.FromSeconds(3));
            while (output.Length != 3) await Task.Delay(5, deadline.Token);
            eq(true, output.ToArray().SequenceEqual(new byte[] { 1, 2, 3 }), "authorized audio reaches the listener");
            auth.Revoke(token);
            try { await copying.WaitAsync(TimeSpan.FromSeconds(3)); }
            catch (OperationCanceledException) { }
            eq(true, lease.Revoked && lease.Token.IsCancellationRequested, "logout cancels even an idle upstream read");
            input.Packets.Writer.TryWrite([4, 5]);
            eq(true, output.Length == 3, "revoked audio forwards no later bytes");
        }

        token = Login();
        await using (var lease = new SessionStreamLease(() => auth.IsValid(token), CancellationToken.None))
        {
            using var input = new AudioInput { OnRead = () => auth.Revoke(token) };
            using var output = new MemoryStream();
            input.Packets.Writer.TryWrite([9]);
            await lease.CopyAsync(input, output).WaitAsync(TimeSpan.FromSeconds(3));
            eq(true, output.Length == 0 && lease.Revoked, "revocation while reading discards the buffered packet");
        }

        await using (var lease = new SessionStreamLease(() => false, CancellationToken.None))
        {
            using var output = new MemoryStream();
            await lease.CopyAsync(new MemoryStream([7]), output);
            eq(true, lease.Revoked && output.Length == 0, "an invalid session cannot start a relay");
        }
    }

    sealed class AudioInput : Stream
    {
        public Channel<byte[]> Packets { get; } = Channel.CreateUnbounded<byte[]>();
        public Action? OnRead { get; init; }
        public override async ValueTask<int> ReadAsync(Memory<byte> buffer, CancellationToken cancellationToken = default)
        {
            var packet = await Packets.Reader.ReadAsync(cancellationToken);
            packet.CopyTo(buffer);
            OnRead?.Invoke();
            return packet.Length;
        }
        public override bool CanRead => true;
        public override bool CanSeek => false;
        public override bool CanWrite => false;
        public override long Length => throw new NotSupportedException();
        public override long Position { get => throw new NotSupportedException(); set => throw new NotSupportedException(); }
        public override void Flush() { }
        public override int Read(byte[] buffer, int offset, int count) => throw new NotSupportedException();
        public override long Seek(long offset, SeekOrigin origin) => throw new NotSupportedException();
        public override void SetLength(long value) => throw new NotSupportedException();
        public override void Write(byte[] buffer, int offset, int count) => throw new NotSupportedException();
    }
}
