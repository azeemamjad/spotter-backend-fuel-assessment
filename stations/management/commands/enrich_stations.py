import csv
import io
import json
import math
from pathlib import Path
import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from stations.models import Station

class Command(BaseCommand):
    help = 'Persist station coordinates from an exact-ID local crosswalk or one US Census address batch.'
    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('--coordinates', help='CSV source_id,latitude,longitude from verified station locations')
        group.add_argument('--census', action='store_true', help='Send missing US street addresses to public Census address-batch geocoder')
        parser.add_argument('--limit',type=int,default=10000)
    def handle(self,*args,**options):
        if not 1 <= options['limit'] <=10000:
            raise CommandError('--limit must be between 1 and 10000.')
        report = {'submitted':0,'matched':0,'unmatched':0,'unknown_ids':0,'invalid':0,'provider_requests':0}
        try:
            if options['coordinates']:
                rows = csv.DictReader(Path(options['coordinates']).read_text(encoding='utf-8-sig').splitlines())
                resolved = [(r['source_id'],r['latitude'],r['longitude']) for r in rows]
                source='verified_crosswalk'
                report['submitted']=len(resolved)
            else:
                stations=list(Station.objects.filter(latitude__isnull=True).order_by('id')[:options['limit']])
                if not stations:
                    self.stdout.write(json.dumps(report)); return
                content=io.StringIO(newline='')
                writer=csv.writer(content)
                for s in stations:
                    writer.writerow([s.source_id,s.address,s.city,s.state,''])
                report['submitted']=len(stations)
                response=requests.post('https://geocoding.geo.census.gov/geocoder/locations/addressbatch',files={'addressFile':('stations.csv',content.getvalue().encode(),'text/csv')},data={'benchmark':'Public_AR_Current'},headers={'User-Agent':settings.PROVIDER_USER_AGENT},timeout=(15,180))
                report['provider_requests']=1
                response.raise_for_status()
                resolved=[]
                for row in csv.reader(io.StringIO(response.text)):
                    if len(row)>=6 and row[2]=='Match':
                        longitude,latitude=row[5].split(',')
                        resolved.append((row[0],latitude,longitude))
                    else:
                        report['unmatched']+=1
                source='US_Census_addressbatch'
            for identity,latitude,longitude in resolved:
                try:
                    lat,lon=float(latitude),float(longitude)
                    if not math.isfinite(lat) or not math.isfinite(lon) or not -90 <=lat<=90 or not -180 <=lon<=180:
                        raise ValueError
                    updated=Station.objects.filter(source_id=identity).update(latitude=lat,longitude=lon,coordinate_source=source)
                    report['matched' if updated else 'unknown_ids']+=1
                except (TypeError,ValueError):
                    report['invalid']+=1
            report['remaining_unlocated']=Station.objects.filter(latitude__isnull=True).count()
            self.stdout.write(json.dumps(report,indent=2))
        except (OSError,requests.RequestException,KeyError) as exc:
            raise CommandError(f'Coordinate enrichment failed: {exc}') from exc
