import csv
import hashlib
import io
import json
import math
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from stations.models import Station

def normalized(value):
    return re.sub(r'[^a-z0-9]', '', value.lower())

ALIASES = {
    'source_id': ['opis truckstop id', 'truckstop id', 'station id', 'id'],
    'name': ['truckstop name', 'station name', 'name'],
    'address': ['address', 'street address', 'street'],
    'city': ['city'], 'state': ['state'],
    'price': ['retail price', 'price', 'fuel price', 'price per gallon'],
    'latitude': ['latitude', 'lat'], 'longitude': ['longitude', 'lon', 'lng'],
}

class Command(BaseCommand):
    help = 'Import actual employer station CSV, preserving unlocated rows for one-time enrichment.'
    def add_arguments(self, parser):
        parser.add_argument('csv_path')
        parser.add_argument('--columns', help='JSON mapping normalized field -> actual CSV column')
        parser.add_argument('--encoding', default='utf-8-sig')
    def handle(self, *args, **options):
        path = Path(options['csv_path'])
        if not path.is_file():
            raise CommandError(f'CSV not found: {path}. Obtain the actual employer attachment.')
        try:
            text = path.read_text(encoding=options['encoding'])
            reader = csv.DictReader(io.StringIO(text, newline=''), dialect=csv.Sniffer().sniff(text[:8192], delimiters=',;\t'))
            headers = reader.fieldnames or []
            available = {normalized(h): h for h in headers}
            mapping = {field: next((available[normalized(a)] for a in aliases if normalized(a) in available), None) for field,aliases in ALIASES.items()}
            if options['columns']:
                mapping.update(json.loads(options['columns']))
            for required in ('name', 'address', 'price'):
                if not mapping.get(required) or mapping[required] not in headers:
                    raise CommandError(f'Missing {required} column. Actual headers: {headers}. Supply --columns JSON.')
            report = {'headers': headers, 'mapping': mapping, 'rows': 0, 'created': 0, 'updated': 0, 'duplicate_rows': 0, 'invalid_rows': 0, 'missing_coordinates': 0, 'invalid_examples': []}
            seen = set()
            with transaction.atomic():
                for row_number,row in enumerate(reader,2):
                    report['rows'] += 1
                    try:
                        def cell(field):
                            return (row.get(mapping.get(field)) or '').strip()
                        price = Decimal(cell('price').replace('$','').replace(',',''))
                        if not price.is_finite() or not 0 < price < 10000:
                            raise ValueError('Price must be finite and positive.')
                        price = price.quantize(Decimal('.0001'))
                        if not 0 < price < 10000:
                            raise ValueError('Price must remain positive and below 10000 at four decimal places.')
                        name, address, city, state = cell('name'),cell('address'),cell('city'),cell('state')
                        if not name or not address:
                            raise ValueError('Station name and address are required.')
                        identity = cell('source_id') or hashlib.sha256('|'.join([name,address,city,state]).casefold().encode()).hexdigest()
                        if identity in seen:
                            report['duplicate_rows'] += 1
                            continue
                        latitude,longitude,coordinate_source = None,None,''
                        if cell('latitude') or cell('longitude'):
                            latitude,longitude = float(cell('latitude')),float(cell('longitude'))
                            if not math.isfinite(latitude) or not math.isfinite(longitude) or not -90 <= latitude <=90 or not -180 <=longitude <=180:
                                raise ValueError('Coordinates are invalid.')
                            coordinate_source = 'employer_csv'
                        defaults = {'name':name,'address':address,'city':city,'state':state,'price':price}
                        # Reimports without coordinates preserve earlier enrichment.
                        if latitude is not None:
                            defaults.update(latitude=latitude,longitude=longitude,coordinate_source=coordinate_source)
                        station,created = Station.objects.update_or_create(source_id=identity,defaults=defaults)
                        report['created' if created else 'updated'] += 1
                        report['missing_coordinates'] += int(station.latitude is None or station.longitude is None)
                        seen.add(identity)
                    except (InvalidOperation, ValueError, TypeError) as exc:
                        report['invalid_rows'] += 1
                        if len(report['invalid_examples']) < 10:
                            report['invalid_examples'].append({'row':row_number,'reason':str(exc)})
            self.stdout.write(json.dumps(report,indent=2))
        except (UnicodeError,csv.Error,json.JSONDecodeError) as exc:
            raise CommandError(f'Cannot parse CSV/configuration: {exc}') from exc
