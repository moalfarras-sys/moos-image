namespace MoRemote;

public readonly record struct LogicalRect(int Left,int Top,int Width,int Height);

public static class CoordinateMapper
{
    public static (int X,int Y) NormalizedToDesktop(double x,double y,LogicalRect target)
    {
        if(!double.IsFinite(x)||!double.IsFinite(y)||target.Width<=0||target.Height<=0)
            throw new ArgumentOutOfRangeException(nameof(x),"Invalid normalized coordinate or target geometry.");
        x=Math.Clamp(x,0,1);y=Math.Clamp(y,0,1);
        return (target.Left+(int)Math.Round(x*Math.Max(1,target.Width-1)),
                target.Top +(int)Math.Round(y*Math.Max(1,target.Height-1)));
    }
}
