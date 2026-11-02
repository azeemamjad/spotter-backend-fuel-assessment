import json
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from stations.models import Station
from stations.osm_matching import match_snapshot


class Command(BaseCommand):
    help = "Export conservative unlocated-station matches from a saved OSM/Overpass JSON snapshot. No network calls or DB mutations."

    def add_arguments(self, parser):
        parser.add_argument("snapshot")
        parser.add_argument("--output", required=True)

    def handle(self, *args, **options):
        try:
            snapshot = json.loads(Path(options["snapshot"]).read_text(encoding="utf-8"))
            records, report = match_snapshot(snapshot, Station.objects.values("source_id", "name", "city", "state", "latitude", "longitude"))
            Path(options["output"]).write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
            self.stdout.write(json.dumps(report, indent=2))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise CommandError(f"Cannot match OSM snapshot: {exc}") from exc
