"""Nearby stations projected to road-polyline segment positions (access detours omitted)."""
import math
from collections import defaultdict
from django.conf import settings
from stations.models import Station

EARTH_MILES = 3958.7613

def haversine(a, b):
    lon1, lat1, lon2, lat2 = map(math.radians, [a[0], a[1], b[0], b[1]])
    x = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return EARTH_MILES * 2 * math.asin(min(1, math.sqrt(x)))

def match_stations(route):
    points = route['geometry']['coordinates']
    corridor = settings.STATION_CORRIDOR_MILES
    annotations = route.get('segment_distances_meters', [])
    distances = [d / 1609.344 for d in annotations] if len(annotations) == len(points)-1 else [haversine(a,b) for a,b in zip(points, points[1:])]
    total = sum(distances)
    scale = route['distance_miles'] / total if total else 0
    distances = [d * scale for d in distances]
    lats, lons = [p[1] for p in points], [p[0] for p in points]
    latpad = corridor / 69 + .001
    lonpad = latpad / max(.05, math.cos(math.radians(max(abs(min(lats)), abs(max(lats))))))
    query = Station.objects.filter(latitude__gte=min(lats)-latpad, latitude__lte=max(lats)+latpad, longitude__gte=min(lons)-lonpad, longitude__lte=max(lons)+lonpad)
    # Index segment bounding boxes locally. Most candidates examine a handful of segments.
    grid, segments, cumulative = defaultdict(list), [], 0.0
    cell = .25
    for index, (a, b, miles) in enumerate(zip(points, points[1:], distances)):
        segments.append((a,b,cumulative,miles))
        for gx in range(math.floor((min(a[0],b[0])-lonpad)/cell), math.floor((max(a[0],b[0])+lonpad)/cell)+1):
            for gy in range(math.floor((min(a[1],b[1])-latpad)/cell), math.floor((max(a[1],b[1])+latpad)/cell)+1):
                grid[gx,gy].append(index)
        cumulative += miles
    selected, examined = [], 0
    for station in query.iterator():
        examined += 1
        best = None
        coslat = math.cos(math.radians(station.latitude))
        for i in grid.get((math.floor(station.longitude/cell),math.floor(station.latitude/cell)), []):
            a,b,start,miles = segments[i]
            ax,ay = (a[0]-station.longitude)*coslat*69.09, (a[1]-station.latitude)*69.09
            bx,by = (b[0]-station.longitude)*coslat*69.09, (b[1]-station.latitude)*69.09
            dx,dy = bx-ax,by-ay
            t = min(1,max(0,-(ax*dx+ay*dy)/(dx*dx+dy*dy))) if dx*dx+dy*dy else 0
            offset = math.hypot(ax+t*dx, ay+t*dy)
            if best is None or offset < best[0]:
                best = offset,start+t*miles
        if best and best[0] <= corridor:
            selected.append({'id': station.source_id, 'name': station.name, 'address': station.address, 'latitude': station.latitude, 'longitude': station.longitude, 'coordinate_source': station.coordinate_source, 'price': str(station.price), 'mile': best[1], 'offset_miles': round(best[0],4)})
    return selected, {'stations_examined': examined, 'corridor_candidates': len(selected), 'corridor_miles': corridor, 'projection_distance_basis': 'OSRM road annotations' if len(annotations)==len(points)-1 else 'Polyline length scaled to provider road distance'}
