"""Exact continuous fuel purchasing on one ordered route; no detour costs."""
from decimal import Decimal, ROUND_HALF_UP
from .errors import PlanError

CAPACITY = Decimal('50')
MPG = Decimal('10')
EPSILON = Decimal('0.000001')

def money(value):
    return str(value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

def optimize(distance_miles, candidates, initial_fuel=50):
    distance, fuel = Decimal(str(distance_miles)), Decimal(str(initial_fuel))
    if not distance.is_finite() or distance < 0 or not fuel.is_finite() or not 0 <= fuel <= CAPACITY:
        raise PlanError('invalid_input', 'Distance must be nonnegative and initial fuel must be between 0 and 50 gallons.')
    stations = sorted((dict(s, mile=Decimal(str(s['mile'])), price=Decimal(str(s['price']))) for s in candidates if 0 <= Decimal(str(s['mile'])) < distance), key=lambda s: (s['mile'], s['price'], str(s['id'])))
    # Next strictly cheaper station, in linear time using a monotone stack.
    cheaper, stack = [None] * len(stations), []
    for i in range(len(stations) - 1, -1, -1):
        while stack and stations[stack[-1]]['price'] >= stations[i]['price']:
            stack.pop()
        cheaper[i] = stack[-1] if stack else None
        stack.append(i)
    previous = Decimal('0')
    stops, legs, total, gallons = [], [], Decimal('0'), Decimal('0')
    for i, station in enumerate(stations):
        leg_distance = station['mile'] - previous
        arrival = fuel - leg_distance / MPG
        if arrival < -EPSILON:
            raise PlanError('infeasible_route', f'No reachable priced station sequence: fuel exhausted before mile {float(station["mile"]):.1f}.', 422)
        fuel = max(Decimal('0'), arrival)
        target = min(CAPACITY, (distance - station['mile']) / MPG)
        j = cheaper[i]
        if j is not None and stations[j]['mile'] - station['mile'] <= CAPACITY * MPG + EPSILON:
            target = (stations[j]['mile'] - station['mile']) / MPG
        purchase = max(Decimal('0'), target - fuel)
        departure = fuel + purchase
        if purchase > EPSILON:
            cost = purchase * station['price']
            stops.append({**{k: v for k, v in station.items() if k not in ('mile', 'price')}, 'route_mile': float(station['mile']), 'price_per_gallon_usd': str(station['price']), 'gallons_purchased': float(purchase), 'purchase_cost_usd': money(cost), 'fuel_on_arrival_gallons': float(fuel), 'fuel_on_departure_gallons': float(departure)})
            total += cost
            gallons += purchase
        legs.append({'from_mile': float(previous), 'to_mile': float(station['mile']), 'distance_miles': float(leg_distance), 'fuel_on_arrival_gallons': float(fuel)})
        fuel, previous = departure, station['mile']
    final_distance = distance - previous
    fuel -= final_distance / MPG
    if fuel < -EPSILON:
        raise PlanError('infeasible_route', 'The destination cannot be reached with the available fuel and priced stations.', 422)
    legs.append({'from_mile': float(previous), 'to_mile': float(distance), 'distance_miles': float(final_distance), 'fuel_on_arrival_gallons': float(max(Decimal('0'), fuel))})
    # Sum rounded line items so displayed totals reconcile exactly.
    display_total = sum((Decimal(s['purchase_cost_usd']) for s in stops), Decimal('0'))
    return {'fuel_stops': stops, 'legs': legs, 'total_purchased_gallons': float(gallons), 'total_purchase_cost_usd': money(display_total), 'unrounded_purchase_cost_usd': str(total), 'trip_fuel_consumed_gallons': float(distance / MPG), 'fuel_at_destination_gallons': float(max(Decimal('0'), fuel)), 'vehicle': {'tank_capacity_gallons': 50, 'fuel_economy_mpg': 10, 'maximum_range_miles': 500, 'initial_fuel_gallons': float(Decimal(str(initial_fuel))), 'initial_fuel_policy': 'Already owned; excluded from new purchase total.'}}
