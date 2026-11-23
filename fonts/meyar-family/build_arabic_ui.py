#!/usr/bin/env python3
"""Build Meyar Arabic from Tajawal, completed with the reviewed Arabic-script coverage.

Owner steering, 2026-11-23: Meyar Arabic should have the quality of Tajawal, the
Arabic face the owner chose. Meyar Arabic therefore takes Tajawal's outlines,
spacing, kerning, mark positioning and vertical metrics unchanged (OFL-1.1,
Copyright 2018 Boutros International; no Reserved Font Name), under the family
name every MoOS surface already requests. Tajawal covers the Arabic language but
not every Arabic-script letter MoOS promises: the image gate requires پ ژ گ چ, and
the previous Meyar Arabic also carried Persian, Urdu, Kurdish and the Supplement and
Extended-A blocks. Only the code points Tajawal lacks are taken from that reviewed
coverage font (the Noto-derived build of `build.py arabic`), instanced at the same
weight, so no character is lost and Arabic text is Tajawal's alone.

Tajawal registers its positioning only under the DFLT script. Merged naively with a
font that has an `arab` script, HarfBuzz picks `arab` and drops every Tajawal mark
offset and kern. The builder makes Tajawal's registration explicit first; --verify
then requires byte-identical shaping (glyphs, advances, offsets) against Tajawal on
an Arabic corpus with harakat, Quranic text, lam-alef, digits and Latin.

    python3 fonts/meyar-family/build_arabic_ui.py \\
        --fill test-results/meyar-family/arabic/MeyarArabic[wght].ttf \\
        --output test-results/meyar-family/arabic-ui [--verify]
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

from fontTools import subset
from fontTools.merge import Merger, Options
from fontTools.pens.statisticsPen import StatisticsPen
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables
from fontTools.varLib import instancer

ROOT = Path(__file__).resolve().parent
UPSTREAM = ROOT / "upstream-tajawal"
LOCK = ROOT / "upstream-tajawal-lock.json"
STYLES = {"ExtraLight": 200, "Light": 300, "Regular": 400, "Medium": 500,
          "Bold": 700, "ExtraBold": 800, "Black": 900}
FAMILY = "Meyar Arabic"
# Arabic-script blocks whose code points the coverage font may contribute.
FILL_RANGES = ((0x0600, 0x06FF), (0x0750, 0x077F), (0x0870, 0x089F), (0x08A0, 0x08FF),
               (0xFB50, 0xFDFF), (0xFE70, 0xFEFF), (0x10E60, 0x10E7F), (0x1EE00, 0x1EEFF))
EPOCH = 0x7C259DC0  # 2001-01-01 in head time; fixed so builds are reproducible
CORPUS = ("مرحبًا بك في نظام MoOS", "مُحَمَّدٌ رَسُولُ اللَّهِ", "الإعدادات والملفات",
          "إلى اللقاء لله", "قُلْ هُوَ اللَّهُ أَحَدٌ", "لأنّ الأمرَ ليس لعبة",
          "تطبيقاتك المفضّلة", "١٢٣٤٥ 12345", "Settings MoOS 2026", "؟ ، ؛ « »",
          "سيظهر الطقس المحلي تلقائياً", "بانتظار القراءة", "الاثنين، ٢٣ نوفمبر ٢٠٢٦",
          "خيارات الجلسة", "إِنَّ مَعَ الْعُسْرِ يُسْرًا", "أؤ إئ آ ءٌ ىً")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_lock() -> None:
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    present = {p.name for p in UPSTREAM.iterdir()}
    if present != set(lock["files"]):
        raise SystemExit("upstream-tajawal differs from its lock: " + str(sorted(present ^ set(lock["files"]))))
    for name, entry in lock["files"].items():
        if sha256(UPSTREAM / name) != entry["sha256"]:
            raise SystemExit("Tajawal upstream drift: " + name)


def explicit_scripts(font: TTFont) -> None:
    """Register Tajawal's DFLT features under arab and latn too (see the module note)."""
    for tag in ("GSUB", "GPOS"):
        table = font[tag].table
        records = {r.ScriptTag: r for r in table.ScriptList.ScriptRecord}
        for script in ("arab", "latn"):
            if script not in records:
                record = otTables.ScriptRecord()
                record.ScriptTag = script
                record.Script = copy.deepcopy(records["DFLT"].Script)
                table.ScriptList.ScriptRecord.append(record)
        table.ScriptList.ScriptRecord.sort(key=lambda r: r.ScriptTag)
        table.ScriptList.ScriptCount = len(table.ScriptList.ScriptRecord)


# Letters both fonts draw, measured as ink area per advance: the visual "colour" of a weight.
COLOUR_SAMPLE = "بتثسشصضطظفقكلمنهي"


def colour(font: TTFont) -> float:
    glyphs, cmap, values = font.getGlyphSet(), font.getBestCmap(), []
    for char in COLOUR_SAMPLE:
        pen = StatisticsPen(glyphset=glyphs)
        glyphs[cmap[ord(char)]].draw(pen)
        values.append(abs(pen.area) / glyphs[cmap[ord(char)]].width)
    return sum(values) / len(values)


def matched_weights(fill_path: Path) -> dict[str, float]:
    """Each Tajawal face's colour, found on the coverage font's weight axis.

    Tajawal's Regular is as dark as the coverage font near wght 333, not 400: instancing
    by the numeric weight drew Persian letters 29% heavier than the Tajawal letters
    beside them. Sample the axis and interpolate to equal colour instead.
    """
    curve = [(w, colour(instancer.instantiateVariableFont(TTFont(fill_path), {"wght": w})))
             for w in range(100, 901, 50)]
    matched = {}
    for style in STYLES:
        target = colour(TTFont(UPSTREAM / f"Tajawal-{style}.ttf"))
        weight = curve[0][0] if target <= curve[0][1] else curve[-1][0]
        for (w0, c0), (w1, c1) in zip(curve, curve[1:]):
            if c0 <= target <= c1:
                weight = w0 + (w1 - w0) * (target - c0) / (c1 - c0)
                break
        matched[style] = round(weight, 1)
    return matched


def coverage_fill(fill_path: Path, weight: float, have: set[int], scratch: Path) -> tuple[Path, list[int]]:
    font = instancer.instantiateVariableFont(TTFont(fill_path), {"wght": weight})
    for table in ("fvar", "gvar", "avar", "STAT", "HVAR", "MVAR", "cvar"):
        if table in font:
            del font[table]
    wanted = sorted(cp for cp in font.getBestCmap()
                    if cp not in have and any(lo <= cp <= hi for lo, hi in FILL_RANGES))
    options = subset.Options()
    options.layout_features = ["*"]
    options.name_IDs = ["*"]
    options.glyph_names = True
    options.notdef_outline = True
    sub = subset.Subsetter(options)
    sub.populate(unicodes=wanted)
    sub.subset(font)
    path = scratch / f"fill-{weight:g}.ttf"
    font.save(path)
    return path, wanted


def set_names(font: TTFont, style: str) -> None:
    ribbi = style in ("Regular", "Bold")
    legacy_family = FAMILY if ribbi else f"{FAMILY} {style}"
    legacy_style = style if ribbi else "Regular"
    postscript = "MeyarArabic-" + style
    table = font["name"]
    keep = {0, 7, 8, 9, 11, 12, 13, 14}
    for record in list(table.names):
        if record.nameID not in keep:
            table.removeNames(nameID=record.nameID)
    copyright_ = ("Copyright 2018 Boutros International (http://www.boutrosfonts.com). "
                  "Arabic-script coverage completion: Copyright 2022 The Noto Project Authors "
                  "(https://github.com/notofonts/arabic).")
    values = {0: copyright_, 1: legacy_family, 2: legacy_style,
              3: f"1.700;MOOS;{postscript}", 4: f"{FAMILY} {style}",
              5: "Version 1.700; Meyar Arabic from Tajawal 1.700 with Noto Arabic coverage",
              6: postscript, 16: FAMILY, 17: style}
    for name_id, text in values.items():
        table.setName(text, name_id, 3, 1, 0x409)
        table.setName(text, name_id, 1, 0, 0)
    table.removeNames(nameID=16, platformID=1)
    table.removeNames(nameID=17, platformID=1)
    if ribbi:
        table.removeNames(nameID=16)
        table.removeNames(nameID=17)


def build_style(style: str, fill_path: Path, out: Path, scratch: Path, fill_weight: float) -> dict:
    weight = STYLES[style]
    base_path = UPSTREAM / f"Tajawal-{style}.ttf"
    base = TTFont(base_path)
    explicit_scripts(base)
    explicit = scratch / f"tajawal-{style}.ttf"
    base.save(explicit)
    fill, wanted = coverage_fill(fill_path, fill_weight, set(base.getBestCmap()), scratch)
    merged = Merger(Options(drop_tables=["vhea", "vmtx", "DSIG", "meta", "STAT"])).merge([str(explicit), str(fill)])
    set_names(merged, style)
    tajawal = TTFont(base_path)
    merged["hhea"].ascent, merged["hhea"].descent, merged["hhea"].lineGap = (
        tajawal["hhea"].ascent, tajawal["hhea"].descent, tajawal["hhea"].lineGap)
    os2, src = merged["OS/2"], tajawal["OS/2"]
    os2.sTypoAscender, os2.sTypoDescender, os2.sTypoLineGap = (
        src.sTypoAscender, src.sTypoDescender, src.sTypoLineGap)
    os2.usWeightClass, os2.fsSelection = src.usWeightClass, src.fsSelection
    merged["head"].macStyle = tajawal["head"].macStyle
    # Clip bounds only: line metrics stay Tajawal's.
    glyf = merged["glyf"]
    y_max = max(getattr(glyf[g], "yMax", 0) for g in merged.getGlyphOrder() if glyf[g].numberOfContours)
    y_min = min(getattr(glyf[g], "yMin", 0) for g in merged.getGlyphOrder() if glyf[g].numberOfContours)
    os2.usWinAscent = max(src.usWinAscent, y_max)
    os2.usWinDescent = max(src.usWinDescent, -y_min)
    merged["head"].created = merged["head"].modified = EPOCH
    merged["head"].fontRevision = tajawal["head"].fontRevision
    target = out / f"MeyarArabic-{style}.ttf"
    merged.recalcTimestamp = False
    merged.save(target, reorderTables=True)
    return {"file": target.name, "weight": weight, "coverageWeight": fill_weight,
            "fromTajawal": len(base.getBestCmap()),
            "fromCoverage": len(wanted), "codepoints": len(merged.getBestCmap()),
            "sha256": sha256(target)}


def shape(path: Path, text: str):
    import uharfbuzz as hb
    font = hb.Font(hb.Face(hb.Blob.from_file_path(str(path))))
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf, {})
    return [(font.glyph_to_string(i.codepoint), i.cluster, p.x_advance, p.x_offset, p.y_offset)
            for i, p in zip(buf.glyph_infos, buf.glyph_positions)]


def verify(out: Path, fill_path: Path) -> dict:
    fill_cmap = {cp for cp in TTFont(fill_path).getBestCmap()
                 if any(lo <= cp <= hi for lo, hi in FILL_RANGES)}
    report = {"styles": {}, "pass": True}
    for style in STYLES:
        built = out / f"MeyarArabic-{style}.ttf"
        upstream = UPSTREAM / f"Tajawal-{style}.ttf"
        identical = [text for text in CORPUS if shape(built, text) == shape(upstream, text)]
        cmap = set(TTFont(built).getBestCmap())
        lost = sorted(fill_cmap - cmap)
        persian = all(ord(c) in cmap for c in "پژگچکی")
        ok = len(identical) == len(CORPUS) and not lost and persian
        report["styles"][style] = {"identicalToTajawal": f"{len(identical)}/{len(CORPUS)}",
                                   "lostCoverage": len(lost), "persianLetters": persian}
        report["pass"] = report["pass"] and ok
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--fill", type=Path, required=True,
                        help="the reviewed coverage font: build.py arabic's MeyarArabic[wght].ttf")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    verify_lock()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    scratch = out / "work"
    scratch.mkdir(exist_ok=True)
    weights = matched_weights(args.fill)
    rows = [build_style(style, args.fill, out, scratch, weights[style]) for style in STYLES]
    for path in scratch.iterdir():
        path.unlink()
    scratch.rmdir()
    result = {"family": FAMILY, "upstream": json.loads(LOCK.read_text())["commit"], "faces": rows}
    if args.verify:
        result["verification"] = verify(out, args.fill)
    (out / "build.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result.get("verification", {"faces": len(rows)}), ensure_ascii=False))
    return 0 if result.get("verification", {"pass": True})["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
