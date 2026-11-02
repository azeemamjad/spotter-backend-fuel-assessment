import json
import math
import time
import uuid
from django.conf import settings
from django.db import DatabaseError
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from stations.models import SavedPlan, Station
from .errors import PlanError
from .fuel import optimize
from .matching import match_stations
from .providers import resolve_location, road_route

@require_GET
def index(request):
    return render(request, 'route_map.html', {'plan': None, 'corridor_miles': settings.STATION_CORRIDOR_MILES})

@require_GET
def health(request):
    try:
        total = Station.objects.count()
        usable = Station.objects.filter(latitude__isnull=False, longitude__isnull=False).count()
        return JsonResponse({'status': 'ok', 'service': 'backend-fuel-assessment', 'station_count': total, 'located_station_count': usable, 'dataset_ready': usable > 0})
    except DatabaseError:
        return JsonResponse({'status': 'setup_required', 'message': 'Run python manage.py migrate.'}, status=503)

@require_GET
def plan_map(request, plan_id):
    saved = SavedPlan.objects.filter(pk=plan_id).first()
    if not saved:
        return render(request, 'route_map.html', {'plan': None, 'map_error': 'This plan was not found.'}, status=404)
    return render(request, 'route_map.html', {'plan': saved.result, 'corridor_miles': saved.result['metadata']['corridor_miles']})

@csrf_exempt  # Stateless public API has no cookie authentication; browser UI sends JSON.
def route_plan(request):
    started = time.perf_counter()
    if request.method != 'POST':
        response = JsonResponse({'error': {'code': 'method_not_allowed', 'message': 'Use POST with application/json.'}}, status=405)
        response['Allow'] = 'POST'
        return response
    try:
        if request.content_type != 'application/json':
            raise PlanError('invalid_content_type', 'Send application/json.', 415)
        if len(request.body) > 10000:
            raise PlanError('invalid_input', 'Request is too large.', 413)
        try:
            payload = json.loads(request.body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise PlanError('invalid_json', 'Request body must be valid JSON.')
        if not isinstance(payload, dict) or not payload.get('origin') or not payload.get('destination'):
            raise PlanError('invalid_input', 'origin and destination are required.')
        initial = payload.get('initial_fuel_gallons', 50)
        try:
            if isinstance(initial, bool):
                raise ValueError
            initial = float(initial)
            if not math.isfinite(initial) or not 0 <= initial <= 50:
                raise ValueError
        except (ValueError, TypeError, OverflowError):
            raise PlanError('invalid_input', 'initial_fuel_gallons must be a number between 0 and 50.')
        # Fail before spending provider calls when the required real dataset is not ready.
        if not Station.objects.filter(latitude__isnull=False, longitude__isnull=False).exists():
            raise PlanError('station_data_unavailable', 'No geolocated priced stations are loaded. Import the employer CSV and enrich missing coordinates before planning.', 503)
        stats = {'routing_requests': 0, 'geocoding_requests': 0, 'geocode_cache_hits': 0}
        origin = resolve_location(payload['origin'], stats)
        destination = resolve_location(payload['destination'], stats)
        route = road_route(origin, destination, stats)
        candidates, matching = match_stations(route)
        total_stations=Station.objects.count()
        located_stations=Station.objects.filter(latitude__isnull=False,longitude__isnull=False).count()
        matching.update({'total_priced_stations':total_stations,'geolocated_stations':located_stations,'unlocated_stations':total_stations-located_stations,'optimization_scope':'Only the geolocated imported station subset; incomplete nationwide coverage.'})
        result = optimize(route['distance_miles'], candidates, initial)
        plan_id = uuid.uuid4()
        result.update({'id': str(plan_id), 'origin': origin, 'destination': destination, 'route': {k:v for k,v in route.items() if k != 'segment_distances_meters'}, 'map_url': request.build_absolute_uri(f'/map/{plan_id}/'), 'assumptions': ['Minimizes new fuel purchases on the single selected road route.', 'Nearby stations are projected onto the route. Station access/detour mileage is omitted; actual highway access and commercial-truck legality are not verified.', 'Initial fuel is already owned and excluded from purchase cost. Consumption is reported separately.', 'Money uses Decimal arithmetic, half-up cents per purchase; total sums displayed purchases.'], 'metadata': {**stats, **matching, 'elapsed_ms': round((time.perf_counter()-started)*1000, 2), 'providers': {'routing': 'OSRM driving', 'geocoding': 'Open-Meteo cities / US Census coordinates'}, 'external_request_count': stats['routing_requests'] + stats['geocoding_requests']}})
        SavedPlan.objects.create(id=plan_id, result=result)
        return JsonResponse(result)
    except PlanError as exc:
        return JsonResponse({'error': {'code': exc.code, 'message': exc.message}}, status=exc.status)
    except DatabaseError:
        return JsonResponse({'error': {'code': 'database_unavailable', 'message': 'Database unavailable. Run migrations and verify the station import.'}}, status=503)
