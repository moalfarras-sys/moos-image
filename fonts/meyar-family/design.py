"""Meyar's source-level design grammar, shared by Arabic, Latin and mono.

Upstream letter identity, combining anchors and contextual shaping are retained.
Small fillets soften terminals; dots use the same rounded-square shoulder.
Every edit is made to compatible source layers, before binary interpolation.
"""
from __future__ import annotations
import copy
import math
from glyphsLib.classes import GSNode,GSPath
from glyphsLib.classes import GSLayer,GSGlyph
from fontTools.pens.recordingPen import DecomposingRecordingPen


def master_layers(font,glyph):
    ids={m.id for m in font.masters}
    return [l for l in glyph.layers if l.layerId in ids]


def reference_layer(font,glyph):
    layers=master_layers(font,glyph)
    return min(layers,key=lambda l:abs(font.masters[l.associatedMasterId].axes[0]-90)+abs(font.masters[l.associatedMasterId].axes[1]-100))


def fillet_indices(path,minimum_y=None):
    nodes=list(path.nodes);indices=[]
    for i,p in enumerate(nodes):
        a=nodes[i-1];b=nodes[(i+1)%len(nodes)]
        if p.type!='line' or b.type!='line' or a.type=='offcurve':continue
        if minimum_y is not None and p.position.y<minimum_y:continue
        u=(a.position.x-p.position.x,a.position.y-p.position.y)
        v=(b.position.x-p.position.x,b.position.y-p.position.y)
        lu=math.hypot(*u);lv=math.hypot(*v)
        if min(lu,lv)<5:continue
        cosine=sum(x*y for x,y in zip(u,v))/(lu*lv)
        if -.985<cosine<.985:indices.append(i)
    return indices


def fillet_path(path,indices,distance):
    original=list(path.nodes);new=[]
    for i,p in enumerate(original):
        if i not in indices:
            # deepcopy(node) follows its parent path/layer/font. Copy only
            # node data, or one terminal edit clones the entire source font.
            n=GSNode(tuple(p.position),type=p.type,smooth=p.smooth)
            if p.userData:n.userData=copy.deepcopy(dict(p.userData))
            new.append(n);continue
        a=original[i-1];b=original[(i+1)%len(original)]
        ux=a.position.x-p.position.x;uy=a.position.y-p.position.y
        vx=b.position.x-p.position.x;vy=b.position.y-p.position.y
        lu=math.hypot(ux,uy);lv=math.hypot(vx,vy)
        if min(lu,lv)<.01:raise ValueError('Degenerate reviewed corner')
        d=min(distance,lu*.23,lv*.23)
        start=(p.position.x+ux/lu*d,p.position.y+uy/lu*d)
        end=(p.position.x+vx/lv*d,p.position.y+vy/lv*d)
        c1=tuple(start[k]+(tuple(p.position)[k]-start[k])*2/3 for k in (0,1))
        c2=tuple(end[k]+(tuple(p.position)[k]-end[k])*2/3 for k in (0,1))
        new.extend([GSNode(start,type='line',smooth=True),GSNode(c1,type='offcurve'),
                    GSNode(c2,type='offcurve'),GSNode(end,type='curve',smooth=True)])
    out=GSPath();out.closed=path.closed;out.nodes=new;return out


def soften_glyph(font,name,minimum_y=None):
    glyph=font.glyphs[name]
    if glyph is None:return []
    reference=reference_layer(font,glyph);pattern=[fillet_indices(p,minimum_y) for p in reference.paths]
    topology=[len(p.nodes) for p in reference.paths]
    changes=[]
    if not any(pattern):return changes
    for layer in master_layers(font,glyph):
        if [len(p.nodes) for p in layer.paths]!=topology:
            raise ValueError('Unreviewed source topology: '+name)
        amount=max(2,min(10,font.masters[layer.associatedMasterId].axes[0]*.055))
        layer.paths=[fillet_path(p,indices,amount) for p,indices in zip(layer.paths,pattern)]
        changes.append({'glyph':name,'layer':layer.layerId,'change':'soft source terminals','distance':amount})
    return changes


def square_circle(path):
    points=[n.position for n in path.nodes if n.type!='offcurve']
    if len(path.nodes)!=12 or len(points)!=4:return None
    left=min(p.x for p in points);right=max(p.x for p in points)
    bottom=min(p.y for p in points);top=max(p.y for p in points)
    rx=(right-left)/2;ry=(top-bottom)/2
    if not 12<min(rx,ry)<110 or not .7<rx/ry<1.4:return None
    cx=(left+right)/2;cy=(bottom+top)/2;k=.70
    coords=[(cx+k*rx,bottom,'offcurve'),(right,cy-k*ry,'offcurve'),(right,cy,'curve'),
            (right,cy+k*ry,'offcurve'),(cx+k*rx,top,'offcurve'),(cx,top,'curve'),
            (cx-k*rx,top,'offcurve'),(left,cy+k*ry,'offcurve'),(left,cy,'curve'),
            (left,cy-k*ry,'offcurve'),(cx-k*rx,bottom,'offcurve'),(cx,bottom,'curve')]
    p=GSPath();p.closed=True;p.nodes=[GSNode((x,y),type=t,smooth=True) for x,y,t in coords]
    # Preserve winding of the original circle.
    if p.direction!=path.direction:p.reverse()
    return p


def latin_design(font):
    changes=[]
    for name in ['i','j','period','colon','semicolon','exclam','question','questiondown','exclamdown','dotaccent','dotbelow']:
        g=font.glyphs[name]
        if g is None:continue
        for layer in master_layers(font,g):
            replaced=[];changed=0
            for path in layer.paths:
                p=square_circle(path);replaced.append(p or path);changed+=p is not None
            if changed:layer.paths=replaced;changes.append({'glyph':name,'layer':layer.layerId,'change':'Meyar dot shoulders'})
    # A raised middle gives M its own rhythm without making it resemble N.
    g=font.glyphs['M'];ref=reference_layer(font,g)
    selection=[i for i,n in enumerate(ref.paths[0].nodes) if n.type!='offcurve' and .43*ref.width<n.position.x<.61*ref.width and n.position.y<160]
    for layer in master_layers(font,g):
        for i in selection:layer.paths[0].nodes[i].position.y+=18
        changes.append({'glyph':'M','layer':layer.layerId,'change':'raised central rhythm','units':18})
    # Retain the original double-storey a/g and every IPA distinction.
    for name in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz':changes+=soften_glyph(font,name)
    return changes


def terminal_cells(font):
    """Fit encoded LGC symbols to the native Konsole Unicode cell policy.

    Snapshot dependent components before modifying any outline. Noto Mono has
    authored double-width digraphs and symbols that Konsole treats as one cell;
    preserving those widths makes unique IPA/Greek letters paint over text.
    """
    import json
    from pathlib import Path
    policy=json.loads((Path(__file__).parent/'terminal-cells.json').read_text())
    targets={r['glyph']:r['terminalCells']*600 for r in policy['adjustments']}
    affected=set(targets)
    while True:
        more={g.name for g in font.glyphs for l in master_layers(font,g)
              if any(c.componentName in affected for c in l.components)}-affected
        if not more:break
        affected.update(more)
    saved=[];changes=[]
    for master in font.masters:
        glyphset={g.name:g.layers[master.id] for g in font.glyphs}
        for name in sorted(affected):
            layer=glyphset[name];pen=DecomposingRecordingPen(glyphset)
            layer.draw(pen);flat=GSLayer();pen.replay(flat.getPen())
            saved.append((name,layer,flat.paths))
    for name,layer,paths in saved:
        layer.components=[];layer.paths=paths
        if name not in targets:continue
        old=layer.width;new=targets[name]
        if old not in [0,500,600,1000,1200,1500,1800]:raise ValueError('Unreviewed terminal source width: '+name)
        if old==new:continue
        if old and new<old:
            scale=new/old
            for p in layer.paths:
                for n in p.nodes:n.position.x*=scale
            for anchor in layer.anchors:anchor.position.x*=scale
        else:
            bounds=layer.bounds
            dx=(new-old)/2 if old else ((new-bounds.size.width)/2-bounds.origin.x if bounds else new/2)
            for p in layer.paths:
                for n in p.nodes:n.position.x+=dx
            for anchor in layer.anchors:anchor.position.x+=dx
        layer.width=new
        changes.append({'glyph':name,'layer':layer.layerId,'change':'native Unicode terminal cells',
                        'oldWidth':old,'newWidth':new,'dependentComponentsSnapshotted':True})
    return changes


def mono_grid(font):
    """700UPM cells match Kawkab's actual Arabic executor, including wide cells.

    Transform components by conjugation: scaling both their base outline and
    their component matrix would otherwise scale composite letters twice.
    """
    changes=[]
    s=7/6
    for g in font.glyphs:
        for layer in g.layers:
            for p in layer.paths:
                for n in p.nodes:n.position.x*=s
            for c in layer.components:
                xx,yx,xy,yy,dx,dy=c.transform;c.transform=(xx,yx/s,xy*s,yy,dx*s,dy)
            for a in layer.anchors:a.position.x*=s
            layer.width=round(layer.width*s)
    return changes+[{'change':'700UPM mono grid; zero-width marks and multi-cell advances preserved','scaleX':s}]


def kawkab_lexical_source(text):
    lines=text.splitlines(keepends=True);changes=[]
    for j,line in enumerate(lines):
        if not line.lstrip().startswith('code = "') or not line.rstrip().endswith('";'):continue
        first=line.index('"');last=line.rindex('"');body=line[first+1:last];out=[];count=0
        for i,c in enumerate(body):
            n=0;k=i-1
            while k>=0 and body[k]=='\\':n+=1;k-=1
            if c=='"' and n%2==0:out.append('\\');count+=1
            out.append(c)
        if count:lines[j]=line[:first+1]+''.join(out)+line[last:];changes.append({'line':j+1,'escapedCodeQuotes':count})
    return ''.join(lines),changes


def compact_mono_marks(font):
    """Optical mark masters, preserving700-unit base advances and cursive joins.

    Legacy Kawkab's alef/hamza/shadda/fatha reaches1932UPM. A source control
    reproduces that on the installed font too. Snapshot/decompose only its21
    mark glyphs before editing, so composite marks are never scaled twice.
    """
    saved=[];changes=[];mark_names=set()
    for m in font.masters:
        glyphset={g.name:g.layers[m.id] for g in font.glyphs}
        for g in font.glyphs:
            if '-ar' not in g.name:continue
            layer=g.layers[m.id];incoming=[a for a in layer.anchors if a.name in ['_top','_bottom']]
            if not incoming:continue
            if len(incoming)!=1:raise ValueError('Unreviewed dual mark anchor: '+g.name)
            mark_names.add(g.name);anchor=incoming[0];pen=DecomposingRecordingPen(glyphset)
            layer.draw(pen);flat=GSLayer();pen.replay(flat.getPen())
            saved.append((g.name,layer,flat.paths,(anchor.position.x,anchor.position.y),anchor.name))
    for name,layer,paths,origin,kind in saved:
        for path in paths:
            for node in path.nodes:
                node.position.x=origin[0]+(node.position.x-origin[0])*.70
                node.position.y=origin[1]+(node.position.y-origin[1])*.70
        layer.components=[];layer.paths=paths
        changes.append({'glyph':name,'layer':layer.layerId,'change':'compact source mark','scale':.70})
    for g in font.glyphs:
        if '-ar' not in g.name:continue
        for layer in master_layers(font,g):
            b=layer.bounds
            if b is None:continue
            bottom=b.origin.y;top=bottom+b.size.height
            for anchor in layer.anchors:
                if anchor.name=='_top':anchor.position.y=bottom
                elif anchor.name=='_bottom':anchor.position.y=top
                elif anchor.name=='top':anchor.position.y=top+36
                elif anchor.name=='bottom':anchor.position.y=bottom-36
            if g.name in mark_names or any(a.name in ['top','bottom'] for a in layer.anchors):
                changes.append({'glyph':g.name,'layer':layer.layerId,'change':'ink-based Arabic mark anchors; join/advance unchanged'})
    return changes


def arabic_terminal_cells(font):
    """Keep encoded Arabic symbols in their native cells without touching joins.

    Glyphs' inferred mark category silently zeroes ten spacing Sk symbols.
    Their source already has700-unit widths and distinct above/below positions.
    Allah's encoded one-cell presentation needs a separate cmap glyph: its old
    four-cell GSUB ligature must keep normal four-letter Arabic text unchanged.
    """
    import json
    from pathlib import Path
    policy=json.loads((Path(__file__).parent/'terminal-cells.json').read_text())['arabic']
    changes=[]
    for row in policy['adjustments']:
        g=font.glyphs[row['glyph']];target=row['terminalCells']*700
        if row['glyph']=='allah-ar':
            new=GSGlyph('allah-ar.cell');new.unicode=f"{row['codepoint']:04X}"
            new.category='Symbol';new.subCategory='Other';new.script='arabic'
            for master in font.masters:
                original=g.layers[master.id];pen=DecomposingRecordingPen({x.name:x.layers[master.id] for x in font.glyphs})
                original.draw(pen);layer=GSLayer();layer.layerId=master.id;layer.associatedMasterId=master.id
                pen.replay(layer.getPen())
                for path in layer.paths:
                    for node in path.nodes:node.position.x*=target/original.width
                layer.width=target;new.layers.append(layer)
            g.unicodes=[];font.glyphs.append(new)
            changes.append({'glyph':g.name,'encodedVariant':new.name,'unicode':row['codepoint'],
                'change':'one-cell presentation; original four-cell word ligature preserved'})
        elif row['controlAdvance']==0:
            if not 0xfbb2<=row['codepoint']<=0xfbbe:raise ValueError('Unexpected Arabic spacing symbol')
            if any(l.width!=700 or l.anchors for l in master_layers(font,g)):
                raise ValueError('Reviewed spacing symbol source changed')
            g.category='Symbol';g.subCategory='Other'
            changes.append({'glyph':g.name,'change':'spacing Sk symbol; retain authored700-unit advance/position'})
        else:
            if g.name not in ['coffee','lock']:raise ValueError('Unexpected wide Arabic-font symbol')
            for layer in master_layers(font,g):
                if layer.width!=700:raise ValueError('Reviewed wide symbol source changed')
                # Center the icon in two cells; keep its drawn proportions.
                for path in layer.paths:
                    for node in path.nodes:node.position.x+=350
                for component in layer.components:component.position.x+=350
                for anchor in layer.anchors:anchor.position.x+=350
                layer.width=1400
            changes.append({'glyph':g.name,'change':'two-cell Unicode icon; original outline proportions'})
    return changes
