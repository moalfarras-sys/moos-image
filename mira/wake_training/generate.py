"""Local synthetic corpus. Owner recording is deliberately excluded."""
from pathlib import Path
import json, wave
import numpy as np
from scipy.signal import resample_poly, lfilter
from piper import PiperVoice, SynthesisConfig

ROOT=Path(__file__).parent
OUT=ROOT/'clips'; OUT.mkdir(exist_ok=True)
rng=np.random.default_rng(729)
voice=PiperVoice.load(ROOT/'ar.onnx')
positive=['مِيرا','يا مِيرا','هاي مِيرا','مِيرَا','ميرا ميرا']
negative=['مرة','أميرة','كبيرة','مديرة','سميرة','مريم','مياه','مرحبا',
          'كيف حالك','شغل الضوء','أطفئ التلفاز','أليكسا','صباح الخير',
          'أنا في البيت','أريد أن أذهب إلى المكتب','شكرا','لماذا','نعم','لا']
manifest=[]
for label,phrases,count in [(1,positive,100),(0,negative,100)]:
 for idx in range(count):
  phrase=phrases[idx%len(phrases)]
  chunks=list(voice.synthesize(phrase,SynthesisConfig(
   length_scale=float(rng.uniform(.8,1.3)),noise_scale=.8,noise_w_scale=.8)))
  raw=np.concatenate([c.audio_float_array for c in chunks])
  sr=chunks[0].sample_rate
  x=resample_poly(raw,16000,sr).astype(np.float32)
  # Trim only digital/synthetic silence; no owner audio or timing is consulted.
  active=np.flatnonzero(np.abs(x)>.02*max(np.max(np.abs(x)),1e-6))
  if len(active): x=x[max(0,active[0]-800):min(len(x),active[-1]+1600)]
  for aug in range(2):
   y=x.copy()
   if aug:
    ratio=float(rng.uniform(.88,1.12))
    y=np.interp(np.arange(0,len(y),ratio),np.arange(len(y)),y)
    delay=int(rng.uniform(.015,.09)*16000)
    y[delay:]+=.2*y[:-delay]
   y=y/max(np.max(np.abs(y)),1e-6)*rng.uniform(.12,.65)
   y+=rng.normal(0,float(rng.uniform(.0001,.004)),len(y))
   name=f'{label}-{idx:03d}-{aug}.wav'
   with wave.open(str(OUT/name),'wb') as w:
    w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000)
    w.writeframes((np.clip(y,-1,1)*32767).astype('<i2').tobytes())
   manifest.append(dict(file=name,label=label,duration=len(y)/16000))
  if idx%25==0:print('generated',label,idx,flush=True)
(ROOT/'manifest.json').write_text(json.dumps(manifest))
print('clips',len(manifest),flush=True)
