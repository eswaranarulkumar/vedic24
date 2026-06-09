# Vedic24 Swiss Ephemeris API

This is a small backend API for Vedic24 WordPress plugin v3.0.

It calculates:

- Swiss Ephemeris sidereal planetary longitudes
- Lahiri Ayanamsa
- Ascendant
- Moon nakshatra and pada
- D1 Rasi chart data
- D9 Navamsa chart data

## Endpoints

Health check:

```text
GET /health
```

Calculation:

```text
POST /swiss-chart
```

## Environment variables

Optional:

```text
VEDIC24_API_KEY=your-secret-api-key
PORT=8000
```

If `VEDIC24_API_KEY` is set, WordPress must send this key as Bearer token.

## WordPress settings

After deploying, put this URL into:

```text
WordPress → Settings → Vedic24 Astrology Engine → Swiss Ephemeris API URL
```

Example:

```text
https://your-app.onrender.com/swiss-chart
```

Then put the same `VEDIC24_API_KEY` into:

```text
Swiss API Key
```

When this works, enable:

```text
Require Swiss Ephemeris
```

## Render deployment

1. Create a free Render account.
2. New → Web Service.
3. Connect GitHub repo or upload these files.
4. Build command:

```text
pip install -r requirements.txt gunicorn
```

5. Start command:

```text
gunicorn app:app
```

6. Add environment variable:

```text
VEDIC24_API_KEY=make-a-long-random-secret
```

7. Your API URL will be:

```text
https://YOUR-APP-NAME.onrender.com/swiss-chart
```

## Test payload

```json
{
  "engine": "swiss_ephemeris",
  "ayanamsa": "lahiri",
  "house_system": "whole_sign",
  "birth": {
    "date": "2026-06-25",
    "time": "14:43",
    "timezone": "Europe/London",
    "utc_offset_seconds": 3600,
    "latitude": 51.752,
    "longitude": -1.2577,
    "place": "Southampton, UK",
    "country": "GB"
  }
}
```
