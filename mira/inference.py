"""Private Responses adapter. No arbitrary tool or shell execution."""
import json,urllib.request,urllib.error
from pathlib import Path
CONFIG=Path.home()/'.config/mo-dot/inference.json'
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None
def request(path,body=None):
 c=json.loads(CONFIG.read_text())
 if c['base_url']!='https://api.synterolink.com/v1' or c['api_backend']!='responses':raise ValueError('Unexpected endpoint or API backend')
 req=urllib.request.Request(c['base_url']+path,data=json.dumps(body).encode() if body is not None else None,headers={'Authorization':'Bearer '+c['api_key'],'Content-Type':'application/json','User-Agent':'MoDot/1.0'})
 try:
  with urllib.request.build_opener(NoRedirect).open(req,timeout=75) as r:return json.load(r)
 except urllib.error.HTTPError as e:
  # Errors must never contain request headers or credential-bearing debug dumps.
  raise RuntimeError('Gateway HTTP '+str(e.code)) from None

def ask(text):
 if not isinstance(text,str) or not text.strip() or len(text)>6000:raise ValueError('Message must be 1–6000 characters')
 c=json.loads(CONFIG.read_text())
 d=request('/responses',{'model':c['model'],'input':[{'role':'system','content':'أنتِ ميرا، مساعدة المالك. أجيبي بلغة المالك بوضوح واختصار. لا تدّعي تنفيذ أي تحكم أو فعل على الكمبيوتر أو الجهاز؛ هذه محادثة نصية فقط.'},{'role':'user','content':text}],'max_output_tokens':300,'stream':False})
 parts=[p.get('text','') for item in d.get('output',[]) if item.get('type')=='message' for p in item.get('content',[]) if p.get('type')=='output_text']
 answer='\n'.join(parts).strip() or d.get('output_text','').strip()
 if not answer:raise RuntimeError('Gateway returned no text')
 return answer,{'model':d.get('model',c['model']),'status':d.get('status'),'usage':d.get('usage')}
if __name__=='__main__':
 try:
  models=request('/models');print('Catalog:',[x.get('id') for x in models.get('data',[])][:35])
 except Exception as e:print('Catalog check:',str(e))
 reply,metadata=ask('ما ناتج 17 ضرب 23؟ أجب بجملة عربية واحدة.');print('Reply:',reply);print('Metadata:',json.dumps(metadata,ensure_ascii=False))
