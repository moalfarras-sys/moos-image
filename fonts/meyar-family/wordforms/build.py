"""Build selectable regular-weight OpenType specimens from the pinned Meyar faces."""
import argparse
import copy
from pathlib import Path
import unicodedata

from fontTools.pens.qtPen import QtPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables as ot
from fontTools.varLib.instancer import instantiateVariableFont
from PySide6.QtGui import QPainterPath, QTransform
from preview import contour, ROOT


def coverage(names):
    result = ot.Coverage()
    result.glyphs = names
    return result


def lookup(kind, tables):
    item = ot.Lookup()
    item.LookupType = kind
    item.LookupFlag = 8  # Ignore combining marks while finding the two word ends.
    item.SubTable = tables
    item.SubTableCount = len(tables)
    return item


def reverse_sub(names, outputs, before):
    sub = ot.ReverseChainSingleSubst()
    sub.Format = 1
    sub.Coverage = coverage(names)
    sub.BacktrackCoverage = [coverage(names)] if before else []
    sub.BacktrackGlyphCount = len(sub.BacktrackCoverage)
    sub.LookAheadCoverage = []
    sub.LookAheadGlyphCount = 0
    sub.Substitute = outputs
    sub.GlyphCount = len(outputs)
    return sub


def forward_rule(names, after, action=None):
    sub = ot.ChainContextSubst()
    sub.Format = 3
    sub.BacktrackCoverage = []
    sub.BacktrackGlyphCount = 0
    sub.InputCoverage = [coverage(names)]
    sub.InputGlyphCount = 1
    sub.LookAheadCoverage = [coverage(names)] if after else []
    sub.LookAheadGlyphCount = len(sub.LookAheadCoverage)
    sub.SubstLookupRecord = []
    if action is not None:
        record = ot.SubstLookupRecord()
        record.SequenceIndex = 0
        record.LookupListIndex = action
        sub.SubstLookupRecord.append(record)
    sub.SubstCount = len(sub.SubstLookupRecord)
    return sub


def install_word_feature(f, variants):
    table = f['GSUB'].table
    lookups = table.LookupList.Lookup
    names = list(variants)
    sharp, rounded = zip(*variants.values())
    round_sub = ot.SingleSubst()
    round_sub.mapping = dict(zip(names, rounded))
    round_index = len(lookups)
    lookups.append(lookup(1, [round_sub]))
    # Each pair consumes precisely one unassigned letter at either end.
    # Reverse scanning for the first letter and forward scanning for the last
    # prevent a substitution from propagating through the same word in a pass.
    left = lookup(8, [reverse_sub(names, names, True), reverse_sub(names, list(sharp), False)])
    right = lookup(6, [forward_rule(names, True), forward_rule(names, False, round_index)])
    feature = ot.FeatureRecord()
    feature.FeatureTag = 'calt'
    feature.Feature = ot.Feature()
    feature.Feature.FeatureParams = None
    feature.Feature.LookupListIndex = []
    for _ in range(32):
        feature.Feature.LookupListIndex.extend([len(lookups), len(lookups)+1])
        lookups.extend([left, right])
    feature.Feature.LookupCount = len(feature.Feature.LookupListIndex)
    table.LookupList.LookupCount = len(lookups)
    records = table.FeatureList.FeatureRecord
    assert all(x.FeatureTag != 'calt' for x in records)
    # Feature indexes are referred to by each script. Keep their sorted order.
    index = sum(x.FeatureTag < 'calt' for x in records)
    records.insert(index, feature)
    for script in table.ScriptList.ScriptRecord:
        langs = [x.LangSys for x in script.Script.LangSysRecord]
        if script.Script.DefaultLangSys:
            langs.append(script.Script.DefaultLangSys)
        for lang in langs:
            lang.FeatureIndex = sorted([i+(i>=index) for i in lang.FeatureIndex] + [index])
            lang.FeatureCount = len(lang.FeatureIndex)
            if lang.ReqFeatureIndex != 65535 and lang.ReqFeatureIndex >= index:
                lang.ReqFeatureIndex += 1
    table.FeatureList.FeatureCount = len(records)


def add_coverage(cov, variants, array=None):
    extra = [(name, i) for i, original in enumerate(cov.glyphs) for name in variants.get(original, ())]
    cov.glyphs.extend(name for name, _ in extra)
    if array is not None:
        array.extend(array[i] for _, i in extra)


def expand_positioning(f, variants):
    for elem in [f['GDEF'].table.GlyphClassDef, f['GDEF'].table.MarkAttachClassDef]:
        if elem:
            for n, alts in variants.items():
                if n in elem.classDefs:
                    elem.classDefs.update(dict.fromkeys(alts, elem.classDefs[n]))
    gdef = f['GDEF'].table
    for row in getattr(gdef.MarkGlyphSetsDef, 'Coverage', []):
        add_coverage(row, variants)
    for name, field, count in [('LigCaretList','LigGlyph','LigGlyphCount'),('AttachList','AttachPoint','GlyphCount')]:
        obj = getattr(gdef, name, None)
        if obj:
            records = getattr(obj, field)
            add_coverage(obj.Coverage, variants, records)
            setattr(obj, count, len(records))
    for owner in f['GPOS'].table.LookupList.Lookup:
        for t in owner.SubTable:
            kind = owner.LookupType
            if kind == 9:
                kind, t = t.ExtensionLookupType, t.ExtSubTable
            if kind == 2 and t.Format == 1:
                for group in t.PairSet:
                    for pair in list(group.PairValueRecord):
                        for v in variants.get(pair.SecondGlyph, ()):
                            dup = copy.copy(pair)
                            dup.SecondGlyph = v
                            group.PairValueRecord.append(dup)
                    group.PairValueRecord.sort(key=lambda x:f.getGlyphID(x.SecondGlyph))
                    group.PairValueCount = len(group.PairValueRecord)
                add_coverage(t.Coverage, variants, t.PairSet)
                t.PairSetCount = len(t.PairSet)
            elif kind == 2 and t.Format == 2:
                add_coverage(t.Coverage, variants)
                for c in [t.ClassDef1, t.ClassDef2]:
                    for n, alts in variants.items():
                        if n in c.classDefs:
                            c.classDefs.update(dict.fromkeys(alts,c.classDefs[n]))
            elif kind in (4,5,6):
                keys = {4:('BaseCoverage','BaseArray','BaseRecord','BaseCount'),
                        5:('LigatureCoverage','LigatureArray','LigatureAttach','LigatureCount'),
                        6:('Mark2Coverage','Mark2Array','Mark2Record','Mark2Count')}[kind]
                cov, array, field, count = keys
                box = getattr(t,array)
                data = getattr(box,field)
                add_coverage(getattr(t,cov),variants,data)
                setattr(box,count,len(data))
            else:
                raise ValueError(f'Unreviewed positioning type {kind}/{t.Format}')


def outline(source, unit, sharp):
    scale = 50/unit
    source = QTransform.fromScale(scale, scale).map(source)
    path = QTransform.fromScale(1/scale, 1/scale).map(contour(source,sharp))
    target = TTGlyphPen(None)
    pen = Cu2QuPen(target, 1, reverse_direction=False)
    i = 0
    while i < path.elementCount():
        e = path.elementAt(i)
        if e.isMoveTo():
            if i: pen.closePath()
            pen.moveTo((e.x,e.y))
        elif e.isLineTo():
            pen.lineTo((e.x,e.y))
        elif e.isCurveTo():
            c, end = path.elementAt(i+1), path.elementAt(i+2)
            pen.curveTo((e.x,e.y),(c.x,c.y),(end.x,end.y))
            i += 2
        i += 1
    if i: pen.closePath()
    return target.glyph()


def build(stem, dest):
    path = ROOT/'system_files/usr/share/fonts/meyar'/f'Meyar{stem}[wght].ttf'
    f = instantiateVariableFont(TTFont(path), {'wght':400})
    cmap = f.getBestCmap()
    letters = {n for c,n in cmap.items() if unicodedata.category(chr(c)).startswith('L')}
    nonletters = {n for c,n in cmap.items() if not unicodedata.category(chr(c)).startswith('L')}
    classes = f['GDEF'].table.GlyphClassDef.classDefs
    # Arabic contextual forms carry no Unicode codepoint. Follow the pinned
    # font's substitution outputs from letters, retaining mark/digit boundaries.
    for _ in range(5):
        for look in f['GSUB'].table.LookupList.Lookup:
            for sub in look.SubTable:
                s = getattr(sub,'ExtSubTable',sub)
                for n,v in getattr(s,'mapping',{}).items():
                    if n in letters:
                        produced = [v] if isinstance(v, str) else v
                        letters.update(g for g in produced if classes.get(g) != 3 and g not in nonletters)
                for n, ligs in getattr(s,'ligatures',{}).items():
                    if n in letters:
                        letters.update(l.LigGlyph for l in ligs if all(v in letters for v in l.Component))
    names = [n for n in f.getGlyphOrder() if n in letters-nonletters and classes.get(n)!=3]
    variants = {n:(n+'.entry',n+'.exit') for n in names}
    glyphset = f.getGlyphSet()
    additions = {}
    for n in names:
        pen = QtPen(glyphset, QPainterPath())
        glyphset[n].draw(pen)
        for v, sharp in zip(variants[n],(True,False)):
            additions[v] = outline(pen.path, f['head'].unitsPerEm, sharp)
            f['hmtx'].metrics[v] = f['hmtx'].metrics[n]
    order = f.getGlyphOrder() + list(additions)
    f['glyf'].glyphs.update(additions)
    f.setGlyphOrder(order)
    expand_positioning(f,variants)
    install_word_feature(f,variants)
    family = 'Meyar Form '+stem
    for rec in f['name'].names:
        if rec.nameID in (1,2,3,4,6,16,17):
            name={1:family,2:'Regular',3:family+' Regular 0.1',4:family+' Regular',6:family.replace(' ','')+'-Regular',16:family,17:'Regular'}[rec.nameID]
            rec.string=name.encode(rec.getEncoding())
    dest.mkdir(parents=True, exist_ok=True)
    f.recalcTimestamp = False
    f['head'].modified = TTFont(path)['head'].modified
    f.save(dest/(family.replace(' ','')+'-Regular.ttf'))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    args=parser.parse_args()
    for family in ('Arabic','Sans'):
        build(family,args.directory)
