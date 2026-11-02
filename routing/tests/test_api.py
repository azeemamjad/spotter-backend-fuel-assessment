import json
from unittest.mock import patch
from django.test import TestCase
from stations.models import Station
from routing.errors import PlanError
from routing.providers import resolve_location
from routing.matching import match_stations

ROUTE={'distance_miles':600,'duration_seconds':36000,'geometry':{'type':'LineString','coordinates':[[-90,40],[-85,40],[-80,40]]},'segment_distances_meters':[482803.2,482803.2]}

class ApiTests(TestCase):
    def post(self,payload):return self.client.post('/api/route-plan/',data=json.dumps(payload),content_type='application/json')
    def test_validation_and_missing_dataset(self):
        self.assertEqual(self.post({}).status_code,400)
        self.assertEqual(self.post({'origin':'A','destination':'B','initial_fuel_gallons':True}).status_code,400)
        self.assertEqual(self.post({'origin':'A','destination':'B'}).json()['error']['code'],'station_data_unavailable')
        self.assertEqual(self.client.get('/api/health/').json()['dataset_ready'],False)
        self.assertEqual(self.client.get('/').status_code,200)
        self.assertEqual(self.client.get('/api/route-plan/').status_code,405)

    @patch('routing.views.road_route',return_value=ROUTE)
    @patch('routing.views.resolve_location')
    def test_route_map_saved_and_accounted(self,resolve,road):
        resolve.side_effect=[{'label':'A','latitude':40,'longitude':-90},{'label':'B','latitude':40,'longitude':-80}]
        Station.objects.create(source_id='mid',name='Station',address='Test fixture',latitude=40,longitude=-85,price='3')
        response=self.post({'origin':'A','destination':'B'})
        self.assertEqual(response.status_code,200,response.content)
        result=response.json();self.assertEqual(result['total_purchase_cost_usd'],'30.00')
        self.assertEqual(result['fuel_stops'][0]['route_mile'],300)
        self.assertEqual(self.client.get('/map/'+result['id']+'/').status_code,200)

    @patch('routing.providers.get_json')
    def test_city_state_and_geocode_cache(self,get):
        get.return_value={'results':[{'name':'Chicago','admin1':'Illinois','latitude':41.8,'longitude':-87.6,'country_code':'US','population':100}]}
        a=resolve_location('Chicago, IL',{});b=resolve_location('Chicago, IL',{})
        self.assertEqual(a,b);self.assertEqual(get.call_count,1)

    @patch('routing.providers.get_json')
    def test_non_us_coordinate_is_rejected(self,get):
        get.return_value={'result':{'geographies':{'States':[]}}}
        with self.assertRaises(PlanError):resolve_location({'latitude':43,'longitude':-79},{})

    def test_matching_uses_road_position_and_corridor(self):
        Station.objects.create(source_id='mid',name='Station',address='Test',latitude=40,longitude=-85,price='3')
        Station.objects.create(source_id='far',name='Far',address='Test',latitude=41,longitude=-85,price='1')
        candidates,stats=match_stations(ROUTE)
        self.assertEqual(len(candidates),1);self.assertEqual(candidates[0]['mile'],300)
