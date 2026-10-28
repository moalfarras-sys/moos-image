#!/usr/bin/env python3
"""Build original Meyar sources; no existing font is read as design input.

Static CFF/TrueType/web exports and a compatible 100–900 gvar family share the
same authored construction. Four optical masters define the stem progression;
these are outlines at source, never a raster/faux-bold filter on a binary font.
"""
import argparse
import hashlib
import json
import os
import logging
import io
from pathlib import Path
import unicodedata as U

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.designspaceLib import DesignSpaceDocument, AxisDescriptor, SourceDescriptor, InstanceDescriptor
from fontTools.varLib import build as build_variable
from fontTools.otlLib.builder import buildStatTable
from fontTools.ttLib import TTFont, newTable
from sources.geometry import Glyph, line, path as P, ellipse as E, combine
from sources import arabic, latin

ROOT=Path(__file__).resolve().parent
WEIGHTS={100:'Thin',200:'ExtraLight',300:'Light',400:'Regular',500:'Medium',600:'SemiBold',700:'Bold',800:'ExtraBold',900:'Black'}
MASTERS={100:28,400:68,700:112,900:142}
EPOCH=3875860800  # 2026-10-26 12:00 UTC in the OpenType 1904 epoch
VERSION='0.100'


def bounds(g,stem=68):
    pts=[pt for contour in g.contours(stem) for pt in contour]
    return (min(x for x,y in pts),min(y for x,y in pts),max(x for x,y in pts),max(y for x,y in pts)) if pts else (0,0,0,0)


def anchors(g,stem=68):
    xmin,ymin,xmax,ymax=bounds(g,stem)
    x=g.top[0] if g.top else g.width//2
    bx=g.bottom[0] if g.bottom else g.width//2
    # Arabic vowel marks follow their local letter body, not a distant tail.
    if any(g.joins):
        local=[y for p in g.contours(stem) for px,y in p if abs(px-bx)<=85]
        if local:ymin=min(local)
    return (x,ymax+30),(bx,ymin-30)


def name(cp):
    if 48<=cp<=57:return ['zero','one','two','three','four','five','six','seven','eight','nine'][cp-48]
    return f'uni{cp:04X}' if cp>126 or cp<33 else chr(cp) if chr(cp).isalnum() else f'uni{cp:04X}'


def designs():
    glyphs={'.notdef':Glyph(650).add(line(85,-100,85,780,565,780,565,-100,85,-100)).add(line(150,0,500,680)),'.null':Glyph(0)}
    cmap={}
    def put(cp,g):
        if g is not None:glyphs[name(cp)]=g;cmap[cp]=name(cp)
    for cp in range(32,127):
        c=chr(cp);put(cp,latin.latin(c) or (latin.digit(int(c)) if c.isdigit() else latin.symbol(c)))
    for cp in list(range(0x300,0x337))+list(range(0x64B,0x657))+[0x670]:put(cp,latin.accent(cp) if cp<0x400 else arabic.mark(cp))
    for cp,(_,_,joining) in arabic.LETTERS.items():
        put(cp,arabic.letter(cp))
        for form in (('fina','init','medi') if joining=='D' else ('fina',) if joining=='R' else ()):
            glyphs[name(cp)+'.'+form]=arabic.letter(cp,form)
    for variant in (0x622,0x623,0x625,0x627):
        for form in ('isol','fina'):glyphs[f'lam_alef{variant:04X}.{form}']=arabic.lamalef(variant,form=='fina')
    # The final yeh after the seen family gets a lower, more spacious return.
    flow=arabic.letter(0x64A,'fina')
    flow.strokes[0]=(P(('M',535,300),('C',560,130,420,100,280,90),('C',85,80,45,-65,210,-80),('Q',375,-100,475,-5)),1,False)
    glyphs['uni064A.fina.flow']=flow
    for i in range(10):put(0x660+i,arabic.digit(i));put(0x6F0+i,arabic.digit(i,True))
    specials='\u00a0\u00ad£€¥$©®°µ×÷·«»؟،؛٪٬٫'+'‘’‚“”„‹›–—‐‑‒…•−±≠≤≥≈∞√∑∏∫π◌←→↑↓↔↕✓✕'
    specials+=''.join(chr(x) for x in list(range(0x2000,0x2010))+list(range(0x202A,0x202F))+[0x202F]+list(range(0x2066,0x206A))+[0xFEFF])
    for c in specials:put(ord(c),latin.symbol(c))
    # Non-decomposing European letters have their own constructions.
    for c,upper in [('Æ',True),('æ',False)]:
        a=latin.latin('A' if upper else 'a');e=latin.latin('E' if upper else 'e').shifted(450 if upper else 420,0)
        g=combine(a,e);g.width=1040 if upper else 975;put(ord(c),g)
    for c,base,dx in [('Œ','O',470),('œ','o',400)]:
        g=combine(latin.latin(base),latin.latin('E' if c=='Œ' else 'e'),dx);g.width=1050 if c=='Œ' else 940;put(ord(c),g)
    for c,base in [('Ø','O'),('ø','o'),('Đ','D'),('đ','d'),('Ł','L'),('ł','l'),('Ħ','H'),('ħ','h')]:
        g=latin.latin(base);g.add(line(80,90,g.width-70,620 if c.isupper() else 460) if c in 'ØøŁł' else line(40,370,g.width-65,370),.8);put(ord(c),g)
    put(0xDF,Glyph(620,top=(320,855),bottom=(310,-140)).add(P(('M',100,0),('L',100,500),('C',95,825,510,815,470,580),('Q',460,465,335,405),('C',650,300,585,-75,290,35))))
    put(0x1E9E,Glyph(700,top=(350,845),bottom=(350,-140)).add(P(('M',100,0),('L',100,710),('L',525,710),('L',340,395),('C',680,320,655,-45,310,20))))
    put(0x131, Glyph(255,top=(128,620),bottom=(128,-130)).add(line(128,0,128,505)))
    put(0x237, Glyph(270,top=(165,620),bottom=(165,-300)).add(P(('M',165,505),('L',165,-90),('Q',165,-250,15,-210))))
    put(0x17F,latin.latin('f'))
    put(0x2206,Glyph(660).add(line(80,0,325,710,580,0,80,0)))
    put(0xF0,latin.latin('o').add(P(('M',175,730),('C',410,655,535,400,510,265))).add(line(145,525,400,735),.7))
    put(0xD0,latin.latin('D').add(line(30,350,320,350),.8))
    for cp,b in [(0xDE,'P'),(0xFE,'p')]:
        g=latin.latin(b)
        # Thorn's bowl sits below its ascender, distinct from the Latin P.
        if cp==0xDE:g=Glyph(630,top=(300,840),bottom=(300,-160)).add(line(100,0,100,710)).add(P(('M',100,560),('L',335,560),('C',645,560,645,185,335,185),('L',100,185)))
        else:g=latin.latin('b').add(line(95,0,95,-225))
        put(cp,g)
    put(0x14A,latin.latin('N').add(P(('M',615,0),('Q',615,-240,420,-200))))
    put(0x14B,latin.latin('n').add(P(('M',495,0),('Q',495,-240,310,-200))))
    for cp,b in [(0x166,'T'),(0x167,'t')]:put(cp,latin.latin(b).add(line(80,350,latin.latin(b).width-50,350),.8))
    put(0x138,Glyph(540,top=(270,620),bottom=(270,-160)).add(line(95,0,95,505)).add(line(445,505,100,190)).add(line(275,350,465,0)))
    for cp,b in [(0x13F,'L'),(0x140,'l')]:put(cp,latin.latin(b).dot(latin.latin(b).width-50,350,.65))
    g=combine(latin.symbol("'"),latin.latin('n'),170);g.width=760;put(0x149,g)
    for cp,a,b in [(0x132,'I','J'),(0x133,'i','j')]:
        g=combine(latin.latin(a),latin.latin(b),latin.latin(a).width);g.width=latin.latin(a).width+latin.latin(b).width;put(cp,g)
    for cp,c in [(0xA1,'!'),(0xBF,'?')]:
        g=latin.symbol(c);g.strokes=[([(g.width-x,710-y) for x,y in p],s,cl) for p,s,cl in g.strokes];g.dots=[(g.width-x,710-y,s) for x,y,s in g.dots];put(cp,g)
    put(0xA2,latin.latin('c').add(line(260,-90,260,640),.8))
    put(0xA4,Glyph(650).add(E(325,350,175,175),.9,True).add(line(90,115,200,225),.8).add(line(450,475,560,585),.8).add(line(90,585,200,475),.8).add(line(450,225,560,115),.8))
    put(0xA6,Glyph(260).add(line(130,-145,130,260)).add(line(130,420,130,800)))
    put(0xAC,Glyph(600).add(line(90,400,510,400,510,150)))
    put(0xB6,Glyph(660).add(line(565,710,565,-120)).add(line(395,710,395,-120)).add(P(('M',395,710),('C',-25,760,-25,255,395,310)),1.3))
    put(0xA7,Glyph(590).add(P(('M',475,670),('C',275,840,25,635,165,470),('L',395,260),('C',570,85,320,-120,120,35))).add(P(('M',165,470),('C',-10,235,225,130,395,260),('C',575,485,350,610,165,470))))
    for cp,base in [(0xA8,0x308),(0xAF,0x304),(0xB4,0x301),(0xB8,0x327)]:
        g=latin.accent(base).shifted(170,610 if cp!=0xB8 else 0);g.width=340;g.mark=None;put(cp,g)
    for cp,c in [(0xAA,'a'),(0xBA,'o')]:
        g=latin.latin(c).scaled(.62,30,370);g.width+=60;put(cp,g)
    for cp,n in [(0xB9,1),(0xB2,2),(0xB3,3)]:
        g=latin.digit(n).scaled(.6,25,360);g.width+=50;put(cp,g)
    for cp,hi,lo in [(0xBC,1,4),(0xBD,1,2),(0xBE,3,4)]:
        g=combine(latin.digit(hi).scaled(.5,15,355),latin.digit(lo).scaled(.5),445)
        g.width=760;g.add(line(220,0,530,710),.65);put(cp,g)
    # Canonical European accents, not arbitrary aliases of unimplemented letters.
    # All precomposed shapes are flattened from our own base and mark geometry.
    for cp in list(range(0xA0,0x250))+list(range(0x1E00,0x1F00))+[0x212B]:
        if cp in cmap:continue
        seq=[ord(c) for c in U.normalize('NFD',chr(cp))]
        if len(seq)<2 or seq[0] not in cmap or not all(s in cmap and glyphs[cmap[s]].mark for s in seq[1:]):continue
        base=glyphs[cmap[0x131 if seq[0]==ord('i') and any(glyphs[cmap[m]].mark=='top' for m in seq[1:]) else 0x237 if seq[0]==ord('j') and any(glyphs[cmap[m]].mark=='top' for m in seq[1:]) else seq[0]]]
        g=Glyph(base.width,list(base.strokes),list(base.dots),base.top,base.bottom)
        for m in seq[1:]:
            mk=glyphs[cmap[m]];top,bottom=anchors(g)
            anchor=top if mk.mark=='top' else bottom
            mb=bounds(mk);origin=mb[1]-10 if mk.mark=='top' else mb[3]+10
            g=combine(g,mk,anchor[0],anchor[1]-origin)
        put(cp,g)
    # Unicode presentation characters are compatibility inputs only; ordinary
    # text uses base Arabic Unicode + GSUB, not presentation-form encoding.
    for cp in range(0xFB50,0xFF00):
        d=U.decomposition(chr(cp)).split()
        if len(d)<2:continue
        form=d[0][1:-1];seq=[int(x,16) for x in d[1:]]
        f={'isolated':'isol','final':'fina','initial':'init','medial':'medi'}.get(form)
        if not f:continue
        target=None
        if len(seq)==1 and seq[0] in arabic.LETTERS:
            target=name(seq[0])+('' if f=='isol' else '.'+f)
        elif len(seq)==2 and seq[0]==0x644 and seq[1] in (0x622,0x623,0x625,0x627):target=f'lam_alef{seq[1]:04X}.{f}'
        if target in glyphs:cmap[cp]=target
    return glyphs,cmap


def features(gs,stem=68):
    out=['languagesystem DFLT dflt;','languagesystem latn dflt;','languagesystem latn DEU;','languagesystem arab dflt;','languagesystem arab ARA;','languagesystem arab FAR;','languagesystem arab URD;']
    marks=[n for n,g in gs.items() if g.mark]
    ligatures=[n for n in gs if n.startswith('lam_alef')]
    bases=[n for n,g in gs.items() if not g.mark and n not in ligatures]
    out += ['@Bases = ['+' '.join(bases)+'];','@Ligatures = ['+' '.join(ligatures)+'];','@Marks = ['+' '.join(marks)+'];','table GDEF { GlyphClassDef @Bases, @Ligatures, @Marks, []; } GDEF;']
    for m in marks:
        g=gs[m];bb=bounds(g,stem);y=bb[1]-10 if g.mark=='top' else bb[3]+10
        out.append(f'markClass {m} <anchor 0 {y}> @MC_{g.mark};')
    # Canonical Arabic compositions precede joining; both encodings match.
    out+=['feature ccmp {']
    latin_top=' '.join(n for n,g in gs.items() if g.mark=='top' and n.startswith('uni03'))
    out.append(f"sub i' [{latin_top}] by uni0131;")
    out.append(f"sub j' [{latin_top}] by uni0237;")
    for a,m,b in [(0x627,0x653,0x622),(0x627,0x654,0x623),(0x627,0x655,0x625),(0x648,0x654,0x624),(0x64A,0x654,0x626)]:out.append(f'sub {name(a)} {name(m)} by {name(b)};')
    out+=['} ccmp;']
    for form in ('init','medi','fina'):
        out.append(f'feature {form} {{ script arab; language dflt;')
        for cp in arabic.LETTERS:
            if name(cp)+'.'+form in gs:out.append(f'sub {name(cp)} by {name(cp)}.{form};')
        out.append('} '+form+';')
    out+=['feature rlig { script arab; language dflt; lookupflag IgnoreMarks;']
    for cp in (0x622,0x623,0x625,0x627):
        for lam,form in [('init','isol'),('medi','fina')]:out.append(f'sub {name(0x644)}.{lam} {name(cp)}.fina by lam_alef{cp:04X}.{form};')
    out+=['} rlig;','feature calt { script arab; language dflt; lookupflag IgnoreMarks;',
          "sub [uni0633.init uni0633.medi uni0634.init uni0634.medi] uni064A.fina' by uni064A.fina.flow;",'} calt;',
          'feature curs { script arab; language dflt; lookupflag RightToLeft IgnoreMarks;']
    for n,g in gs.items():
        if not any(g.joins):continue
        entry=f'<anchor {g.width} 110>' if g.joins[0] else '<anchor NULL>'
        exit='<anchor 0 110>' if g.joins[1] else '<anchor NULL>'
        out.append(f'pos cursive {n} {entry} {exit};')
    out+=['} curs;','feature mark {']
    for n,g in gs.items():
        if g.mark or n in ligatures or not g.strokes and not g.dots:continue
        top,bot=anchors(g,stem)
        out.append(f'pos base {n} <anchor {top[0]} {top[1]}> mark @MC_top <anchor {bot[0]} {bot[1]}> mark @MC_bottom;')
    for n in ligatures:
        y=bounds(gs[n],stem)[3]+35
        out.append(f'pos ligature {n} <anchor 410 {y}> mark @MC_top <anchor 410 -90> mark @MC_bottom ligComponent <anchor 100 {y}> mark @MC_top <anchor 100 -90> mark @MC_bottom;')
    out+=['} mark;','feature mkmk {']
    for n in marks:
        m=gs[n].mark;bb=bounds(gs[n],stem);y=bb[3]+30 if m=='top' else bb[1]-30
        out.append(f'pos mark {n} <anchor 0 {y}> mark @MC_{m};')
    out+=['} mkmk;','feature kern { script latn; language dflt;']
    for a,b,k in [('A','V',-65),('A','W',-45),('A','Y',-60),('V','A',-65),('W','A',-45),('Y','A',-60),('T','a',-65),('T','o',-70),('T','e',-65),('T','y',-45),('V','a',-40),('V','o',-40),('W','a',-30),('Y','o',-70),('Y','e',-65),('F','o',-30),('L','T',-35),('P','a',-25)]:out.append(f'pos {a} {b} {k};')
    out+=['} kern;','feature tnum {']
    for n in range(10):out.append(f'sub {name(48+n)} by {name(48+n)};')  # default figures are already tabular
    out+=['} tnum;']
    return '\n'.join(out)+'\n'


def build_font(gs,cmap,stem,weight,style,ttf=True):
    fb=FontBuilder(1000,isTTF=ttf);order=list(gs);fb.setupGlyphOrder(order);fb.setupCharacterMap(cmap)
    outlines={};metrics={}
    for n,g in gs.items():
        contours=g.contours(stem)
        # Keep terminal points even when rounding makes two neighbours coincide
        # at one master. Removing one only at Black silently freezes that glyph
        # in varLib instead of producing a continuous weight interpolation.
        pen=TTGlyphPen(None,outputImpliedClosingLine=True) if ttf else T2CharStringPen(g.width,None)
        for p in contours:
            if len(p)<3:continue
            pen.moveTo(p[0])
            for pt in p[1:]:pen.lineTo(pt)
            pen.closePath()
        outlines[n]=pen.glyph() if ttf else pen.getCharString()
        metrics[n]=(g.width,min([x for p in contours for x,y in p],default=0))
        if ttf and contours:outlines[n].flags[0]|=0x40  # OVERLAP_SIMPLE for compatible masters
    if ttf:fb.setupGlyf(outlines)
    else:fb.setupCFF('Meyar-'+style,{'FullName':'Meyar '+style,'FamilyName':'Meyar','Weight':style,'version':VERSION,'Notice':'Copyright 2026 The MoOS Project. Original outlines. Licensed under SIL OFL 1.1.'},outlines,{})
    fb.setupHorizontalMetrics(metrics);fb.setupHorizontalHeader(ascent=1320,descent=-420,lineGap=0)
    fb.setupNameTable({'familyName':'Meyar','styleName':style,'uniqueFontIdentifier':f'MoOS:Meyar:{VERSION}:{style}',
        'fullName':'Meyar '+style,'psName':'Meyar-'+style,'version':'Version '+VERSION,
        'copyright':'Copyright 2026 The MoOS Project. Original Meyar design.',
        'designer':'MoOS Project','manufacturer':'MoOS Project',
        'description':'Original Arabic–Latin interface typeface. Engineering development build; see source qualification status.',
        'licenseDescription':'This Font Software is licensed under the SIL Open Font License, Version 1.1.',
        'licenseInfoURL':'https://openfontlicense.org','typographicFamily':'Meyar','typographicSubfamily':style})
    fb.setupOS2(version=4,sTypoAscender=1320,sTypoDescender=-420,sTypoLineGap=0,usWinAscent=1480,usWinDescent=520,
        usWeightClass=weight,usWidthClass=5,fsType=0,fsSelection=(0x80|0x20 if weight==700 else 0x80|0x40 if weight==400 else 0x80),
        sxHeight=515,sCapHeight=710,achVendID='MoOS')
    fb.setupPost();fb.setupMaxp();fb.font['head'].created=EPOCH;fb.font['head'].modified=EPOCH;fb.font['head'].fontRevision=float(VERSION)
    fb.font['head'].macStyle=1 if weight==700 else 0
    # Arabic family name in Unicode, separate from stable Latin technical ID.
    fb.font['name'].setName('مِعيار',16,3,1,0x401)
    fb.font['name'].setName('مِعيار',1,3,1,0x401)
    addOpenTypeFeaturesFromString(fb.font,features(gs,stem))
    if ttf:
        fb.font['gasp']=newTable('gasp');fb.font['gasp'].gaspRange={65535:15}
    fb.font.recalcTimestamp=False
    return fb.font


def export_ufo(gs,cmap,stem,path):
    import ufoLib2
    f=ufoLib2.Font();f.info.familyName='Meyar';f.info.styleName='Regular' if stem==68 else 'Bold';f.info.unitsPerEm=1000
    f.info.ascender=1320;f.info.descender=-420;f.info.xHeight=515;f.info.capHeight=710
    reverse={}
    for cp,n in cmap.items():reverse.setdefault(n,[]).append(cp)
    for n,g in gs.items():
        u=f.newGlyph(n);u.width=g.width;u.unicodes=reverse.get(n,[]);pen=u.getPen()
        for pts in g.contours(stem):
            pen.moveTo(pts[0])
            for pt in pts[1:]:pen.lineTo(pt)
            pen.closePath()
        if g.mark:
            bb=bounds(g,stem);y=bb[1]-10 if g.mark=='top' else bb[3]+10
            u.appendAnchor({'name':'_'+g.mark,'x':0,'y':y})
        else:
            top,bottom=anchors(g,stem)
            for kind,anchor in [('top',top),('bottom',bottom)]:
                u.appendAnchor({'name':kind,'x':anchor[0],'y':anchor[1]})
    f.features.text=features(gs,stem);f.save(path,overwrite=True)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=ROOT/'dist');ap.add_argument('--ufo',action='store_true');args=ap.parse_args()
    dest=args.output;dest.mkdir(parents=True,exist_ok=True);(dest/'masters').mkdir(exist_ok=True)
    gs,cmap=designs();ds=DesignSpaceDocument();ax=AxisDescriptor();ax.name='Weight';ax.tag='wght';ax.minimum=100;ax.default=400;ax.maximum=900;ds.addAxis(ax)
    for w,stem in MASTERS.items():
        style=WEIGHTS[w];f=build_font(gs,cmap,stem,w,style);p=dest/'masters'/f'Meyar-{style}.ttf';f.save(p,reorderTables=True)
        src=SourceDescriptor();src.path=str(p.resolve());src.name=style;src.familyName='Meyar';src.styleName=style;src.location={'Weight':w}
        if w==400:src.copyInfo=True;src.copyLib=True;src.copyFeatures=True
        ds.addSource(src)
    for w,style in WEIGHTS.items():
        i=InstanceDescriptor();i.familyName='Meyar';i.styleName=style;i.location={'Weight':w};ds.addInstance(i)
    ds.write(dest/'Meyar.designspace')
    class VariationRefusal(logging.Handler):
        def emit(self,record):
            if 'incompatible masters' in record.getMessage():
                raise ValueError('Non-interpolating glyph: '+record.getMessage())
    refusal=VariationRefusal();logging.getLogger('fontTools.varLib').addHandler(refusal)
    try:vf,_,_=build_variable(ds)
    finally:logging.getLogger('fontTools.varLib').removeHandler(refusal)
    buildStatTable(vf,[{'tag':'wght','name':'Weight','values':[{'value':w,'name':s,'flags':2 if w==400 else 0} for w,s in WEIGHTS.items()]}])
    vf['head'].created=EPOCH;vf['head'].modified=EPOCH;vf.recalcTimestamp=False
    vf.save(dest/'Meyar[wght].ttf');vf.flavor='woff2';vf.save(dest/'Meyar[wght].woff2');vf.flavor=None
    # Read the serialized GDEF 1.3 back before instancing. varLib's in-memory
    # upgrade adds VarStore but fontTools4.67 does not materialize the optional
    # MarkGlyphSetsDef field inherited from1.2; its instancer then raises.
    # The actual SFNT decoder fills that absent optional offset as None.
    vf=TTFont(dest/'Meyar[wght].ttf',recalcTimestamp=False)
    from fontTools.varLib.instancer import instantiateVariableFont
    for w,style in WEIGHTS.items():
        ttf=instantiateVariableFont(vf,{'wght':w},inplace=False,updateFontNames=True)
        ttf['head'].created=EPOCH;ttf['head'].modified=EPOCH;ttf.recalcTimestamp=False;ttf.save(dest/f'Meyar-{style}.ttf')
        ttf.flavor='woff2';ttf.save(dest/f'Meyar-{style}.woff2')
        # Source stem interpolation matches the four-master progression exactly.
        lo=max(k for k in MASTERS if k<=w);hi=min(k for k in MASTERS if k>=w)
        stem=MASTERS[lo] if lo==hi else MASTERS[lo]+(MASTERS[hi]-MASTERS[lo])*(w-lo)/(hi-lo)
        otf=build_font(gs,cmap,stem,w,style,False);otf.save(dest/f'Meyar-{style}.otf')
    (dest/'Meyar.fea').write_text(features(gs))
    (dest/'coverage.json').write_text(json.dumps({'version':VERSION,'glyphs':len(gs),'unicodeCount':len(cmap),'codepoints':[f'{cp:04X}' for cp in sorted(cmap)],'weights':WEIGHTS,'masters':MASTERS,'status':'engineering development; native visual acceptance required'},indent=2,ensure_ascii=False)+'\n')
    if args.ufo:
        for w in (400,700):export_ufo(gs,cmap,MASTERS[w],dest/f'Meyar-{WEIGHTS[w]}.ufo')
    files={p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(dest.iterdir()) if p.suffix in ('.ttf','.otf','.woff2')}
    (dest/'manifest.json').write_text(json.dumps(files,indent=2)+'\n')
    print(json.dumps({'glyphs':len(gs),'unicode':len(cmap),'exports':len(files),'bytes':sum(x['bytes'] for x in files.values())}))


if __name__=='__main__':main()
