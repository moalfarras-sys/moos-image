"""Native Qt and real private HTTP flows; never touch the owner's profile/session."""
import io
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
import uuid
import subprocess
import sys
import shutil
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_QUICK_BACKEND','software')
from community.client import Controller, normalized_picture, private_directory
from community.transport import Api,ApiError
from community.service import create_app
from PIL import Image,PngImagePlugin
from PySide6.QtCore import QObject,QUrl,QLocale,qInstallMessageHandler
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
import uvicorn
import socket

APP=QGuiApplication.instance() or QGuiApplication([])


def pump(until,timeout=8):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        APP.processEvents()
        if until():return
        time.sleep(.01)
    raise AssertionError('native flow timed out')


class NativeClient(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name)
        cls.app=create_app(cls.root/'server',public_origin='https://community.example.test',registration_open=True)
        cls.socket=socket.socket();cls.socket.bind(('127.0.0.1',0))
        cls.port=cls.socket.getsockname()[1]
        cls.server=uvicorn.Server(uvicorn.Config(cls.app,host='127.0.0.1',port=cls.port,
                                     log_level='error',access_log=False,proxy_headers=False))
        cls.thread=threading.Thread(target=cls.server.run,kwargs={'sockets':[cls.socket]},daemon=True)
        cls.thread.start();pump(lambda:cls.server.started)
        cls.api=Api('http://127.0.0.1:'+str(cls.port),review=True)
        cls.accounts={}
        for name in ('alice','bob'):
            credentials={'username':name,'password':'private-fixture-pass-'+name}
            cls.api.request('POST','/v1/accounts',body=credentials|{'display_name':name})
            cls.accounts[name]=cls.api.request('POST','/v1/session',body=credentials)

    @classmethod
    def tearDownClass(cls):
        cls.server.should_exit=True;cls.thread.join(timeout=5);cls.socket.close();cls.tmp.cleanup()

    def setUp(self):
        self.profile=tempfile.TemporaryDirectory();self.addCleanup(self.profile.cleanup)
        self.c=Controller(self.api,self.profile.name,'ar')
        self.addCleanup(self.c.close)
        self.c.login('alice','private-fixture-pass-alice')
        pump(lambda:self.c.data['signedIn'] and not self.c.data['busy'])

    def test_report_photo_receipt_private_read_and_restart_draft(self):
        picture=Path(self.profile.name)/'fixture.png';Image.new('RGB',(32,32),'teal').save(picture)
        self.c.choosePicture(QUrl.fromLocalFile(str(picture)).toString(),'report')
        pump(lambda:bool(self.c.data['picture']) and not self.c.data['busy'])
        self.c.saveReportDraft('صورة من الاختبار','وصف خاص طويل للاختبار',0,False)
        self.c.createThread('صورة من الاختبار','وصف خاص طويل للاختبار','problem',False)
        pump(lambda:self.c.data['pending']==0 and bool(self.c.data['images']) and not self.c.data['busy'])
        identity=self.c.data['selectedThread'];image=self.c.data['images'][0]['id']
        with self.assertRaises(ApiError):
            self.api.request('GET','/v1/images/'+image,token=self.accounts['bob']['token'])
        self.c.loadImage(image)
        pump(lambda:bool(self.c.data['images'][0].get('source')) and not self.c.data['busy'])
        cached=Path(QUrl(self.c.data['images'][0]['source']).toLocalFile())
        self.assertEqual(cached.stat().st_mode&0o777,0o600)
        self.c.saveReplyDraft('رد محفوظ قبل الإغلاق')
        self.c.close();self.assertFalse(cached.exists())
        second=Controller(self.api,self.profile.name,'ar')
        self.addCleanup(second.close)
        second.login('alice','private-fixture-pass-alice');pump(lambda:second.data['signedIn'] and not second.data['busy'])
        second.selectThread(identity);pump(lambda:bool(second.data['selectedTitle']) and not second.data['busy'])
        self.assertEqual(second.data['replyDraft'],'رد محفوظ قبل الإغلاق')
        second.sendMessage('رد محفوظ قبل الإغلاق')
        pump(lambda:second.data['pending']==0 and len(second.data['messages'])==2 and not second.data['busy'])

    def test_unreceived_send_survives_restart_and_only_real_receipt_clears_it(self):
        with patch.object(self.api,'request',side_effect=ApiError('offline')):
            self.c.createThread('اختبار الانقطاع','وصف خاص أثناء انقطاع الاتصال','problem',False)
            pump(lambda:self.c.data['error'] and not self.c.data['busy'])
        draft=self.c.outbox.pending()[0]['id'];self.c.close()
        second=Controller(self.api,self.profile.name,'ar');self.addCleanup(second.close)
        second.login('alice','private-fixture-pass-alice');pump(lambda:second.data['signedIn'] and not second.data['busy'])
        self.assertEqual(second.outbox.pending()[0]['id'],draft)
        second.retryPending();pump(lambda:second.data['pending']==0 and not second.data['busy'])
        self.assertEqual(second.outbox.get(draft)['state'],'received')

    def test_switching_accounts_discards_late_private_results(self):
        generation=self.c.generation
        self.c.login('bob','private-fixture-pass-bob')
        pump(lambda:self.c.data['signedIn'] and self.c.data['displayName']=='bob' and not self.c.data['busy'])
        self.c.complete(generation,{'private':'alice'},'',lambda _:self.c.publish(messages=[{'body':'leak'}]))
        self.assertEqual(self.c.data['messages'],[])
        self.assertEqual(self.c.outbox.pending(),[])

    def test_selection_race_ignores_an_older_conversation(self):
        queued=[]
        with patch.object(self.c,'submit',side_effect=lambda work,done:queued.append((work,done))):
            self.c.selectThread('first');self.c.selectThread('second')
        queued[0][1]({'thread':{'id':'first','title':'private first','state':'received'},'messages':[],'images':[]})
        self.assertEqual(self.c.data['selectedThread'],'second')

    def test_real_qml_loads_both_directions_and_narrow_layout_without_warnings(self):
        for locale,direction in (('ar_SA',True),('en_US',False)):
            QLocale.setDefault(QLocale(locale));self.c.language='ar' if direction else 'en'
            messages=[];old=qInstallMessageHandler(lambda _type,_ctx,text:messages.append(text))
            engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('community',self.c)
            engine.load(QUrl.fromLocalFile(str(Path(__file__).with_name('main.qml'))))
            self.assertEqual(len(engine.rootObjects()),1,messages)
            root=engine.rootObjects()[0];root.setWidth(560);root.setHeight(720)
            for _ in range(15):APP.processEvents();time.sleep(.01)
            # Locale singleton is process-cached. Each direction is additionally
            # checked by separate native review subprocesses.
            root.close();engine.deleteLater();APP.processEvents();qInstallMessageHandler(old)
            failures=[m for m in messages if any(x in m for x in ('ReferenceError','TypeError','Unable','binding loop','Binding loop','not a type'))]
            self.assertEqual(failures,[],failures)


class PictureSafety(unittest.TestCase):
    def test_alpha_and_metadata_cannot_reveal_hidden_pixels_or_coordinates(self):
        raw=io.BytesIO();meta=PngImagePlugin.PngInfo();meta.add_text('location','private')
        Image.new('RGBA',(12,12),(255,0,0,0)).save(raw,format='PNG',pnginfo=meta)
        clean=normalized_picture(raw.getvalue())
        with Image.open(io.BytesIO(clean)) as image:
            self.assertEqual(image.convert('RGB').getpixel((0,0)),(255,255,255))
            self.assertNotIn('location',image.info)
        for data in (b'<svg xmlns="http://www.w3.org/2000/svg"><image href="https://example.test"/></svg>',b'not image',raw.getvalue()[:30]):
            with self.assertRaises(ApiError):normalized_picture(data)

    def test_large_raster_and_shared_profile_fail_before_preview(self):
        large=io.BytesIO();Image.new('RGB',(2100,2100)).save(large,format='PNG')
        with self.assertRaises(ApiError):normalized_picture(large.getvalue())
        with tempfile.TemporaryDirectory() as directory:
            Path(directory).chmod(0o755)
            with self.assertRaises(ValueError):private_directory(directory)


class ShippedLauncher(unittest.TestCase):
    def test_actual_staged_entrypoint_renders_and_bad_qml_fails(self):
        from community.stage_client import stage
        source=Path(__file__).parent
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);stage(source,root/'community')
            home=root/'home';home.mkdir(mode=0o700)
            config=root/'service.json';config.write_text('{"schema":1,"service_url":"https://community.example.test"}')
            env=dict(os.environ,HOME=str(home),XDG_CONFIG_HOME=str(home/'.config'),
                     XDG_DATA_HOME=str(home/'.local/share'),QT_QPA_PLATFORM='offscreen',
                     QT_QUICK_BACKEND='software',QT_QUICK_CONTROLS_STYLE='Basic')
            command=[sys.executable,'-m','community.client','--service-config',str(config),
                     '--capture',str(root/'frame.png')]
            good=subprocess.run(command,cwd=root,env=env,capture_output=True,text=True,timeout=15)
            self.assertEqual(good.returncode,0,good.stdout+good.stderr)
            self.assertIn('MOOS_COMMUNITY_UI_READY',good.stdout);self.assertTrue((root/'frame.png').is_file())
            (root/'frame.png').unlink()
            (root/'community/main.qml').write_text('import QtQuick\nThisTypeDoesNotExist {}')
            bad=subprocess.run(command,cwd=root,env=env,capture_output=True,text=True,timeout=15)
            self.assertNotEqual(bad.returncode,0);self.assertFalse((root/'frame.png').exists())
            self.assertIn('failed to load',bad.stderr)

    def test_failed_capture_exits_instead_of_leaving_a_live_hung_probe(self):
        with tempfile.TemporaryDirectory() as directory:
            env=dict(os.environ,HOME=directory,XDG_CONFIG_HOME=directory+'/.config',
                     XDG_DATA_HOME=directory+'/.local/share',QT_QPA_PLATFORM='offscreen',
                     QT_QUICK_BACKEND='software',QT_QUICK_CONTROLS_STYLE='Basic')
            result=subprocess.run([sys.executable,'-m','community.client','--service-url','https://community.example.test',
                '--capture',str(Path(directory)/'missing-parent/frame.png')],env=env,capture_output=True,text=True,timeout=15)
            self.assertEqual(result.returncode,2,result.stdout+result.stderr)
            self.assertIn('MOOS_COMMUNITY_CAPTURE_FAILED',result.stdout)


if __name__=='__main__':unittest.main()
