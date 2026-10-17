#!/usr/bin/env python3
"""An installed native Linux app must never resolve to its Android package namesake."""
import sys,json,pathlib,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tests'))
import test_moos_storectl as backend

class PlatformIdentity(backend.StoreTestCase):
 def test_the_linux_application_action_never_launches_the_android_package(self):
  catalogue=json.loads((ROOT/'system_files/usr/share/moos/store/catalog.json').read_text())
  apps={a['id']:a for a in catalogue['apps']}
  for app_id in ('com.shatteredpixel.shatteredpixeldungeon','com.unicornsonlsd.finamp'):
   with self.subTest(app=app_id):
    adapter=backend.FakeAdapter(user=[app_id]);runner=backend.FakeRunner()
    controller,_=self.controller([apps[app_id]],adapter=adapter,runner=runner)
    code,document=controller.run(app_id)
    self.assertEqual(code,0,document)
    self.assertEqual(adapter.launches,[app_id],document)
    self.assertFalse(any('waydroid' in argument for command in runner.commands for argument in command),runner.commands)

if __name__=='__main__':unittest.main()
