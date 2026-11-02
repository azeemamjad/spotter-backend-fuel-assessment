import csv
import io
import json
import math
import re
from pathlib import Path
import requests
from django.conf import settings
from django.utils import timezone
from django.core.management.base import BaseCommand, CommandError
from stations.models import Station, Geocode

def census_matches(text,report):
    resolved=[]
    for row in csv.reader(io.StringIO(text)):
        if len(row)>=6 and row[2]=='Match' and row[3]=='Exact':
            longitude,latitude=row[5].split(',')
            resolved.append((row[0],latitude,longitude,{'match_type':row[3],'matched_address':row[4],'benchmark':'Public_AR_Current','retrieved_at':timezone.now().isoformat()}))
        else:
            report['unmatched']+=1
            report['rejected_non_exact']+=int(len(row)>3 and row[2]=='Match')
    return resolved

class Command(BaseCommand):
    help = 'Persist station coordinates from an exact-ID local crosswalk or one US Census address batch.'
    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('--coordinates', help='CSV source_id,latitude,longitude from verified station locations')
        group.add_argument('--census', action='store_true', help='Send missing US street addresses to public Census address-batch geocoder')
        group.add_argument('--census-results',help='Apply a previously saved Census batch response CSV without a network call')
        parser.add_argument('--limit',type=int,default=10000)
        parser.add_argument('--refresh',action='store_true',help='Refresh Census locations for all stations, including already located ones.')
    def handle(self,*args,**options):
        if not 1 <= options['limit'] <=10000:
            raise CommandError('--limit must be between 1 and 10000.')
        report = {'submitted':0,'matched':0,'exact_matches':0,'unmatched':0,'rejected_non_exact':0,'rejected_locality_mismatch':0,'unknown_ids':0,'invalid':0,'provider_requests':0}
        try:
            if options['coordinates']:
                path=Path(options['coordinates'])
                rows = json.loads(path.read_text(encoding='utf-8-sig')) if path.suffix=='.json' else csv.DictReader(path.read_text(encoding='utf-8-sig').splitlines())
                resolved = [(r['source_id'],r['latitude'],r['longitude'],r.get('provenance',{})) for r in rows]
                source='verified_crosswalk'
                report['submitted']=len(resolved)
            elif options['census_results']:
                text=Path(options['census_results']).read_text(encoding='utf-8-sig')
                report['submitted']=sum(1 for _ in csv.reader(io.StringIO(text)))
                resolved=census_matches(text,report)
                source='US_Census_addressbatch'
            else:
                query=Station.objects.all() if options['refresh'] else Station.objects.filter(latitude__isnull=True)
                stations=list(query.order_by('id')[:options['limit']])
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
                archive=Path('data/census-last-response.csv')
                archive.parent.mkdir(exist_ok=True)
                archive.write_text(response.text,encoding='utf-8')
                resolved=census_matches(response.text,report)
                source='US_Census_addressbatch'
            for identity,latitude,longitude,metadata in resolved:
                try:
                    lat,lon=float(latitude),float(longitude)
                    if not math.isfinite(lat) or not math.isfinite(lon) or not -90 <=lat<=90 or not -180 <=lon<=180:
                        raise ValueError
                    if metadata.get('match_type')=='Exact' and metadata.get('matched_address'):
                        station=Station.objects.filter(source_id=identity).first()
                        address_parts=[v.strip() for v in metadata['matched_address'].split(',')]
                        normalized=lambda value:re.sub('[^A-Z0-9]','',value.upper())
                        if station and (len(address_parts)<4 or normalized(address_parts[-3])!=normalized(station.city) or normalized(address_parts[-2])!=normalized(station.state)):
                            report['rejected_locality_mismatch']+=1
                            continue
                    updated=Station.objects.filter(source_id=identity).update(latitude=lat,longitude=lon,coordinate_source=metadata.get('provider',source))
                    if updated and metadata:
                        Geocode.objects.update_or_create(key='station:'+identity,defaults={'result':{'provider':source,'latitude':lat,'longitude':lon,**metadata}})
                    report['matched' if updated else 'unknown_ids']+=1
                    if updated and metadata.get('match_type')=='Exact':
                        report['exact_matches']+=1
                except (TypeError,ValueError):
                    report['invalid']+=1
            report['remaining_unlocated']=Station.objects.filter(latitude__isnull=True).count()
            self.stdout.write(json.dumps(report,indent=2))
        except (OSError,requests.RequestException,KeyError) as exc:
            raise CommandError(f'Coordinate enrichment failed: {exc}') from exc
