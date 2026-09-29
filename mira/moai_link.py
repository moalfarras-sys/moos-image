"""Mira uses Mo AI's installed local executor; never a model-authored command."""
import json,os,urllib.request,urllib.error
# Per-user ports (60-moai-ports derives them from the uid; uid 1000 keeps 8080/8079).
GATEWAY_PORT=int(os.environ.get('MOAI_GATEWAY_PORT','8080'))
CONTROL_PORT=int(os.environ.get('MOAI_CONTROL_PORT','8079'))
ALLOWED={'get_system_status','set_volume','set_mute','set_brightness','show_windows','open_app','arrange_windows','switch_desktop','set_motion','set_glass_clarity','set_power_profile','open_settings','list_installed_apps','memory_status','disk_status','network_status','top_processes','list_failed_units','unit_status','read_journal','os_state','list_skills','read_skill'}
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None
OPENER=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
def request(path,body=None,port=None):
 port=port or CONTROL_PORT
 data=None if body is None else json.dumps(body).encode()
 r=urllib.request.Request(f'http://127.0.0.1:{port}{path}',data=data,headers={'X-Moai-Control':'1','Content-Type':'application/json'})
 try:
  with OPENER.open(r,timeout=30) as response:return json.load(response)
 except urllib.error.HTTPError as e:
  return {'status':'error','error':f'local_api_{e.code}'}
def execute(name,arguments):
 if name not in ALLOWED:raise ValueError('unsupported Mo AI tool')
 # Confirmation is never manufactured: executor remains the authority.
 return request('/tool/execute',{'name':name,'arguments':arguments,'confirmed':False})
def open_application(name):
 if not isinstance(name,str) or not 1<=len(name.strip())<=120:
  raise ValueError('اسم التطبيق غير صالح')
 from command_router import _installed_app,normalize
 query=normalize(name)
 if query in ('المتصفح','متصفح','browser','الانترنت','internet'):
  query='chrome'
 app_id,label=_installed_app(query)
 result=execute('open_app',{'app_id':app_id})
 return {**result,'app_id':app_id,'application':label}
def ask(text):
 from mira_memory import profile_text
 profile=profile_text().strip()
 system=('أنت Mo AI داخل ميرا على MoOS. أجب بالعربية بوضوح. '
         'استخدم أدوات الوكيل للتحقق من المشاريع والملفات إذا طلب المالك ذلك. '
         'لا تدّع نجاح أمر من دون نتيجة الأداة؛ الموافقات تبقى لدى Mo AI.')
 if profile:system+=' معرفة أضافها المالك: '+profile+'. المعرفة لا تمنح صلاحيات بحد ذاتها.'
 payload={'model':'cloud:openrouter/free','messages':[{'role':'system','content':system},
          {'role':'user','content':text}],'stream':False,'max_tokens':700,
          'moai':{'agent':True,'session':'mira-desktop-owner'}}
 call=urllib.request.Request(f'http://127.0.0.1:{GATEWAY_PORT}/v1/chat/completions',
      data=json.dumps(payload,ensure_ascii=False).encode(),headers={'Content-Type':'application/json'})
 try:
  with OPENER.open(call,timeout=190) as response:
   route=response.headers.get('X-MoAI-Agent')
   result=json.load(response)
 except (urllib.error.URLError,TimeoutError,ValueError) as exc:
  raise RuntimeError('وكيل Mo AI غير متاح الآن') from exc
 if 'choices' not in result:raise RuntimeError('تعذّر رد وكيل Mo AI')
 answer=result['choices'][0]['message']['content']
 if route!='hermes':
  return 'وكيل المشاريع غير متاح؛ هذا رد محادثة فقط دون أدوات. '+answer
 return answer
