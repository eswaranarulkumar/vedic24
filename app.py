import os
import math
from datetime import datetime, timezone, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS
import swisseph as swe

app = Flask(__name__)
CORS(app)

API_KEY = os.environ.get("VEDIC24_API_KEY", "").strip()

PLANETS = {
    "Sun": swe.SUN,
    "Moon": swe.MOON,
    "Mars": swe.MARS,
    "Mercury": swe.MERCURY,
    "Jupiter": swe.JUPITER,
    "Venus": swe.VENUS,
    "Saturn": swe.SATURN,
    "Rahu": swe.TRUE_NODE,
}

SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]

NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni",
    "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha",
    "Anuradha", "Jyeshtha", "Mula", "Purva Ashadha", "Uttara Ashadha",
    "Shravana", "Dhanishta", "Shatabhisha", "Purva Bhadrapada",
    "Uttara Bhadrapada", "Revati"
]

def normalize_degree(deg):
    return float(deg) % 360.0

def sign_num_from_lon(lon):
    return int(math.floor(normalize_degree(lon) / 30.0)) + 1

def sign_name_from_lon(lon):
    return SIGNS[sign_num_from_lon(lon) - 1]

def nakshatra_from_lon(lon):
    lon = normalize_degree(lon)
    segment = 360.0 / 27.0
    idx = int(math.floor(lon / segment))
    within = lon - (idx * segment)
    pada = int(math.floor(within / (segment / 4.0))) + 1
    return {
        "name": NAKSHATRAS[max(0, min(26, idx))],
        "pada": max(1, min(4, pada)),
    }

def navamsa_sign_from_lon(lon):
    lon = normalize_degree(lon)
    rasi_index = int(math.floor(lon / 30.0))  # 0 based
    within_sign = lon - (rasi_index * 30.0)
    navamsa_part = int(math.floor(within_sign / (30.0 / 9.0)))  # 0..8

    # Movable signs start from same sign, fixed from 9th, dual from 5th.
    modality = rasi_index % 3
    if modality == 0:
        start = rasi_index
    elif modality == 1:
        start = (rasi_index + 8) % 12
    else:
        start = (rasi_index + 4) % 12

    return ((start + navamsa_part) % 12) + 1

def build_chart_data_from_lons(planet_lons, asc_sign_num):
    houses = {}
    for house in range(1, 13):
        houses[str(house)] = {
            "sign_num": ((asc_sign_num + house - 2) % 12) + 1,
            "items": []
        }

    houses["1"]["items"].append("ASC")

    order = [
        ("Sun", "SU"), ("Moon", "MO"), ("Mars", "MA"), ("Mercury", "ME"),
        ("Jupiter", "JU"), ("Venus", "VE"), ("Saturn", "SA"),
        ("Rahu", "RA"), ("Ketu", "KE")
    ]

    for planet, label in order:
        lon = planet_lons.get(planet)
        if lon is None:
            continue
        sign_num = sign_num_from_lon(lon)
        house = ((sign_num - asc_sign_num + 12) % 12) + 1
        houses[str(house)]["items"].append(label)

    return {
        "asc_sign_num": asc_sign_num,
        "houses": houses
    }

def build_chart_data_from_signs(planet_signs, asc_sign_num):
    houses = {}
    for house in range(1, 13):
        houses[str(house)] = {
            "sign_num": ((asc_sign_num + house - 2) % 12) + 1,
            "items": []
        }

    houses["1"]["items"].append("ASC")

    labels = {
        "Sun": "SU", "Moon": "MO", "Mars": "MA", "Mercury": "ME",
        "Jupiter": "JU", "Venus": "VE", "Saturn": "SA",
        "Rahu": "RA", "Ketu": "KE"
    }

    for planet in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]:
        sign_num = planet_signs.get(planet)
        if sign_num is None:
            continue
        house = ((int(sign_num) - asc_sign_num + 12) % 12) + 1
        houses[str(house)]["items"].append(labels[planet])

    return {
        "asc_sign_num": asc_sign_num,
        "houses": houses
    }

def parse_birth_datetime_utc(payload):
    birth = payload.get("birth", {})
    date_str = birth.get("date")
    time_str = birth.get("time")
    offset_seconds = int(birth.get("utc_offset_seconds", 0))

    if not date_str or not time_str:
        raise ValueError("Missing birth.date or birth.time")

    # WordPress sends local date/time + UTC offset seconds.
    local_naive = datetime.fromisoformat(f"{date_str}T{time_str}:00")
    utc_dt = local_naive - timedelta(seconds=offset_seconds)
    return utc_dt.replace(tzinfo=timezone.utc)

def auth_ok():
    if not API_KEY:
        return True
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth.replace("Bearer ", "", 1).strip() == API_KEY
    return request.headers.get("X-API-Key", "").strip() == API_KEY

@app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "service": "Vedic24 Swiss Ephemeris API",
        "engine": "Swiss Ephemeris",
        "ayanamsa": "Lahiri"
    })

@app.post("/swiss-chart")
def swiss_chart():
    if not auth_ok():
        return jsonify({"error": "Unauthorized"}), 401

    try:
        payload = request.get_json(force=True)
        birth = payload.get("birth", {})

        utc_dt = parse_birth_datetime_utc(payload)
        jd_ut = swe.julday(
            utc_dt.year,
            utc_dt.month,
            utc_dt.day,
            utc_dt.hour + (utc_dt.minute / 60.0) + (utc_dt.second / 3600.0)
        )

        latitude = float(birth.get("latitude", 0))
        longitude = float(birth.get("longitude", 0))

        swe.set_sid_mode(swe.SIDM_LAHIRI)
        flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED

        sidereal_longitudes = {}
        planets = {}

        for name, planet_id in PLANETS.items():
            result, ret_flag = swe.calc_ut(jd_ut, planet_id, flags)
            lon = normalize_degree(result[0])
            speed = float(result[3]) if len(result) > 3 else 0.0
            sidereal_longitudes[name] = lon
            planets[name] = {
                "longitude": lon,
                "sign_num": sign_num_from_lon(lon),
                "sign": sign_name_from_lon(lon),
                "degree_in_sign": lon % 30.0,
                "retrograde": speed < 0
            }

        # Ketu is always opposite Rahu.
        ketu_lon = normalize_degree(sidereal_longitudes["Rahu"] + 180.0)
        sidereal_longitudes["Ketu"] = ketu_lon
        planets["Ketu"] = {
            "longitude": ketu_lon,
            "sign_num": sign_num_from_lon(ketu_lon),
            "sign": sign_name_from_lon(ketu_lon),
            "degree_in_sign": ketu_lon % 30.0,
            "retrograde": True
        }

        # Sidereal ascendant using Swiss Ephemeris house calculation.
        cusps, ascmc = swe.houses_ex(jd_ut, latitude, longitude, b'P', flags)
        asc_lon = normalize_degree(ascmc[0])
        asc_sign_num = sign_num_from_lon(asc_lon)

        moon_lon = sidereal_longitudes["Moon"]
        nak = nakshatra_from_lon(moon_lon)

        d1 = build_chart_data_from_lons(sidereal_longitudes, asc_sign_num)

        navamsa_planet_signs = {
            planet: navamsa_sign_from_lon(lon)
            for planet, lon in sidereal_longitudes.items()
        }
        navamsa_asc_sign_num = navamsa_sign_from_lon(asc_lon)
        d9 = build_chart_data_from_signs(navamsa_planet_signs, navamsa_asc_sign_num)

        return jsonify({
            "engine": "Swiss Ephemeris",
            "ayanamsa": "Lahiri",
            "julian_day_ut": jd_ut,
            "utc_datetime": utc_dt.isoformat(),
            "ascendant_longitude": asc_lon,
            "ascendant": {
                "longitude": asc_lon,
                "sign_num": asc_sign_num,
                "sign": sign_name_from_lon(asc_lon),
                "degree_in_sign": asc_lon % 30.0
            },
            "sidereal_longitudes": sidereal_longitudes,
            "planets": planets,
            "nakshatra": nak,
            "d1": d1,
            "d9": d9
        })

    except Exception as exc:
        return jsonify({"error": str(exc)}), 400

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
