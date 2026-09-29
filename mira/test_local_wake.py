"""Short-utterance wake matching without opening a live microphone."""
import unittest
import queue
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from local_wake import is_wake, offer_speech, transcribe_wake


class FakeModel:
    def __init__(self, *answers):
        self.answers = iter(answers)
        self.calls = []

    def transcribe(self, _samples, **kwargs):
        self.calls.append(kwargs)
        text, no_speech, logprob = next(self.answers)
        return [SimpleNamespace(text=text, no_speech_prob=no_speech,
                                avg_logprob=logprob)], None


class LocalWakeTest(unittest.TestCase):
    def test_name_variants_and_word_boundary(self):
        for phrase in ('ميرا', 'يا ميرا', 'هاي ميرا', 'ميرا ميرا',
                       'يا مينا', 'هاي ميرنا', 'ميا', 'hey mira', 'meera'):
            self.assertTrue(is_wake(phrase), phrase)
        for phrase in ('يا', 'مرة', 'كاميرا', 'متى', 'أطفئ الضوء', 'مينا'):
            self.assertFalse(is_wake(phrase), phrase)

    def test_short_name_accepts_plausible_asr_score_without_prompting(self):
        model = FakeModel(('ميرا', .6, -1.1))
        pcm = np.full(16000, 2000, dtype='<i2').tobytes()
        with patch('local_wake.get_speech_timestamps', return_value=[{'start':0,'end':16000}]):
            self.assertTrue(transcribe_wake(model, pcm))
        self.assertEqual(len(model.calls), 1)
        self.assertNotIn('hotwords', model.calls[0])

    def test_low_confidence_keyword_does_not_wake(self):
        model = FakeModel(('ميرا', .9, -.5), ('other', .2, -.5))
        pcm = np.full(16000, 2000, dtype='<i2').tobytes()
        with patch('local_wake.get_speech_timestamps', return_value=[{'start':0,'end':16000}]):
            self.assertFalse(transcribe_wake(model, pcm))

    def test_bilingual_retry_even_when_arabic_result_empty(self):
        model = FakeModel(('', .95, -2), ('mira', .4, -.5))
        pcm = np.full(16000, 2000, dtype='<i2').tobytes()
        with patch('local_wake.get_speech_timestamps', return_value=[{'start':0,'end':16000}]):
            self.assertTrue(transcribe_wake(model, pcm))
        self.assertEqual([call['language'] for call in model.calls], ['ar', None])

    def test_silence_cannot_wake(self):
        model = FakeModel()
        self.assertFalse(transcribe_wake(model, np.zeros(16000, dtype='<i2').tobytes()))
        self.assertEqual(model.calls, [])

    def test_energy_without_speech_never_runs_whisper(self):
        model = FakeModel()
        pcm = np.full(16000, 2000, dtype='<i2').tobytes()
        with patch('local_wake.get_speech_timestamps', return_value=[]):
            self.assertFalse(transcribe_wake(model, pcm))
        self.assertEqual(model.calls, [])

    def test_slow_decoder_drops_old_audio_instead_of_blocking_capture(self):
        pending = queue.Queue(maxsize=2)
        for phrase in (b'old', b'newer', b'newest'):
            offer_speech(pending, phrase)
        self.assertEqual([pending.get_nowait()[1] for _ in range(2)],
                         [b'newer', b'newest'])


if __name__ == '__main__':
    unittest.main()
