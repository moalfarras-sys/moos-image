#!/usr/bin/env python3
"""Executed binary/shaping qualification. A skipped gvar glyph is a failure."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
import unicodedata as U
import uharfbuzz as hb
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from build import designs, MASTERS, WEIGHTS, name
from sources.arabic import LETTERS


def shape(file,text,weight=400,features=None):
    face=hb.Face(Path(file).read_bytes());font=hb.Font(face);font.set_variations({'wght':weight})
    b=hb.Buffer();b.add_str(text);b.guess_segment_properties();hb.shape(font,b,features or {})
    return [(font.glyph_to_string(i.codepoint),i.cluster,p.x_advance,p.y_advance,p.x_offset,p.y_offset) for i,p in zip(b.glyph_infos,b.glyph_positions)]


def verify(directory):
    failures=[];checks=[]
    def check(label,value):
        checks.append(label)
        if not value:failures.append(label)
    vf=TTFont(directory/'Meyar[wght].ttf');gs,cmap=designs();axis=vf['fvar'].axes
    check('one continuous weight axis',len(axis)==1 and (axis[0].axisTag,axis[0].minValue,axis[0].defaultValue,axis[0].maxValue)==('wght',100,400,900))
    check('nine named instances',{i.coordinates['wght'] for i in vf['fvar'].instances}==set(WEIGHTS))
    check('source cmap equals binary',vf.getBestCmap()==cmap)
    check('Latin1 and ExtendedA complete',all(cp in cmap for cp in range(0xA0,0x180)))
    check('Arabic, Persian and Western digits distinct',len({cmap[c] for c in list(range(48,58))+list(range(0x660,0x66A))+list(range(0x6F0,0x6FA))})==30)
    check('embedding unrestricted',vf['OS/2'].fsType==0)
    check('OS2 use typo metrics valid',vf['OS/2'].version>=4 and vf['OS/2'].fsSelection&0x80)
    required={'init','medi','fina','rlig','calt','ccmp'}
    check('Arabic GSUB features',required.issubset({r.FeatureTag for r in vf['GSUB'].table.FeatureList.FeatureRecord}))
    check('GPOS owners',{'curs','kern','mark','mkmk'}.issubset({r.FeatureTag for r in vf['GPOS'].table.FeatureList.FeatureRecord}))
    for cp,(_,_,joining) in LETTERS.items():
        if joining!='D':continue
        runs=shape(directory/'Meyar[wght].ttf',chr(cp)*3)
        check('joining '+hex(cp),[r[0] for r in runs]==[name(cp)+'.fina',name(cp)+'.medi',name(cp)+'.init'])
    for text in ['لا','لأ','لإ','لآ','بلا','بَلَا']:
        r=shape(directory/'Meyar[wght].ttf',text)
        check('required ligature '+text,any(x[0].startswith('lam_alef') for x in r))
    check('ZWNJ breaks joining',all('.medi' not in r[0] for r in shape(directory/'Meyar[wght].ttf','ب\u200cب')))
    check('ZWJ joins',any('.init' in r[0] for r in shape(directory/'Meyar[wght].ttf','ب\u200d')))
    for pre,decomp in [('أ','أ'),('إ','إ'),('آ','آ'),('é','é'),('Ü','Ü')]:
        check('canonical '+pre,shape(directory/'Meyar[wght].ttf',pre)==shape(directory/'Meyar[wght].ttf',decomp))
    a=shape(directory/'Meyar[wght].ttf','بَّ');b=shape(directory/'Meyar[wght].ttf','بَّ',features={'mkmk':False})
    check('mark stacking changes positioning',a!=b)
    check('marks have zero advance',all(vf['hmtx'][n][0]==0 for n,g in gs.items() if g.mark))
    check('kerning has effect',sum(x[2] for x in shape(directory/'Meyar[wght].ttf','AVATAR'))<sum(x[2] for x in shape(directory/'Meyar[wght].ttf','AVATAR',features={'kern':False})))
    check('contextual alternate executes',any(x[0]=='uni064A.fina.flow' for x in shape(directory/'Meyar[wght].ttf','سي')))
    masters=[TTFont(directory/'masters'/('Meyar-'+WEIGHTS[w]+'.ttf')) for w in MASTERS]
    variable=TTFont(directory/'Meyar[wght].ttf');sensitive=[]
    for n in variable.getGlyphOrder():
        topologies=[(list(f['glyf'][n].endPtsOfContours),list(f['glyf'][n].flags)) if f['glyf'][n].numberOfContours else ([],[]) for f in masters]
        check('master topology '+n,all(t==topologies[0] for t in topologies))
        coords=[list(f['glyf'][n].coordinates) if f['glyf'][n].numberOfContours else [] for f in masters]
        if any(c!=coords[0] for c in coords):
            sensitive.append(n);check('variation exists '+n,bool(variable['gvar'].variations[n]))
    # Intermediate locations exercise real interpolation, not only named masters.
    for w in (100,137,200,300,400,457,500,600,700,800,863,900):
        font=instantiateVariableFont(variable,{'wght':w},inplace=False)
        check('interpolation '+str(w),len(font.getGlyphOrder())==len(gs) and not any(g.isComposite() for g in font['glyf'].glyphs.values()))
        sample='مِعيار العربية فارسی اردو MoOS Straße Größe café 0123 ٠١٢٣ ۰۱۲۳ /home/ملفات'
        check('no missing glyphs '+str(w),all(r[0]!='.notdef' for r in shape(directory/'Meyar[wght].ttf',sample,w)))
    for style in WEIGHTS.values():
        for ext in ('ttf','otf','woff2'):
            f=TTFont(directory/f'Meyar-{style}.{ext}');check('roundtrip '+style+'.'+ext,f.getBestCmap()==cmap)
            check('shape '+style+'.'+ext,all(x[0]!='.notdef' for x in shape(directory/f'Meyar-{style}.{ext}','مِعيار Meyar ÄÖÜß لا')) if ext!='woff2' else True)
    # HarfBuzz reads SFNT, webfont transport is decompressed before shaping.
    f=TTFont(directory/'Meyar[wght].woff2');f.flavor=None;buf=io.BytesIO();f.save(buf);web=hb.Face(buf.getvalue())
    check('variable WOFF2 decode',web.glyph_count==len(gs))
    return {'checks':len(checks),'failures':failures,'glyphs':len(gs),'unicode':len(cmap),'varyingGlyphs':len(sensitive),'scope':'compiled fonts/HarfBuzz; not physical default or signed installation'}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('directory',type=Path);ap.add_argument('--receipt',type=Path);args=ap.parse_args()
    r=verify(args.directory);print(json.dumps(r,ensure_ascii=False,indent=2))
    if args.receipt:args.receipt.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
    sys.exit(bool(r['failures']))


if __name__=='__main__':main()
