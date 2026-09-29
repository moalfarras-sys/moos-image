"""Fixed local Home Assistant bridge. Token stays in owner's private config."""
import json,urllib.request,urllib.error,re,os,time
from pathlib import Path
CONFIG=Path.home()/'.config/mo-dot/home.json'
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None
OPENER=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
def save_token(token):
 token=token.strip()
 if len(token)<40 or any(c.isspace() for c in token):raise ValueError('رمز الوصول غير صالح')
 CONFIG.parent.mkdir(parents=True,exist_ok=True)
 fd=os.open(CONFIG,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
 with os.fdopen(fd,'w') as f:json.dump({'token':token},f)
 os.chmod(CONFIG,0o600)
def request(path,body=None):
 if not CONFIG.exists():raise RuntimeError('اربط Home Assistant من تبويب البيت أولاً')
 token=json.loads(CONFIG.read_text())['token'];data=None if body is None else json.dumps(body).encode()
 r=urllib.request.Request('http://127.0.0.1:8123/api/'+path,data=data,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
 try:
  with OPENER.open(r,timeout=8) as response:return json.load(response)
 except urllib.error.HTTPError as e:raise RuntimeError('تعذّر ربط البيت: '+str(e.code)) from None
 except urllib.error.URLError:raise RuntimeError('خادم البيت غير متاح') from None
def entities():
 states=request('states');return [{'entity_id':s['entity_id'],'name':s.get('attributes',{}).get('friendly_name',s['entity_id']),'state':s['state'],'rgb_color':s.get('attributes',{}).get('rgb_color'),'brightness':s.get('attributes',{}).get('brightness'),'volume_level':s.get('attributes',{}).get('volume_level'),'supported_features':s.get('attributes',{}).get('supported_features',0),'supported_color_modes':s.get('attributes',{}).get('supported_color_modes',[]),'is_hue_group':s.get('attributes',{}).get('is_hue_group',False),'members':s.get('attributes',{}).get('entity_id',[]) if s.get('attributes',{}).get('is_hue_group') else []} for s in states if s['entity_id'].split('.')[0] in ('light','switch','media_player') and not s['entity_id'].split('.',1)[1].startswith('mira_')]

def summary():
 """Count lights from a fresh HA snapshot; keep aggregate Hue groups separate."""
 listed=entities()
 lights=[x for x in listed if x['entity_id'].startswith('light.')]
 online=[x for x in lights if x['state'] not in ('unavailable','unknown')]
 leaves=[x for x in online if not (x.get('is_hue_group') and x.get('members'))]
 physical=[x for x in lights if not (x.get('is_hue_group') and x.get('members'))]
 return {'status':'ok','lights_total':len(physical),'lights_available':len(leaves),
         'light_groups_available':len(online)-len(leaves),'lights_on':sum(x['state']=='on' for x in leaves),
         'lights_unavailable':len(physical)-len(leaves),
         'devices_available':sum(x['state'] not in ('unavailable','unknown') for x in listed)}
COLORS={'red':(255,55,70),'pink':(255,90,175),'purple':(145,80,255),'blue':(55,110,255),'green':(35,210,130),'yellow':(255,210,65),'orange':(255,125,35)}
def control(entity_id,action,value=None,color=None):
 if not isinstance(entity_id,str) or not re.fullmatch(r'(light|switch|media_player)\.[a-z0-9_]+',entity_id):raise ValueError('اختر جهاز بيت مدعوماً فقط')
 known={x['entity_id']:x for x in entities()}
 if entity_id not in known:raise ValueError('الجهاز غير موجود في البيت')
 if known[entity_id]['state'] in ('unavailable','unknown'):raise ValueError('الجهاز غير متاح حالياً')
 domain=entity_id.split('.')[0];data={'entity_id':entity_id};features=known[entity_id].get('supported_features') or 0
 if domain=='media_player':
  required={'turn_on':128,'turn_off':256,'volume':4,'media_play':16384,'media_pause':1}.get(action)
  if required and not (features & required):raise ValueError('هذا التلفزيون لا يدعم هذا التحكم عبر Home Assistant')
 if action in ('turn_on','turn_off'):service=action
 elif action=='brightness' and domain=='light':
  if isinstance(value,bool) or not isinstance(value,(float,int)) or not 0<=value<=100:raise ValueError('brightness 0–100')
  service='turn_on';data['brightness_pct']=value
 elif action=='volume' and domain=='media_player':
  if isinstance(value,bool) or not isinstance(value,(float,int)) or not 0<=value<=100:raise ValueError('volume 0–100')
  service='volume_set';data['volume_level']=value/100
 elif action=='color' and domain=='light':
  if color not in COLORS:raise ValueError('اختر لوناً مدعوماً')
  modes=known[entity_id].get('supported_color_modes') or []
  if not any(m in modes for m in ('hs','xy','rgb','rgbw','rgbww')):raise ValueError('هذه الإضاءة لا تدعم الألوان')
  service='turn_on';data['rgb_color']=COLORS[color]
 elif action in ('media_play','media_pause') and domain=='media_player':service=action
 else:raise ValueError('الأمر غير مدعوم لهذا الجهاز')
 request('services/'+domain+'/'+service,data)
 state=None;verified=False
 for attempt in range(10):
  state=request('states/'+entity_id);attrs=state.get('attributes') or {}
  if action in ('turn_on','turn_off'):verified=state['state']==('on' if action=='turn_on' else 'off')
  elif action=='color':
   rgb=attrs.get('rgb_color');verified=state['state']=='on' and bool(rgb) and max(abs(a-b) for a,b in zip(rgb,COLORS[color]))<=35
  elif action=='brightness':verified=state['state']=='on' and attrs.get('brightness') is not None and abs(attrs['brightness']*100/255-value)<=8
  elif action=='volume':verified=attrs.get('volume_level') is not None and abs(attrs['volume_level']*100-value)<=8
  elif action=='media_play':verified=state['state']=='playing'
  elif action=='media_pause':verified=state['state']=='paused'
  if verified:break
  if attempt<9:time.sleep(.3)
 return {'status':'ok' if verified else 'pending','service_accepted':True,'verified':verified,'entity_id':entity_id,'observed_state':state['state']}


def control_all_lights(action):
 """Apply an explicit on/off request to each currently available HA light.

 Return per-device readback; an unavailable or unverified light never becomes a
 false global success. This deliberately excludes switches and media players.
 """
 if action not in ('turn_on','turn_off'):
  raise ValueError('تشغيل أو إطفاء الإضاءة فقط')
 # Hue groups aggregate their member lamps. Sending the same bulk action to a
 # group after its members can overwrite each lamp's individual color/level.
 lights=[item for item in entities() if item['entity_id'].startswith('light.') and not (item.get('is_hue_group') and item.get('members'))]
 if not lights:
  raise ValueError('لا توجد إضاءة مرتبطة بالبيت')
 results=[]
 for item in lights:
  entity_id=item['entity_id']
  if item['state'] in ('unavailable','unknown'):
   results.append({'entity_id':entity_id,'name':item['name'],'status':'unavailable'})
   continue
  try:
   outcome=control(entity_id,action)
   results.append({'entity_id':entity_id,'name':item['name'],'status':outcome['status'],'observed_state':outcome['observed_state']})
  except (RuntimeError,ValueError) as exc:
   results.append({'entity_id':entity_id,'name':item['name'],'status':'error','error':str(exc)})
 confirmed=sum(item['status']=='ok' for item in results)
 return {'status':'ok' if confirmed==len(results) else 'partial',
         'action':action,'confirmed':confirmed,'total':len(results),'results':results}
