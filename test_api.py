
import json
from app import app
client = app.test_client()
resp = client.get("/health")
assert resp.status_code == 200, resp.data
payload = {
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
resp = client.post("/swiss-chart", json=payload)
assert resp.status_code == 200, resp.data
data = resp.get_json()
print("engine=", data["engine"])
print("ayanamsa=", data["ayanamsa"])
print("sun_sign=", data["planets"]["Sun"]["sign"])
print("moon_sign=", data["planets"]["Moon"]["sign"])
print("nakshatra=", data["nakshatra"]["name"], data["nakshatra"]["pada"])
print("asc=", data["ascendant"]["sign"])
assert data["planets"]["Sun"]["sign"] == "Gemini"
assert data["planets"]["Moon"]["sign"] == "Libra"
assert data["nakshatra"]["name"] == "Vishakha"
assert data["nakshatra"]["pada"] == 1
