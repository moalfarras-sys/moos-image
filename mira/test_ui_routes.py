"""Exercise Mira's visible routes without touching live devices."""
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ['MIRA_TEST_MODE']='1'
_settings=tempfile.TemporaryDirectory(prefix='mira-v4-test-')
os.environ['XDG_CONFIG_HOME']=_settings.name

from PySide6.QtCore import QObject,Signal
from PySide6.QtWidgets import QApplication,QPushButton
import app


class FakeBridge(QObject):
    connected=Signal(object)
    state=Signal(object)
    error=Signal(str)
    command_state=Signal(str,str)
    voice_state=Signal(str,str)
    def __init__(self,voice_name='Aoede'):
        super().__init__()
        self.online=True
        self.voice_name=voice_name
        self.voice=None
        self.commands=[]
    def start(self):pass
    def command(self,*args):self.commands.append(args)
    def set_voice(self,value):self.commands.append(('voice',value))
    def cancel_voice(self):self.commands.append(('cancel',))


class UiRoutesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt=QApplication.instance() or QApplication([])
        cls.bridge_patch=patch.object(app,'Bridge',FakeBridge)
        cls.bridge_patch.start()
    @classmethod
    def tearDownClass(cls):
        cls.bridge_patch.stop()
        _settings.cleanup()
    def setUp(self):
        self.window=app.Window()
        self.qt.processEvents()
    def tearDown(self):
        self.window.close()

    def wait_for(self,predicate):
        for _ in range(100):
            self.qt.processEvents()
            if predicate():return
            time.sleep(.01)
        self.fail('async route did not finish')

    def test_five_real_workspaces_and_two_preserved_faces(self):
        w=self.window
        self.assertEqual(w.tabs.count(),5)
        for index in range(5):
            w.tabs.setCurrentIndex(index)
            self.assertEqual(w.tabs.currentIndex(),index)
        self.assertEqual(set(w.face_choices),{'rose','holo'})
        for style,button in w.face_choices.items():
            button.click()
            self.assertEqual(w.face_style,style)
            self.assertEqual(w.settings.value('face_style'),style)
        w.voice_phase='ready'
        w.mic_btn.click()
        self.assertIn(('wake','wake_assistant_1'),w.bridge.commands)
        self.assertIn('أطلب من Echo',w.voice_bar.status_text)
        w.on_device_command_state('wake','sent')
        self.assertIn('أُرسل طلب',w.voice_bar.status_text)
        w.on_voice_state('activating','')
        self.assertEqual(w.voice_phase,'thinking')
        w.stop_btn.setEnabled(True)
        w.stop_btn.click()
        self.assertIn(('cancel',),w.bridge.commands)

    def test_local_wake_uses_same_verified_echo_route(self):
        w=self.window
        w.voice_phase='ready'
        w.local_wake_enabled=True
        w.handle_instance_command(b'wake')
        self.assertIn(('wake','wake_assistant_1'),w.bridge.commands)
        count=len(w.bridge.commands)
        w.voice_phase='listening'
        w.handle_instance_command(b'wake')
        self.assertEqual(len(w.bridge.commands),count)

    def test_empty_echo_audio_is_reported_honestly(self):
        w=self.window
        w.on_voice_state('stats','{"microphone_bytes": 0, "reply_bytes": 0}')
        self.assertIn('لم يصل صوت من Echo',w.voice_bar.status_text)
        w.on_voice_state('stats','{"microphone_bytes": 4096, "microphone_peak": 900, '
                                 '"reply_bytes": 0, "heard": ""}')
        self.assertIn('لم يُفهم السؤال',w.voice_bar.status_text)

    def test_home_buttons_run_backend_and_show_honest_result(self):
        w=self.window
        fixture=[{'entity_id':'light.desk','name':'Desk','state':'on','brightness':128,
                  'supported_features':0,'supported_color_modes':['xy'],'rgb_color':[255,0,0]}]
        w.home_result({'kind':'devices','devices':fixture})
        self.assertEqual(w.home_list.count(),1)
        self.assertTrue(w.home_off.isEnabled())
        with patch('home_link.control',return_value={
            'status':'ok','entity_id':'light.desk','observed_state':'off'
        }) as control,patch('home_link.entities',return_value=fixture):
            w.home_off.click()
            self.wait_for(lambda: control.called)
            control.assert_called_with('light.desk','turn_off',value=None,color=None)
        with patch('home_link.control_all_lights',return_value={
            'status':'partial','confirmed':1,'total':2,'results':[]
        }) as bulk,patch('home_link.entities',return_value=fixture):
            w.run_home_action('all_off')
            self.wait_for(lambda: bulk.called)
            bulk.assert_called_with('turn_off')

    def test_tv_control_never_changes_all_lights(self):
        w=self.window
        self.assertFalse(w.dev_tv.toggle_enabled)
        fixture=[{'entity_id':'media_player.lounge','name':'Lounge TV','state':'off',
                  'supported_features':128|256}]
        w.home_result({'kind':'devices','devices':fixture})
        self.assertEqual(w.tv_entity_id,'media_player.lounge')
        self.assertTrue(w.dev_tv.toggle_enabled)
        with patch.object(w.home_jobs,'run') as run:
            w.dev_tv.toggle_requested.emit(True)
            run.assert_called_once_with('turn_on','media_player.lounge')
        self.assertFalse(w.dev_tv.is_on)  # UI changes only after backend readback.
        w.home_result({'kind':'devices','devices':[dict(fixture[0],state='on')]})
        self.assertTrue(w.dev_tv.is_on)
        with patch.object(w.home_jobs,'run') as run:
            w.dev_tv.toggle_requested.emit(False)
            run.assert_called_once_with('turn_off','media_player.lounge')

    def test_no_invented_chat_or_weather(self):
        w=self.window
        self.assertIn('اسأل ميرا',w.empty_chat.text())
        self.assertNotIn('Samsung TV',w.conversation_log.toPlainText())
        self.assertNotIn('إليك توقعات الطقس في برلين غداً',w.conversation_log.toPlainText())
        self.assertEqual(w.weather_clock.temp_lbl.text(),'—°')
        self.assertIn('حدّد المدينة',w.weather_clock.desc_lbl.text())
        with patch('weather_link.current') as weather:
            w.update_weather_async()
            weather.assert_not_called()

    def test_weather_city_and_face_shortcut(self):
        w=self.window
        w.weather_city_input.setText('برلين')
        with patch.object(w,'update_weather_async') as update:
            w.save_weather_city()
            update.assert_called_once()
        self.assertEqual(w.settings.value('weather_city'),'برلين')
        shortcut=next(b for b in w.findChildren(QPushButton)
                      if b.toolTip()=='اختيار وجه ميرا من الإعدادات')
        shortcut.click()
        self.assertEqual(w.tabs.currentIndex(),4)

    def test_dock_labels_open_their_matching_real_screen(self):
        w=self.window
        buttons=w.dock_categories.findChildren(QPushButton)
        self.assertEqual([b.text().split(' ',1)[1] for b in buttons],
                         ['البيت','الكمبيوتر','المحادثة','الإعدادات'])
        for button,index in zip(buttons,[1,3,2,4]):
            button.click()
            self.assertEqual(w.tabs.currentIndex(),index)
        self.assertTrue(any(b.text()=='التطبيقات المثبتة' for b in w.pc_buttons))

    def test_microphone_source_selection_is_saved_and_restarts_listener(self):
        w=self.window
        w.mic_source_picker.addItem('test-mic','test-mic')
        with patch.object(w,'stop_local_wake') as stop,patch.object(w,'start_local_wake') as start:
            w.mic_source_picker.setCurrentIndex(w.mic_source_picker.findData('test-mic'))
        self.assertEqual(w.settings.value('local_wake_source'),'test-mic')
        stop.assert_called_once_with()
        start.assert_called_once_with()

    def test_computer_read_buttons_reach_moai_bridge(self):
        w=self.window
        with patch.object(w.pc_jobs,'run') as run:
            for button in w.pc_buttons:
                button.click()
        self.assertEqual([call.args[0] for call in run.call_args_list],
                         ['get_system_status','memory_status','disk_status',
                          'network_status','top_processes','list_failed_units',
                          'list_installed_apps'])

    def test_home_detail_buttons_target_only_selected_device(self):
        w=self.window
        light={'entity_id':'light.desk','name':'Desk','state':'off',
               'supported_features':40,'supported_color_modes':['xy'],
               'brightness':100}
        w.home_result({'kind':'devices','devices':[light]})
        with patch.object(w.home_jobs,'run') as run:
            w.home_on.click()
            w.home_color_button.click()
            w.home_brightness.sliderReleased.emit()
        self.assertEqual(run.call_args_list[0].args,('turn_on','light.desk',None,None))
        self.assertEqual(run.call_args_list[1].args[0:2],('color','light.desk'))
        self.assertEqual(run.call_args_list[2].args[0:2],('brightness','light.desk'))

    def test_profile_save_is_private_and_voice_settings_reach_bridge(self):
        w=self.window
        w.profile_editor.setPlainText('أعمل على MoOS وميرا')
        w.profile_save.click()
        from mira_memory import PROFILE
        self.assertIn('MoOS',PROFILE.read_text())
        self.assertEqual(PROFILE.stat().st_mode & 0o777,0o600)
        w.voice_picker.setCurrentIndex(w.voice_picker.findData('Kore'))
        self.assertEqual(w.voice_name,'Kore')
        self.assertEqual(w.bridge.voice_name,'Kore')

    def test_computer_and_text_routes(self):
        w=self.window
        with patch('moai_link.execute',return_value={'status':'ok','output':'real system status'}) as execute:
            w.run_pc_tool('get_system_status')
            self.wait_for(lambda: execute.called)
            execute.assert_called_with('get_system_status',{})
        with patch('command_router.dispatch',return_value=None),patch.object(w.chat_bridge,'ask') as ask:
            w.chat_input.setText('مرحبا ميرا')
            w.chat_input.returnPressed.emit()
            self.wait_for(lambda: ask.called)
            ask.assert_called_with('مرحبا ميرا')
        self.assertIn('مرحبا ميرا',w.conversation_log.toPlainText())

    def test_attachment_enters_message(self):
        w=self.window
        with tempfile.NamedTemporaryFile('w',suffix='.txt',encoding='utf-8',delete=False) as file:
            file.write('Mira attachment test')
            path=file.name
        try:
            with patch.object(app.QFileDialog,'getOpenFileName',return_value=(path,'')):
                w.attach_text()
            self.assertIn('Mira attachment test',w.chat_input.text())
        finally:
            Path(path).unlink()

    def test_mobile_navigation_and_single_command_dock(self):
        w=self.window
        w.resize(480,900)
        w.show()
        self.qt.processEvents()
        self.assertTrue(w.mobile_menu_button.isVisible())
        self.assertFalse(w.context_panel.isVisible())
        w.mobile_menu_button.menu().actions()[1].trigger()
        self.assertEqual(w.tabs.currentIndex(),1)
        self.assertIs(w.chat_input.parentWidget(),w.conversation_composer)
        w.chat_input.setText('ميرا افحصي حالة الكمبيوتر')
        with patch.object(w.command_bridge,'run') as run:
            w.conversation_composer.findChildren(QPushButton)[1].click()
            run.assert_called_once_with('ميرا افحصي حالة الكمبيوتر')
        self.assertFalse(w.stop_btn.isEnabled())
        w.on_voice_state('listening','')
        self.assertTrue(w.stop_btn.isEnabled())
        self.assertEqual(w.orb.phase,'listening')
        w.on_voice_state('thinking','')
        self.assertEqual(w.orb.phase,'thinking')
        w.on_voice_state('speaking','')
        self.assertEqual(w.orb.phase,'speaking')
        w.on_voice_state('ready','')
        self.assertFalse(w.stop_btn.isEnabled())

    def test_quick_actions_are_real_commands(self):
        w=self.window
        with patch.object(w,'_send_command') as send:
            buttons=w.dock_quick.findChildren(QPushButton)
            self.assertEqual(len(buttons),2)
            buttons[0].click()
            buttons[1].click()
            self.assertEqual(send.call_args_list[0].args[0],'ميرا، أطفئي كل الأضواء')
            self.assertEqual(send.call_args_list[1].args[0],'ميرا، افحصي حالة الكمبيوتر')

    def test_computer_volume_requires_observed_readback(self):
        w=self.window
        output=[]
        w.pc_jobs.result.connect(output.append)
        from unittest.mock import call
        with patch('moai_link.execute',side_effect=[
            {'status':'ok','output':'requested'},
            {'status':'ok','output':'{"volume":42,"brightness":80}'},
        ]) as execute:
            w.pc_jobs.run('set_volume',{'value':'42'})
            self.wait_for(lambda:bool(output))
            self.assertEqual(output[0]['status'],'ok')
            self.assertEqual(execute.call_args_list,[call('set_volume',{'value':'42'}),call('get_system_status',{})])
        output.clear()
        with patch('moai_link.execute',side_effect=[
            {'status':'ok','output':'requested'},
            {'status':'ok','output':'{"volume":40,"brightness":80}'},
        ]):
            w.pc_jobs.run('set_volume',{'value':'42'})
            self.wait_for(lambda:bool(output))
            self.assertEqual(output[0]['status'],'pending')


if __name__=='__main__':unittest.main()
