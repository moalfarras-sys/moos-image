using System.Diagnostics;
namespace MoRemote;
public static class PowerActions
{
    public static bool Run(string action) { var args=action.ToLowerInvariant() switch {"lock"=>"lock-session","sleep"=>"suspend","signout" or "logoff"=>"terminate-user "+Environment.UserName,"restart"=>"reboot","shutdown"=>"poweroff",_=>""}; if(args.Length==0)return false; try{Process.Start(new ProcessStartInfo("systemctl",args){UseShellExecute=false});return true;}catch{return false;} }
}
