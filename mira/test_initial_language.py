import unittest
import i18n


class InitialLanguage(unittest.TestCase):
    def test_saved_explicit_choice_is_preserved(self):
        self.assertEqual(i18n.initial_language('ar', {'LANGUAGE': 'en_US'}), 'ar')
        self.assertEqual(i18n.initial_language('en', {'LANGUAGE': 'ar'}), 'en')

    def test_fresh_profile_follows_the_supported_session(self):
        for env, expected in (({'LANGUAGE': 'en_US:ar', 'LANG': 'ar_SA.UTF-8'}, 'en'),
                              ({'LANGUAGE': 'ar:en', 'LANG': 'en_US.UTF-8'}, 'ar'),
                              ({'LC_ALL': 'ar_SA.UTF-8'}, 'ar'),
                              ({'LANG': 'en-US.UTF-8'}, 'en')):
            with self.subTest(environment=env):
                self.assertEqual(i18n.initial_language(None, env), expected)

    def test_unknown_technical_and_unsupported_locales_default_to_arabic(self):
        for env in ({}, {'LANG': 'C.UTF-8'}, {'LANG': 'de_DE.UTF-8'}):
            self.assertEqual(i18n.initial_language(None, env), 'ar')
        self.assertEqual(i18n.initial_language('invalid', {'LANGUAGE': 'en'}), 'en')


if __name__ == '__main__':
    unittest.main(verbosity=2)
