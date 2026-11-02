import itertools
from decimal import Decimal
from django.test import SimpleTestCase
from routing.fuel import optimize
from routing.errors import PlanError

def station(mile,price,id=None):
    return {'id':id or str(mile),'mile':mile,'price':price}

def exhaustive(distance,stations,initial):
    # Integer gallons are exact here: integer prices, initial fuel, and all leg consumption.
    states={initial:0};previous=0
    for s in stations:
        cost_to_reach=(s['mile']-previous)//10
        arrived={fuel-cost_to_reach:cost for fuel,cost in states.items() if fuel>=cost_to_reach}
        states={}
        for fuel,cost in arrived.items():
            for departure in range(fuel,51):
                value=cost+(departure-fuel)*s['price']
                states[departure]=min(states.get(departure,float('inf')),value)
        previous=s['mile']
    return min((cost for fuel,cost in states.items() if fuel >= (distance-previous)//10),default=None)

class FuelTests(SimpleTestCase):
    def test_full_tank_short_trip_and_exact_range(self):
        for distance in (0,100,500):
            plan=optimize(distance,[],50)
            self.assertEqual(plan['total_purchase_cost_usd'],'0.00')
            self.assertEqual(plan['fuel_at_destination_gallons'],50-distance/10)

    def test_multiple_stops_and_accounting(self):
        p=optimize(1400,[station(400,4),station(800,3),station(1200,5)])
        self.assertEqual(len(p['fuel_stops']),3)
        self.assertEqual(p['total_purchase_cost_usd'],'320.00')
        self.assertEqual(p['total_purchased_gallons'],90)
        self.assertEqual(sum(Decimal(s['purchase_cost_usd']) for s in p['fuel_stops']),Decimal(p['total_purchase_cost_usd']))
        for stop in p['fuel_stops']:
            self.assertGreaterEqual(stop['fuel_on_arrival_gallons'],0)
            self.assertLessEqual(stop['fuel_on_departure_gallons'],50)

    def test_cheaper_station_changes_purchase(self):
        p=optimize(800,[station(300,5),station(400,2)],30)
        self.assertEqual(p['fuel_stops'][0]['gallons_purchased'],10)
        self.assertEqual(p['total_purchase_cost_usd'],'130.00')
        expensive=optimize(800,[station(300,5),station(400,6)],30)
        self.assertEqual(expensive['total_purchase_cost_usd'],'250.00')

    def test_infeasible_gap_and_empty_tank(self):
        for distance,stations,initial in [(501,[],50),(100,[station(50,1)],0),(1100,[station(400,3),station(1001,1)],50)]:
            with self.assertRaises(PlanError):optimize(distance,stations,initial)

    def test_zero_initial_at_priced_origin(self):
        p=optimize(100,[station(0,3)],0)
        self.assertEqual(p['total_purchase_cost_usd'],'30.00')

    def test_monetary_rounding_sum(self):
        p=optimize(1401,[station(400,3.3333),station(800,3.1234),station(1200,4.9999)])
        self.assertEqual(sum(Decimal(s['purchase_cost_usd']) for s in p['fuel_stops']),Decimal(p['total_purchase_cost_usd']))

    def test_greedy_matches_exhaustive_small_cases(self):
        for prices in itertools.product((1,3,5),repeat=3):
            for initial in (0,10,30,50):
                stations=[station(mile,price) for mile,price in zip((0,200,500),prices)]
                with self.subTest(prices=prices,initial=initial):
                    expected=exhaustive(800,stations,initial)
                    actual=optimize(800,stations,initial)
                    self.assertEqual(Decimal(actual['unrounded_purchase_cost_usd']),Decimal(expected))
