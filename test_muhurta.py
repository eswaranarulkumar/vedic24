"""Focused native-Linux regressions. Synthetic chart values; no model/email calls."""
import copy
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import app as backend


class MuhurtaRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = {
            'event': {'type': 'Business Launch / Opening', 'policy_id': 'vedic24-business-daytime-v1',
                      'start_date': '2026-11-01', 'end_date': '2026-11-30',
                      'location': {'place': 'Lima', 'country': 'PE', 'latitude': -12.0466888,
                                   'longitude': -77.0430886, 'timezone': 'America/Lima'}},
            'natal': {'moon_longitude': 97.52111111111111, 'ascendant_sign': 'Gemini'}
        }
        cls.headers = {'Authorization': 'Bearer local-regression-only'}
        with patch.object(backend, 'API_KEY', 'local-regression-only'):
            response = backend.app.test_client().post('/muhurta', json=cls.payload, headers=cls.headers)
        if response.status_code != 200:
            raise AssertionError((response.status_code, response.get_json()))
        cls.result = response.get_json()

    def test_native_windows_and_all_requested_days(self):
        self.assertEqual(self.result['calculation']['ephemeris_mode'], 'swiss_files')
        self.assertEqual(len(self.result['days']), 30)
        self.assertEqual(self.result['calculation']['all_requested_local_days_processed'], 30)
        expected = [('2026-11-25T05:37-05:00','2026-11-25T06:20-05:00',43),
                    ('2026-11-16T12:00-05:00','2026-11-16T12:55-05:00',55),
                    ('2026-11-06T17:04-05:00','2026-11-06T17:40-05:00',36)]
        actual = [(c['start_local'],c['end_local'],c['duration_minutes']) for c in self.result['recommended_candidates']]
        self.assertEqual(actual,expected)
        for c in self.result['recommended_candidates']:
            self.assertEqual(datetime.fromisoformat(c['start_local']),datetime.fromisoformat(c['start_utc']))

    def test_phase_reference_and_sign_lord_separation(self):
        expected={'New Moon':'2026-11-09T07:02:00+00:00','Full Moon':'2026-11-24T14:53:00+00:00'}
        for phase in self.result['moon_phases']:
            self.assertLess(abs((datetime.fromisoformat(phase['utc'])-datetime.fromisoformat(expected[phase['phase']])).total_seconds()),60)
        self.assertEqual(self.result['natal_identity']['ascendant_sign_lord'],'Mercury')
        for c in self.result['recommended_candidates']:
            self.assertEqual(c['transits_at_midpoint']['Saturn']['sign'],'Pisces')

    def test_existing_auth_required_for_new_route(self):
        with patch.object(backend,'API_KEY','local-regression-only'):
            self.assertEqual(backend.app.test_client().post('/muhurta',json=self.payload).status_code,401)

    def test_invalid_location_and_unsupported_event_rejected(self):
        client=backend.app.test_client()
        with patch.object(backend,'API_KEY','local-regression-only'):
            for kind in ['missing_location','wrong_policy','invalid_zone']:
                data=copy.deepcopy(self.payload)
                if kind=='missing_location':del data['event']['location']
                if kind=='wrong_policy':data['event']['type']='Wedding / Vivah'
                if kind=='invalid_zone':data['event']['location']['timezone']='invalid/zone'
                self.assertEqual(client.post('/muhurta',json=data,headers=self.headers).status_code,400)


if __name__=='__main__':unittest.main()
