import unittest
from unittest.mock import patch

import app as backend


class EphemerisRegression(unittest.TestCase):
    def setUp(self):
        self.client = backend.app.test_client()
        self.payload = {"birth": {"date": "2000-01-01", "time": "12:00",
                                  "utc_offset_seconds": 0, "latitude": 0, "longitude": 0}}
        self.headers = {"Authorization": "Bearer regression-only"}
        self.auth = patch.object(backend, "API_KEY", "regression-only")
        self.auth.start()
        self.addCleanup(self.auth.stop)

    def test_file_precision_and_authentication(self):
        self.assertEqual(self.client.post('/swiss-chart', json=self.payload).status_code, 401)
        response = self.client.post('/swiss-chart', json=self.payload, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['utc_datetime'], '2000-01-01T12:00:00+00:00')
        self.assertEqual(data['ayanamsa'], 'Lahiri')
        # Independent official Swiss DLL reference for synthetic J2000 input.
        self.assertAlmostEqual(data['sidereal_longitudes']['Moon'], 199.47052896032176, places=8)
        self.assertTrue(all(flag & 7 == 2 for flag in data['ephemeris']['returned_flags'].values()))

    def test_missing_files_return_no_chart(self):
        with patch.object(backend.os.path, 'isfile', return_value=False):
            response = self.client.post('/swiss-chart', json=self.payload, headers=self.headers)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()['code'], 'ephemeris_unavailable')
        self.assertNotIn('sidereal_longitudes', response.get_json())

    def test_silent_fallback_return_flag_is_rejected(self):
        with patch.object(backend.swe, 'calc_ut', return_value=((0, 0, 0, 0, 0, 0), 65860)):
            response = self.client.post('/swiss-chart', json=self.payload, headers=self.headers)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('sidereal_longitudes', response.get_json())

    def test_utc_date_rollover(self):
        for date, time, offset, expected in [
            ('2000-01-01', '01:00', 19800, '1999-12-31T19:30:00+00:00'),
            ('2000-01-01', '23:00', -18000, '2000-01-02T04:00:00+00:00'),
        ]:
            result = backend.parse_birth_datetime_utc({'birth': {'date': date, 'time': time,
                                                                 'utc_offset_seconds': offset}})
            self.assertEqual(result.isoformat(), expected)


if __name__ == '__main__':
    unittest.main()
