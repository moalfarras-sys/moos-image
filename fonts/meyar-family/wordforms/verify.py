"""Compare contextual forms, mark positions and advances with the native source."""
import argparse
from pathlib import Path
import uharfbuzz as hb
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[3]
SAMPLES = {
    'Arabic': ['مِعْيَارٌ', 'العَرَبِيَّةُ', 'الملفات', 'الشَّاشَةُ', 'لَا', 'ببب', 'اتّصال', 'موج،موج', '١٢٣'],
    'Sans': ['Meyar', 'Waveform', 'Architecture', 'office', 'office file', 'Éditeur',
             'Καλημέρα', 'Клавиатура', 'MoOS', 'a'*64, '1+2=3', 'A\u0301BC'],
}


def shape(path, text):
    table = TTFont(path)
    font = hb.Font(hb.Face(path.read_bytes()))
    font.set_variations({'wght':400})
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font,buf)
    return [(table.getGlyphName(i.codepoint), i.cluster, p.x_advance, p.y_advance, p.x_offset, p.y_offset)
            for i,p in zip(buf.glyph_infos,buf.glyph_positions)]


def verify(directory):
    for family, words in SAMPLES.items():
        src = ROOT/'system_files/usr/share/fonts/meyar'/f'Meyar{family}[wght].ttf'
        dst = directory/f'MeyarForm{family}-Regular.ttf'
        for text in words:
            original, new = shape(src,text), shape(dst,text)
            clean = [(name.removesuffix('.entry').removesuffix('.exit'), *rest) for name,*rest in new]
            assert clean == original, (family,text,clean,original)
            if text.isalpha() or text == 'مِعْيَارٌ' or text == 'العَرَبِيَّةُ':
                forms = sorted((cluster,name.rsplit('.',1)[-1]) for name,cluster,*_ in new
                               if name.endswith(('.entry','.exit')))
                assert forms and [f for _,f in forms] == ['entry']*((len(forms)+1)//2) + ['exit']*(len(forms)//2), (text,forms)
                if text in ('مِعْيَارٌ','العَرَبِيَّةُ'):
                    assert len(forms) == sum(c.isalpha() for c in text), (text,forms)
    print(sum(map(len,SAMPLES.values())), 'native shaping comparisons passed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    verify(parser.parse_args().directory)
