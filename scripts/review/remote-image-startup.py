#!/usr/bin/env python3
"""Read-only final-image Remote runtime proof. Pass an immutable local image ID.

No host mounts, session connections, GUI, portals, input or external networking.
The container has its own network namespace (network=none); only its loopback
sockets are used. All state lives in the container's private /tmp tmpfs.
"""
import argparse,json,pathlib,re,subprocess,tempfile,uuid

INNER = r'''
import hashlib,json,os,pathlib,socket,subprocess,tempfile,time,urllib.request
r=pathlib.Path(tempfile.mkdtemp(prefix="remote-proof-")); r.chmod(0o700)
agent=pathlib.Path("/usr/lib/mo-remote/MoRemotePersonal")
assert agent.is_file() and os.access(agent,os.X_OK),"image agent executable missing"
base=os.environ.copy()
for key in ("MOREMOTE_PRELOGIN","ASPNETCORE_URLS","DOTNET_URLS"):
 base.pop(key,None)
children=[]
def environment(name,port):
 d=r/name;d.mkdir(mode=0o700)
 for name in ("home","data","runtime","config","cache"): (d/name).mkdir(mode=0o700)
 env=base.copy();env.update(HOME=str(d/"home"),MOREMOTE_DATA_DIR=str(d/"data"),XDG_RUNTIME_DIR=str(d/"runtime"),XDG_DATA_HOME=str(d/"data"),XDG_CONFIG_HOME=str(d/"config"),XDG_CACHE_HOME=str(d/"cache"),DBUS_SESSION_BUS_ADDRESS="unix:path="+str(d/"no-session-bus"),DBUS_SYSTEM_BUS_ADDRESS="unix:path="+str(d/"no-system-bus"),YDOTOOL_SOCKET=str(d/"no-input-socket"),WAYLAND_DISPLAY="wayland-no-compositor",PIPEWIRE_RUNTIME_DIR=str(d/"runtime"),PULSE_SERVER="unix:"+str(d/"no-audio-socket"))
 (d/"data/config.dat").write_text(json.dumps({"Port":port}))
 return d,env
try:
 with socket.socket() as holder:
  holder.bind(("127.0.0.1",0));holder.listen();port=holder.getsockname()[1]
  d,env=environment("occupied",port)
  result=subprocess.run([str(agent)],env=env,text=True,capture_output=True,timeout=15)
  log=(d/"data/log.txt").read_text()
  assert result.returncode==75,{"exit":result.returncode,"stderr":result.stderr,"log":log}
  assert "occupied; leaving its listener intact" in log,log
  assert "Linux server listening on loopback" not in log,log
  assert not (d/"runtime/mo-remote/endpoint.json").exists()
  assert holder.getsockname()[1]==port and holder.getsockopt(socket.SOL_SOCKET,socket.SO_ACCEPTCONN)==1
  # Kestrel ListenLocalhost can bind IPv6 before IPv4 fails. Disposal must
  # release that partial listener, while our fixture retains the IPv4 port.
  with socket.socket(socket.AF_INET6) as partial:
   partial.setsockopt(socket.IPPROTO_IPV6,socket.IPV6_V6ONLY,1)
   partial.bind(("::1",port))
  negative={"exit":result.returncode,"log":log,"stdout":result.stdout,"stderr":result.stderr,"partial_ipv6_released":True,"fixture_holder_preserved":True}
 # Fresh process, same port, after holder release. No listener is ever killed.
 d,env=environment("released",port)
 out=(d/"stdout.log").open("w");err=(d/"stderr.log").open("w")
 process=subprocess.Popen([str(agent)],env=env,stdout=out,stderr=err);children.append(process)
 response=None;until=time.monotonic()+12
 while time.monotonic()<until:
  assert process.poll() is None,"positive agent exited before HTTP"
  try:
   with urllib.request.urlopen("http://127.0.0.1:"+str(port)+"/api/status",timeout=.5) as received:
    response=json.load(received)
   break
  except (OSError,ValueError):time.sleep(.1)
 assert response is not None,"positive agent never served HTTP"
 assert response.get("firstRun") is True and response.get("preLogin") is False,response
 assert "Linux server listening on loopback" in (d/"data/log.txt").read_text()
 process.terminate();exitcode=process.wait(timeout=10)
 out.close();err.close()
 assert exitcode==0,{"positive_exit":exitcode,"stderr":(d/"stderr.log").read_text()}
 with socket.socket() as rebound:
  rebound.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);rebound.bind(("127.0.0.1",port))
 assert not (d/"runtime/mo-remote/endpoint.json").exists()
 hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest()for p in (agent,agent.with_suffix(".dll"),pathlib.Path("/usr/lib/mo-remote/mo-remote-portal.py"))if p.is_file()}
 receipt={"result":"PASS","negative":negative,"positive":{"http_status":200,"first_run":response["firstRun"],"pre_login":response["preLogin"],"sigterm_exit":exitcode,"socket_released":True,"log":(d/"data/log.txt").read_text(),"stderr":(d/"stderr.log").read_text()},"artifact_hashes":hashes,"isolation":"read-only root; private tmpfs; uid65534; no capabilities; network=none loopback only; nonexistent private session/system/input/Wayland/audio paths; no host mounts","limits":["Isolated MOREMOTE_DATA_DIR intentionally suppresses canonical endpoint publication; source integration and helper controls cover that ordering.","Container image runtime proof, not installed account handoff, physical display, phone endurance, signed delivery or boot proof."]}
 print(json.dumps(receipt,indent=2),flush=True)
finally:
 for child in children:
  if child.poll() is None:
   child.terminate()
   try:child.wait(timeout=3)
   except subprocess.TimeoutExpired:child.kill();child.wait()
'''

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('image_id',help='immutable local sha256 image ID, not a tag')
 args=parser.parse_args()
 if not re.fullmatch(r'(?:sha256:)?[a-f0-9]{64}',args.image_id):parser.error('an immutable 64-digit image ID is required')
 image='sha256:'+args.image_id.removeprefix('sha256:')
 actual=subprocess.run(['podman','image','inspect','--format','{{.Id}}',image],text=True,capture_output=True,timeout=10,check=True).stdout.strip()
 if actual.removeprefix('sha256:')!=image.removeprefix('sha256:'):raise RuntimeError('image identity mismatch')
 evidence=pathlib.Path(tempfile.mkdtemp(prefix='moos-final-image-remote-'));print('EVIDENCE '+str(evidence),flush=True)
 container='moos-remote-proof-'+uuid.uuid4().hex
 command=['podman','run','--name',container,'--rm','--network=none','--read-only','--tmpfs','/tmp:rw,nosuid,nodev,size=128m','--user','65534:65534','--cap-drop=ALL','--security-opt','no-new-privileges','--pids-limit=128','--entrypoint','/usr/bin/python3',image,'-']
 try:
  result=subprocess.run(command,input=INNER,text=True,capture_output=True,timeout=55)
 except subprocess.TimeoutExpired as failure:
  result=subprocess.CompletedProcess(command,124,'','private container proof exceeded55s: '+str(failure))
 finally:
  # Only this UUID-named fixture may be removed; never a host service/container.
  subprocess.run(['podman','rm','--force',container],text=True,capture_output=True,timeout=10)
 (evidence/'stdout.json').write_text(result.stdout);(evidence/'stderr.log').write_text(result.stderr)
 receipt={'image_id':image,'command':command,'exit_code':result.returncode,'evidence':str(evidence)}
 if result.returncode==0:
  receipt.update(json.loads(result.stdout))
 else:
  receipt.update(result='FAIL',stderr=result.stderr,stdout=result.stdout)
 (evidence/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
 print(json.dumps(receipt,indent=2))
 return result.returncode

if __name__=='__main__':raise SystemExit(main())
