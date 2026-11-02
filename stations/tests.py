import io
import json
import tempfile
from pathlib import Path
from django.test import TestCase
from django.core.management import call_command
from .models import Station
from .management.commands.enrich_stations import census_matches

class ImportTests(TestCase):
    def test_actual_style_headers_invalid_duplicates_idempotency(self):
        content='OPIS Truckstop ID,Truckstop Name,Address,City,State,Rack ID,Retail Price\n1,Test A,100 Main St,Chicago,IL,1,3.499\n1,Test A,100 Main St,Chicago,IL,1,3.499\n2,Test B,200 Main St,Chicago,IL,2,-1\n3,Test C,300 Main St,Chicago,IL,3,NaN\n4,Test D,400 Main St,Chicago,IL,4,0.000000001\n'
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

    def test_source_precision_non_us_and_conflicting_duplicate_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'stations.csv'
            path.write_text('id,name,address,city,state,price\n1,Test,100 Main,Chicago,IL,3.00733333\n1,Test,100 Main,Chicago,IL,4.12345678\n2,Canada,100 Main,Toronto,ON,1.234\n',encoding='utf-8')
            output=io.StringIO();call_command('import_stations',str(path),stdout=output)
        self.assertEqual(str(Station.objects.get().price),'3.00733333')
        self.assertEqual(json.loads(output.getvalue())['conflicting_duplicate_rows'],1)
        self.assertEqual(json.loads(output.getvalue())['non_us_rows'],1)

    def test_coordinate_crosswalk_persists(self):
        Station.objects.create(source_id='a',name='A',address='100 Main',price='3')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'coordinates.csv';path.write_text('source_id,latitude,longitude\na,41.8,-87.6\n',encoding='utf-8')
            call_command('enrich_stations',coordinates=str(path),stdout=io.StringIO())
        self.assertEqual(Station.objects.get().coordinate_source,'verified_crosswalk')

    def test_census_non_exact_matches_are_excluded(self):
        report={'unmatched':0,'rejected_non_exact':0}
        text='"1","100 MAIN, CHICAGO, IL","Match","Exact","100 MAIN ST, CHICAGO, IL, 60601","-87.6,41.8"\n"2","I-80 EXIT 332, AURORA, NE","Match","Non_Exact","332 STATE HWY 14, AURORA, NE, 68818","-97.9,40.7"\n'
        matches=census_matches(text,report)
        self.assertEqual(len(matches),1)
        self.assertEqual(matches[0][0],'1')
        self.assertEqual(report['rejected_non_exact'],1)

    def test_census_exact_wrong_locality_is_excluded(self):
        Station.objects.create(source_id='a',name='A',address='100 Main',city='Chicago',state='IL',price='3')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'census.csv'
            path.write_text('"a","100 MAIN, CHICAGO, IL","Match","Exact","100 MAIN ST, BOSTON, MA, 02101","-71,42"\n',encoding='utf-8')
            output=io.StringIO();call_command('enrich_stations',census_results=str(path),stdout=output)
        self.assertIsNone(Station.objects.get().latitude)
        self.assertEqual(json.loads(output.getvalue())['rejected_locality_mismatch'],1)
