using System.Drawing;
using System.Drawing.Imaging;
using SharpGen.Runtime;
using Vortice.Direct3D;
using Vortice.Direct3D11;
using Vortice.DXGI;
using static Vortice.Direct3D11.D3D11;
using static Vortice.DXGI.DXGI;

namespace MoRemote;

/// <summary>
/// GPU-composited screen capture via DXGI Desktop Duplication. Much smoother than BitBlt and
/// captures hardware-accelerated windows, videos and games that BitBlt renders black. One
/// duplication per monitor. Anything unexpected (no GPU support, RDP, another app already
/// duplicating, resolution change) surfaces as <see cref="GrabStatus.Lost"/> or a failed
/// <see cref="TryCreate"/> so the coordinator falls back to GDI.
/// </summary>
internal sealed class DxgiCapture : ICaptureBackend
{
    public string Name => "DXGI";

    private readonly ID3D11Device _device;
    private readonly ID3D11DeviceContext _context;
    private readonly IDXGIOutputDuplication _dupl;
    private readonly int _w, _h;

    private ID3D11Texture2D? _staging;
    private Bitmap? _bmp;
    private bool _haveFrame;

    private DxgiCapture(ID3D11Device device, ID3D11DeviceContext context, IDXGIOutputDuplication dupl, int w, int h)
    {
        _device = device; _context = context; _dupl = dupl; _w = w; _h = h;
    }

    /// <summary>Build a duplication for the output that matches <paramref name="bounds"/>, or null if unavailable.</summary>
    public static DxgiCapture? TryCreate(Rectangle bounds)
    {
        IDXGIFactory1? factory = null;
        try
        {
            if (CreateDXGIFactory1(out factory).Failure || factory == null) return null;

            for (uint ai = 0; factory.EnumAdapters1(ai, out IDXGIAdapter1 adapter).Success; ai++)
            {
                try
                {
                    for (uint oi = 0; adapter.EnumOutputs(oi, out IDXGIOutput output).Success; oi++)
                    {
                        try
                        {
                            var dc = output.Description.DesktopCoordinates;
                            bool match = dc.Left == bounds.Left && dc.Top == bounds.Top;
                            if (!match) { output.Dispose(); continue; }

                            using var output1 = output.QueryInterface<IDXGIOutput1>();
                            if (D3D11CreateDevice(adapter, DriverType.Unknown,
                                    DeviceCreationFlags.BgraSupport, null!,
                                    out ID3D11Device device, out ID3D11DeviceContext context).Failure)
                            { output.Dispose(); return null; }

                            IDXGIOutputDuplication dupl;
                            try { dupl = output1.DuplicateOutput(device); }
                            catch { device.Dispose(); context.Dispose(); output.Dispose(); return null; }

                            output.Dispose();
                            return new DxgiCapture(device, context, dupl, bounds.Width, bounds.Height);
                        }
                        catch { output.Dispose(); }
                    }
                }
                finally { adapter.Dispose(); }
            }
            return null;
        }
        catch { return null; }
        finally { factory?.Dispose(); }
    }

    public GrabStatus Grab(Rectangle bounds, out Bitmap? frame)
    {
        frame = null;
        IDXGIResource? resource = null;
        try
        {
            // Longer wait for the very first frame, short otherwise (unchanged screen → reuse last).
            var result = _dupl.AcquireNextFrame(_haveFrame ? 120u : 500u, out _, out resource);
            if (result == Vortice.DXGI.ResultCode.WaitTimeout)
            {
                frame = _haveFrame ? _bmp : null;
                return GrabStatus.Unchanged;
            }
            if (result.Failure) return GrabStatus.Lost;

            using var tex = resource!.QueryInterface<ID3D11Texture2D>();
            EnsureStaging();
            _context.CopyResource(_staging!, tex);

            var map = _context.Map(_staging!, 0u, MapMode.Read, Vortice.Direct3D11.MapFlags.None);
            try
            {
                EnsureBitmap();
                CopyRows(map.DataPointer, map.RowPitch);
            }
            finally { _context.Unmap(_staging!, 0); }

            _haveFrame = true;
            frame = _bmp;
            return GrabStatus.Updated;
        }
        catch (SharpGenException ex)
        {
            if (ex.ResultCode == Vortice.DXGI.ResultCode.WaitTimeout) { frame = _haveFrame ? _bmp : null; return GrabStatus.Unchanged; }
            return GrabStatus.Lost; // AccessLost etc. → coordinator rebuilds / falls back
        }
        catch { return GrabStatus.Lost; }
        finally
        {
            resource?.Dispose();
            try { _dupl.ReleaseFrame(); } catch { }
        }
    }

    private unsafe void CopyRows(IntPtr src, uint srcPitch)
    {
        var data = _bmp!.LockBits(new Rectangle(0, 0, _w, _h), ImageLockMode.WriteOnly, PixelFormat.Format32bppRgb);
        try
        {
            long rowBytes = _w * 4;
            byte* s = (byte*)src;
            byte* d = (byte*)data.Scan0;
            for (int y = 0; y < _h; y++)
                Buffer.MemoryCopy(s + (long)y * srcPitch, d + (long)y * data.Stride, rowBytes, rowBytes);
        }
        finally { _bmp.UnlockBits(data); }
    }

    private void EnsureStaging()
    {
        if (_staging != null) return;
        _staging = _device.CreateTexture2D(new Texture2DDescription
        {
            Width = (uint)_w,
            Height = (uint)_h,
            MipLevels = 1,
            ArraySize = 1,
            Format = Format.B8G8R8A8_UNorm,
            SampleDescription = new SampleDescription(1, 0),
            Usage = ResourceUsage.Staging,
            BindFlags = BindFlags.None,
            CPUAccessFlags = CpuAccessFlags.Read,
            MiscFlags = ResourceOptionFlags.None,
        });
    }

    private void EnsureBitmap()
    {
        _bmp ??= new Bitmap(_w, _h, PixelFormat.Format32bppRgb);
    }

    public void Dispose()
    {
        try { _dupl.Dispose(); } catch { }
        try { _staging?.Dispose(); } catch { }
        try { _context.Dispose(); } catch { }
        try { _device.Dispose(); } catch { }
        try { _bmp?.Dispose(); } catch { }
    }
}
