"""Measure where each expression frame's face sits, so every frame can be shown with one framing.

The two faces arrive as sprite sheets whose cells differ in size, scale and head position
(`mira-rose-frames-v3.png` cells are square, the expression sheets are portrait). Showing them as
they are makes the head jump on every expression change. This tool finds, for each cell, the scale
and offset of the face relative to the style's reference cell by normalised cross-correlation of the
eyes-to-chin region, and writes `faces.json`: for every expression, the source sheet and the crop
rectangle (in sheet pixels) of one canonical portrait square. The app only crops; it never alters the
artwork. Run it again only when a sheet changes:

    python devtools/align_faces.py            # needs numpy + Pillow
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]

# Grid layout and the expression each cell shows, exactly as the original app sliced them.
SHEETS = {
    'rose': [
        ('mira-rose-frames-v3.png', 2, 2, ['neutral', 'speaking_open', 'speaking_round', 'blink']),
        ('mira-expressions-a.png', 3, 2, ['happy', 'excited', 'playful', 'thinking', 'sad', 'annoyed']),
        ('mira-expressions-b.png', 3, 2, ['attentive', 'surprised', 'reassuring', 'curious', 'proud', 'sleepy']),
    ],
    'holo': [
        ('mira-holo-moods-v1.png', 3, 2, ['neutral', 'excited', 'curious', 'attentive', 'sad', 'annoyed']),
        ('mira-holo-moods-2-v1.png', 3, 2, ['playful', 'thinking', 'surprised', 'proud', 'reassuring', 'sleepy']),
        ('mira-holo-speech-v1.png', 3, 1, ['blink', 'speaking_round', 'speaking_open']),
    ],
}
# Eyebrows-to-chin region of each style's reference cell (cell pixels) and the portrait square
# (centre and half side, reference cell pixels) that every frame is framed to.
REFERENCE = {
    'rose': {'cell': ('mira-rose-frames-v3.png', 0), 'roi': (195, 195, 435, 450), 'centre': (314, 300), 'half': 236},
    'holo': {'cell': ('mira-holo-moods-v1.png', 0), 'roi': (90, 205, 330, 455), 'centre': (208, 305), 'half': 196},
}
WORK = 0.25  # correlation runs at quarter resolution, then refines at half


def load(sheet):
    return Image.open(ROOT / sheet).convert('L')


def cells(sheet, cols, rows):
    image = load(sheet)
    w, h = image.width // cols, image.height // rows
    for index in range(cols * rows):
        x, y = index % cols, index // cols
        yield index, (x * w, y * h, w, h), image.crop((x * w, y * h, x * w + w, y * h + h))


def as_array(image, scale):
    size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    return np.asarray(image.resize(size, Image.LANCZOS), dtype=np.float64)


def ncc(frame, template):
    """Normalised cross-correlation of template over every valid position in frame."""
    th, tw = template.shape
    fh, fw = frame.shape
    if th > fh or tw > fw:
        return None
    t = template - template.mean()
    tnorm = np.sqrt((t * t).sum()) or 1.0
    shape = (fh + th, fw + tw)
    corr = np.fft.irfft2(np.fft.rfft2(frame, shape) * np.conj(np.fft.rfft2(t, shape)), shape)[:fh - th + 1, :fw - tw + 1]
    ii = np.pad(frame, ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    ii2 = np.pad(frame * frame, ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    def window(a):
        return a[th:, tw:] - a[:-th, tw:] - a[th:, :-tw] + a[:-th, :-tw]
    s, s2 = window(ii), window(ii2)
    n = th * tw
    var = np.maximum(s2 - s * s / n, 1e-9)
    return corr / (np.sqrt(var) * tnorm)


def locate(frame_img, template_img, scales, work):
    frame = as_array(frame_img, work)
    best = (-2, None, None)
    for scale in scales:
        template = as_array(template_img, work * scale)
        score = ncc(frame, template)
        if score is None:
            continue
        y, x = np.unravel_index(np.argmax(score), score.shape)
        if score[y, x] > best[0]:
            best = (float(score[y, x]), scale, (x / work, y / work))
    return best


def main():
    result = {'version': 1, 'styles': {}}
    for style, sheets in SHEETS.items():
        ref = REFERENCE[style]
        ref_sheet, ref_index = ref['cell']
        layout = next((cols, rows) for name, cols, rows, _ in sheets if name == ref_sheet)
        ref_cell = dict((i, img) for i, _, img in cells(ref_sheet, *layout))[ref_index]
        x0, y0, x1, y1 = ref['roi']
        template = ref_cell.crop((x0, y0, x1, y1))
        frames = {}
        for sheet, cols, rows, names in sheets:
            for index, (cx, cy, cw, ch), img in cells(sheet, cols, rows):
                coarse = locate(img, template, np.arange(0.70, 1.65, 0.03), WORK)
                fine = locate(img, template, np.arange(coarse[1] - 0.03, coarse[1] + 0.031, 0.006), 0.5)
                score, scale, (tx, ty) = fine
                # Map the reference portrait square into this cell: p_cell = scale * (p_ref - roi0) + t.
                centre_x = scale * (ref['centre'][0] - x0) + tx
                centre_y = scale * (ref['centre'][1] - y0) + ty
                half = scale * ref['half']
                frames[names[index]] = {
                    'sheet': sheet,
                    'cell': [cx, cy, cw, ch],
                    'crop': [round(float(cx + centre_x - half), 1), round(float(cy + centre_y - half), 1),
                             round(float(2 * half), 1), round(float(2 * half), 1)],
                    'score': round(float(score), 3),
                }
                print(f'{style:5s} {names[index]:15s} score={score:.3f} scale={scale:.3f} '
                      f'crop={frames[names[index]]["crop"]} cell={cw}x{ch}')
        result['styles'][style] = frames
    (ROOT / 'faces.json').write_text(json.dumps(result, indent=1) + '\n')


def motion_frames():
    """Register only new motion patches; preserve every existing face calibration.

    Match the stable nose/cheek bridge, excluding changing eyelids and lips.
    Originals remain the neutral/expressive/closed-blink source.
    """
    result = json.loads((ROOT / 'faces.json').read_text())
    for style in ('rose', 'holo'):
        ref = REFERENCE[style]
        original = next(c[2] for c in cells(ref['cell'][0], 2 if style == 'rose' else 3, 2)
                        if c[0] == 0)
        roi = (250, 275, 375, 345) if style == 'rose' else (165, 300, 250, 365)
        template = original.crop(roi)
        names = ('blink_half', 'speaking_small', 'speaking_medium', 'speaking_oo')
        sheet = 'mira-' + style + '-motion-v1.png'
        for index, (cx, cy, cw, ch), img in cells(sheet, 2, 2):
            coarse = locate(img, template, np.arange(0.65, 2.0, 0.025), WORK)
            fine = locate(img, template, np.arange(coarse[1] - 0.025, coarse[1] + 0.026, 0.005), 0.5)
            score, scale, (tx, ty) = fine
            if score < 0.75:
                raise ValueError(f'{style}/{names[index]} nose registration failed: {score:.3f}')
            x = cx + scale * (ref['centre'][0] - roi[0] - ref['half']) + tx
            y = cy + scale * (ref['centre'][1] - roi[1] - ref['half']) + ty
            side = 2 * scale * ref['half']
            result['styles'][style][names[index]] = {
                'sheet': sheet, 'cell': [cx, cy, cw, ch],
                'crop': [round(float(v), 1) for v in (x, y, side, side)],
                'score': round(float(score), 3)}
            print(style, names[index], result['styles'][style][names[index]])
    (ROOT / 'faces.json').write_text(json.dumps(result, indent=1) + '\n')


if __name__ == '__main__':
    if "--motion" not in sys.argv:
        main()
    motion_frames()
