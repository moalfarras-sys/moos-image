#!/usr/bin/env python3
"""Native Qt ink/line tests; keeps typography failures observable in pixels."""
import argparse
from collections import deque
import json
import math
from pathlib import Path
from PySide6.QtGui import QGuiApplication,QFontDatabase,QFont,QTextLayout,QImage,QPainter,QColor,QRawFont
from fontTools.ttLib import TTFont
from PySide6.QtCore import QPointF,QRectF


def render(text,font,clip=False):
    im=QImage(1400,500,QImage.Format.Format_ARGB32);im.fill(QColor('white'))
    lay=QTextLayout(text,font);lay.beginLayout();line=lay.createLine();line.setLineWidth(1300);lay.endLayout()
    p=QPainter(im);p.setPen(QColor('black'))
    if clip:p.setClipRect(QRectF(0,90,1400,line.height()))
    lay.draw(p,QPointF(45,90));p.end()
    # QTextLine references its QTextLayout's storage. Return measured values,
    # never a dangling line after the local layout has been destroyed.
    return im,{'ascent':line.ascent(),'height':line.height()}


def ink(im):return {(x,y) for y in range(im.height()) for x in range(im.width()) if im.pixelColor(x,y).red()<180}


def components(points,min_size=3):
    unseen=set(points);sizes=[]
    while unseen:
        first=unseen.pop();todo=[first];n=1
        while todo:
            x,y=todo.pop()
            for v in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                if v in unseen:unseen.remove(v);todo.append(v);n+=1
        if n>=min_size:sizes.append(n)
    return sorted(sizes,reverse=True)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('font',type=Path);ap.add_argument('receipt',type=Path);args=ap.parse_args()
    app=QGuiApplication([]);assert QFontDatabase.addApplicationFont(str(args.font))>=0
    failures=[];rows=[]
    expected_hhea=TTFont(args.font).getTableData('hhea')
    for weight in (100,400,700,900):
        f=QFont('Meyar');f.setPixelSize(100);f.setWeight(QFont.Weight(weight))
        if bytes(QRawFont.fromFont(f).fontTable('hhea'))!=expected_hhea:
            failures.append(f'stale font selected at {weight}');continue
        for text in ('أَّ','آَّ','إِّ','بُّ','Ǻ','ç','í','ǰ','مِعْيَارٌ'):
            im,line=render(text,f);clipped,_=render(text,f,True);full=ink(im);crop=ink(clipped);missing=full-crop;lost=len(missing)
            rows.append(dict(text=text,weight=weight,ascent=line['ascent'],lineHeight=line['height'],lostInkPixels=lost,lostInkY=[min(y for x,y in missing),max(y for x,y in missing)] if missing else None))
            if lost:failures.append(f'line clipping {weight} {text}: {lost}')
        im,_=render('∞',f);points=ink(im);xs=[x for x,y in points];ys=[y for x,y in points]
        # Bound all white components by an extra exterior pixel; subtract exterior.
        white={(x,y) for x in range(min(xs)-1,max(xs)+2) for y in range(min(ys)-1,max(ys)+2)}-points
        holes=len(components(white,min_size=10))-1
        rows.append(dict(symbol='infinity',weight=weight,holes=holes))
        if holes!=2:failures.append(f'infinity counters {weight}: {holes}')
        for text,expected in [('ببب',4),('ممم',1),('ههه',1),('ععع',1),('سسس',1),('ننن',4)]:
            im,_=render(text,f);n=len(components(ink(im)))
            rows.append(dict(joinedText=text,weight=weight,inkComponents=n,expected=expected))
            if n!=expected:failures.append(f'ink connectivity {weight} {text}: {n} expected {expected}')
    result={'checks':len(rows),'failures':failures,'rows':rows,'owner':'native Qt QTextLayout/QPainter','scope':'compiled font ink; not authentication or signed installation'}
    args.receipt.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'checks':len(rows),'failures':failures},ensure_ascii=False))
    raise SystemExit(bool(failures))


if __name__=='__main__':main()
