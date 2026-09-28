"""Local persistence stays readable and does not grant capabilities."""
import os
import tempfile
import unittest
from pathlib import Path


class MemoryTest(unittest.TestCase):
    def test_profile_and_conversation_survive_reload(self):
        with tempfile.TemporaryDirectory() as temp:
            old=os.environ.get('XDG_CONFIG_HOME')
            os.environ['XDG_CONFIG_HOME']=temp
            import importlib, mira_memory
            memory=importlib.reload(mira_memory)
            try:
                memory.save_profile('طوّرت ميرا مع MoOS. مشروعي هو مساعد منزلي.')
                memory.add_message('user','مرحبا ميرا')
                memory.add_message('mira','أهلاً بك')
                memory.add_message('action','حدث التنفيذ')
                self.assertIn('MoOS',memory.profile_text())
                self.assertEqual([m['role'] for m in memory.recent_messages()],['user','mira'])
                memory.add_message('user','كم ضوء عندي؟')
                memory.add_message('mira','يوجد ')
                memory.add_message('mira','ضوءان.')
                history=memory.recent_messages(3)
                self.assertEqual([m['role'] for m in history],['mira','user','mira'])
                self.assertEqual(history[-1]['text'],'يوجد ضوءان.')
                self.assertEqual(Path(memory.PROFILE).stat().st_mode & 0o777,0o600)
                self.assertEqual(Path(memory.CONVERSATION).stat().st_mode & 0o777,0o600)
            finally:
                if old is None:os.environ.pop('XDG_CONFIG_HOME',None)
                else:os.environ['XDG_CONFIG_HOME']=old
                importlib.reload(mira_memory)
