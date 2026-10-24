#!/usr/bin/env python3
"""Execute the real overlay transaction against a private Plasma JS adapter.

The adapter executes production JavaScript; it never reaches the owner's bus.
Silently refusing setters must restore the full previous scene and fail.
"""
from pathlib import Path
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OWNER = ROOT / 'system_files/usr/bin/moos-theme'
NODE = shutil.which('node')
ADAPTER = r'''
const fs=require('fs');
const file=process.env.PROBE_STATE;
let rows=JSON.parse(fs.readFileSync(file,'utf8'));
let changed=false;
const defaults={ShowDashboard:false,HubClock:true,HubWeather:true,HubSystem:true,MotionMode:'1',AmbientMotion:'true',Image:''};
global.desktops=()=>rows.map(row=>({
 get wallpaperPlugin(){return row.plugin},set wallpaperPlugin(v){row.plugin=v},
 get id(){return row.id},currentConfigGroup:[],
 readConfig(k,fallback){return row.config[k]===undefined?(defaults[k]===undefined?fallback:defaults[k]):row.config[k]},
 writeConfig(k,v){
  const refuse=process.env.PROBE_REFUSAL||'';
  if(refuse==='all')return;
  if(refuse==='hide'&&k==='ShowDashboard'&&v===false)return;
  row.config[k]=v;
 },reloadConfig(){}
}));
global.print=(value)=>console.log(value);
try{eval(process.argv[2]);fs.writeFileSync(file,JSON.stringify(rows));}
catch(e){console.error(String(e));process.exit(1)}
'''


def scene(shown=False, cards=(True, True, True), plugin='org.moos.ui2.wallpaper'):
    return [{'id':1,'plugin':plugin,'config':{
        'ShowDashboard':str(shown).lower(), 'HubClock':str(cards[0]).lower(),
        'HubWeather':str(cards[1]).lower(), 'HubSystem':str(cards[2]).lower(),
        'Image':'/tmp/owned original.png','MotionMode':'0','AmbientMotion':'false'}},
        {'id':2,'plugin':plugin,'config':{
        'ShowDashboard':str(shown).lower(), 'HubClock':str(cards[0]).lower(),
        'HubWeather':str(cards[1]).lower(), 'HubSystem':str(cards[2]).lower(),
        'Image':'/tmp/another original.png','MotionMode':'2','AmbientMotion':'true'}}]


@unittest.skipUnless(NODE, 'native JavaScript runtime unavailable')
class Overlay(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='moos-overlay-')
        self.addCleanup(self.temp.cleanup)
        self.private=Path(self.temp.name)
        self.state=self.private/'scene.json'
        self.bin=self.private/'bin';self.bin.mkdir()
        driver=self.private/'plasma.js';driver.write_text(ADAPTER)
        bridge=self.bin/'gdbus'
        bridge.write_text('#!/usr/bin/env python3\nimport os,subprocess,sys\n'
                         'r=subprocess.run(['+repr(NODE)+','+repr(str(driver))+',sys.argv[-1]],env=os.environ)\n'
                         'raise SystemExit(r.returncode)\n')
        bridge.chmod(0o755)
        self.env=dict(os.environ,PATH=str(self.bin)+os.pathsep+os.environ.get('PATH',''),
                      HOME=str(self.private), XDG_RUNTIME_DIR=str(self.private),
                      XDG_CONFIG_HOME=str(self.private/'config'),XDG_STATE_HOME=str(self.private/'state'),
                      DBUS_SESSION_BUS_ADDRESS='unix:path='+str(self.private/'no-bus'),PROBE_STATE=str(self.state))
        self.env.pop('DISPLAY',None);self.env.pop('WAYLAND_DISPLAY',None)
        self.state.write_text(json.dumps(scene()))

    def run_owner(self, *args, refusal=''):
        return subprocess.run(['bash',str(OWNER),'hub',*args],env=dict(self.env,PROBE_REFUSAL=refusal),
                              capture_output=True,text=True,timeout=15)

    def test_off_on_roundtrip_and_no_theme_or_image_replacement(self):
        before=scene();self.state.write_text(json.dumps(before))
        self.assertEqual(self.run_owner().stdout.strip(),'off')
        for wanted in ('on','off'):
            result=self.run_owner(wanted)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(result.stdout.strip(),wanted)
            self.assertEqual(self.run_owner().stdout.strip(),wanted)
            after=json.loads(self.state.read_text())
            for old,new in zip(before,after):
                self.assertEqual(old['plugin'],new['plugin'])
                self.assertEqual({k:v for k,v in old['config'].items() if k!='ShowDashboard'},
                                 {k:v for k,v in new['config'].items() if k!='ShowDashboard'})

    def test_mixed_unavailable_and_malformed_have_no_writes(self):
        invalid=scene();invalid[0]['config']['ShowDashboard']='unknown'
        for rows in ([],scene(plugin='org.kde.image'),[scene()[0],scene(True)[1]],invalid):
            self.state.write_text(json.dumps(rows));before=self.state.read_bytes()
            self.assertNotEqual(self.run_owner().returncode,0)
            self.assertEqual(json.loads(self.state.read_text()),rows)
        self.state.write_text(json.dumps(scene()))
        for bad in ('true','ON','on;whoami','../on','', 'on extra'):
            before=self.state.read_bytes();result=self.run_owner(bad)
            self.assertEqual(result.returncode,2,(bad,result.stderr))
            self.assertEqual(before,self.state.read_bytes())
        self.assertEqual(self.run_owner('on','extra').returncode,2)

    def test_all_cards_off_reenables_a_visible_instrument(self):
        self.state.write_text(json.dumps(scene(True,(False,False,False))))
        self.assertEqual(self.run_owner().stdout.strip(),'off')
        self.assertEqual(self.run_owner('on').returncode,0)
        self.assertEqual(self.run_owner().stdout.strip(),'on')
        for row in json.loads(self.state.read_text()):
            self.assertTrue(all(row['config'][k] for k in ('HubClock','HubWeather','HubSystem')))

    def test_silent_setter_refusal_fails_and_restores_exact_snapshot(self):
        for refusal in ('all','hide'):
            before=scene(True,(True,False,True));self.state.write_text(json.dumps(before))
            result=self.run_owner('off',refusal=refusal)
            self.assertNotEqual(result.returncode,0)
            self.assertNotIn('off',result.stdout)
            self.assertIn('rolled back',result.stderr)
            self.assertEqual(json.loads(self.state.read_text()),before)

    def test_optional_default_real_loader_and_settings_readback(self):
        package=ROOT/'system_files/usr/share/plasma/wallpapers/org.moos.ui2.wallpaper'
        cfg=ET.parse(package/'contents/config/main.xml')
        ns={'k':'http://www.kde.org/standards/kcfg/1.0'}
        default=cfg.find('.//k:entry[@name="ShowDashboard"]/k:default',ns)
        self.assertEqual(default.text,'false')
        main=(package/'contents/ui/main.qml').read_text()
        self.assertIn('root.configuration.ShowDashboard === true',main)
        self.assertIn('active: bentoFrame.dashboardRequested',main)
        ui=(ROOT/'moos-settings-kcm/modules/appearance/ui/main.qml').read_text()
        for contract in ('kcm.runFixed("theme-hub", value)','kcm.runFixed("theme-hub-status")',
                         'currentHub !== expected','phase = "verifying"','moos://settings/desktop'):
            self.assertIn(contract,ui)

if __name__=='__main__':unittest.main()
