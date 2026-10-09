"""Opt-in native/TLS acceptance using a new synthetic private member account.

No public proposal, owner screenshot, raw logs or real member content is read.
The report is deleted at the end; the private receipt names the exact fixture
account for local operator cleanup. It is never a genuine bug or repair claim.
"""
import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import secrets
import tempfile
import time

from community.test_client import APP,pump
from community.client import Controller
from community.transport import Api
from PySide6.QtCore import QObject,QUrl,QLocale,QPointF,QPoint,Qt,qInstallMessageHandler
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest
from PIL import Image


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--service-url',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if ctypes.CDLL(None).prctl(4,0,0,0,0)!=0:raise RuntimeError('private review required')
    QLocale.setDefault(QLocale('ar_SA'))
    APP.setLayoutDirection(QLocale().textDirection())
    args.output.mkdir(parents=True,mode=0o700,exist_ok=True)
    api=Api(args.service_url)
    credentials={'username':'audit_station_'+secrets.token_hex(4),'password':secrets.token_urlsafe(24)}
    api.request('POST','/v1/accounts',body=credentials|{'display_name':'اختبار خاص للواجهة الأصلية'})
    controller=None;identity=None;token=None;frames=[];warnings=[]
    previous=qInstallMessageHandler(lambda mode,context,message:warnings.append(message))
    receipt={'schema':1,'service_url':api.endpoint,'scope':'real-physical-wayland/source-qt/actual-oracle-https/synthetic-private-account',
             'fixture_username':credentials['username'],'source_file_sha256':{name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in ('client.py','main.qml','transport.py')}}
    try:
        with tempfile.TemporaryDirectory() as profile:
            controller=Controller(api,profile,'ar')
            engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('community',controller)
            engine.load(QUrl.fromLocalFile(str(Path(__file__).with_name('main.qml'))))
            if not engine.rootObjects():raise AssertionError(warnings)
            root=engine.rootObjects()[0];root.setWidth(1040);root.setHeight(760)
            controller.login(credentials['username'],credentials['password'])
            pump(lambda:controller.data['signedIn'] and not controller.data['busy'],timeout=25)
            token=controller.token
            def click(name):
                item=root.findChild(QQuickItem,name)
                p=item.mapToScene(QPointF(item.width()/2,item.height()/2))
                assert item.property('enabled') and 0<=p.x()<root.width() and 0<=p.y()<root.height()
                QTest.mouseClick(root,Qt.LeftButton,Qt.NoModifier,QPoint(round(p.x()),round(p.y())))
            click('newReport');editor=root.findChild(QObject,'reportEditor');pump(lambda:editor.property('opened'))
            root.findChild(QObject,'reportTitle').setProperty('text','اختبار تلقائي خاص — الواجهة على Oracle')
            root.findChild(QObject,'reportBody').setProperty('text','هذه بيانات اختبار اصطناعية فقط، ليست مشكلة مستخدم حقيقية. نختبر وصول الصورة وحفظ المسودة والرد من الخدمة.')
            file=Path(profile)/'synthetic.png';Image.new('RGB',(400,240),'teal').save(file)
            controller.choosePicture(QUrl.fromLocalFile(str(file)).toString(),'report')
            pump(lambda:bool(controller.data['picture']) and not controller.data['busy'],timeout=20)
            def capture(stage):
                for _ in range(30):APP.processEvents();time.sleep(.015)
                image=root.grabWindow();assert not image.isNull()
                path=args.output/(stage+'.png');assert image.save(str(path))
                frames.append({'file':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'physical_px':[image.width(),image.height()]})
            capture('oracle-report-editor-ar')
            click('sendReport')
            pump(lambda:controller.data['pending']==0 and bool(controller.data['images']) and not controller.data['busy'],timeout=40)
            identity=controller.data['selectedThread']
            dialog=root.findChild(QObject,'conversation')
            from PySide6.QtCore import QMetaObject
            QMetaObject.invokeMethod(dialog,'open');pump(lambda:dialog.property('opened'))
            controller.loadImage(controller.data['images'][0]['id'])
            pump(lambda:bool(controller.data['images'][0].get('source')) and not controller.data['busy'],timeout=25)
            capture('oracle-private-image-ar')
            assert controller.data['pending']==0
            faults=[w for w in warnings if any(x in w for x in ('ReferenceError','TypeError','Unable to assign','Binding loop','binding loop'))]
            assert not faults,faults
            receipt.update(passed=True,frames=frames,rtl=root.property('rtl'),actual_tls=True,real_button_clicks=2,
                           fixture_thread=identity,layout_errors=faults,private_owner_content=False)
            root.close();controller.close();controller=None
            engine.deleteLater();APP.processEvents()
    finally:
        if controller:controller.close()
        if identity and token:
            api.request('DELETE','/v1/threads/'+identity,token=token)
            receipt['fixture_thread_deleted']=True
        if token:api.request('DELETE','/v1/session',token=token)
        (args.output/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
        qInstallMessageHandler(previous)
    print(json.dumps({'native_oracle_tls_review':'passed','frames':len(frames),'fixture_username':credentials['username'],'thread_deleted':receipt.get('fixture_thread_deleted')}))


if __name__=='__main__':main()
