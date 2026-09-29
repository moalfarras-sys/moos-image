"""Bulk lighting contract: leaf lamps only, real readbacks, honest partials."""
import unittest
from unittest.mock import patch

import command_router
import home_link


LIGHTS = [
    {'entity_id': 'light.desk', 'name': 'Desk', 'state': 'on'},
    {'entity_id': 'light.group', 'name': 'Group', 'state': 'on',
     'is_hue_group': True, 'members': ['light.desk']},
    {'entity_id': 'light.offline', 'name': 'Offline', 'state': 'unavailable'},
    {'entity_id': 'switch.plug', 'name': 'Plug', 'state': 'on'},
]


class BulkLightsTest(unittest.TestCase):
    def test_fresh_summary_does_not_double_count_hue_groups(self):
        with patch.object(home_link, 'entities', return_value=LIGHTS):
            summary=home_link.summary()
        self.assertEqual(summary['lights_available'],1)
        self.assertEqual(summary['lights_total'],2)
        self.assertEqual(summary['light_groups_available'],1)
        self.assertEqual(summary['lights_on'],1)
        self.assertEqual(summary['lights_unavailable'],1)

    def test_only_leaf_lights_and_partial_readback(self):
        with patch.object(home_link, 'entities', return_value=LIGHTS), patch.object(
            home_link, 'control', return_value={'status':'ok','observed_state':'off'}
        ) as control:
            result = home_link.control_all_lights('turn_off')
        control.assert_called_once_with('light.desk', 'turn_off')
        self.assertEqual((result['confirmed'], result['total'], result['status']), (1, 2, 'partial'))
        self.assertEqual(result['results'][1]['status'], 'unavailable')

    def test_failed_readback_is_not_success(self):
        with patch.object(home_link, 'entities', return_value=LIGHTS[:1]), patch.object(
            home_link, 'control', return_value={'status':'pending','observed_state':'on'}
        ):
            result = home_link.control_all_lights('turn_off')
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['confirmed'], 0)

    def test_arabic_and_english_bulk_phrases(self):
        with patch.object(command_router, 'control_all_lights', return_value={
            'status':'partial','confirmed':1,'total':2
        }) as bulk:
            for message, action in (
                ('ميرا اطفئي كل الأضواء', 'turn_off'),
                ('شغلي جميع الاضاءات', 'turn_on'),
                ('turn off all lights', 'turn_off'),
            ):
                result = command_router.dispatch(message)
                bulk.assert_called_with(action)
                self.assertEqual(result['kind'], 'home')
                self.assertIn('1/2', result['message'])

    def test_reject_non_power_bulk_request(self):
        with self.assertRaises(ValueError):
            home_link.control_all_lights('color')

    def test_named_city_weather_uses_live_provider(self):
        with patch.object(command_router,'current_weather',return_value={
            'status':'ok','city':'برلين','condition_ar':'غائم جزئياً',
            'temperature_c':14.1,'source':'Open-Meteo'
        }) as weather:
            result=command_router.dispatch('ميرا ما الطقس الآن في برلين؟')
        weather.assert_called_once_with('برلين')
        self.assertEqual(result['kind'],'weather')
        self.assertIn('14.1',result['message'])
        with self.assertRaises(ValueError):
            command_router.dispatch('ما الطقس؟')

    def test_home_status_command_reads_fresh_summary(self):
        observed={'status':'ok','lights_available':4,'lights_total':6,
                  'lights_on':1,'devices_available':8}
        with patch.object(command_router,'summary',return_value=observed) as summary:
            result=command_router.dispatch('ميرا، حالة المنزل')
        summary.assert_called_once_with()
        self.assertEqual(result['kind'],'home')
        self.assertIn('4 من 6',result['message'])


if __name__ == '__main__':
    unittest.main()
