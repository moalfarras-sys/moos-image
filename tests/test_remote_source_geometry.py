#!/usr/bin/env python3
"""Capture geometry is upstream of scaling; never promote encoded startup caps to screen size."""
import ast,os,pathlib,types,unittest,io
ROOT=pathlib.Path(__file__).resolve().parents[1]
HELPER=pathlib.Path(os.environ.get('MOOS_SOURCE_GEOMETRY_HELPER',ROOT/'moremote/agent-linux/mo-remote-portal.py'))
def functions():
 tree=ast.parse(HELPER.read_text());nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('source_size','on_sample')]
 ns={};exec(compile(ast.Module(body=nodes,type_ignores=[]),str(HELPER),'exec'),ns);return ns
class Caps:
 def __init__(self,w,h):self.w,self.h=w,h
 def is_empty(self):return False
 def get_structure(self,_):return self
 def get_value(self,k):return self.w if k=='width' else self.h
class Source:
 def __init__(self,caps):self.caps=caps
 def get_static_pad(self,_):return self
 def get_current_caps(self):return self.caps
class Geometry(unittest.TestCase):
 def exercise(self,source):
  ns=functions();sent=[];health=[];scheduled=[]
  buffer=types.SimpleNamespace(map=lambda _:(True,types.SimpleNamespace(data=b'encoded')),unmap=lambda _:None)
  sample=types.SimpleNamespace(get_caps=lambda:Caps(640,480),get_buffer=lambda:buffer)
  sink=types.SimpleNamespace(emit=lambda _:sample)
  ns.update(state={'sw':0,'sh':0},Gst=types.SimpleNamespace(FlowReturn=types.SimpleNamespace(OK=0),MapFlags=types.SimpleNamespace(READ=1)),GLib=types.SimpleNamespace(idle_add=lambda fn:scheduled.append(fn)),rebuild=lambda:None,send_frame=lambda b:sent.append(b) or True,video_health=types.SimpleNamespace(note_frame=lambda t:health.append(t)),monotonic_ms=lambda:123)
  if 'source_size' in ns:ns['on_sample'](sink,source)
  else:ns['on_sample'](sink)
  return ns['state'],sent,health,scheduled
 def test_encoded_640_pixels_do_not_replace_a_4k_capture_size(self):
  state,sent,health,scheduled=self.exercise(Source(Caps(3840,2160)))
  self.assertEqual((state['sw'],state['sh']),(3840,2160));self.assertEqual(sent,[b'encoded']);self.assertEqual(health,[123]);self.assertEqual(len(scheduled),1)
 def test_unknown_capture_caps_cannot_publish_a_false_healthy_picture(self):
  state,sent,health,scheduled=self.exercise(Source(None));self.assertEqual((state['sw'],state['sh']),(0,0));self.assertEqual(sent+health+scheduled,[])
 def test_invalid_sizes_do_not_become_source_geometry(self):
  for size in [(0,480),(-1,480),(640,999999),('640',480)]:
   state,sent,health,_=self.exercise(Source(Caps(*size)));self.assertEqual(state['sw'],0);self.assertEqual(sent+health,[])
 @unittest.skipUnless(os.environ.get('MOOS_GST_SOURCE_PROOF')=='1','Opt-in native GStreamer chain; no desktop/portal')
 def test_real_raw_full_hd_is_not_the_encoded_640_by_360(self):
  import gi
  gi.require_version('Gst','1.0');from gi.repository import Gst
  Gst.init(None);ns=functions();frames=[];scheduled=[]
  ns.update(state={'sw':0,'sh':0},Gst=Gst,GLib=types.SimpleNamespace(idle_add=lambda fn:scheduled.append(fn)),rebuild=lambda:None,send_frame=lambda b:frames.append(bytes(b)) or True,video_health=types.SimpleNamespace(note_frame=lambda _:None),monotonic_ms=lambda:1)
  pipeline=Gst.parse_launch('videotestsrc name=source pattern=ball num-buffers=5 ! video/x-raw,width=1920,height=1080 ! videoscale ! video/x-raw,width=640,height=360 ! videoconvert ! jpegenc ! appsink name=sink emit-signals=true sync=false')
  source=pipeline.get_by_name('source');sink=pipeline.get_by_name('sink')
  sink.connect('new-sample',lambda sink: ns['on_sample'](sink,source) if 'source_size' in ns else ns['on_sample'](sink))
  try:
   pipeline.set_state(Gst.State.PLAYING);message=pipeline.get_bus().timed_pop_filtered(10*Gst.SECOND,Gst.MessageType.EOS|Gst.MessageType.ERROR)
   self.assertIsNotNone(message,'No finite pipeline result');self.assertEqual(message.type,Gst.MessageType.EOS)
  finally:pipeline.set_state(Gst.State.NULL)
  self.assertEqual((ns['state']['sw'],ns['state']['sh']),(1920,1080));self.assertEqual(len(frames),5)
  from PIL import Image
  self.assertTrue(all(Image.open(io.BytesIO(frame)).size==(640,360) for frame in frames))
  self.assertGreater(len(set(frames)),1,'The finite source must actually change its decoded pictures')
if __name__=='__main__':unittest.main()
