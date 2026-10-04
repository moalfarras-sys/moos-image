#!/usr/bin/env python3
"""Composition-only review from shipped assets. Native/boot proof is separate."""
import argparse
from pathlib import Path
import re
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
THEME = ROOT / 'system_files/usr/share/plymouth/themes/moos'

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--width', type=int, default=1920)
    parser.add_argument('--height', type=int, default=1080)
    parser.add_argument('--out', type=Path, required=True, help='review artifact directory')
    args = parser.parse_args()
    text = (THEME / 'moos.script').read_text()
    geometry = re.search(r'stage_w = fmin\(sw \* ([0-9.]+), sh \* ([0-9.]+) \* INTRO_ASPECT\)', text)
    aspect = float(re.search(r'INTRO_ASPECT = ([0-9.]+);', text)[1])
    if not geometry or args.width <= 0 or args.height <= 0:
        raise SystemExit('invalid geometry')
    w, h = args.width, args.height
    backdrop = Image.open(THEME / 'boot-backdrop.png').convert('RGBA')
    scale = max(w / backdrop.width, h / backdrop.height)
    backdrop = backdrop.resize((round(backdrop.width * scale), round(backdrop.height * scale)), Image.Resampling.LANCZOS)
    frame = backdrop.crop(((backdrop.width-w)//2, (backdrop.height-h)//2,
                           (backdrop.width+w)//2, (backdrop.height+h)//2))
    stage_w = min(w * float(geometry[1]), h * float(geometry[2]) * aspect)
    hero = Image.open(THEME / 'intro1.png').convert('RGBA').resize((round(stage_w), round(stage_w/aspect)), Image.Resampling.LANCZOS)
    frame.alpha_composite(hero, ((w-hero.width)//2, (h-hero.height)//2))
    args.out.mkdir(parents=True, exist_ok=True)
    frame.save(args.out / f'composition-{w}x{h}.png')
    print('Composition artifact only; does not prove native rendering or boot.')

if __name__ == '__main__':
    main()
