#!/usr/bin/env python3
"""Generate the MoOS keyboard's emoji data from Plasma's own emoji dictionaries.

    python3 scripts/generate_keyboard_emoji.py [--source /usr/share/plasma/emoji] [--check]

Plasma's emoji picker (plasma-desktop) ships one dictionary per language, built from
Unicode CLDR: every emoji in Unicode order, its category, its name and its search
keywords, translated. MoOS's on-screen keyboard reads the same data so its emoji sheet,
its Touch Bar suggestions and its accessible names say what KDE's picker says, in Arabic
and in English (German keywords too: German is a keyboard layout here).

The dictionaries are qCompress'd: a 4-byte big-endian length, then zlib, then a
little-endian stream of (u32 count, then per emoji: string content, string name,
u32 category, u32 keyword count, strings). A string is a u32 byte length and UTF-8.

Output: system_files/usr/lib64/qt6/qml/org/moos/keyboard/EmojiData.js, a `.pragma
library` file the keyboard imports once. --check regenerates in memory and fails when the
committed file differs (the image's Plasma moved its CLDR data).
"""
from __future__ import annotations

import argparse
import json
import re
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "system_files/usr/lib64/qt6/qml/org/moos/keyboard/EmojiData.js"
LANGUAGES = ("ar", "en", "de")
NAME_LANGUAGES = ("ar", "en")
# Plasma's category numbers (emojier's Emoji::Category). 3 is "Component" (bare skin-tone
# and hair modifiers), which a picker never offers on its own.
CATEGORIES = (
    (1, "smileys", "😀", "الوجوه والمشاعر", "Smileys & Emotion"),
    (2, "people", "👋", "الناس والجسد", "People & Body"),
    (4, "nature", "🐻", "الحيوانات والطبيعة", "Animals & Nature"),
    (5, "food", "🍔", "الطعام والشراب", "Food & Drink"),
    (6, "travel", "✈", "السفر والأماكن", "Travel & Places"),
    (7, "activities", "⚽", "الأنشطة", "Activities"),
    (8, "objects", "💡", "الأشياء", "Objects"),
    (9, "symbols", "♥", "الرموز", "Symbols"),
    (10, "flags", "🏳", "الأعلام", "Flags"),
)
# The most used emoji (Unicode's published emoji frequency ranking, its top rows), plus
# the open hands Arabic writers use for a prayer. They rank first among equal keyword
# matches and seed the Touch Bar until a person has recent emoji of their own.
POPULAR = ("😂❤️🤣👍😭🙏😘🥰😍😊🎉😁💕🥺😅🔥☺️🤦♥️🤷🙄😆🤗😉🎂🤔👏🙂😳🥳😎👌💜😔💪✨💖👀😋"
           "😏😢👉💗😩💯🌹💞🎈💙😃😡💐😜🙈🤞😄🤤🙌🤪❣️😀💋💀👇💔😌💓🤩🙃😬😱😴🤭😐🌞😒😇🌸"
           "😈🎶✌️🎊🥵😞💚☀️🖤💰😚👑🎁💥🙋☹️😑🥴👈💩✅🤲🌙")
TONES = tuple(chr(c) for c in range(0x1F3FB, 0x1F400))
VS16 = "️"
# Arabic marks Hunspell and a person never type: tashkeel, tatweel, superscript alef.
ARABIC_MARKS = re.compile("[ؐ-ًؚ-ٰٟۖ-ۭـ]")
WORD = re.compile(r"[^\W_]+", re.UNICODE)


def load(path: Path) -> list[tuple[str, str, int, list[str]]]:
    data = path.read_bytes()
    raw = zlib.decompress(data[4:])
    if struct.unpack(">I", data[:4])[0] != len(raw):
        raise SystemExit(f"{path}: qCompress length does not match its zlib payload")
    offset = 0

    def u32() -> int:
        nonlocal offset
        value = struct.unpack_from("<I", raw, offset)[0]
        offset += 4
        return value

    def text() -> str:
        nonlocal offset
        size = u32()
        value = raw[offset:offset + size].decode("utf-8")
        offset += size
        return value

    out = []
    for _ in range(u32()):
        content, name, category = text(), text(), u32()
        out.append((content, name, category, [text() for _ in range(u32())]))
    if offset != len(raw):
        raise SystemExit(f"{path}: {len(raw) - offset} trailing bytes; the dictionary format changed")
    return out


def normalize(word: str) -> str:
    """The same folding TouchBarLogic.normalize applies to what a person types."""
    word = ARABIC_MARKS.sub("", word.casefold())
    return (word.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ٱ", "ا")
            .replace("ى", "ي").replace("ة", "ه"))


def bare(content: str) -> str:
    return "".join(ch for ch in content if ch not in TONES and ch != VS16)


def split_emoji(text: str, known: set[str]) -> list[str]:
    """Split a run of emoji into known emoji (longest match first)."""
    out, i = [], 0
    while i < len(text):
        for size in range(min(8, len(text) - i), 0, -1):
            if bare(text[i:i + size]) in known:
                out.append(text[i:i + size])
                i += size
                break
        else:
            raise SystemExit(f"POPULAR has an unknown emoji at {text[i:i + 4]!r}")
    return out


def build(source: Path) -> str:
    dictionaries = {lang: load(source / f"{lang}.dict") for lang in LANGUAGES}
    # The same emoji in every language. en.dict sorts a few of them differently (it puts
    # 👨 before 👱); ar.dict and de.dict keep Unicode's order, so Arabic's order is used.
    order = [entry[0] for entry in dictionaries["ar"]]
    for lang, entries in dictionaries.items():
        if sorted(entry[0] for entry in entries) != sorted(order):
            raise SystemExit(f"{lang}.dict lists different emoji from ar.dict")
    known = {number for number, *_ in CATEGORIES}
    base = [entry for entry in dictionaries["ar"]
            if entry[2] in known and not any(tone in entry[0] for tone in TONES)]
    # Skin tones: the five variants that carry one tone (repeated for every person in it).
    variants: dict[int, list[str]] = {}
    by_bare = {bare(entry[0]): i for i, entry in enumerate(base)}
    for content, *_ in dictionaries["ar"]:
        present = {tone for tone in TONES if tone in content}
        if len(present) == 1 and bare(content) in by_bare:
            variants.setdefault(by_bare[bare(content)], []).append(content)
    tones = {index: found for index, found in variants.items() if len(found) == 5}

    starts, previous = [], None
    for i, entry in enumerate(base):
        if entry[2] != previous:
            if entry[2] in [n for n, *_ in CATEGORIES[:len(starts)]]:
                raise SystemExit("an emoji category is not contiguous in Plasma's order")
            starts.append(i)
            previous = entry[2]
    if len(starts) != len(CATEGORIES) or [base[s][2] for s in starts] != [n for n, *_ in CATEGORIES]:
        raise SystemExit("Plasma's emoji categories changed; review CATEGORIES")

    popular = [bare(e) for e in split_emoji(POPULAR, {bare(entry[0]) for entry in base})]
    popularity = {e: rank for rank, e in reversed(list(enumerate(popular)))}
    names = {}
    keywords = {}
    for lang in LANGUAGES:
        rows = {entry[0]: entry for entry in dictionaries[lang]}
        if lang in NAME_LANGUAGES:
            names[lang] = [rows[entry[0]][1] for entry in base]
        index: dict[str, dict[int, tuple[int, int]]] = {}
        for i, entry in enumerate(base):
            content, name, _category, annotations = rows[entry[0]]
            # Rank 0: a word of its name ("قلب أحمر" for ❤️); 1: a whole keyword;
            # 2: a word inside a longer keyword. A popular emoji matched by its name or a
            # whole keyword leads them all.
            for rank, phrases in ((0, [name]), (1, annotations), (2, annotations)):
                for phrase in phrases:
                    tokens = ([normalize(phrase)] if rank == 1
                              else [normalize(t) for t in WORD.findall(phrase)])
                    for token in tokens:
                        if len(token) < 2 or " " in token:
                            continue
                        bucket = index.setdefault(token, {})
                        known = popularity.get(bare(content), len(popularity))
                        key = (0 if known < len(popularity) and rank < 2 else 1, rank, known)
                        if i not in bucket or key < bucket[i]:
                            bucket[i] = key
        keywords[lang] = {token: ",".join(str(i) for i, _key in sorted(bucket.items(),
                                                                         key=lambda item: (item[1], item[0])))
                          for token, bucket in sorted(index.items())}

    def js(value) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    header = (
        "// Generated by scripts/generate_keyboard_emoji.py from Plasma's emoji dictionaries\n"
        "// (/usr/share/plasma/emoji, Unicode CLDR data, Unicode License v3); do not edit.\n"
        ".pragma library\n\n"
    )
    body = [
        f"var emoji = {js([entry[0] for entry in base])};",
        "var categories = " + js([{"key": key, "glyph": glyph, "ar": ar, "en": en, "start": start}
                                   for (_n, key, glyph, ar, en), start in zip(CATEGORIES, starts)]) + ";",
        "var popular = " + js([by_bare[bare(e)] for e in split_emoji(POPULAR, set(by_bare))]) + ";",
        "var tones = " + js({str(i): found for i, found in sorted(tones.items())}) + ";",
        "var names = " + js(names) + ";",
        "var keywords = " + js(keywords) + ";",
    ]
    return header + "\n".join(body) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("/usr/share/plasma/emoji"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = build(args.source)
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != text:
            print(f"{OUTPUT.relative_to(ROOT)} is stale: rerun scripts/generate_keyboard_emoji.py",
                  file=sys.stderr)
            return 1
        print("keyboard emoji data matches Plasma's dictionaries")
        return 0
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)} ({len(text.encode())} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
