"""Conservative, offline identity matching; never guess by nearest city."""
import math
import re
from collections import defaultdict


def normalized(value):
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


def brand(value):
    name = normalized(value)
    return next((b for b in ("loves", "flyingj", "pilot") if name.startswith(b)), None)


def store_numbers(tags):
    numbers = set()
    for key in ("ref", "name", "official_name", "branch"):
        value = str(tags.get(key, ""))
        if key == "ref" and value.isdigit():
            numbers.add(str(int(value)))
        match = re.search(r"#\s*(\d+)\b", value)
        if match:
            numbers.add(str(int(match[1])))
    for key in ("website", "contact:website"):
        match = re.search(r"^https?://(?:www\.)?loves\.com/locations/(\d+)(?:/|$)", str(tags.get(key, "")))
        if match:
            numbers.add(str(int(match[1])))
        match = re.search(r"^https?://(?:www\.)?pilotflyingj\.com/stores/(\d+)(?:/|$)", str(tags.get(key, "")))
        if match:
            numbers.add(str(int(match[1])))
    return numbers


def miles(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    x = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return 7917.5226 * math.asin(min(1, math.sqrt(x)))


def match_snapshot(snapshot, stations):
    """Return coordinate records and rejection diagnostics without DB/network IO."""
    index, candidates = defaultdict(list), defaultdict(list)
    report = {"objects": len(snapshot.get("elements", [])), "identity_candidates": 0,
              "ambiguous_identity": 0, "locality_mismatch_or_missing": 0,
              "no_truck_evidence": 0, "invalid_coordinates": 0, "spatial_conflicts": 0,
              "already_located": 0, "accepted": 0}
    for station in stations:
        match = re.search(r"#\s*(\d+)\b", station["name"])
        chain = brand(station["name"])
        if match and chain:
            index[chain, str(int(match[1]))].append(station)
    for element in snapshot.get("elements", []):
        tags = element.get("tags", {})
        if tags.get("amenity") != "fuel":
            continue
        chain, numbers = brand(tags.get("brand", "")), store_numbers(tags)
        if not chain or not numbers:
            continue
        if len(numbers) != 1:
            report["ambiguous_identity"] += 1
            continue
        source = index.get((chain, next(iter(numbers))), [])
        if len(source) != 1:
            report["ambiguous_identity"] += 1
            continue
        report["identity_candidates"] += 1
        station = source[0]
        if not tags.get("addr:city") or not tags.get("addr:state") or normalized(tags["addr:city"]) != normalized(station["city"]) or normalized(tags["addr:state"]) != normalized(station["state"]):
            report["locality_mismatch_or_missing"] += 1
            continue
        hgv = tags.get("hgv", "")
        if "no" in hgv.split(";") or not (hgv in ("yes", "only", "designated") or tags.get("fuel:HGV_diesel") == "yes"):
            report["no_truck_evidence"] += 1
            continue
        point = element if "lat" in element else element.get("center", {})
        lat, lon = point.get("lat"), point.get("lon")
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in (lat, lon)) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
            report["invalid_coordinates"] += 1
            continue
        if station.get("latitude") is not None and station.get("longitude") is not None:
            report["already_located"] += 1
            continue
        record = {"source_id": station["source_id"], "latitude": lat, "longitude": lon,
                  "provenance": {"provider": "OpenStreetMap_identity_match",
                    "source_url": f"https://www.openstreetmap.org/{element['type']}/{element['id']}",
                    "snapshot_time": snapshot.get("osm3s", {}).get("timestamp_osm_base"),
                    "license": "ODbL-1.0", "match_type": "exact_brand_store_city_state_with_truck_evidence",
                    "coordinate_accuracy": "OSM point or bounding-box center of truck fuel POI; access detours unverified",
                    "matched_tags": {k: tags[k] for k in ("brand", "ref", "name", "website", "addr:city", "addr:state", "addr:street", "addr:housenumber", "hgv", "fuel:HGV_diesel") if k in tags}}}
        priority = (tags.get("fuel:HGV_diesel") == "yes", hgv == "only", hgv in ("yes", "designated"), element["type"] == "node")
        candidates[station["source_id"]].append((priority, record))
    accepted = []
    for source_id, matches in sorted(candidates.items()):
        points = [(r["latitude"], r["longitude"]) for _, r in matches]
        if any(miles(a, b) > .25 for i, a in enumerate(points) for b in points[i+1:]):
            report["spatial_conflicts"] += 1
            continue
        record = max(matches, key=lambda item: (item[0], item[1]["provenance"]["source_url"]))[1]
        record["provenance"]["corroborating_osm_urls"] = sorted(r["provenance"]["source_url"] for _, r in matches)
        accepted.append(record)
    report["accepted"] = len(accepted)
    return accepted, report
