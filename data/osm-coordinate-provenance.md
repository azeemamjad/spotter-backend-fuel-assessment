# OSM coverage review - 3 November 2026

Accepted coordinate coverage: **105 / 6,626 US stations (1.58%)**, previously 79. **6,521 remain unresolved and excluded. This API is not nationwide complete.** The 26 additions supplement 75 Census Exact locality-matched addresses and four official Love's POIs; they do not replace those locations.

The saved Overpass snapshot contains 1,663 POIs, with OSM base timestamp `2026-11-02T16:58:27Z`. Source snapshot SHA-256: `c782e9d136acfdb679f51ff685ce552f9b69a1944c005965ccac9e67da189470` (raw research snapshot retained locally, not bundled). The accepted coordinate-only subset is bundled in `osm-station-coordinates.json` and merged into `station-coordinates.json`; no employer prices are copied into these files.

## Acceptance and rejection rules

`python manage.py match_osm_stations data/osm-truckstop-pois.json --output data/osm-station-coordinates.json` runs offline, writes candidates and does not update the database. It requires an exact chain/store number and normalized city/state match to exactly one imported OPIS station. Store numbers come from OSM ref/name/official location URL. Positive HGV or HGV-diesel evidence is required; `hgv=no`, contradictory access tags, missing localities, unknown/non-unique identities and non-finite coordinates are rejected. Existing accepted locations are preserved. Multiple matching objects must lie within 0.25 miles; an HGV-diesel/truck-lane object is preferred deterministically. No nearest-city or proximity-only identity matching is used.

Snapshot diagnostics: 251 objects reached a unique source identity, 43 had absent/non-unique/conflicting identities, 174 lacked a matching city/state, 50 lacked acceptable truck evidence, zero had invalid coordinates or spatial conflicts; 26 distinct unlocated station IDs were accepted. Counts describe objects at different validation stages, not mutually exclusive station totals.

These are **identity-matched community map POIs**, not official-brand or field-surveyed coordinates. A way/relation uses its bounding-box center. Highway exit connectivity and detours remain unverified. Source prices and source duplicates follow the existing first-valid-US-row-per-OPIS policy.

## Accepted source objects

| OPIS station ID | Matched city / state | OSM evidence |
|---|---|---|
| 1914 | Green River, UT | [Source object](https://www.openstreetmap.org/way/325139238) |
| 2923 | Ruther Glen, VA | [Source object](https://www.openstreetmap.org/way/781067019) |
| 52471 | Beaverdam, OH | [Source object](https://www.openstreetmap.org/way/229321016) |
| 64755 | Boonville, MO | [Source object](https://www.openstreetmap.org/way/554602290) |
| 65033 | Beaverdam, OH | [Source object](https://www.openstreetmap.org/way/229320513) |
| 66040 | Kingman, AZ | [Source object](https://www.openstreetmap.org/way/223539583) |
| 66120 | Dandridge, TN | [Source object](https://www.openstreetmap.org/node/6616599586) |
| 66478 | Tecumseh, KS | [Source object](https://www.openstreetmap.org/way/379404861) |
| 66747 | Roscoe, IL | [Source object](https://www.openstreetmap.org/way/225052242) |
| 66912 | Cedar City, UT | [Source object](https://www.openstreetmap.org/way/225054742) |
| 66937 | Rolla, MO | [Source object](https://www.openstreetmap.org/way/677336597) |
| 67037 | Burbank, OH | [Source object](https://www.openstreetmap.org/way/225055027) |
| 67624 | Bennett, CO | [Source object](https://www.openstreetmap.org/way/224603696) |
| 69073 | Springville, UT | [Source object](https://www.openstreetmap.org/way/923227496) |
| 69307 | Hamel, IL | [Source object](https://www.openstreetmap.org/way/1324624103) |
| 69741 | Tolleson, AZ | [Source object](https://www.openstreetmap.org/way/1004594293) |
| 69837 | South Holland, IL | [Source object](https://www.openstreetmap.org/way/1259728861) |
| 69995 | Tucson, AZ | [Source object](https://www.openstreetmap.org/way/855741041) |
| 70107 | Bellville, OH | [Source object](https://www.openstreetmap.org/way/1017955890) |
| 70157 | Waterloo, IA | [Source object](https://www.openstreetmap.org/way/1073996101) |
| 70592 | Elgin, SC | [Source object](https://www.openstreetmap.org/node/10228325504) |
| 71262 | Etna, OH | [Source object](https://www.openstreetmap.org/way/1236321435) |
| 71318 | Elk Grove Village, IL | [Source object](https://www.openstreetmap.org/way/1259770389) |
| 71487 | Fillmore, UT | [Source object](https://www.openstreetmap.org/way/1092683302) |
| 71490 | Heflin, AL | [Source object](https://www.openstreetmap.org/node/13770704758) |
| 7263 | Big Springs, NE | [Source object](https://www.openstreetmap.org/node/7502086792) |

## Licensing and next coverage work

OSM-derived coordinates/tags are attributed to [OpenStreetMap contributors](https://www.openstreetmap.org/copyright) and made available under [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/). This applies to the OSM-derived subset; Census and official-brand records retain their separate provenance. Public brand pages could not be reliably fetched in this run (name-resolution/timeout errors), so no guessed official coordinates were added.

To expand further, obtain an authorized bulk location source keyed by OPIS IDs or exact chain/store identifiers; validate city/state, conflicts and truck-fuel access before import. Keep enrichment outside route requests, retain provenance, and report exact excluded counts. Do not loosen locality or identity checks to inflate coverage. A nationwide optimum cannot be claimed while 6,521 locations are unresolved.

## Fresh real-data route checks

Chicago-Denver and the reverse both succeeded with two purchases; Chicago-Cleveland and Las Vegas-Salt Lake City succeeded on the initial tank. Atlanta-Dallas and Chicago-New York returned HTTP 422 for the loaded subset. All feasible plans passed fuel-balance assertions. The Chicago-Denver demonstration still uses two official Love's locations and totals $169.19, excluding initial fuel. These results do not establish broad national route coverage.
