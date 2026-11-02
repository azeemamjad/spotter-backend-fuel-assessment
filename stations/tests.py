import io
import json
import tempfile
from pathlib import Path
from django.test import TestCase
from django.core.management import call_command
from .models import Station

class ImportTests(TestCase):
    def test_actual_style_headers_invalid_duplicates_idempotency(self):
        content='OPIS Truckstop ID,Truckstop Name,Address,City,State,Rack ID,Retail Price\n1,Test A,100 Main St,Chicago,IL,1,3.499\n1,Test A,100 Main St,Chicago,IL,1,3.499\n2,Test B,200 Main St,Chicago,IL,2,-1\n3,Test C,300 Main St,Chicago,IL,3,NaN\n4,Test D,400 Main St,Chicago,IL,4,0.00001\n'
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'stations.csv';path.write_text(content,encoding='utf-8')
            out=io.StringIO();call_command('import_stations',str(path),stdout=out)
            report=json.loads(out.getvalue())
            self.assertEqual((report['created'],report['duplicate_rows'],report['invalid_rows'],report['missing_coordinates']),(1,1,3,1))
            Station.objects.filter(source_id='1').update(latitude=41.8,longitude=-87.6,coordinate_source='verified_crosswalk')
            call_command('import_stations',str(path),stdout=io.StringIO())
            self.assertEqual(Station.objects.count(),1)
            self.assertEqual(Station.objects.get().latitude,41.8)

    def test_quoted_multiline_address_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'stations.csv'
            path.write_text('id,name,address,price\n1,Test,"100 Main St\nSuite A",3.499\n',encoding='utf-8')
            call_command('import_stations',str(path),stdout=io.StringIO())
        self.assertEqual(Station.objects.get().address,'100 Main St\nSuite A')

    def test_coordinate_crosswalk_persists(self):
        Station.objects.create(source_id='a',name='A',address='100 Main',price='3')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'coordinates.csv';path.write_text('source_id,latitude,longitude\na,41.8,-87.6\n',encoding='utf-8')
            call_command('enrich_stations',coordinates=str(path),stdout=io.StringIO())
        self.assertEqual(Station.objects.get().coordinate_source,'verified_crosswalk')
