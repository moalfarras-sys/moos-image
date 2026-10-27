"""Original Meyar construction primitives. Coordinates in 1000 units/em.

No font or traced artwork is an input. Paths are authored centre lines; the
offset builder retains point order across optical masters, including terminals.
"""
import math
from dataclasses import dataclass, field


def path(*commands):
    points = []
    start = None
    for c in commands:
        if c[0] == 'M':
            points.append((c[1], c[2])); start = points[-1]
        elif c[0] == 'L':
            points.append((c[1], c[2]))
        elif c[0] in ('Q', 'C'):
            p = points[-1]
            n = 20 if c[0] == 'C' else 14
            for i in range(1, n + 1):
                t = i / n; u = 1 - t
                if c[0] == 'Q':
                    points.append((u*u*p[0]+2*u*t*c[1]+t*t*c[3], u*u*p[1]+2*u*t*c[2]+t*t*c[4]))
                else:
                    points.append((u**3*p[0]+3*u*u*t*c[1]+3*u*t*t*c[3]+t**3*c[5], u**3*p[1]+3*u*u*t*c[2]+3*u*t*t*c[4]+t**3*c[6]))
        elif c[0] == 'Z':
            if points[-1] != start: points.append(start)
    return points


def ellipse(cx, cy, rx, ry, start=0, end=360, n=64):
    p=[(cx+rx*math.cos(math.radians(start+(end-start)*i/n)), cy+ry*math.sin(math.radians(start+(end-start)*i/n))) for i in range(n+1)]
    if abs(end-start)==360:p[-1]=p[0]
    return p


def area(p):
    return sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(p,p[1:]+p[:1]))/2


def stroke(points, width, closed=False):
    """Parallel offset, small elliptical caps; constant master topology.

    Arabic join ends overhang their advance boundary by half a stem. This is
    intentional ink overlap, while GPOS cursive anchors remain at the advance.
    """
    pts = list(points)
    if closed and math.dist(pts[-1],pts[0])<1e-6: pts.pop()
    normals = []
    for i, p in enumerate(pts):
        a = pts[(i-1) % len(pts)] if closed or i else p
        b = pts[(i+1) % len(pts)] if closed or i < len(pts)-1 else p
        # Intersect the two parallel segment offsets. A raw chord normal
        # thins long diagonals at the M/N/V apex and is not a stroke join.
        dx,dy=p[0]-a[0],p[1]-a[1];d=math.hypot(dx,dy)
        ex,ey=b[0]-p[0],b[1]-p[1];e=math.hypot(ex,ey)
        if not d:dx,dy,d=ex,ey,e
        if not e:ex,ey,e=dx,dy,d
        u=(-dy/(d or 1),dx/(d or 1));v=(-ey/(e or 1),ex/(e or 1))
        nx,ny=u[0]+v[0],u[1]+v[1];k=math.hypot(nx,ny) or 1
        nx,ny=nx/k,ny/k
        projection=max(.35,nx*v[0]+ny*v[1])
        normals.append((nx/projection,ny/projection))
    r=width/2
    left=[(p[0]+n[0]*r,p[1]+n[1]*r) for p,n in zip(pts,normals)]
    right=[(p[0]-n[0]*r,p[1]-n[1]*r) for p,n in zip(pts,normals)]
    if closed:
        outer,inner=(left,right) if abs(area(left))>abs(area(right)) else (right,left)
        if area(outer)>0:outer.reverse()
        if area(inner)<0:inner.reverse()
        return [outer,inner]
    def cap(p,n,sign):
        a=math.atan2(n[1],n[0])
        return [(p[0]+r*math.cos(a+sign*math.pi*i/10),p[1]+r*math.sin(a+sign*math.pi*i/10)) for i in range(1,10)]
    # Clockwise from left at the terminal to right, then back round the origin.
    out=left+cap(pts[-1],normals[-1],-1)+list(reversed(right))+cap(pts[0],(-normals[0][0],-normals[0][1]),-1)
    if area(out)>0:out.reverse()
    return [out]


@dataclass
class Glyph:
    width: int
    strokes: list = field(default_factory=list)
    dots: list = field(default_factory=list)
    top: tuple | None = None
    bottom: tuple | None = None
    mark: str | None = None
    joins: tuple = (False, False)  # right incoming, left outgoing
    dots_stem_gain: float = 0

    def add(self, points, scale=1, closed=False):
        self.strokes.append((points,scale,closed));return self

    def dot(self,x,y,scale=1):
        self.dots.append((x,y,scale));return self

    def contours(self, stem):
        # Marks remain lighter than display strokes at the dark end. Scaling
        # them like the base body closes the shadda and crowds stacked vowels.
        # Their dedicated optical progression is part of all four masters.
        if self.mark and stem>68:stem=68+(stem-68)*.36
        out=[]
        for p,s,c in self.strokes:out.extend(stroke(p,stem*s,c))
        for x,y,s in self.dots:
            # Rounded lozenge: a quiet, visible signature shared by both scripts.
            r=(stem*.28+25)*s
            if y>0:y+=max(0,stem-68)*self.dots_stem_gain
            pts=[]
            for i in range(32):
                t=2*math.pi*i/32; ct,st=math.cos(t),math.sin(t)
                xx=math.copysign(abs(ct)**.72,ct)*r
                yy=math.copysign(abs(st)**.72,st)*r*.86
                angle=.12
                pts.append((x+xx*math.cos(angle)-yy*math.sin(angle), y+xx*math.sin(angle)+yy*math.cos(angle)))
            if area(pts)>0:pts.reverse()
            out.append(pts)
        return [[(round(x),round(y)) for x,y in p] for p in out]

    def shifted(self,dx,dy):
        return Glyph(self.width, [([(x+dx,y+dy) for x,y in p],s,c) for p,s,c in self.strokes], [(x+dx,y+dy,s) for x,y,s in self.dots], self.top,self.bottom,self.mark,self.joins,self.dots_stem_gain)

    def scaled(self,s,dx=0,dy=0):
        return Glyph(round(self.width*s), [([(x*s+dx,y*s+dy) for x,y in p],w*s,c) for p,w,c in self.strokes], [(x*s+dx,y*s+dy,r*s) for x,y,r in self.dots], (round(self.top[0]*s+dx),round(self.top[1]*s+dy)) if self.top else None, (round(self.bottom[0]*s+dx),round(self.bottom[1]*s+dy)) if self.bottom else None,self.mark,self.joins,self.dots_stem_gain*s)


def line(*xy):return path(('M',*xy[:2]),*[('L',*xy[i:i+2]) for i in range(2,len(xy),2)])


def combine(a,b,dx=0,dy=0):
    b=b.shifted(dx,dy)
    return Glyph(a.width,a.strokes+b.strokes,a.dots+b.dots,a.top,a.bottom,a.mark,a.joins,a.dots_stem_gain)
