#!/usr/bin/env python3
"""Build Meyar Arabic as an explicitly attributed Noto Sans Arabic derivative.

Owner26Oct rejects the experimental from-scratch Arabic. This independent
source lane preserves the upstream Arabic shaping system and modifies actual
compatible source outlines, rather than replacing that system with skeletons.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import glyphsLib
from glyphsLib.classes import GSNode, GSPath
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools.otlLib.builder import buildStatTable

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT/'upstream/sources/NotoSansArabic.glyphspackage'
STYLES = {100:'Thin',200:'ExtraLight',300:'Light',400:'Regular',500:'Medium',
          600:'SemiBold',700:'Bold',800:'ExtraBold',900:'Black'}
DOTS = ('dotabove-ar','dotbelow-ar','twodotshorizontalabove-ar',
        'twodotshorizontalbelow-ar','twodotsverticalabove-ar',
        'twodotsverticalbelow-ar','threedotsupabove-ar','threedotsupbelow-ar',
        'threedotsdownabove-ar','threedotsdownbelow-ar','fourdotsabove-ar',
        'fourdotsbelow-ar')
EPOCH = 3875817600  # 2026-10-26T00:00:00Z, OpenType epoch


def fingerprint(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_upstream():
    lock=json.loads((ROOT/'upstream-lock.json').read_text())
    for name,record in lock['files'].items():
        path=ROOT/'upstream'/name
        if path.is_symlink() or not path.is_file() or fingerprint(path)!=record['sha256']:
            raise ValueError('Upstream source drift: '+name)
    return lock


def rounded_dot(original):
    """Four cubic squircle arcs retain the original ink bounds and centre.

    k=.70 flattens the shoulders relative to the original circular .55 curves.
    It changes the primitive consistently at every weight/width master, without
    changing dot placement, bearings or any Arabic attachment anchors.
    """
    points=[n.position for n in original.nodes if n.type!='offcurve']
    if len(points)!=4 or len(original.nodes)!=12:
        raise ValueError('Unreviewed dot contour topology')
    left=min(p.x for p in points);right=max(p.x for p in points)
    bottom=min(p.y for p in points);top=max(p.y for p in points)
    cx=(left+right)/2;cy=(top+bottom)/2;rx=(right-left)/2;ry=(top-bottom)/2;k=.70
    # Same counterclockwise orientation as the upstream primitive.
    coords=[(cx+k*rx,bottom,'offcurve'),(right,cy-k*ry,'offcurve'),(right,cy,'curve'),
            (right,cy+k*ry,'offcurve'),(cx+k*rx,top,'offcurve'),(cx,top,'curve'),
            (cx-k*rx,top,'offcurve'),(left,cy+k*ry,'offcurve'),(left,cy,'curve'),
            (left,cy-k*ry,'offcurve'),(cx-k*rx,bottom,'offcurve'),(cx,bottom,'curve')]
    p=GSPath();p.closed=True
    p.nodes=[GSNode((round(x),round(y)),type=t,smooth=True) for x,y,t in coords]
    return p


def prepare(target,control=False):
    f=glyphsLib.GSFont(SOURCE)
    f.familyName='Noto Arabic Source Control' if control else 'Meyar Arabic'
    f.versionMajor=0;f.versionMinor=200
    f.copyright += '\nMeyar Arabic modifications Copyright 2026 MoOS project; SIL OFL1.1.'
    f.designer='The Noto Project Authors; MoOS modifications'
    changes=[]
    if not control:
        for g in f.glyphs:
            if not any(g.name==n or g.name.startswith(n+'.') for n in DOTS):continue
            for layer in g.layers:
                if not layer.paths:continue
                replacement=[rounded_dot(p) for p in layer.paths]
                # Selected primitives contain paths only. Refuse an upstream
                # component change instead of silently discarding it.
                if layer.components:raise ValueError('Dot primitive contains components: '+g.name)
                layer.paths=replacement
                changes.append({'glyph':g.name,'layer':layer.layerId,'change':'rounded-square dot; original bounds/anchors/advance'})
        # Carefully bounded opening of the isolated/final meem head, without
        # touching its baseline join, tail, advance, or positioning anchors.
        for name in ['meem-ar','meem-ar.fina']:
            g=f.glyphs[name]
            for layer in g.layers:
                if layer.layerId not in {m.id for m in f.masters}:continue
                if len(layer.paths)!=1 or len(layer.paths[0].nodes)!=29:
                    # The final uses a distinct reviewed construction. Leave it
                    # unchanged rather than applying isolated node indices.
                    if name.endswith('.fina'):continue
                    raise ValueError('Unreviewed meem construction')
                nodes=layer.paths[0].nodes
                master=f.masters[layer.associatedMasterId]
                delta=3 if master.axes[0]<50 else 5 if master.axes[0]<120 else 7
                for index in [18,19,20]:nodes[index].position.y+=delta
                nodes[21].position.x+=delta*.5;nodes[22].position.x+=delta*.5
                changes.append({'glyph':name,'layer':layer.layerId,'change':'open head counter','units':delta})
    target.parent.mkdir(parents=True,exist_ok=True)
    f.save(target)
    return changes


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=ROOT/'dist')
    ap.add_argument('--control',action='store_true');ap.add_argument('--otf',action='store_true');args=ap.parse_args()
    lock=checked_upstream();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    source=out/'source'/('NotoArabicControl.glyphs' if args.control else 'MeyarArabic.glyphs')
    changes=prepare(source,args.control)
    (out/'source-changes.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2)+'\n')
    base=out/'MeyarArabic[wdth,wght].ttf'
    env=os.environ|{'SOURCE_DATE_EPOCH':'1792972800','PYTHONHASHSEED':'0'}
    subprocess.run([sys.executable,'-m','fontmake','-g',str(source),
        '--glyph-data',str(ROOT/'upstream/sources/GlyphData.xml'),'-o','variable',
        '--output-path',str(base),'--master-dir',str(out/'master_ufo'),
        '--instance-dir',str(out/'instance_ufo'),'--designspace-path',str(out/'source/MeyarArabic.designspace'),
        '--no-production-names','--verbose','WARNING'],env=env,check=True,cwd=out)
    f=TTFont(base,recalcTimestamp=False)
    f=instantiateVariableFont(f,{'wdth':100},inplace=True)
    f.recalcTimestamp=False;f['head'].created=f['head'].modified=EPOCH
    if [a.axisTag for a in f['fvar'].axes]!=['wght']:raise ValueError('Unexpected variable axes')
    if not args.control:
        # Real Black alef+hamza+shadda+fatha reaches1474UPM. Reserve ink
        # room in the font itself; a card that fits a line must fit its marks.
        f['hhea'].ascent=1536;f['OS/2'].sTypoAscender=1536
        f['OS/2'].usWinAscent=max(f['OS/2'].usWinAscent,1536)
    buildStatTable(f,[{'tag':'wght','name':'Weight','values':[
        {'value':w,'name':s,'flags':2 if w==400 else 0} for w,s in STYLES.items()]}])
    f.save(out/'MeyarArabic[wght].ttf');f.flavor='woff2';f.save(out/'MeyarArabic[wght].woff2');f.flavor=None
    for weight,style in STYLES.items():
        static=instantiateVariableFont(f,{'wght':weight},inplace=False,updateFontNames=True)
        static.recalcTimestamp=False;static['head'].created=static['head'].modified=EPOCH
        static.save(out/f'MeyarArabic-{style}.ttf');static.flavor='woff2';static.save(out/f'MeyarArabic-{style}.woff2')
    if args.otf:
        subprocess.run([sys.executable,'-m','fontmake','-g',str(source),
            '--glyph-data',str(ROOT/'upstream/sources/GlyphData.xml'),'-o','otf',
            '-i','^Meyar Arabic ('+'|'.join(STYLES.values())+')$',
            '--output-dir',str(out/'static_cff'),'--master-dir',str(out/'master_ufo'),
            '--instance-dir',str(out/'instance_ufo'),'--no-production-names',
            '--verbose','WARNING'],env=env,check=True,cwd=out)
        for style in STYLES.values():
            matches=list((out/'static_cff').glob('*-'+style+'.otf'))
            if len(matches)!=1:raise ValueError('Missing or ambiguous CFF style: '+style)
            otf=TTFont(matches[0],recalcTimestamp=False)
            otf['hhea'].ascent=1536;otf['OS/2'].sTypoAscender=1536
            otf['OS/2'].usWinAscent=max(otf['OS/2'].usWinAscent,1536)
            otf['head'].created=otf['head'].modified=EPOCH;otf.save(out/f'MeyarArabic-{style}.otf')
    files={p.name:{'sha256':fingerprint(p),'bytes':p.stat().st_size} for p in sorted(out.iterdir()) if p.suffix in ('.ttf','.otf','.woff2')}
    (out/'manifest.json').write_text(json.dumps({'family':f['name'].getDebugName(1),'version':'0.200','upstreamRevision':lock['revision'],
        'derivative':True,'license':'OFL-1.1','sourceChanges':len(changes),'glyphs':len(f.getGlyphOrder()),
        'unicodeCount':len(f.getBestCmap()),'files':files},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'sourceChanges':len(changes),'glyphs':len(f.getGlyphOrder()),'unicodeCount':len(f.getBestCmap()),'exports':len(files)}))


if __name__=='__main__':main()
