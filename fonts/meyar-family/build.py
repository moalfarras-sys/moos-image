#!/usr/bin/env python3
"""Source build for Meyar's LGC/IPA and matching 700-cell mono companion."""
import argparse,hashlib,json,os,subprocess,sys,re,importlib.util,copy
from pathlib import Path
import glyphsLib
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools.otlLib.builder import buildStatTable
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.ttLib.tables import otTables
from design import latin_design,mono_grid,soften_glyph,kawkab_lexical_source,master_layers,fillet_path,compact_mono_marks,terminal_cells,arabic_terminal_cells

ROOT=Path(__file__).resolve().parent
STYLES={100:'Thin',200:'ExtraLight',300:'Light',400:'Regular',500:'Medium',600:'SemiBold',700:'Bold',800:'ExtraBold',900:'Black'}
EPOCH=3875904000 # 2026-10-27


def mono_metadata(font):
    if any(advance%700 for advance,lsb in font['hmtx'].metrics.values()):
        raise ValueError('A mono outline escaped the700-unit grid')
    font['post'].isFixedPitch=1;font['OS/2'].xAvgCharWidth=700
    font['OS/2'].panose.bProportion=9
    # The optical mono mark masters peak at1523UPM in Bold. Both script
    # owners use one natural cell, with64+UPM of upper room and no clipped ink.
    font['hhea'].ascent=1600;font['hhea'].descent=-768
    font['OS/2'].sTypoAscender=1600;font['OS/2'].sTypoDescender=-768
    font['OS/2'].usWinAscent=max(font['OS/2'].usWinAscent,1600)
    font['OS/2'].usWinDescent=max(font['OS/2'].usWinDescent,768)


def cff_from_static(font,target):
    """CFF from canonical static variable instantiation, with exact grid widths.

    Direct CFF instance interpolation rounds some source component metrics by
    one unit. Export the already-qualified quadratic outlines as exact cubic
    equivalents; keep the same cmap/layout/metrics, with no width coercion.
    """
    seen=set()
    def points_are_portable(obj):
        if id(obj) in seen:return
        seen.add(id(obj))
        if isinstance(obj,(otTables.Anchor,otTables.CaretValue)) and getattr(obj,'Format',None)==2:
            raise ValueError('TrueType point attachment requires reviewed CFF coordinates')
        if isinstance(obj,dict):children=obj.values()
        elif isinstance(obj,(list,tuple)):children=obj
        elif hasattr(obj,'__dict__'):children=obj.__dict__.values()
        else:return
        for value in children:points_are_portable(value)
    for tag in ['GPOS','GDEF']:
        if tag in font:points_are_portable(font[tag].table)
    gs=font.getGlyphSet();strings={}
    for name in font.getGlyphOrder():
        pen=T2CharStringPen(font['hmtx'][name][0],gs);gs[name].draw(pen);strings[name]=pen.getCharString()
    fb=FontBuilder(font['head'].unitsPerEm,isTTF=False);fb.font=copy.deepcopy(font);fb.font.sfntVersion='OTTO'
    for tag in ['glyf','loca','fpgm','prep','cvt ','gasp']:
        if tag in fb.font:del fb.font[tag]
    fb.setupCFF(font['name'].getDebugName(6),{'FullName':font['name'].getDebugName(4),
        'FamilyName':font['name'].getDebugName(16) or font['name'].getDebugName(1),
        'Notice':font['name'].getDebugName(0)},strings,{})
    fb.setupMaxp();fb.font.recalcTimestamp=False;fb.font.save(target)


def static_name(font,family,style):
    for n,value in {1:family,2:style,4:family+' '+style,6:family.replace(' ','')+'-'+style,16:family,17:style}.items():
        font['name'].setName(value,n,3,1,0x409)
        font['name'].setName(value,n,1,0,0)
    font['head'].macStyle=1 if style=='Bold' else 0
    font['OS/2'].fsSelection=(font['OS/2'].fsSelection&~(0x20|0x40))|(0x20 if style=='Bold' else 0x40)


def locked(folder,name):
    j=json.loads((ROOT/name).read_text())
    for n,r in j['files'].items():
        p=ROOT/folder/n
        if p.is_symlink() or not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=r['sha256']:raise ValueError('Upstream drift: '+n)
    return j


def compile_source(source,out,stem,family,otf=False,glyph_data=None):
    env=os.environ|{'SOURCE_DATE_EPOCH':'1793059200','PYTHONHASHSEED':'0'}
    cmd=[sys.executable,'-m','fontmake','-g',str(source),'-o','otf' if otf else 'variable',
         '--master-dir',str(out/'masters'),'--instance-dir',str(out/'instances'),'--no-production-names','--verbose','WARNING']
    if otf:cmd+=['-i','^'+re.escape(family)+' ('+'|'.join(STYLES.values())+')$','--output-dir',str(out/'cff')]
    else:cmd+=['--output-path',str(out/(stem+'[wdth,wght].ttf'))]
    data=glyph_data or ROOT/'upstream-lgc/sources/GlyphData.xml'
    if data.exists():cmd+=['--glyph-data',str(data)]
    subprocess.run(cmd,env=env,cwd=out,check=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('kind',choices=['sans','arabic','mono','mono-arabic']);p.add_argument('--output',type=Path,required=True);p.add_argument('--control',action='store_true');p.add_argument('--otf',action='store_true');a=p.parse_args()
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=True);(out/'source').mkdir(exist_ok=True)
    family={'sans':'Meyar Sans','arabic':'Meyar Arabic','mono':'Meyar Mono','mono-arabic':'Meyar Mono Arabic'}[a.kind]
    stem=family.replace(' ','');changes=[];glyph_data=None
    if a.kind=='arabic':
        spec=importlib.util.spec_from_file_location('meyar_arabic_base',ROOT.parent/'meyar-arabic/build.py')
        base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base);lock=base.checked_upstream()
        tmp=out/'source/ArabicBase.glyphs';changes+=base.prepare(tmp,a.control);f=glyphsLib.GSFont(tmp)
        glyph_data=ROOT.parent/'meyar-arabic/upstream/sources/GlyphData.xml'
        if not a.control:
            for name in ['alef-ar','alef-ar.fina','alef-ar.short','alef-ar.short.fina','lam-ar.init','lam-ar.medi','kafDotless-ar.init']:
                changes+=soften_glyph(f,name,minimum_y=300)
    elif a.kind=='mono-arabic':
        lock=locked('upstream-kawkab','upstream-kawkab-lock.json')
        text,lexical=kawkab_lexical_source((ROOT/'upstream-kawkab/src/Kawkab Mono.glyphs').read_text())
        tmp=out/'source/KawkabParsed.glyphs';tmp.write_text(text);f=glyphsLib.GSFont(tmp);changes+=lexical
        # Glyphs' modern token expander treats a literal dollar in a feature
        # label as a numeric token, even inside quotes. Use FEA string escapes
        # for precisely those legacy labels; their decoded text remains '$'.
        for prefix in f.featurePrefixes:
            lines=prefix.code.splitlines(keepends=True);count=0
            for i,line in enumerate(lines):
                if '[$]' not in line:continue
                match=re.search(r'\bname\s+(1|3)\s+',line)
                if not match:raise ValueError('Unreviewed dollar token in legacy feature')
                lines[i]=line.replace('[$]',r'[\24]' if match[1]=='1' else r'[\0024]');count+=1
            if count:prefix.code=''.join(lines);changes.append({'featurePrefix':prefix.name,'dollarLabelEscapes':count,'decodedLabelUnchanged':True})
        if not a.control:
            for name in ['dotabove-ar','dotbelow-ar','dotcenter-ar','twodotsverticalabove-ar','twodotsverticalbelow-ar','twodotshorizontalabove-ar','twodotshorizontalbelow-ar','threedotsdownabove-ar','threedotsdownbelow-ar','threedotsupabove-ar','threedotsupbelow-ar']:
                g=f.glyphs[name]
                if g is None:continue
                for l in master_layers(f,g):
                    paths=[]
                    for q in l.paths:
                        if len(q.nodes)!=4:raise ValueError('Unreviewed mono dot: '+name)
                        paths.append(fillet_path(q,list(range(4)),12))
                    if paths:l.paths=paths;changes.append({'glyph':name,'layer':l.layerId,'change':'soft-corner mono dot; original700 advance/anchors'})
            changes+=compact_mono_marks(f)
            changes+=arabic_terminal_cells(f)
    else:
        lock=locked('upstream-lgc','upstream-lgc-lock.json')
        source=ROOT/'upstream-lgc/sources'/('NotoSans.glyphspackage' if a.kind=='sans' else 'NotoSansMono.glyphspackage')
        f=glyphsLib.GSFont(source)
        if not a.control:changes+=latin_design(f)
        if a.kind=='mono':
            if not a.control:changes+=terminal_cells(f)
            changes+=mono_grid(f)
    f.familyName=family+(' Control' if a.control else '');f.versionMajor=0;f.versionMinor=300
    # These derivatives retain OFL1.1's embedding permission. The legacy
    # Kawkab source carried an Editable-only metadata flag; do not inherit it.
    f.customParameters['fsType']=[]
    if a.kind in ['mono','mono-arabic']:f.customParameters['isFixedPitch']=True
    f.copyright+='\nMeyar source modifications Copyright2026 MoOS project; SIL OFL1.1.'
    source=out/'source'/(stem+'.glyphs');f.save(source);(out/'source-changes.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2)+'\n')
    if a.kind=='mono-arabic':
        # Preserve the actual authored Light/Regular/Bold weight range.
        cmd=[sys.executable,'-m','fontmake','-g',str(source),'-o','ttf','-i','^'+f.familyName+' (Regular|Bold)$',
             '--output-dir',str(out/'static'),'--master-dir',str(out/'masters'),'--instance-dir',str(out/'instances'),'--no-production-names','--verbose','WARNING']
        subprocess.run(cmd,env=os.environ|{'SOURCE_DATE_EPOCH':'1793059200'},check=True,cwd=out)
        for style in ['Regular','Bold']:
            matches=list((out/'static').glob('*-'+style+'.ttf'));assert len(matches)==1,matches
            font=TTFont(matches[0],recalcTimestamp=False);static_name(font,f.familyName,style);mono_metadata(font)
            font['head'].created=font['head'].modified=EPOCH;font.save(out/(stem+'-'+style+'.ttf'))
            font.flavor='woff2';font.save(out/(stem+'-'+style+'.woff2'));font.flavor=None
        if a.otf:
            for style in ['Regular','Bold']:
                cff_from_static(TTFont(out/(stem+'-'+style+'.ttf'),recalcTimestamp=False),out/(stem+'-'+style+'.otf'))
    else:
        compile_source(source,out,stem,f.familyName,glyph_data=glyph_data)
        font=TTFont(out/(stem+'[wdth,wght].ttf'),recalcTimestamp=False);font=instantiateVariableFont(font,{'wdth':100},inplace=True)
        if a.kind=='arabic':
            font['hhea'].ascent=1536;font['OS/2'].sTypoAscender=1536;font['OS/2'].usWinAscent=max(font['OS/2'].usWinAscent,1536)
        if a.kind=='mono':mono_metadata(font)
        buildStatTable(font,[{'tag':'wght','name':'Weight','values':[{'value':w,'name':s,'flags':2 if w==400 else 0} for w,s in STYLES.items()]}])
        font.recalcTimestamp=False;font['head'].created=font['head'].modified=EPOCH;font.save(out/(stem+'[wght].ttf'));font.flavor='woff2';font.save(out/(stem+'[wght].woff2'));font.flavor=None
        for w,s in STYLES.items():
            static=instantiateVariableFont(font,{'wght':w},inplace=False,updateFontNames=True);static.recalcTimestamp=False;static['head'].created=static['head'].modified=EPOCH
            static.save(out/(stem+'-'+s+'.ttf'));static.flavor='woff2';static.save(out/(stem+'-'+s+'.woff2'))
        if a.otf:
            for style in STYLES.values():
                cff_from_static(TTFont(out/(stem+'-'+style+'.ttf'),recalcTimestamp=False),out/(stem+'-'+style+'.otf'))
    files={p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(out.iterdir()) if p.suffix in ['.ttf','.woff2','.otf']}
    (out/'manifest.json').write_text(json.dumps({'family':f.familyName,'version':'0.300','upstream':lock['repository'],'revision':lock['revision'],'license':'OFL-1.1','sourceChanges':len(changes),'glyphs':len(font.getGlyphOrder()),'unicode':len(font.getBestCmap()),'files':files},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'family':f.familyName,'sourceChanges':len(changes),'glyphs':len(font.getGlyphOrder()),'unicode':len(font.getBestCmap())}))


if __name__=='__main__':main()
