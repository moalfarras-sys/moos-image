#!/usr/bin/env python3
"""Run the actual QML product policy: distinct publishers stay distinct, variants stay actionable."""
import pathlib,shutil,subprocess,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
class ProductIdentity(unittest.TestCase):
 @unittest.skipUnless(shutil.which('node'),'Node runtime unavailable')
 def test_actual_product_policy(self):
  path=ROOT/'system_files/usr/share/moos/apps/store/StoreProducts.js'
  code=path.read_text().replace('.pragma library','')+r'''
const assert=require('node:assert/strict');const installed=a=>a.installed===true;
const native={id:'ai.lmstudio.lm-studio',kind:'flatpak'}, publisher={id:'lmstudio',kind:'appdrop'};
assert.deepEqual(unique([publisher,native],installed),[native]);
assert.deepEqual(unique([publisher,{...native,compat:{verdict:'blocked'}}],installed),[publisher]);
assert.deepEqual(unique([{...publisher,installed:true},native],installed).map(a=>a.id),['lmstudio']);
const calculators=[{id:'org.gnome.Calculator',name:'Calculator'},{id:'org.kde.kalk',name:'Calculator'}];
assert.equal(unique(calculators,installed).length,2);
assert.equal(unique([{id:'com.jetbrains.IntelliJ-IDEA-Ultimate',name:'IntelliJ IDEA'},{id:'com.jetbrains.IntelliJ-IDEA-Community',name:'IntelliJ IDEA'}],installed).length,2);
assert.equal(variants(native,[publisher,native,...calculators]).length,2);
assert.equal(variants(null,[]).length,0);
const android={id:'org.videolan.vlc',kind:'android'},linux={id:'org.videolan.VLC',kind:'flatpak'};
assert.equal(unique([android,linux],installed)[0].id,linux.id);
assert.equal(unique([android],installed)[0].id,android.id);
assert.equal(variants(linux,[android,linux]).length,2);
assert.equal(key({id:'native.org.mozilla.firefox',kind:'native'}),'org.mozilla.firefox');
assert.notEqual(key({id:'native.calculator',kind:'native'}),key({id:'calculator',kind:'npm'}));
console.log('12 product identity controls passed');
'''
  r=subprocess.run(['node','-e',code],capture_output=True,text=True,timeout=10);self.assertEqual(r.returncode,0,r.stderr)
if __name__=='__main__':unittest.main()
