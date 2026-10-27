#!/usr/bin/env python3
"""Real KDE collection refusal: choose a bounded image before native adoption."""
import contextlib
import io
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
from urllib.parse import quote

ROOT=Path(__file__).resolve().parents[1]
BRIDGE=runpy.run_path(str(ROOT/'system_files/usr/bin/moos-kde-wallpaper-adopt'))
API=runpy.run_path(str(ROOT/'system_files/usr/libexec/moos-session-appearance'))
G=BRIDGE['main'].__globals__
CATALOG=ROOT/'system_files/usr/share/moos/theme-profiles.tsv'


@unittest.skipUnless(os.name=='posix','native Linux wallpaper ownership')
class CollectionAdoption(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='moos-wallpaper-adoption-')
        self.addCleanup(self.temp.cleanup)
        home=Path(self.temp.name)
        class FixturePath(type(home)):
            @classmethod
            def home(cls): return cls(home)
            def read_text(self,*args,**kwargs):
                if str(self)=='/usr/share/moos/theme-profiles.tsv': return CATALOG.read_text()
                return super().read_text(*args,**kwargs)
        self.home=home;self.collection=home/'Collection';self.collection.mkdir()
        self.image=self.collection/"صورة #1%? 'quote' $(literal).png"
        from PIL import Image
        Image.new('RGB',(64,36),'#258bb0').save(self.image)
        self.addCleanup(patch.stopall)
        patch.dict(G,Path=FixturePath).start()
        patch.object(sys,'argv',['moos-kde-wallpaper-adopt',str(self.collection)+'/*']).start()
        self.api={name:API[name] for name in ('decode_path','raster')}
        self.api['profiles']=lambda:API['profiles'](CATALOG)
        self.api.update(selected_look=lambda:'org.moos.ui2.bloom',installed_look=lambda *_:True,
                        preferred_image=lambda *_:self.image)
        def load(path):
            self.assertEqual(path,'/usr/libexec/moos-session-appearance')
            return self.api
        patch.object(G['runpy'],'run_path',side_effect=load).start()
        self.commands=[];self.native=[];self.picker_code=0;self.picker_error=''
        def run(args,**kwargs):
            self.commands.append(args)
            self.assertNotIn('shell',kwargs)
            if args[0]=='/usr/bin/setpriv':
                self.assertEqual(args[:5],['/usr/bin/setpriv','--pdeathsig','TERM','--','/usr/bin/kdialog'])
                return subprocess.CompletedProcess(args,self.picker_code,str(self.image)+'\n' if self.picker_code==0 else '',self.picker_error)
            self.assertEqual(args[:2],['/usr/bin/moos-theme','wallpaper-token'])
            self.assertEqual(args[2],quote(str(self.image),safe='-._~'))
            self.assertTrue(kwargs['check'])
            return subprocess.CompletedProcess(args,0,'','')
        patch.object(G['subprocess'],'run',side_effect=run).start()
        patch.dict(G,native_apply=lambda image:self.native.append(image)).start()

    def execute(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:BRIDGE['main']()
        return output.getvalue()

    def test_flat_collection_uses_native_picker_and_existing_moos_transaction(self):
        self.assertIn('MOOS_KDE_WALLPAPER_APPLIED',self.execute())
        self.assertEqual(len(self.commands),2)
        self.assertFalse(self.native)

    def test_cancelling_picker_writes_no_wallpaper_and_executes_no_transaction(self):
        self.picker_code=1
        self.assertIn('MOOS_KDE_WALLPAPER_CANCELLED',self.execute())
        self.assertEqual(len(self.commands),1)
        self.assertFalse(self.native)

    def test_failed_picker_is_not_a_successful_cancel(self):
        self.picker_code=1;self.picker_error='platform unavailable'
        with self.assertRaisesRegex(ValueError,'picker failed'):self.execute()
        self.assertEqual(len(self.commands),1)
        self.assertFalse(self.native)

    def test_invalid_bitmap_never_reaches_the_desktop(self):
        from PIL import UnidentifiedImageError
        self.image.write_bytes(b'not an image')
        with self.assertRaises(UnidentifiedImageError):self.execute()
        self.assertEqual(len(self.commands),1)
        self.assertFalse(self.native)

    def test_standard_package_uses_its_preferred_image_without_a_collection_picker(self):
        (self.collection/'contents/images').mkdir(parents=True)
        self.execute()
        self.assertEqual(len(self.commands),1)
        self.assertEqual(self.commands[0][0],'/usr/bin/moos-theme')

    def test_external_theme_keeps_plasmas_native_wallpaper_owner(self):
        self.api['selected_look']=lambda:'My saved appearance'
        self.execute()
        self.assertEqual(len(self.commands),1)
        self.assertEqual(self.native,[self.image])

    def test_native_apply_uses_json_file_url_data_and_requires_actual_readback(self):
        captured=[]
        outputs=[{'plugin':'org.kde.image','image':self.image.as_uri()}]
        class Bus:
            def call_sync(_self,*args):
                captured.append(args)
                class Result:
                    def unpack(_self):return [json.dumps(outputs)]
                return Result()
        bus=Bus()
        gio=types.SimpleNamespace(BusType=types.SimpleNamespace(SESSION=0),DBusCallFlags=types.SimpleNamespace(NONE=0),bus_get_sync=lambda *_:bus)
        glib=types.SimpleNamespace(Variant=lambda signature,value:value)
        module=types.ModuleType('gi.repository');module.Gio=gio;module.GLib=glib
        with patch.dict(sys.modules,{'gi.repository':module}):
            BRIDGE['native_apply'](self.image)
            for refused in ([],[{'plugin':'org.moos.ui2.wallpaper','image':self.image.as_uri()}],
                            [{'plugin':'org.kde.image','image':'file:///another.png'}]):
                outputs[:]=refused
                with self.assertRaisesRegex(ValueError,'readback differs'):BRIDGE['native_apply'](self.image)
        script=captured[0][4][0]
        value,_end=json.JSONDecoder().raw_decode(script.removeprefix('var image='))
        self.assertEqual(value,self.image.as_uri())
        self.assertNotIn('$(literal)',script)
        self.assertEqual(captured[0][3],'evaluateScript')


if __name__=='__main__':unittest.main()
