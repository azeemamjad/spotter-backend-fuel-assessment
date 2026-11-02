# Station data

The actual employer CSV is loaded locally at `fuel-prices-for-be-assessment.csv` and gitignored. It contains 8,151 rows, seven OPIS/Truckstop/Address/City/State/Rack/Retail Price columns and no coordinates. US-only import yields 6,626 unique stations after excluding 620 Canadian rows / 905 US duplicate rows. Prices preserve eight decimals; first valid US observation per OPIS ID is retained because no timestamp/fuel-type discriminator exists.

Committed `station-coordinates.json` contains 105 accepted locations with provenance: 75 Census Exact city/state matches 4 official Love's POIs and 26 exact-identity-matched OSM truck-fuel POIs. No employer prices are included. Reproduce using `python manage.py enrich_stations --coordinates data/station-coordinates.json` after importing the original CSV. The other 6,521 US stations remain unlocated/excluded. See `verified-i80-coordinate-provenance.md` for official evidence.

Raw Census responses, employer CSV, database and caches are ignored. All 451 Non_Exact matches were rejected because highway descriptors can resolve to unrelated streets/cities. No city-center substitutes are used. Census Exact locations remain street-address approximations, not independently verified station POIs.

The OSM-derived additions are separately identified as `OpenStreetMap_identity_match`, with original object URLs/tags, snapshot time and ODbL attribution. They are point or fuel-canopy bounding-box centers, not surveyed entrance coordinates. See `osm-coordinate-provenance.md`.
