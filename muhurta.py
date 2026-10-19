"""Muhurta-only calculation layer. Existing natal/D1/D9/dasha code is untouched.

One explicitly named business-opening policy, not a universal muhurta rulebook.
Windows are whole minutes wholly inside a stable calculated interval. Daytime
only, sunrise by Swiss Hindu-rising convention; no guessed clocks or fallback.
"""
import hashlib
import json
import math
import os
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

UTC = timezone.utc
SIGNS = ['Aries','Taurus','Gemini','Cancer','Leo','Virgo','Libra','Scorpio','Sagittarius','Capricorn','Aquarius','Pisces']
LORDS = ['Mars','Venus','Mercury','Moon','Sun','Mercury','Venus','Mars','Jupiter','Saturn','Saturn','Jupiter']
NAKS = ['Ashwini','Bharani','Krittika','Rohini','Mrigashira','Ardra','Punarvasu','Pushya','Ashlesha','Magha','Purva Phalguni','Uttara Phalguni','Hasta','Chitra','Swati','Vishakha','Anuradha','Jyeshtha','Mula','Purva Ashadha','Uttara Ashadha','Shravana','Dhanishta','Shatabhisha','Purva Bhadrapada','Uttara Bhadrapada','Revati']
NAK_LORDS = ['Ketu','Venus','Sun','Moon','Mars','Rahu','Jupiter','Saturn','Mercury']
TITHIS = ['Pratipada','Dwitiya','Tritiya','Chaturthi','Panchami','Shashthi','Saptami','Ashtami','Navami','Dashami','Ekadashi','Dwadashi','Trayodashi','Chaturdashi','Purnima']
YOGAS = ['Vishkambha','Priti','Ayushman','Saubhagya','Shobhana','Atiganda','Sukarma','Dhriti','Shoola','Ganda','Vriddhi','Dhruva','Vyaghata','Harshana','Vajra','Siddhi','Vyatipata','Variyana','Parigha','Shiva','Siddha','Sadhya','Shubha','Shukla','Brahma','Indra','Vaidhriti']
MOVABLE_KARANAS = ['Bava','Balava','Kaulava','Taitila','Garija','Vanija','Vishti']
POLICY_ID = 'vedic24-business-daytime-v1'
POLICY = {
    'id': POLICY_ID, 'event_type': 'Business Launch / Opening',
    'display_name': 'Daytime business-opening selection with personal Moon checks',
    'weekdays': [0,2,3,4],
    'nakshatras': [0,3,4,6,7,11,12,13,14,16,20,21,22,23,25,26],
    'excluded_tithis': [4,9,14,19,24,29,30],
    'excluded_yogas': [17,27], 'excluded_karanas': ['Vishti'],
    'tarabala': [2,4,6,8,9], 'chandrabala': [1,3,6,7,10,11],
    'minimum_minutes': 15,
    'sources': [
        'https://nidarshanavedh.com/muhurat/business-opening-muhurat/',
        'https://panchangtime.com/about/tarabala',
        'https://nidarshanavedh.com/calculators/chandrabala-calculator/',
        'https://vedangam.org/jyotisha/panchanga/muhurta'],
    'limitations': [
        'A named business-opening policy; other traditions may select differently.',
        'Daytime windows only. No wedding or other event policy is inferred.',
        'Checks Panchang, tarabala, chandrabala, Moon eighth from election lagna, Rahu Kalam, Yamaganda and Gulika.',
        'Does not claim exhaustive lagna shuddhi, divisional election charts, combustion, eclipses, Durmuhurta or every regional exception.',
        'Ranking prefers Mercury/Jupiter weekday or hora, then longer usable intervals; no outcome probability is calculated.']}
# Monday=0; one-based daylight eighths and weekday planetary rulers.
EXCLUSION_PARTS = {'Rahu Kalam':[2,7,5,6,4,3,8], 'Yamaganda':[4,3,2,1,7,6,5], 'Gulika':[6,5,4,3,2,1,7]}
DAY_LORDS = ['Moon','Mars','Mercury','Jupiter','Venus','Saturn','Sun']
HORA_ORDER = ['Saturn','Jupiter','Mars','Sun','Venus','Mercury','Moon']


class MuhurtaInputError(ValueError):
    pass


class MuhurtaCalculationError(RuntimeError):
    pass


def parse_event(payload):
    if not isinstance(payload,dict) or not isinstance(payload.get('event'),dict) or not isinstance(payload.get('natal'),dict):
        raise MuhurtaInputError('Structured event and natal objects are required.')
    event = payload.get('event', {})
    if event.get('type') != POLICY['event_type'] or event.get('policy_id') != POLICY_ID:
        raise MuhurtaInputError('An explicit supported event policy is required.')
    location = event.get('location', {})
    if not isinstance(location,dict):raise MuhurtaInputError('Structured event location is required.')
    for key in ('place','country','latitude','longitude','timezone'):
        if key not in location or location[key] in ('',None):
            raise MuhurtaInputError('Missing event location.' + key)
    try:
        tz = ZoneInfo(location['timezone'])
        lat, lon = float(location['latitude']), float(location['longitude'])
        start, end = date.fromisoformat(event['start_date']), date.fromisoformat(event['end_date'])
    except (ValueError, KeyError, ZoneInfoNotFoundError, TypeError) as exc:
        raise MuhurtaInputError('Invalid event coordinates, IANA timezone or ISO date.') from exc
    if not math.isfinite(lat) or not math.isfinite(lon) or abs(lat) > 60 or abs(lon) > 180:
        raise MuhurtaInputError('Coordinates invalid or outside the supported 60-degree latitude range.')
    if not isinstance(location['country'],str) or len(location['country'])!=2 or not location['country'].isalpha() or location['country']!=location['country'].upper():
        raise MuhurtaInputError('Event country must be an uppercase ISO alpha-2 code.')
    if end < start or (end-start).days > 30:
        raise MuhurtaInputError('Event interval must contain 1 to 31 days in chronological order.')
    natal = payload.get('natal', {})
    moon = natal.get('moon_longitude')
    if not isinstance(moon,(float,int)) or isinstance(moon,bool) or not math.isfinite(moon) or not 0 <= moon < 360:
        raise MuhurtaInputError('Verified natal Moon longitude is required for personal matching.')
    return event, location, tz, lat, lon, start, end, float(moon)


def karana(index):
    if index == 0: return 'Kimstughna'
    if index >= 57: return ['Shakuni','Chatushpada','Naga'][index-57]
    return MOVABLE_KARANAS[(index-1)%7]


def panchang(sun, moon):
    elongation = (moon-sun)%360
    number = int(elongation//12)+1
    return {'tithi_number':number,
            'tithi':('Shukla ' if number <= 15 else 'Krishna ') + ('Amavasya' if number == 30 else TITHIS[(number-1)%15]),
            'paksha':'Shukla' if number <= 15 else 'Krishna',
            'nakshatra_index':int((moon%360)//(360/27)),
            'nakshatra':NAKS[int((moon%360)//(360/27))],
            'yoga_number':int(((sun+moon)%360)//(360/27))+1,
            'yoga':YOGAS[int(((sun+moon)%360)//(360/27))],
            'karana':karana(int(elongation//6)),
            'moon_sign_number':int((moon%360)//30)+1,
            'moon_sign':SIGNS[int((moon%360)//30)]}


def natal_identity(moon_longitude, ascendant_sign):
    if ascendant_sign not in SIGNS: raise MuhurtaInputError('Unknown natal ascendant sign.')
    return {'ascendant_sign':ascendant_sign, 'ascendant_sign_lord':LORDS[SIGNS.index(ascendant_sign)],
            'moon_sign':SIGNS[int(moon_longitude//30)],
            'moon_nakshatra':NAKS[int(moon_longitude//(360/27))],
            'moon_nakshatra_lord':NAK_LORDS[int(moon_longitude//(360/27))%9]}


class Calculator:
    def __init__(self, swe, ephe_path):
        self.swe = swe
        for filename in ('sepl_18.se1','semo_18.se1'):
            if not os.path.isfile(os.path.join(ephe_path,filename)):
                raise MuhurtaCalculationError('Required Swiss files unavailable; fallback rejected.')
        swe.set_ephe_path(ephe_path)
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        self.flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED
        self.cache = {}

    def jd(self, dt):
        u=dt.astimezone(UTC)
        return self.swe.julday(u.year,u.month,u.day,u.hour+u.minute/60+u.second/3600+u.microsecond/3600000000)

    def planet(self, dt, body):
        values, flags = self.swe.calc_ut(self.jd(dt),body,self.flags)
        if flags & 7 != self.swe.FLG_SWIEPH:
            raise MuhurtaCalculationError('Swiss file calculation unavailable; fallback rejected.')
        return values

    def core(self, dt, lat, lon):
        key=(dt.timestamp(),lat,lon)
        if key not in self.cache:
            sun, moon = self.planet(dt,self.swe.SUN)[0], self.planet(dt,self.swe.MOON)[0]
            _, asc = self.swe.houses_ex(self.jd(dt),lat,lon,b'P',self.flags)
            value=panchang(sun,moon)
            value['ascendant_sign_number']=int((asc[0]%360)//30)+1
            value['ascendant_sign']=SIGNS[value['ascendant_sign_number']-1]
            value['ascendant_sign_lord']=LORDS[value['ascendant_sign_number']-1]
            self.cache[key]=value
        return dict(self.cache[key])

    def solar(self, day, tz, lat, lon):
        start=datetime.combine(day,time.min,tzinfo=tz).astimezone(UTC)
        times=[]
        for flag in (self.swe.CALC_RISE,self.swe.CALC_SET):
            code, values=self.swe.rise_trans(self.jd(start),self.swe.SUN,flag|self.swe.BIT_HINDU_RISING,(lon,lat,0),0,0,self.swe.FLG_SWIEPH)
            if code != 0: raise MuhurtaCalculationError('No local sunrise or sunset; no guessed fallback.')
            y,m,d,h=self.swe.revjul(values[0])
            dt=datetime(y,m,d,tzinfo=UTC)+timedelta(hours=h)
            if dt.astimezone(tz).date()!=day: raise MuhurtaCalculationError('Solar event outside local date.')
            times.append(dt)
        if times[1] <= times[0]: raise MuhurtaCalculationError('Invalid local daylight interval.')
        return times

    def phases(self, start, end, tz):
        out=[]
        cursor=start
        def elong(dt): return (self.planet(dt,self.swe.MOON)[0]-self.planet(dt,self.swe.SUN)[0])%360
        while cursor < end:
            following=min(end,cursor+timedelta(hours=6))
            a,b=elong(cursor),elong(following)
            target=360 if b<a else 180
            if (target==360 and b<a) or (target==180 and a<180<=b):
                lo,hi=cursor,following
                for _ in range(20):
                    mid=lo+(hi-lo)/2
                    value=elong(mid)
                    passed=(value<180) if target==360 else value>=180
                    if passed:hi=mid
                    else:lo=mid
                out.append({'phase':'New Moon' if target==360 else 'Full Moon','utc':hi.isoformat(timespec='seconds'),'local':hi.astimezone(tz).isoformat(timespec='seconds')})
            cursor=following
        return out


def exclusions(day, sunrise, sunset):
    eighth=(sunset-sunrise)/8
    return [{'name':name,'start':sunrise+eighth*(parts[day.weekday()]-1),'end':sunrise+eighth*parts[day.weekday()]} for name,parts in EXCLUSION_PARTS.items()]


def inspect_minute(calc, start, end, day, sunrise, sunset, blocked, lat, lon, natal_moon):
    if any(start < x['end'] and end > x['start'] for x in blocked): return None,'local_exclusion'
    samples=[calc.core(dt,lat,lon) for dt in (start,start+(end-start)/2,end-timedelta(microseconds=1))]
    if any(s != samples[0] for s in samples[1:]):return None,'transition_minute'
    s=samples[0]
    tara=((s['nakshatra_index']-int(natal_moon//(360/27)))%27)%9+1
    chandra=(s['moon_sign_number']-1-int(natal_moon//30))%12+1
    moon_from_lagna=(s['moon_sign_number']-s['ascendant_sign_number'])%12+1
    for bad,reason in [
        (day.weekday() not in POLICY['weekdays'],'weekday'),
        (s['nakshatra_index'] not in POLICY['nakshatras'],'nakshatra'),
        (s['tithi_number'] in POLICY['excluded_tithis'],'tithi'),
        (s['yoga_number'] in POLICY['excluded_yogas'],'yoga'),
        (s['karana'] in POLICY['excluded_karanas'],'karana'),
        (tara not in POLICY['tarabala'],'tarabala'),
        (chandra not in POLICY['chandrabala'],'chandrabala'),
        (moon_from_lagna==8,'moon_eighth_from_lagna')]:
        if bad:return None,reason
    hora_duration=(sunset-sunrise)/12
    h1=int((start-sunrise)/hora_duration)
    h2=int((end-timedelta(microseconds=1)-sunrise)/hora_duration)
    if h1!=h2:return None,'hora_transition'
    s.update({'tarabala_number':tara,'chandrabala_house':chandra,'moon_house_from_event_lagna':moon_from_lagna,
              'hora_lord':HORA_ORDER[(HORA_ORDER.index(DAY_LORDS[day.weekday()])+h1)%7],
              'weekday':day.strftime('%A')})
    return s,None


def calculate(payload,swe,ephe_path):
    event,location,tz,lat,lon,start_day,end_day,natal_moon=parse_event(payload)
    identity=natal_identity(natal_moon,payload['natal'].get('ascendant_sign'))
    calc=Calculator(swe,ephe_path)
    windows=[]; days=[]
    day=start_day
    while day<=end_day:
        rise,setting=calc.solar(day,tz,lat,lon)
        blocked=exclusions(day,rise,setting)
        cursor=datetime.fromtimestamp(math.ceil(rise.timestamp()/60)*60,UTC)
        stop=datetime.fromtimestamp(math.floor(setting.timestamp()/60)*60,UTC)
        previous=None; rejected={}
        while cursor<stop:
            following=cursor+timedelta(minutes=1)
            state,reason=inspect_minute(calc,cursor,following,day,rise,setting,blocked,lat,lon,natal_moon)
            if state is None:
                rejected[reason]=rejected.get(reason,0)+1;previous=None
            elif previous and previous['_state']==state and previous['_end']==cursor:
                previous['_end']=following
            else:
                previous={'_start':cursor,'_end':following,'_state':state,'date':day.isoformat()};windows.append(previous)
            cursor=following
        days.append({'date':day.isoformat(),'sunrise':rise.astimezone(tz).isoformat(timespec='seconds'),'sunset':setting.astimezone(tz).isoformat(timespec='seconds'),
                     'excluded_intervals':[{'name':x['name'],'start':x['start'].astimezone(tz).isoformat(timespec='seconds'),'end':x['end'].astimezone(tz).isoformat(timespec='seconds')} for x in blocked],
                     'rejected_minute_counts':rejected})
        day+=timedelta(days=1)
    candidates=[]
    for w in windows:
        minutes=int((w['_end']-w['_start']).total_seconds()/60)
        if minutes<POLICY['minimum_minutes']:continue
        mid=w['_start']+(w['_end']-w['_start'])/2
        transit={}
        for name,body in [('Mercury',swe.MERCURY),('Jupiter',swe.JUPITER),('Saturn',swe.SATURN)]:
            xx=calc.planet(mid,body)
            transit[name]={'sign':SIGNS[int((xx[0]%360)//30)],'retrograde':xx[3]<0,'reference_utc':mid.isoformat(timespec='seconds')}
        item={'date':w['date'],'start_local':w['_start'].astimezone(tz).isoformat(timespec='minutes'),'end_local':w['_end'].astimezone(tz).isoformat(timespec='minutes'),
              'start_utc':w['_start'].isoformat(timespec='minutes'),'end_utc':w['_end'].isoformat(timespec='minutes'),
              'duration_minutes':minutes,'event_facts':w['_state'],'transits_at_midpoint':transit}
        item['id']='MS-'+hashlib.sha256(json.dumps(item,sort_keys=True).encode()).hexdigest()[:12]
        candidates.append(item)
    ranked=sorted(candidates,key=lambda x:(x['event_facts']['hora_lord'] not in ('Mercury','Jupiter'),x['event_facts']['weekday'] not in ('Wednesday','Thursday'),-x['duration_minutes'],x['start_utc']))
    top=[]
    for c in ranked:
        if c['date'] not in {x['date'] for x in top}:top.append(c)
        if len(top)==3:break
    begin=datetime.combine(start_day,time.min,tzinfo=tz).astimezone(UTC)
    finish=datetime.combine(end_day+timedelta(days=1),time.min,tzinfo=tz).astimezone(UTC)
    return {'contract_version':'1.0','policy':POLICY,'event':event,'natal_identity':identity,
            'calculation':{'engine':'Swiss Ephemeris','ayanamsa':'Lahiri','ephemeris_mode':'swiss_files','window_precision':'whole-minute conservative intervals','sunrise_method':'Swiss BIT_HINDU_RISING','all_requested_local_days_processed':len(days),
                           'lunar_phase_interval_complete':True,'lunar_phase_start_utc':begin.isoformat(timespec='seconds'),'lunar_phase_end_utc':finish.isoformat(timespec='seconds')},
            'moon_phases':calc.phases(begin,finish,tz),'days':days,'candidates':candidates,'recommended_candidates':top,
            'status':'candidates_calculated' if top else 'no_matching_window'}


def register(app, auth_ok, swe, ephe_path):
    from flask import request,jsonify
    @app.post('/muhurta')
    def muhurta_route():
        if not auth_ok():return jsonify({'error':'Unauthorized'}),401
        try:return jsonify(calculate(request.get_json(force=True),swe,ephe_path))
        except MuhurtaInputError as exc:return jsonify({'code':'invalid_muhurta_request','error':str(exc)}),400
        except MuhurtaCalculationError as exc:return jsonify({'code':'muhurta_calculation_unavailable','error':str(exc)}),503
