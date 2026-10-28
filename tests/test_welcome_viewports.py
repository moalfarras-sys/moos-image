#!/usr/bin/env python3
"""Native Welcome flow: scroll original actions, keep caption ink inside cards.

Runs the real installed QML host with private buses/config/cache. It does not
install apps, change a theme, or activate the live installer destination.
"""
from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'system_files/usr/share/moos/apps/welcome/main.qml'
DRIVER = r'''
    Gate.TestCase {
        id: viewportCheck
        name: "MoOSWelcomeViewports"
        when: true
        function test_originalActionsAndPages() {
            wait(900);
            if (win.height+win.fs(56)>Screen.desktopAvailableHeight+1)
                console.warn("MOOS_WELCOME_VIEWPORTS_FAILED initial window leaves no native frame room");
            verify(win.height+win.fs(56)<=Screen.desktopAvailableHeight+1,"initial window leaves no native frame room");
            win.minimumWidth=0; win.minimumHeight=0;
            win.width=__WIDTH__; win.height=__HEIGHT__; win.lang="__LANG__";
            wait(180);
            function fits(item, owner) {
                const p=item.mapToItem(owner,0,0);
                return p.x>=-1 && p.y>=-1 && p.x+item.width<=owner.width+1 && p.y+item.height<=owner.height+1;
            }
            function ink(item, owner) {
                if (!item.visible) return;
                if (item.text !== undefined && String(item.text).length && item.paintedWidth !== undefined) {
                    if (item.paintedWidth>item.width+1 || item.paintedHeight>item.height+1)
                        console.warn("MOOS_WELCOME_VIEWPORTS_FAILED caption ink clipped: "+item.text);
                    verify(item.paintedWidth<=item.width+1 && item.paintedHeight<=item.height+1,
                           "caption ink clipped: "+item.text);
                    verify(fits(item,owner),"caption outside card: "+item.text);
                }
                for (let child of item.children || []) ink(child,owner);
            }
            function reveal(item,page) {
                item.forceActiveFocus(Qt.TabFocusReason); wait(180);
                verify(fits(item,page),"focused original action outside viewport");
                ink(item,item);
            }
            // Preserve both live actions. Natural wheel scrolling must recover
            // them before pointer and keyboard use of the original Begin.
            mouseWheel(hero,hero.width/2,hero.height/2,0,-3000); wait(500);
            tryCompare(hero,"moving",false,3000);
            if (!(fits(welcomeHeroBegin,hero)&&fits(liveInstallButton,hero)))
                console.warn("MOOS_WELCOME_VIEWPORTS_FAILED live actions did not scroll into view");
            verify(fits(welcomeHeroBegin,hero)&&fits(liveInstallButton,hero),"live actions did not scroll into view");
            ink(welcomeHeroBegin,welcomeHeroBegin); ink(liveInstallButton,liveInstallButton);
            mouseClick(welcomeHeroBegin,welcomeHeroBegin.width/2,welcomeHeroBegin.height/2); wait(100);
            compare(win.step,1,"original Begin pointer destination");
            win.goBack(); wait(100);
            reveal(welcomeHeroBegin,hero); keyClick(Qt.Key_Return); wait(100);
            compare(win.step,1,"original Begin keyboard destination");
            for (let grid of [lookGrid,directionGrid]) {
                win.step=grid===lookGrid?1:2; wait(180);
                const page=grid===lookGrid?lookPage:dirPage;
                for (let card of grid.children) {
                    if (!card.activeFocusOnTab) continue;
                    reveal(card,page); ink(card,card);
                }
            }
            win.step=5; wait(180);
            for (let action of [welcomeOpenStore,welcomeOpenMira,welcomeConnectDevices]) reveal(action,donePage);
            // Exercise the existing device popup, without launching Settings
            // or any privileged/hardware action from inside it.
            keyClick(Qt.Key_Return); wait(150); verify(devicesPopup.opened,"device popup destination");
            devicesPopup.close(); wait(80);
            console.warn("MOOS_WELCOME_VIEWPORTS_PASS "+JSON.stringify({width:win.width,height:win.height,fontScale:win.fontScale,rtl:win.rtl}));
        }
    }
'''


class WelcomeViewports(unittest.TestCase):
    @unittest.skipUnless(shutil.which('moos-qml-shell'), 'native MoOS QML host unavailable on SDK-free worker')
    def test_native_actions_cards_and_broken_scroll(self):
        with tempfile.TemporaryDirectory(prefix='moos-welcome-viewports-') as td:
            private = Path(td)
            for name in ('home','runtime','config','cache','data'):
                (private/name).mkdir(mode=0o700)
            env = dict(os.environ, HOME=str(private/'home'), XDG_RUNTIME_DIR=str(private/'runtime'),
                XDG_CONFIG_HOME=str(private/'config'), XDG_CONFIG_DIRS=str(private/'config'),
                XDG_CACHE_HOME=str(private/'cache'), XDG_DATA_HOME=str(private/'data'),
                XDG_DATA_DIRS=str(ROOT/'system_files/usr/share')+':/usr/share',
                DBUS_SESSION_BUS_ADDRESS='unix:path='+str(private/'absent-session'),
                DBUS_SYSTEM_BUS_ADDRESS='unix:path='+str(private/'absent-system'),
                QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software',
                QML_IMPORT_PATH=str(ROOT/'system_files/usr/lib64/qt6/qml'),
                QML_DISABLE_DISK_CACHE='1', QML_XHR_ALLOW_FILE_READ='1',
                QT_QPA_PLATFORMTHEME='kde', QT_QUICK_CONTROLS_STYLE='Basic',
                QT_FORCE_STDERR_LOGGING='1', LANG='en_US.UTF-8')
            from native_meyar_fontconfig import configure
            configure(env,private)
            for width,height,language,font,broken in [(640,480,'ar',10,None),
                    (360,640,'ar',16,None),(331,550,'ar',16,None),(1536,864,'en',10,None),
                    (640,480,'ar',10,'scroll'),(360,640,'ar',16,'frame'),(331,550,'ar',16,'word')]:
                colors=(ROOT/'system_files/usr/share/color-schemes/MoOSUI2Aurora.colors').read_text()
                (private/'config/kdeglobals').write_text(colors+'\n[General]\nfont=Meyar Sans,'+str(font)+
                    '\n[KDE]\nAnimationDurationFactor=0\nLookAndFeelPackage=org.moos.ui2.aurora\n[Icons]\nTheme=MoOSUI2Aurora\n')
                (private/'config/plasmarc').write_text('[Theme]\nname=MoOSUI2Aurora\n')
                body=SOURCE.read_text().replace('import QtQuick\n','import QtQuick\nimport QtTest as Gate\n',1)
                if broken == 'scroll':
                    needle='id: hero\n                columnItem: heroColumn'
                    self.assertEqual(body.count(needle),1)
                    body=body.replace(needle,needle+'\n                interactive: false',1)
                if broken == 'frame':
                    needle='height: Math.min(760, availableWindowHeight)'
                    self.assertEqual(body.count(needle),1)
                    body=body.replace(needle,'height: Math.min(760, Screen.desktopAvailableHeight * 0.92)',1)
                if broken == 'word':
                    needle='font.pixelSize: win.typePx(13)\n                                            wrapMode: Text.Wrap\n                                            maximumLineCount: 2'
                    self.assertEqual(body.count(needle),1)
                    body=body.replace(needle,needle.replace('Text.Wrap','Text.WordWrap'),1)
                driver=DRIVER.replace('__WIDTH__',str(width)).replace('__HEIGHT__',str(height)).replace('__LANG__',language)
                body=body[:body.rfind('}')]+driver+body[body.rfind('}'):]
                qml=private/'welcome.qml'; qml.write_text(body)
                result=subprocess.run(['/usr/bin/moos-qml-shell','--app-id','org.moos.welcome',
                    '--icon','moos-welcome','--qml',str(qml),'--','--cache='+str(private/'cache/store'),
                    '--live=1','--device-plan='+str(private/'absent-plan.json')],
                    env=env,capture_output=True,text=True,timeout=25)
                log=result.stdout+result.stderr
                if broken:
                    self.assertNotIn('MOOS_WELCOME_VIEWPORTS_PASS ',log)
                    self.assertIn('live actions did not scroll into view' if broken=='scroll' else
                        'initial window leaves no native frame room' if broken=='frame' else
                        'caption ink clipped:',log,log[-8000:])
                else:
                    self.assertEqual(result.returncode,0,log[-8000:])
                    self.assertIn('MOOS_WELCOME_VIEWPORTS_PASS ',log,log[-8000:])
                    for error in ('ReferenceError:','TypeError:','Cannot assign','is not a type','Binding loop'):
                        self.assertNotIn(error,log,log[-8000:])


if __name__ == '__main__':
    unittest.main()
