from copy import deepcopy
from django.test import SimpleTestCase
from .osm_matching import match_snapshot


class OsmMatchingTests(SimpleTestCase):
    def setUp(self):
        self.station = {"source_id": "fixture", "name": "LOVES TRAVEL STOP #306", "city": "Dandridge", "state": "TN", "latitude": None, "longitude": None}
        self.poi = {"type": "node", "id": 1, "lat": 36.01, "lon": -83.53, "tags": {"amenity": "fuel", "brand": "Love's", "ref": "306", "addr:city": "Dandridge", "addr:state": "TN", "hgv": "yes"}}

    def match(self, pois=None, stations=None):
        return match_snapshot({"osm3s": {"timestamp_osm_base": "2026-11-02T16:58:27Z"}, "elements": pois or [self.poi]}, stations or [self.station])

    def test_exact_identity_preserves_provenance(self):
        rows, report = self.match()
        self.assertEqual(report["accepted"], 1)
        self.assertEqual(rows[0]["source_id"], "fixture")
        self.assertEqual(rows[0]["provenance"]["source_url"], "https://www.openstreetmap.org/node/1")

    def test_wrong_locality_or_no_truck_evidence_is_rejected(self):
        for key, value in (("amenity", "restaurant"), ("addr:city", "Elsewhere"), ("addr:state", "KY"), ("hgv", "no"), ("hgv", "no;yes"), ("hgv", "")):
            with self.subTest(key=key, value=value):
                poi = deepcopy(self.poi); poi["tags"][key] = value
                self.assertEqual(self.match([poi])[0], [])

    def test_ambiguous_store_identity_or_far_apart_pois_is_rejected(self):
        other = dict(self.station, source_id="second")
        self.assertEqual(self.match(stations=[self.station, other])[0], [])
        distant = deepcopy(self.poi); distant["id"] = 2; distant["lat"] += .1
        self.assertEqual(self.match([self.poi, distant])[0], [])

    def test_existing_coordinates_are_preserved(self):
        self.assertEqual(self.match(stations=[dict(self.station, latitude=36.0, longitude=-83.0)])[0], [])

    def test_official_store_url_and_way_center_can_support_identity(self):
        poi = deepcopy(self.poi); poi["type"] = "way"; poi["center"] = {"lat": poi.pop("lat"), "lon": poi.pop("lon")}
        poi["tags"].pop("ref"); poi["tags"]["website"] = "https://www.loves.com/locations/306"
        self.assertEqual(self.match([poi])[1]["accepted"], 1)
