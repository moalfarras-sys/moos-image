namespace MoRemote;

public sealed class InputSequenceGuard
{
    private long _last;
    public bool Accept(long sequence,long timestampMs,long nowMs,out string error)
    {
        if(sequence<=_last){error="duplicate or out-of-order sequence";return false;}
        if(Math.Abs(nowMs-timestampMs)>30000){error="stale timestamp";return false;}
        _last=sequence;error="";return true;
    }
}
