#!/usr/bin/env python3
"""Execute coverage, shaping, mark-ink and fixed-cell controls on built fonts."""
import argparse,json,unicodedata as ud
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.pens.boundsPen import BoundsPen
import uharfbuzz as hb

FAMILIES={'sans':'MeyarSans','arabic':'MeyarArabic','mono':'MeyarMono','mono-arabic':'MeyarMonoArabic'}
STYLES={100:'Thin',200:'ExtraLight',300:'Light',400:'Regular',500:'Medium',600:'SemiBold',700:'Bold',800:'ExtraBold',900:'Black'}
TEXTS={
'sans':['Meyar AVATAR To Wa','ÄÖÜ äöü ß Straße Größe','Český Polski Łódź ąćęłńóśźż','İı Şş Ğğ Çç Türkiye','Æ Ø Å Þ Ð ð þ æ œ Œ','Tiếng Việt Ắ Ề ự Ỹ','Ελληνικά ΆΈ ΐ ΰ ᾱ','Русский Українська ї є ґ ѣ','a ɑ ɐ ɒ æ ɛ e ə ɘ ɜ ɝ','ŋ ɲ ɳ n ʃ ʒ ʂ ʐ θ ð ɸ β ɹ ɻ ʁ ʀ ʔ ʕ ħ ʜ ʡ','t͡ʃ kʷ r̥ n̩ ã ə́ ᵊ ᶑ'],
'arabic':['مِعيار العربية الإعدادات الملفات','ببب تتت ثثث ججج ححح خخخ','سسس ششش صصص ضضض ططط ظظظ','ععع غغغ ففف ققق ككك للل ممم ننن ههه ييي','لا لأ لإ لآ بلا بلأ بلإ بلآ','أَ أَّ آَّ إِّ بِّ مِعْيَارٌ الله','پژوهش فارسی پاکستان اردو'],
}


class Font:
    def __init__(self,p):
        self.path=p;self.tt=TTFont(p);self.hb=hb.Font(hb.Face(p.read_bytes()));self.hb.scale=(1000,1000);self.gs=self.tt.getGlyphSet()
    def shape(self,text,language=None):
        b=hb.Buffer();b.add_str(text);b.guess_segment_properties()
        if language:b.language=language
        hb.shape(self.hb,b)
        return [(self.tt.getGlyphName(i.codepoint),q.x_advance,q.y_advance,q.x_offset,q.y_offset) for i,q in zip(b.glyph_infos,b.glyph_positions)]
    def ink(self,text):
        lo=0;hi=0
        for n,xa,ya,x,y in self.shape(text):
            pen=BoundsPen(self.gs);self.gs[n].draw(pen)
            if pen.bounds:lo=min(lo,pen.bounds[1]+y);hi=max(hi,pen.bounds[3]+y)
        return lo,hi


def main():
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();rows=[];problems=[];comparisons=0;ink=[]
    for kind,stem in FAMILIES.items():
        weights=[400,700] if kind=='mono-arabic' else list(STYLES)
        for w in weights:
            style=STYLES[w];f=Font(a.root/kind/(stem+'-'+style+'.ttf'));old=Font(a.root/(kind+'-control')/(stem+'-'+style+'.ttf'))
            expected=old.tt.getBestCmap().copy()
            if kind=='mono-arabic':expected[0xfdf2]='allah-ar.cell'
            assert f.tt.getBestCmap()==expected,(kind,w,'coverage drift')
            expected_order=old.tt.getGlyphOrder()+(['allah-ar.cell'] if kind=='mono-arabic' else [])
            assert f.tt.getGlyphOrder()==expected_order,(kind,w,'glyph order drift')
            policy=json.loads((Path(__file__).parent/'terminal-cells.json').read_text())
            allowed={x['glyph']:x['terminalCells']*700 for x in policy['adjustments']} if kind=='mono' else {}
            if kind=='mono-arabic':
                allowed={x['glyph']:x['terminalCells']*700 for x in policy['arabic']['adjustments'] if x['glyph']!='allah-ar'}
                allowed['allah-ar.cell']=700
            assert all((n in allowed and x[0]==allowed[n]) or (n in old.tt['hmtx'].metrics and x[0]==old.tt['hmtx'][n][0])
                for n,x in f.tt['hmtx'].metrics.items()),(kind,w,'unreviewed advance drift')
            assert f.tt['OS/2'].usWeightClass==w,(kind,w,'incorrect weight')
            assert f.tt['OS/2'].fsType==0
            if kind in ['mono','mono-arabic']:
                assert f.tt['post'].isFixedPitch==1
                assert all(advance%700==0 for advance,lsb in f.tt['hmtx'].metrics.values())
            if kind in ['mono','mono-arabic']:
                widths=policy['positiveWidths'] if kind=='mono' else policy['arabic']['positiveWidths']
                for cp,cells in widths.items():
                    n=f.tt.getBestCmap()[int(cp)]
                    assert f.tt['hmtx'][n][0]==cells*700,(kind,w,cp,'native terminal width mismatch')
                    shaped=f.shape(chr(int(cp)))
                    assert ud.category(chr(int(cp)))=='Cf' or sum(q[1] for q in shaped)==cells*700,(kind,w,cp,'native shaped cell mismatch')
            if kind in ['sans','mono']:
                c=f.tt.getBestCmap()
                for low,high in [(0x250,0x2b0),(0x1d00,0x1dc0),(0x300,0x370),(0xa0,0x180)]:
                    assert all(cp in c for cp in range(low,high) if ud.category(chr(cp))[0] in 'LM'),(kind,w,'missing Latin/phonetic letter')
            sample=TEXTS['arabic'] if kind in ['arabic','mono-arabic'] else TEXTS['sans']
            for text in sample:
                now=f.shape(text);before=old.shape(text);comparisons+=1
                assert not any(n=='.notdef' for n,*_ in now),(kind,w,text,'missing glyph')
                if kind=='mono-arabic':
                    # Optical marks deliberately change offsets; language and
                    # fixed-cell advances must retain their real native control.
                    assert [(n,x,y) for n,x,y,*_ in now]==[(n,x,y) for n,x,y,*_ in before],(kind,w,text,'joining/advance drift')
                else:assert now==before,(kind,w,text,'unintended layout drift')
            if kind in ['arabic','mono-arabic']:
                for text in ['أَّ','آَّ','بِّ','مِعْيَارٌ','الله']:
                    lo,hi=f.ink(text);fits=lo>=f.tt['hhea'].descent and hi<=f.tt['hhea'].ascent
                    ink.append({'family':kind,'weight':w,'text':text,'ink':[lo,hi],'line':[f.tt['hhea'].descent,f.tt['hhea'].ascent],'fits':fits})
                    if not fits:problems.append(ink[-1])
            for ext in ['otf','woff2']:
                path=a.root/kind/(stem+'-'+style+'.'+ext)
                if not path.exists():continue
                parsed=TTFont(path)
                assert parsed.getBestCmap()==f.tt.getBestCmap(),(kind,w,ext,'export coverage drift')
                assert all(parsed['hmtx'][n][0]==f.tt['hmtx'][n][0] for n in f.tt.getGlyphOrder()),(kind,w,ext,'export advance drift')
            rows.append({'family':kind,'weight':w,'glyphs':len(f.tt.getGlyphOrder()),'unicode':len(f.tt.getBestCmap())})
    result={'pass':not problems,'shapingComparisons':comparisons,'families':rows,'inkCases':ink,'problems':problems,'scope':'source fonts and actual native upstream controls; no installed/default/signed acceptance implied'}
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'pass':not problems,'shapingComparisons':comparisons,'fontInstances':len(rows),'inkCases':len(ink),'problems':problems},ensure_ascii=False));assert not problems


if __name__=='__main__':main()
