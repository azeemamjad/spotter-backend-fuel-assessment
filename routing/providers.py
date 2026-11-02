import hashlib
import json
import math
import requests
from django.conf import settings
from django.core.cache import cache
from stations.models import Geocode
from .errors import PlanError


def get_json(url, params, provider, stats):
    stats[provider + '_requests'] = stats.get(provider + '_requests', 0) + 1
    try:
        response = requests.get(url, params=params, headers={'User-Agent': settings.PROVIDER_USER_AGENT}, timeout=settings.PROVIDER_TIMEOUT_SECONDS)
        if response.status_code == 429:
            raise PlanError('provider_rate_limit', f'{provider} rate limit reached. Please try later.', 503)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError('Expected JSON object')
        return payload
    except (requests.RequestException, ValueError) as exc:
        raise PlanError('provider_unavailable', f'{provider} did not return a valid response. Try again later.', 502) from exc

STATE_NAMES = dict(pair.split(':',1) for pair in 'AL:Alabama|AK:Alaska|AZ:Arizona|AR:Arkansas|CA:California|CO:Colorado|CT:Connecticut|DE:Delaware|FL:Florida|GA:Georgia|HI:Hawaii|ID:Idaho|IL:Illinois|IN:Indiana|IA:Iowa|KS:Kansas|KY:Kentucky|LA:Louisiana|ME:Maine|MD:Maryland|MA:Massachusetts|MI:Michigan|MN:Minnesota|MS:Mississippi|MO:Missouri|MT:Montana|NE:Nebraska|NV:Nevada|NH:New Hampshire|NJ:New Jersey|NM:New Mexico|NY:New York|NC:North Carolina|ND:North Dakota|OH:Ohio|OK:Oklahoma|OR:Oregon|PA:Pennsylvania|RI:Rhode Island|SC:South Carolina|SD:South Dakota|TN:Tennessee|TX:Texas|UT:Utah|VT:Vermont|VA:Virginia|WA:Washington|WV:West Virginia|WI:Wisconsin|WY:Wyoming|DC:District of Columbia'.split('|'))


def resolve_location(value, stats, require_us=True):
    if isinstance(value, str):
        value = ' '.join(value.strip().split())
        if not value or len(value) > 250:
            raise PlanError('invalid_input', 'Locations must contain 1–250 characters.')
        key = 'city:' + value.casefold()
        parts = [p.strip() for p in value.split(',') if p.strip()]
        if not parts:
            raise PlanError('invalid_input', 'A city name is required.')
        city = parts[0]
        region = parts[1] if len(parts) > 1 and parts[1].upper() not in ('US','USA','UNITED STATES') else None
        if len(parts)>2 and parts[-1].upper() not in ('US','USA','UNITED STATES'):
            raise PlanError('outside_usa', 'Both locations must be inside the United States.')
        region = STATE_NAMES.get(region.upper(), region) if region else None
        coordinates = None
    elif isinstance(value, dict) and set(value) >= {'latitude', 'longitude'}:
        try:
            if isinstance(value['latitude'], bool) or isinstance(value['longitude'], bool):
                raise ValueError
            lat, lon = float(value['latitude']), float(value['longitude'])
            if not math.isfinite(lat) or not math.isfinite(lon) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
                raise ValueError
        except (ValueError, TypeError, OverflowError):
            raise PlanError('invalid_input', 'Coordinates must be finite latitude/longitude values in range.')
        key = f'coordinate:{lat:.6f},{lon:.6f}'
        coordinates = (lat,lon)
    else:
        raise PlanError('invalid_input', 'origin and destination must be city strings or objects with latitude and longitude.')
    saved = Geocode.objects.filter(key=key).first()
    if saved:
        stats['geocode_cache_hits'] = stats.get('geocode_cache_hits', 0) + 1
        return saved.result
    if coordinates:
        data = get_json('https://geocoding.geo.census.gov/geocoder/geographies/coordinates', {'x':lon,'y':lat,'benchmark':'Public_AR_Current','vintage':'Current_Current','format':'json','layers':'States'}, 'geocoding', stats)
        states = data.get('result',{}).get('geographies',{}).get('States',[])
        state = next((s for s in states if s.get('STUSAB') in STATE_NAMES or s.get('NAME') in STATE_NAMES.values()),None)
        if not state:
            raise PlanError('outside_usa', 'Coordinates must be within a US state or the District of Columbia.')
        result = {'label':f'{lat}, {lon} ({state.get("NAME","US")})','latitude':lat,'longitude':lon,'country_code':'us'}
    else:
        data = get_json('https://geocoding-api.open-meteo.com/v1/search', {'name':city,'count':100,'language':'en','format':'json','countryCode':'US'}, 'geocoding', stats)
        matches = [r for r in data.get('results',[]) if r.get('country_code')=='US' and (not region or r.get('admin1','').casefold()==region.casefold())]
        exact = [r for r in matches if r.get('name','').casefold()==city.casefold()]
        matches = exact or matches
        if not matches:
            raise PlanError('location_not_found', 'No matching US city was found. Use City, State or explicit coordinates.')
        if not region and len({r.get('admin1') for r in matches})>1:
            raise PlanError('ambiguous_location', 'City exists in multiple states. Specify City, State.')
        item = max(matches,key=lambda r:r.get('population',0))
        result = {'label':', '.join(filter(None,[item['name'],item.get('admin1'),'USA'])),'latitude':item['latitude'],'longitude':item['longitude'],'country_code':'us'}
    Geocode.objects.update_or_create(key=key, defaults={'result': result})
    return result

def road_route(origin, destination, stats):
    coordinates = f'{origin["longitude"]},{origin["latitude"]};{destination["longitude"]},{destination["latitude"]}'
    params = {'overview': 'full', 'geometries': 'geojson', 'annotations': 'distance,duration', 'steps': 'false', 'alternatives': 'false'}
    key = 'route:' + hashlib.sha256((settings.OSRM_URL + coordinates + json.dumps(params, sort_keys=True)).encode()).hexdigest()
    result = cache.get(key)
    if result:
        stats['route_cache_hit'] = True
        return result
    stats['route_cache_hit'] = False
    data = get_json(settings.OSRM_URL + '/route/v1/driving/' + coordinates, params, 'routing', stats)
    if data.get('code') != 'Ok' or not data.get('routes'):
        raise PlanError('no_route', 'No road route was found between these locations.', 422)
    route = data['routes'][0]
    geometry = route.get('geometry', {})
    if route.get('distance', -1) < 0 or route.get('duration', -1) < 0 or geometry.get('type') != 'LineString' or len(geometry.get('coordinates', [])) < 2:
        raise PlanError('provider_invalid_response', 'Routing provider returned incomplete road geometry.', 502)
    result = {'geometry': geometry, 'distance_miles': route['distance'] / 1609.344, 'duration_seconds': route['duration'], 'segment_distances_meters': [v for leg in route.get('legs', []) for v in leg.get('annotation', {}).get('distance', [])]}
    cache.set(key, result, 3600)
    return result
