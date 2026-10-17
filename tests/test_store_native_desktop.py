#!/usr/bin/env python3
"""Effective XDG precedence and native app ownership, without touching the desktop."""
import importlib.util,os,pathlib,tempfile,unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('native',ROOT/'system_files/usr/lib/moos/moos_store_desktop.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class NativeInventory(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=pathlib.Path(self.tmp.name);self.user=self.root/'user/applications';self.system=self.root/'system/applications';self.user.mkdir(parents=True);self.system.mkdir(parents=True)
  self.env=patch.dict(os.environ,{'HOME':str(self.root),'XDG_DATA_HOME':str(self.user.parent),'XDG_DATA_DIRS':str(self.system.parent),'LANGUAGE':'ar','XDG_CURRENT_DESKTOP':'KDE'});self.env.start();self.addCleanup(self.env.stop)
 def entry(self,root,name='org.example.App.desktop',extra=''):
  (root/name).write_text('[Desktop Entry]\nType=Application\nName=Example\nName[ar]=مثال\nExec=/usr/bin/example %U\nIcon=example\n'+extra)
 def test_localized_native_apps_are_installed_but_not_offered_for_download(self):
  self.entry(self.system);a=mod.inventory()[0];self.assertEqual(a['name'],'مثال');self.assertEqual(a['management'],'os');self.assertTrue(a['installed']);self.assertFalse(a['listed']);self.assertFalse(a['installable']);self.assertEqual(a['desktop_id'],'org.example.App.desktop')
 def test_owner_override_is_one_external_app(self):
  self.entry(self.system);self.entry(self.user,extra='Name=Owner\n');a=mod.inventory();self.assertEqual(len(a),1);self.assertEqual(a[0]['management'],'external')
 def test_hidden_override_masks_the_image_copy(self):
  self.entry(self.system);self.entry(self.user,extra='Hidden=true\n');self.assertEqual(mod.inventory(),[])
 def test_packaged_exports_are_not_duplicated(self):
  for i,key in enumerate(mod.MARKERS):self.entry(self.user,f'org.example.App{i}.desktop',f'{key}=org.example.App\n')
  self.assertEqual(mod.inventory(),[])
 def test_invisible_helpers_wrong_desktop_and_missing_executables_are_excluded(self):
  for i,extra in enumerate(['NoDisplay=true','OnlyShowIn=GNOME;','NotShowIn=KDE;','TryExec=/nonexistent/example']):self.entry(self.system,f'org.example.App{i}.desktop',extra+'\n')
  self.assertEqual(mod.inventory(),[])
 def test_find_rechecks_effective_launcher_and_never_returns_an_arbitrary_path(self):
  self.entry(self.user);self.assertIsNotNone(mod.find('native.org.example.App'));self.assertIsNone(mod.find('native.../etc/passwd'));self.assertIsNone(mod.find('org.example.App'))
  self.entry(self.user,extra='Hidden=true\n');self.assertIsNone(mod.find('native.org.example.App'))
 def test_bad_stronger_launcher_does_not_expose_a_masked_lower_copy(self):
  self.entry(self.system);(self.user/'org.example.App.desktop').write_text('broken');self.assertEqual(mod.inventory(),[])
 def test_native_state_survives_a_cached_index_refresh_and_disappears_with_its_launcher(self):
  import importlib.machinery,sys
  loader=importlib.machinery.SourceFileLoader('index_native_fixture',str(ROOT/'system_files/usr/bin/moos-store-index'));spec=importlib.util.spec_from_loader(loader.name,loader);index=importlib.util.module_from_spec(spec);sys.modules[loader.name]=index;loader.exec_module(index)
  self.entry(self.system)
  args=dict(installed={},catalog={'apps':[]},preferences=['ar'])
  first=index.apply_lifecycle([],snapshot={'native':mod.inventory()},**args)
  self.assertEqual(len(first),1);self.assertEqual(first[0]['management'],'os');self.assertTrue(first[0]['installed'])
  refreshed=index.apply_lifecycle(first,snapshot={'native':mod.inventory()},**args)
  self.assertEqual(len(refreshed),1)
  self.assertEqual(index.apply_lifecycle(refreshed,snapshot={'native':[]},**args),[])

 def test_a_dropped_android_package_masks_its_exported_native_launcher(self):
  import importlib.machinery,sys
  loader=importlib.machinery.SourceFileLoader('index_android_alias',str(ROOT/'system_files/usr/bin/moos-store-index'));spec=importlib.util.spec_from_loader(loader.name,loader);index=importlib.util.module_from_spec(spec);sys.modules[loader.name]=index;loader.exec_module(index)
  self.entry(self.system,extra='Exec=waydroid app launch org.example.Notes\n')
  snapshot={'native':mod.inventory(),'android':[{'package':'org.example.Notes','file':'notes.apk','version':'1'}]}
  result=index.apply_lifecycle([],snapshot=snapshot,installed={},catalog={'apps':[]},preferences=['ar'])
  self.assertEqual(len(result),1,result);self.assertEqual(result[0]['kind'],'android')

# Reuse only the isolated fixture/recorders; these never execute a native launcher.
import test_moos_storectl as backend
class NativeExecutor(backend.StoreTestCase):
 def launcher(self):
  root=pathlib.Path(os.environ['XDG_DATA_HOME'])/'applications';root.mkdir(parents=True)
  (root/'org.example.Native.desktop').write_text('[Desktop Entry]\nType=Application\nName=Native\nExec=/usr/bin/native-example %U\n')
  return root
 def test_native_run_uses_the_effective_launcher_and_fixed_desktop_service(self):
  self.launcher();runner=backend.FakeRunner();controller,_=self.controller([],runner=runner)
  code,doc=controller.run('native.org.example.Native')
  self.assertEqual(code,0,doc);self.assertEqual(runner.spawned,[[backend.MODULE.GTK_LAUNCH,'org.example.Native.desktop']])
  self.assertEqual(doc['state'],'success')
 def test_deleted_or_hidden_launcher_cannot_be_opened_from_a_stale_index(self):
  root=self.launcher();(root/'org.example.Native.desktop').unlink();runner=backend.FakeRunner();controller,_=self.controller([],runner=runner)
  with self.assertRaises(backend.MODULE.StoreError) as refused:controller.run('native.org.example.Native')
  self.assertEqual(refused.exception.message_key,'not_installed');self.assertEqual(runner.commands,[])
 def test_failed_native_launch_is_not_reported_as_opened(self):
  self.launcher();runner=backend.FakeRunner()
  def refused(argv): raise backend.MODULE.StoreError('launch refused')
  runner.spawn=refused;controller,_=self.controller([],runner=runner)
  code,doc=controller.run('native.org.example.Native');self.assertNotEqual(code,0);self.assertEqual(doc['state'],'failed')

if __name__=='__main__':unittest.main()
