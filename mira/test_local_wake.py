"""Short-utterance wake matching without opening a live microphone."""
import unittest
from types import SimpleNamespace

import numpy as np

from local_wake import is_wake, transcribe_wake


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
                       'مينا', 'ميرنا', 'ميا', 'hey mira', 'meera'):
            self.assertTrue(is_wake(phrase), phrase)
        for phrase in ('يا', 'مرة', 'كاميرا', 'متى', 'أطفئ الضوء'):
            self.assertFalse(is_wake(phrase), phrase)

    def test_short_name_accepts_plausible_weak_asr_score(self):
        model = FakeModel(('ميرا', .7, -1.3))
        pcm = np.full(16000, 2000, dtype='<i2').tobytes()
        self.assertTrue(transcribe_wake(model, pcm))
        self.assertEqual(len(model.calls), 1)
        self.assertIn('ميرا', model.calls[0]['hotwords'])

    def test_bilingual_retry_even_when_arabic_result_empty(self):
        model = FakeModel(('', .95, -2), ('mira', .4, -.5))
        pcm = np.full(16000, 2000, dtype='<i2').tobytes()
        self.assertTrue(transcribe_wake(model, pcm))
        self.assertEqual([call['language'] for call in model.calls], ['ar', None])

    def test_silence_cannot_wake(self):
        model = FakeModel()
        self.assertFalse(transcribe_wake(model, np.zeros(16000, dtype='<i2').tobytes()))
        self.assertEqual(model.calls, [])


if __name__ == '__main__':
    unittest.main()
