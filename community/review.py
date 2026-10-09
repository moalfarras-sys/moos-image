"""Rendered/input review against a private real API; only synthetic account data."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time

from community.test_client import NativeClient,APP,pump
from community.client import Controller
from PySide6.QtCore import QObject,QUrl,QLocale,QMetaObject,QPoint,Qt,qInstallMessageHandler
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest
from PIL import Image


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--language',choices=('ar','en'),required=True)
    parser.add_argument('--width',type=int,default=1040)
    parser.add_argument('--height',type=int,default=760)
    args=parser.parse_args()
    if ctypes.CDLL(None).prctl(4,0,0,0,0)!=0:raise RuntimeError('private review required')
    QLocale.setDefault(QLocale('ar_SA' if args.language=='ar' else 'en_US'))
    args.output.mkdir(parents=True,mode=0o700,exist_ok=True)
    NativeClient.setUpClass()
    controller=None;engine=None
    warnings=[];previous=qInstallMessageHandler(lambda mode,context,message:warnings.append(message))
    try:
        with tempfile.TemporaryDirectory() as profile:
            controller=Controller(NativeClient.api,profile,args.language)
            engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('community',controller)
            engine.load(QUrl.fromLocalFile(str(Path(__file__).with_name('main.qml'))))
            if not engine.rootObjects():raise AssertionError(warnings)
            root=engine.rootObjects()[0];root.setWidth(args.width);root.setHeight(args.height)
            controller.login('alice','private-fixture-pass-alice')
            pump(lambda:controller.data['signedIn'] and not controller.data['busy'])
            # QTest clicks the real Qt item, not an external owner's pointer.
            button=root.findChild(QQuickItem,'newReport')
            from PySide6.QtCore import QPointF
            position=button.mapToScene(QPointF(button.width()/2,button.height()/2))
            if not (0<=position.x()<root.width() and 0<=position.y()<root.height()):
                raise AssertionError('new-report button is outside the window')
            QTest.mouseClick(root,Qt.LeftButton,Qt.NoModifier,QPoint(round(position.x()),round(position.y())))
            dialog=root.findChild(QObject,'reportEditor');pump(lambda:dialog.property('opened'))
            title=root.findChild(QObject,'reportTitle');body=root.findChild(QObject,'reportBody')
            title.setProperty('text','اختبار إعداد الشاشة' if args.language=='ar' else 'Display settings review')
            body.setProperty('text','هذه بيانات مراجعة تجريبية فقط. نريد تكبير النص مع بقاء الأزرار واضحة.' if args.language=='ar' else 'Synthetic review data only. Larger text should keep the controls clear.')
            picture=Path(profile)/'synthetic.png';Image.new('RGB',(400,240),'teal').save(picture)
            controller.choosePicture(QUrl.fromLocalFile(str(picture)).toString(),'report')
            pump(lambda:bool(controller.data['picture']) and not controller.data['busy'])
            def capture(stage):
                for _ in range(30):APP.processEvents();time.sleep(.015)
                image=root.grabWindow()
                if image.isNull():raise AssertionError('native frame unavailable')
                file=args.output/(stage+'-'+args.language+'.png')
                if not image.save(str(file)):raise AssertionError('frame save failed')
                return {'file':file.name,'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),
                        'physical_px':[image.width(),image.height()],'language':args.language,'stage':stage}
            frames=[capture('report-editor')]
            send=root.findChild(QQuickItem,'sendReport')
            position=send.mapToScene(QPointF(send.width()/2,send.height()/2))
            if not (0<=position.x()<root.width() and 0<=position.y()<root.height()):
                raise AssertionError('send button is outside the window')
            if not send.property('enabled'):raise AssertionError('valid report button disabled')
            QTest.mouseClick(root,Qt.LeftButton,Qt.NoModifier,QPoint(round(position.x()),round(position.y())))
            pump(lambda:controller.data['pending']==0 and bool(controller.data['images']) and not controller.data['busy'])
            frames.append(capture('conversations'))
            dialog=root.findChild(QObject,'conversation');QMetaObject.invokeMethod(dialog,'open')
            pump(lambda:dialog.property('opened'))
            controller.loadImage(controller.data['images'][0]['id'])
            pump(lambda:bool(controller.data['images'][0].get('source')) and not controller.data['busy'])
            frames.append(capture('private-conversation'))
            faults=[w for w in warnings if any(x in w for x in ('ReferenceError','TypeError','Binding loop','binding loop','Unable to assign'))]
            if faults:raise AssertionError(faults)
            receipt={'schema':1,'scope':'source-native-qt/private-real-http/synthetic-accounts',
                     'language':args.language,'logical_px':[args.width,args.height],
                     'rtl':root.property('rtl'),'source_file_sha256':{
                         name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                         for name in ('client.py','main.qml','service.py')},
                     'frames':frames,'real_button_clicks':2,'layout_errors':faults}
            (args.output/('review-'+args.language+'.json')).write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
            print(json.dumps({'review':'passed','language':args.language,'rtl':receipt['rtl'],'frames':len(frames)}))
            root.close();controller.close();controller=None
            engine.deleteLater();APP.processEvents();engine=None
    finally:
        if controller:controller.close()
        NativeClient.tearDownClass();qInstallMessageHandler(previous)


if __name__=='__main__':main()
