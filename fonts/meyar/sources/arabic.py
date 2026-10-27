"""Meyar's authored Arabic system: shared joins, bowls and signature loops.

This file contains design coordinates, never imports outlines from another face.
"""
from .geometry import Glyph, path as P, ellipse as E, line, combine

# codepoint: construction, dots (positive above; negative below), joining class.
LETTERS = {
0x621:('hamza',0,'U'),0x622:('alefMadda',0,'R'),0x623:('alefHamza',0,'R'),0x624:('wawHamza',0,'R'),0x625:('alefBelow',0,'R'),0x626:('yehHamza',0,'D'),
0x627:('alef',0,'R'),0x628:('beh',-1,'D'),0x629:('heh',2,'R'),0x62A:('beh',2,'D'),0x62B:('beh',3,'D'),0x62C:('hah',-1,'D'),0x62D:('hah',0,'D'),0x62E:('hah',1,'D'),
0x62F:('dal',0,'R'),0x630:('dal',1,'R'),0x631:('reh',0,'R'),0x632:('reh',1,'R'),0x633:('seen',0,'D'),0x634:('seen',3,'D'),0x635:('sad',0,'D'),0x636:('sad',1,'D'),
0x637:('tah',0,'D'),0x638:('tah',1,'D'),0x639:('ain',0,'D'),0x63A:('ain',1,'D'),0x640:('tatweel',0,'C'),0x641:('feh',1,'D'),0x642:('qaf',2,'D'),
0x643:('kaf',0,'D'),0x644:('lam',0,'D'),0x645:('meem',0,'D'),0x646:('noon',1,'D'),0x647:('heh',0,'D'),0x648:('waw',0,'R'),0x649:('yeh',0,'D'),0x64A:('yeh',-2,'D'),
0x671:('alefWasla',0,'R'),0x679:('beh',4,'D'),0x67E:('beh',-3,'D'),0x686:('hah',-3,'D'),0x688:('dal',4,'R'),0x691:('reh',4,'R'),0x698:('reh',3,'R'),
0x6A4:('feh',3,'D'),0x6A9:('keheh',0,'D'),0x6AD:('kaf',3,'D'),0x6AF:('gaf',0,'D'),0x6BA:('noon',0,'D'),0x6BE:('hehDo',0,'D'),0x6C0:('hehHamza',0,'R'),
0x6C1:('heh',0,'D'),0x6CC:('farsiYeh',0,'D'),0x6D2:('yehBarree',0,'R'),0x6D5:('heh',0,'R'),
}


def hamza():
    return Glyph(260).add(P(('M',215,400),('C',125,450,60,385,105,340),('L',225,340),('L',60,245)),.78)


def mark(cp):
    g=Glyph(0,mark='bottom' if cp in (0x64D,0x650,0x655,0x656,0x65C) else 'top')
    if cp in (0x64B,0x64C,0x64D):
        base={0x64B:0x64E,0x64C:0x64F,0x64D:0x650}[cp]
        a=mark(base);g=combine(a,a,0,95);g.mark=a.mark
    elif cp in (0x64E,0x650):g.add(line(-65,0,75,62),.60)
    elif cp==0x64F:g.add(E(25,45,49,42),.54,True).add(P(('M',70,25),('Q',65,-35,-55,-42)),.54)
    elif cp==0x651:g.add(P(('M',-85,65),('L',-75,10),('Q',-35,-35,-5,30),('Q',28,-35,65,0),('L',85,70)),.55)
    elif cp==0x652:g.add(E(0,25,51,40),.5,True)
    elif cp==0x653:g.add(P(('M',-125,0),('Q',-65,90,0,30),('Q',65,-25,125,48)),.52)
    elif cp in (0x654,0x655):
        g=hamza().shifted(-140,-285);g.width=0;g.mark='bottom' if cp==0x655 else 'top'
    elif cp in (0x670,0x656):g.add(line(-8,-12,8,140),.52)
    else:return None
    return g


def letter(cp, form='isol'):
    kind,dots,j=LETTERS[cp]; right=form in ('fina','medi'); left=form in ('init','medi') and j in ('D','C')
    base=kind
    if kind.startswith('alef'):base='alef'
    if kind in ('wawHamza',):base='waw'
    if kind in ('yehHamza','farsiYeh'):base='yeh'
    if kind in ('hehDo','hehHamza'):base='heh'
    if kind in ('keheh','gaf'):base='kaf'
    w={'alef':245,'hamza':280,'beh':590 if not left else 360,'noon':510 if not left else 350,'yeh':625 if not left else 360,
       'hah':650 if not left else 540,'seen':900 if not left else 730,'sad':820 if not left else 700,'tah':640,
       'ain':605 if not left else 435,'feh':690 if not left else 430,'qaf':640 if not left else 430,'kaf':655 if not left else 540,
       'lam':490 if not left else 320,'meem':455 if not left else 395,'heh':510 if not left else 420,'dal':465,'reh':435,'waw':475,
       'tatweel':300,'yehBarree':750}[base]
    g=Glyph(w,joins=(right,left),dots_stem_gain=.75); top=410;dotx=w/2
    def add(*args,s=1):g.add(P(*args),s)
    def join_to(x,y=110):
        if right:g.add(line(w,110,x,y))
    if base=='hamza':return hamza()
    if base=='tatweel':g.add(line(0,110,w,110));g.joins=(True,True)
    elif base=='alef':
        add(('M',120,100),('C',120,320,111,510,125,710));join_to(120);top=770;dotx=120
    elif base in ('beh','noon','yeh'):
        if left:
            add(('M',w-85,305),('Q',w-65,110,w-150,110),('L',0,110));join_to(w-115)
        else:
            add(('M',w-90,300),('C',w-65,90,w-100,-28,w/2,-32),('C',120,-42,65,15,80,135));join_to(w-103)
        dotx=w-100 if left else w/2
        if base=='noon':top=425
        if kind=='farsiYeh':dots=-2 if left else 0
    elif base=='hah':
        add(('M',w-95,345),('C',w-260,435,w-410,370,w-425,305),('L',w-160,215),('Q',w-65,185,w-105,110))
        if left:g.add(line(w-105,110,0,110))
        else:add(('M',w-105,110),('C',w-260,105,100,100,95,-28),('C',90,-150,235,-180,400,-120))
        join_to(w-105);dotx=w-260;top=465
    elif base=='seen':
        add(('M',w-80,325),('L',w-90,170),('Q',w-155,60,w-230,180),('L',w-230,300),('L',w-245,170),('Q',w-320,60,w-385,180),('L',w-385,280),('Q',w-385,115,w-470,110))
        if left:g.add(line(w-470,110,0,110))
        else:add(('M',w-470,110),('C',w-470,-70,165,-120,95,-28),('Q',60,20,80,140))
        join_to(w-110);dotx=w-235;top=455
    elif base in ('sad','tah'):
        x=w-270
        add(('M',w-65,125),('C',w-50,350,w-245,440,w-440,165),('Q',w-490,90,w-405,110),('L',w-65,125))
        if base=='tah':g.add(P(('M',w-195,150),('Q',w-220,400,w-200,680)));top=750;dotx=w-390
        else:dotx=w-255;top=450
        if left:g.add(line(w-405,110,0,110))
        else:add(('M',w-405,110),('C',w-425,-85,155,-100,90,-18),('Q',60,25,80,145))
        join_to(w-80,120)
    elif base=='ain':
        if form=='medi':
            add(('M',w-95,110),('L',w-310,265),('Q',w-170,415,w-85,250),('L',w-300,110),('L',0,110));join_to(w-95)
        else:
            add(('M',w-80,365),('C',w-260,475,w-390,310,w-260,235),('Q',w-175,180,w-90,185))
            if left:add(('M',w-90,185),('Q',w-225,110,0,110))
            else:add(('M',w-90,185),('C',w-240,125,85,100,90,-30),('C',100,-175,280,-175,425,-95))
            join_to(w-200,110)
        top=470;dotx=w-240
    elif base in ('feh','qaf'):
        cx=w-170
        g.add(E(cx,285,100,113),1,True)
        add(('M',w-78,240),('Q',w-60,110,w-195,110))
        if left:g.add(line(w-195,110,0,110))
        else:add(('M',w-195,110),('C',w-210,-55,120,-90,85,25),('L',80,140))
        join_to(w-85);top=495;dotx=cx
    elif base=='lam':
        add(('M',w-95,710),('L',w-95,170))
        if left:add(('M',w-95,170),('Q',w-100,110,0,110))
        else:add(('M',w-95,170),('C',w-75,-90,140,-110,90,0),('Q',65,35,80,145))
        join_to(w-98);top=785;dotx=w-95
    elif base=='kaf':
        if left:
            add(('M',w-80,660),('L',100,350),('Q',w-145,250,w-95,110),('L',0,110));join_to(w-95)
        else:
            add(('M',w-100,660),('L',w-100,155),('Q',w-90,30,w-240,25),('L',150,25),('Q',65,30,85,140));join_to(w-100)
            add(('M',w-250,435),('L',w-370,340),('Q',w-205,325,w-305,240),s=.7)
        if kind in ('keheh','gaf'):
            g.strokes=[]
            add(('M',w-75,665),('L',105,370),('Q',w-100,290,w-90,155),('Q',w-85,110,0 if left else 120,110))
            if not left:g.add(line(120,110,85,165))
            join_to(w-90)
        if kind=='gaf':g.add(line(145,475,w-80,740),.7)
        top=800;dotx=w/2
    elif base=='meem':
        # An inclined, open-counter pebble; the lower terminal has a long neck.
        add(('M',w-95,160),('C',w-75,345,w-255,380,w-285,225),('C',w-315,85,w-175,90,w-95,160))
        join_to(w-100,155)
        if left:add(('M',w-280,180),('Q',w-310,110,0,110))
        else:add(('M',w-280,180),('Q',105,110,105,20),('L',105,-210))
        top=415;dotx=w-190
    elif base=='heh':
        if form=='medi' or kind=='hehDo' and left:
            g.add(E(w/2,250,118,127),1,True).add(E(w/2,30,105,102),.94,True).add(line(0,110,w,110));top=460
        elif left:
            add(('M',w-95,110),('C',w-55,380,w-255,425,w-310,265),('C',w-380,60,w-160,55,w-95,110),('Q',w-230,110,0,110));top=455
        else:
            add(('M',w-95,105),('C',w-70,365,w-255,450,w-355,245),('C',w-450,30,w-170,-20,w-95,105));join_to(w-95);top=465
        dotx=w/2
    elif base=='dal':
        add(('M',125,445),('C',220,395,355,230,335,120),('Q',305,65,95,95));join_to(335);dotx=190;top=530
    elif base=='reh':
        add(('M',w-115,295),('C',w-75,80,w-205,-110,75,-155));join_to(w-110);dotx=w-130;top=415
    elif base=='waw':
        g.add(E(w-195,280,110,108),1,True)
        add(('M',w-88,265),('C',w-50,65,w-240,-140,85,-145));join_to(w-100);dotx=w-195;top=490
    elif base=='yehBarree':
        add(('M',w-100,265),('Q',w-40,100,w-220,100),('L',100,100),('Q',40,75,100,0),('L',w-150,0));join_to(w-100);top=350
    if dots:
        if dots==4:g.add(line(dotx-45,top+75,dotx-45,top+10,dotx+55,top+10,dotx+20,top+55),.55);top+=120
        else:
            y=top if dots>0 else (-60 if left or base=='hah' else -200)
            n=abs(dots)
            for x,dy in ({1:[(0,0)],2:[(-65,0),(65,0)],3:[(-65,0),(65,0),(0,100)]}[n]):g.dot(dotx+x,y+dy,.83)
            if dots>0:top+=90 if n<3 else 190
    g.top=(round(dotx),top+65);g.bottom=(round(dotx),-290 if dots<0 else -240)
    if kind in ('alefMadda','alefHamza','alefBelow','alefWasla','wawHamza','yehHamza','hehHamza'):
        m=mark(0x653 if kind=='alefMadda' else 0x655 if kind=='alefBelow' else 0x654)
        y=-115 if kind=='alefBelow' else (770 if base=='alef' else top+20)
        if kind=='alefWasla':m=Glyph(0).add(P(('M',-75,0),('Q',-40,90,5,25),('Q',60,100,75,0)),.5)
        g=combine(g,m,round(dotx),y);g.top=(round(dotx),y+180 if y>0 else top+65)
    return g


def lamalef(variant=0x627, final=False):
    w=510;g=Glyph(w,joins=(final,False),top=(260,865),bottom=(220,-160))
    g.add(P(('M',410,710),('L',410,205),('Q',420,20,110,45)))
    g.add(P(('M',100,700),('Q',170,365,350,80)))
    if final:g.add(line(w,110,405,110))
    if variant!=0x627:g=combine(g,mark(0x653 if variant==0x622 else 0x655 if variant==0x625 else 0x654),100,790 if variant!=0x625 else -100)
    return g


def digit(n, persian=False):
    g=Glyph(560,top=(280,800),bottom=(280,-130))
    defs={
      0:[('M',280,340),('Q',365,260,280,185),('Q',195,260,280,340)],
      1:[('M',235,700),('Q',285,430,300,40)],
      2:[('M',100,635),('Q',225,470,310,625),('Q',440,720,455,560),('Q',275,450,300,40)],
      3:[('M',80,650),('Q',175,475,245,650),('Q',345,475,415,650),('Q',490,430,315,45)],
      4:[('M',430,680),('L',140,445),('L',395,315),('L',150,75)],
      5:[('M',280,650),('C',55,390,30,85,270,70),('C',520,65,500,390,280,650)],
      6:[('M',95,650),('Q',230,540,445,645),('Q',315,360,290,40)],
      7:[('M',95,650),('L',275,55),('L',465,650)],
      8:[('M',95,60),('L',275,655),('L',465,60)],
      9:[('M',425,410),('C',230,330,85,470,160,620),('C',285,795,490,620,400,420),('Q',335,235,350,40)],
    }
    if persian and n==4:defs[n]=[('M',330,690),('L',120,445),('L',430,445),('Q',285,265,300,40)]
    if persian and n==5:defs[n]=[('M',90,45),('L',90,300),('Q',255,320,280,660),('Q',305,320,470,300),('L',470,45)]
    if persian and n==6:defs[n]=[('M',410,665),('Q',180,530,150,380),('Q',145,270,425,305),('Q',255,165,285,40)]
    g.add(P(*defs[n]),.95,closed=n in (0,5) and not(persian and n==5))
    return g
