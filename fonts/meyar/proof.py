#!/usr/bin/env python3
"""Render the actual compiled fonts with Qt's native shaping/rasterization.

This is a type specimen, not a substitute desktop or acceptance of installation.
"""
import argparse
import json
from pathlib import Path
from PySide6.QtGui import QGuiApplication,QImage,QPainter,QColor,QFont,QFontDatabase,QRawFont
from PySide6.QtCore import Qt,QRectF


def main():
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('output',type=Path);args=p.parse_args()
    app=QGuiApplication([])
    for style in ('Thin','Regular','Medium','Bold','Black'):
        file=args.directory/f'Meyar-{style}.ttf'
        assert QFontDatabase.addApplicationFont(str(file))>=0,file
    image=QImage(1440,1800,QImage.Format.Format_ARGB32_Premultiplied);image.fill(QColor('#f5f3ee'));d=QPainter(image)
    d.setRenderHint(QPainter.RenderHint.Antialiasing)
    y=60
    def row(text,size=32,weight=400,rtl=False,color='#1d3440',height=None):
        nonlocal y
        f=QFont('Meyar');f.setPixelSize(size);f.setWeight(QFont.Weight(weight));d.setFont(f);d.setPen(QColor(color))
        h=height or max(40,round(size*1.65))
        d.drawText(QRectF(65,y,1310,h),int(Qt.AlignmentFlag.AlignRight if rtl else Qt.AlignmentFlag.AlignLeft)|int(Qt.AlignmentFlag.AlignVCenter),text);y+=h
    row('MEYAR / مِعيار',72,500,False,'#096b72',130)
    row('Original Arabic–Latin typeface · engineering proof 0.100',22,height=55)
    row('مِعيار — نِظامٌ عَرَبِيٌّ بِهُوِيَّةٍ مُسْتَقِلَّةٍ',46,400,True,height=110)
    row('واجهة واضحة، اتصالات طبيعية، ومساحات مريحة للقراءة.',37,400,True,height=95)
    row('ميم هاء عين غين كاف ياء سين شين حاء جيم نون لام ألف باء',36,400,True,height=90)
    row('ببب تتت ثثث ححح ععع ممم ههه ككك ييي سسس ننن للا لا لأ لإ لآ',37,400,True,height=100)
    row('پژوهش فارسی، یک رابط کاربری · اردو پاکستان',32,400,True,height=80)
    row('MoOS · Meyar · Hamburg · Straße · Größe · café',36,400,height=85)
    row('ABCDEFGHIJKLMNOPQRSTUVWXYZ',34,400,height=75)
    row('abcdefghijklmnopqrstuvwxyz · Il1 O0 · AVATAR To Wa',34,400,height=75)
    row('0123456789   ٠١٢٣٤٥٦٧٨٩   ۰۱۲۳۴۵۶۷۸۹',38,400,True,height=90)
    row('€ 29.95  $ 80  £ 12 · ٥٠٠ ل.س · ± × ÷ ≤ ≥ ≠ √ ∞',32,400,True,height=85)
    row('/home/moos/المستندات · Datei_2026-10-26.txt',28,height=70)
    for size in (11,12,14,16):row(f'{size}px   الإعدادات والمظهر — اختر خلفية سطح المكتب  ·  Settings, files and applications',size,400,False,height=45)
    for weight in (100,400,500,700,900):row(f'{weight}   مِعيار — نظام عربي جميل   Meyar Arabic & Latin',32,weight,True,height=80)
    d.end();assert image.save(str(args.output));print(json.dumps({'image':str(args.output),'rawFamily':QRawFont.fromFont(QFont('Meyar')).familyName(),'heightUsed':y}))


if __name__=='__main__':main()
