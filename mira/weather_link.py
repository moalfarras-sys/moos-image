"""Read current modeled weather for a named city from Open-Meteo; no device location lookup."""
import json
import re
import urllib.parse
import urllib.request

CONDITIONS={0:'صحو',1:'غائم جزئياً',2:'غائم جزئياً',3:'غائم',45:'ضباب',48:'ضباب',
            51:'رذاذ',53:'رذاذ',55:'رذاذ',61:'مطر',63:'مطر',65:'مطر غزير',
            71:'ثلج',73:'ثلج',75:'ثلج كثيف',80:'زخات مطر',81:'زخات مطر',82:'زخات غزيرة',
            95:'عواصف رعدية',96:'عواصف رعدية',99:'عواصف رعدية'}

def _json(url):
    request=urllib.request.Request(url,headers={'User-Agent':'Mira-Neural-OS/1.0'})
    with urllib.request.urlopen(request,timeout=8) as response:
        if response.url.split('/')[2] not in ('geocoding-api.open-meteo.com','api.open-meteo.com'):
            raise ValueError('Unexpected weather host')
        return json.load(response)

def current(city):
    if not isinstance(city,str) or not re.fullmatch(r'[\w\s\-،,.]{2,80}',city,re.UNICODE):
        raise ValueError('اذكر اسم مدينة واضحاً')
    city=city.strip()
    if not city:raise ValueError('اذكر اسم مدينة واضحاً')
    geo='https://geocoding-api.open-meteo.com/v1/search?'+urllib.parse.urlencode(
        {'name':city,'count':1,'language':'ar','format':'json'})
    found=_json(geo).get('results') or []
    if not found:raise ValueError('لم أجد هذه المدينة؛ اذكر المدينة والبلد')
    place=found[0]
    forecast='https://api.open-meteo.com/v1/forecast?'+urllib.parse.urlencode({
        'latitude':place['latitude'],'longitude':place['longitude'],
        'current':'temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m',
        'timezone':'auto','forecast_days':1})
    data=_json(forecast)
    observed=data.get('current') or {}
    if not isinstance(observed.get('temperature_2m'),(int,float)):
        raise RuntimeError('خدمة الطقس لم ترسل درجة حرارة حديثة')
    return {'status':'ok','city':place['name'],'country':place.get('country',''),
            'time':observed.get('time'),'temperature_c':observed['temperature_2m'],
            'humidity_percent':observed.get('relative_humidity_2m'),
            'wind_kmh':observed.get('wind_speed_10m'),
            'condition_ar':CONDITIONS.get(observed.get('weather_code'),'حالة غير محددة'),
            'source':'Open-Meteo','source_url':'https://open-meteo.com/en/docs'}
