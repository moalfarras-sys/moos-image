#!/usr/bin/python3
"""Persistent KDE RemoteDesktop portal input helper. JSON lines in/out; no shell commands."""
import json,sys,uuid
import gi
gi.require_version("Gio","2.0")
from gi.repository import Gio,GLib

BUS="org.freedesktop.portal.Desktop"; PATH="/org/freedesktop/portal/desktop"; IFACE="org.freedesktop.portal.RemoteDesktop"
bus=Gio.bus_get_sync(Gio.BusType.SESSION,None)

def request(method,signature,values,iface=IFACE):
    handle=values[-1].get("handle_token") if isinstance(values[-1],dict) else None
    handle=handle.unpack() if handle else ("req_"+uuid.uuid4().hex)
    sender=bus.get_unique_name().lstrip(":").replace(".","_")
    expected=f"/org/freedesktop/portal/desktop/request/{sender}/{handle}"
    loop=GLib.MainLoop(); answer={}
    def response(_c,_sender,_path,_iface,_signal,params):
        code,data=params.unpack();answer.update(code=code,data=data);loop.quit()
    sid=bus.signal_subscribe(BUS,"org.freedesktop.portal.Request","Response",expected,None,Gio.DBusSignalFlags.NONE,response)
    result=bus.call_sync(BUS,PATH,iface,method,GLib.Variant(signature,values),GLib.VariantType.new("(o)"),Gio.DBusCallFlags.NONE,10000,None)
    GLib.timeout_add_seconds(60,lambda:(loop.quit(),False)[1]);loop.run();bus.signal_unsubscribe(sid)
    if answer.get("code")!=0: raise RuntimeError(f"portal {method} denied/cancelled ({answer.get('code','timeout')})")
    return answer["data"]

token="moremote_"+uuid.uuid4().hex
created=request("CreateSession","(a{sv})",({"handle_token":GLib.Variant("s",token),"session_handle_token":GLib.Variant("s",token+"s")},))
session=created["session_handle"]
request("SelectDevices","(oa{sv})",(session,{"handle_token":GLib.Variant("s",token+"d"),"types":GLib.Variant("u",3)}))
started=request("Start","(osa{sv})",(session,"",{"handle_token":GLib.Variant("s",token+"x")}))
streams=started.get("streams",[]);stream=int(streams[0][0]) if streams else 0
empty={}

def notify(method,sig,args):
    bus.call_sync(BUS,PATH,IFACE,method,GLib.Variant(sig,args),None,Gio.DBusCallFlags.NO_AUTO_START,1000,None)

print(json.dumps({"type":"ready","backend":"KDE RemoteDesktop portal","stream":stream}),flush=True)
for line in sys.stdin:
 try:
  m=json.loads(line);t=m.get("type")
  if t=="relative": notify("NotifyPointerMotion","(oa{sv}dd)",(session,empty,float(m["dx"]),float(m["dy"])))
  elif t=="absolute" and stream: notify("NotifyPointerMotionAbsolute","(oa{sv}udd)",(session,empty,stream,float(m["x"]),float(m["y"])))
  elif t=="button": notify("NotifyPointerButton","(oa{sv}iu)",(session,empty,int(m["button"]),1 if m["down"] else 0))
  elif t=="axis": notify("NotifyPointerAxis","(oa{sv}dd)",(session,empty,float(m["dx"]),float(m["dy"])))
  elif t=="key": notify("NotifyKeyboardKeycode","(oa{sv}iu)",(session,empty,int(m["code"]),1 if m["down"] else 0))
  elif t=="keysym": notify("NotifyKeyboardKeysym","(oa{sv}iu)",(session,empty,int(m["keysym"]),1 if m["down"] else 0))
  elif t=="ping": print(json.dumps({"type":"pong"}),flush=True)
 except Exception as e: print(json.dumps({"type":"error","error":str(e)}),flush=True)
