#!/usr/bin/env python3
"""Real Qt product grouping, variant selection and safe native app management."""
import pathlib,tempfile,unittest,os
import test_mo_store_ui_pages as walk
@unittest.skipUnless(walk.RUNTIME,'Requires native Qt MoOS runtime')
class Experience(unittest.TestCase):
 def test_grouping_keeps_every_variant_actionable_and_native_apps_visible(self):
  setup="""var base=app.allApps[0]; var make=function(id,kind,name,extra){return Object.assign({},base,{id:id,kind:kind,source:kind==='flatpak'?'flatpak':'moos',name:name,name_en:name,ar:name,curated:false,listed:true,installed:false,compat:{verdict:'ok',reasons:[]},install:null,flatpak_ref:'',installed_scope:'',installed_scopes:[]},extra||{})}; var items=[make('lmstudio','appdrop','LM Studio'),make('ai.lmstudio.lm-studio','flatpak','LM Studio'),make('org.gnome.Calculator','flatpak','Calculator'),make('org.kde.kalk','flatpak','Calculator'),make('native.org.example.Viewer','native','Local viewer',{installed:true,listed:false,installable:false,management:'os'})];app.adoptCatalogue(items,{});app.navigate('apps')"""
  steps=[{'label':'index','until':'app.indexReady','settle':100},
   {'label':'real product grouping','do':setup,'until':'app.visibleApps.length === 3','timeout':3000},
   {'label':'every variant remains addressable','do':"if(app.variantsOf(app.appById('lmstudio')).length!==2)throw new Error('variant disappeared'); app.openDetails(app.appById('lmstudio'))",'until':"app.page==='app'",'settle':100},
   {'label':'switch variant','do':"app.showApp(app.appById('ai.lmstudio.lm-studio'))",'until':"app.selectedApp.id==='ai.lmstudio.lm-studio'",'settle':100},
   {'label':'native application management','do':"app.navigate('library');var native=app.appById('native.org.example.Viewer'); if(!app.hasRunnableLifecycle(native)||app.canRemove(native)||!app.systemManagedOnly(native))throw new Error('native ownership/action mismatch')",'until':'app.libraryApps.length === 1','settle':100},
   {'label':'native app page','do':"app.openDetails(app.appById('native.org.example.Viewer'))",'until':"app.page==='app'",'settle':150},
   {'label':'installed platform variants','do':setup+"; app.adoptCatalogue(items.concat([make('org.videolan.VLC','flatpak','VLC',{installed:true}),make('org.videolan.vlc','android','VLC Android',{installed:true,engine:'android'})]),{}); app.navigate('library'); app.libraryKind='android'; app.filterLibrary()",'until':"app.libraryApps.length===1 && app.libraryApps[0].id==='org.videolan.vlc'",'settle':100},
   {'label':'platform count retains installed alternatives','do':"if(app.libraryCount('android')!==1 || app.libraryCount('linux')!==2) throw new Error('installed platform variant count lost'); app.libraryKind='all'; app.filterLibrary()",'until':'app.libraryApps.length===2','settle':100}]
  steps=[{'settle':120,'timeout':15000,**step} for step in steps]
  with tempfile.TemporaryDirectory(prefix='moos-store-experience-') as td:
   for v in walk.VARIANTS[:2]:
    with self.subTest(language=v['language']):
     r=walk.run_walk(v,pathlib.Path(os.environ.get('MOOS_STORE_UI_UNDER_TEST',walk.STORE)),pathlib.Path(td)/v['name'],steps);self.assertEqual(r.returncode,0,r.stderr[-5000:]);self.assertEqual(walk.problems(r.stderr),[],r.stderr[-5000:])
if __name__=='__main__':unittest.main()
