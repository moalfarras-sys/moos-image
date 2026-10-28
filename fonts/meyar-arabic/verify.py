#!/usr/bin/env python3
"""Independent regression checks against a build of the unmodified source."""
import argparse
import hashlib
import json
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.pens.boundsPen import BoundsPen
import uharfbuzz as hb

ROOT=Path(__file__).resolve().parent
WORDS='''مِعيار العربية الإعدادات النظام التطبيقات الملفات المظهر الشبكة الشاشة
مرحبًا محمد أحمد إبراهيم اللغة القراءة الكتابة تطوير واضح جميل مستقل
ببب تتت ثثث ججج ححح خخخ سسس ششش صصص ضضض ططط ظظظ ععع غغغ
ففف ققق ككك للل ممم ننن ههه ييي لا لأ لإ لآ بلا بلأ بلإ بلآ
بَ بُ بِ بً بٌ بٍ بْ بَّ بِّ أَ أَّ آَّ إِّ لَأ لأَ لإِ
پژوهش فارسی پاکستان اردو یک کاربری ی ک گ چ پ ٠١٢٣٤٥٦٧٨٩ ۰۱۲۳۴۵۶۷۸۹'''.split()
STYLES=['Thin','ExtraLight','Light','Regular','Medium','SemiBold','Bold','ExtraBold','Black']


def shape(path,text,language):
    font=TTFont(path);h=hb.Font(hb.Face(path.read_bytes()));h.scale=(1000,1000)
    b=hb.Buffer();b.add_str(text);b.guess_segment_properties();b.language=language;hb.shape(h,b)
    return [(font.getGlyphName(i.codepoint),q.x_advance,q.y_advance,q.x_offset,q.y_offset) for i,q in zip(b.glyph_infos,b.glyph_positions)]


def main():
    p=argparse.ArgumentParser();p.add_argument('modified',type=Path);p.add_argument('control',type=Path);p.add_argument('--output',type=Path);a=p.parse_args()
    rows=[];issues=[];changed=set();bearings=[];lines=[]
    for weight,style in enumerate(STYLES,1):
        fixed=a.modified/f'MeyarArabic-{style}.ttf';old=a.control/fixed.name
        f=TTFont(fixed);o=TTFont(old)
        assert f.getGlyphOrder()==o.getGlyphOrder(),'glyph-order regression'
        assert f.getBestCmap()==o.getBestCmap(),'coverage regression'
        assert all(f['hmtx'][n][0]==o['hmtx'][n][0] for n in f.getGlyphOrder()),'advance/spacing regression'
        bearings.extend({'weight':weight*100,'glyph':n,'upstream':o['hmtx'][n][1],'modified':f['hmtx'][n][1]}
            for n in f.getGlyphOrder() if f['hmtx'][n][1]!=o['hmtx'][n][1])
        assert f['OS/2'].usWeightClass==weight*100
        assert f['OS/2'].fsType==0
        for table in ('GSUB','GPOS','GDEF'):
            assert f.getTableData(table)==o.getTableData(table),table+' changed'
        for name in f.getGlyphOrder():
            if f['glyf'][name].compile(f['glyf'])!=o['glyf'][name].compile(o['glyf']):changed.add(name)
        for text in WORDS:
            for lang in ('ar','fa','ur'):
                got=shape(fixed,text,lang);expected=shape(old,text,lang)
                if got!=expected or any(n=='.notdef' for n,*_ in got):issues.append({'weight':weight*100,'text':text,'language':lang,'fixed':got,'control':expected})
        for text in ['أَّ','آَّ','بِّ','مِعْيَارٌ']:
            gs=f.getGlyphSet();lo=0;hi=0
            for n,xa,ya,x,y in shape(fixed,text,'ar'):
                pen=BoundsPen(gs);gs[n].draw(pen)
                if pen.bounds:lo=min(lo,pen.bounds[1]+y);hi=max(hi,pen.bounds[3]+y)
            fits=lo>=f['hhea'].descent and hi<=f['hhea'].ascent
            lines.append({'weight':weight*100,'text':text,'ink':[lo,hi],'line':[f['hhea'].descent,f['hhea'].ascent],'fits':fits})
            if not fits:issues.append({'weight':weight*100,'text':text,'error':'ink outside natural font line'})
        rows.append({'weight':weight*100,'glyphs':len(f.getGlyphOrder()),'unicode':len(f.getBestCmap()),'layoutTablesIdentical':True})
    assert changed,'No actual outline modifications'
    vf=TTFont(a.modified/'MeyarArabic[wght].ttf')
    assert len(vf['fvar'].axes)==1 and vf['fvar'].axes[0].axisTag=='wght'
    assert [vf['fvar'].axes[0].minValue,vf['fvar'].axes[0].defaultValue,vf['fvar'].axes[0].maxValue]==[100,400,900]
    result={'pass':not issues,'weights':rows,'shapingComparisons':len(STYLES)*len(WORDS)*3,
        'changedCompiledOutlines':sorted(changed),'inkBearingChanges':bearings,'markLineCases':lines,'issues':issues,
        'scope':'Arabic source derivative; layout compared against unmodified pinned upstream. Not signed OS delivery.'}
    if a.output:a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'pass':result['pass'],'shapingComparisons':result['shapingComparisons'],'changedOutlines':len(changed),'issues':len(issues)}))
    assert result['pass'],issues[:3]


if __name__=='__main__':main()
