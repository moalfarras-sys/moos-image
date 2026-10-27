#!/usr/bin/env python3
"""Native Qt specimen; image is private review evidence, not an OS mockup."""
import argparse
import json
from pathlib import Path
from PySide6.QtGui import QGuiApplication,QFontDatabase,QFont,QImage,QPainter,QColor,QTextLayout,QTextOption,QFontMetricsF
from PySide6.QtCore import Qt,QPointF,QRectF


def main():
    p=argparse.ArgumentParser();p.add_argument('fonts',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    app=QGuiApplication([])
    for name in ('Regular','Medium','Bold','Black'):
        assert QFontDatabase.addApplicationFont(str((a.fonts/f'MeyarArabic-{name}.ttf').resolve()))>=0
    image=QImage(1500,1750,QImage.Format.Format_ARGB32_Premultiplied);image.fill(QColor('#f6f4ee'))
    painter=QPainter(image);painter.setPen(QColor('#142d3a'));painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    y=30;readback=[]
    def row(text,size=32,weight=400):
        nonlocal y
        f=QFont('Meyar Arabic');f.setPixelSize(size);f.setWeight(QFont.Weight(weight))
        layout=QTextLayout(text,f);option=QTextOption();option.setTextDirection(Qt.LayoutDirection.RightToLeft)
        option.setAlignment(Qt.AlignmentFlag.AlignRight);layout.setTextOption(option);layout.beginLayout()
        line=layout.createLine();line.setLineWidth(1380);line.setPosition(QPointF(0,0));layout.endLayout()
        layout.draw(painter,QPointF(60,y));readback.append({'text':text,'size':size,'weight':weight,'height':line.height(),'width':line.naturalTextWidth()})
        y+=line.height()+15
    row('مِعيار — العربية أولًا',57,500)
    row('خط عربي مشتق من مصدر مفتوح، بوصلٍ وتشكيلٍ صحيحين.',30)
    row('مرحبًا بك في نظام MoOS — الإعدادات والتطبيقات والملفات',32)
    row('محمد، إبراهيم، مريم، جميلة، يوسف — القراءة والكتابة',32)
    row('ببب تتت ثثث ججج ححح خخخ سسس ششش صصص ضضض',30)
    row('ططط ظظظ ععع غغغ ففف ققق ككك للل ممم ننن ههه ييي',30)
    row('لا — لأ — لإ — لآ — بلا — بلأ — بلإ — بلآ',32)
    row('أَ أَّ آَّ إِّ بَّ بِّ — مِعْيَارٌ — لَأ — لأَ — لإِ',34)
    row('پژوهش فارسی — پاکستان اردو — پ چ ژ ک گ ی',30)
    row('١٢٣٤٥٦٧٨٩٠ — ۱۲۳۴۵۶۷۸۹۰ — 0123456789',30)
    row('MoOS 24.10 — الشاشة والصوت — /home/moos/ملفات — 125,50 €',26)
    for size in (11,12,14,16):row('الإعدادات والمظهر — اختر خلفية سطح المكتب — الملفات والتطبيقات',size)
    for weight in (400,500,700,900):row('مِعيار — نظامٌ عربيٌّ واضحٌ وجميل',32,weight)
    painter.end();assert y<image.height(),('Specimen clipping',y);assert image.save(str(a.output))
    (a.output.with_suffix('.json')).write_text(json.dumps({'heightUsed':y,'rows':readback,'source':'actual compiled Meyar Arabic via native Qt'},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'image':str(a.output),'heightUsed':y}))


if __name__=='__main__':main()
