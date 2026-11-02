# Spotter backend fuel assessment

[GitHub](https://github.com/azeemamjad/spotter-backend-fuel-assessment) Ã‚Â· Django **6.1.2**, Python **3.14.7** verified.

This independent backend assessment returns an OSRM road route, cost-effective fuel purchases, tank-balance checks, measured provider diagnostics and a saved interactive map. The vehicle holds **50 US gallons**, achieves **10 MPG** and has **500 miles** maximum range. Initial fuel is already owned; purchase cost excludes it and trip consumption is reported separately.

**Coverage limitation:** the actual employer CSV is imported, but only **105 of 6,626 US stations (1.58%)** have accepted coordinates: 75 Census Exact street-address matches, 4 verified official Love's station locations and 26 strictly identity-matched OSM truck-fuel POIs. The other **6,521** remain excluded. Optimization uses this located subset on the selected route; it does not claim nationwide optimality. Both demonstrated ChicagoÃ¢â‚¬â€œDenver fuel stops use official station coordinates.

## Reproduce locally

Use Python 3.12Ã¢â‚¬â€œ3.14. From this directory in PowerShell:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-lock.txt
Copy-Item .env.example .env
.\.venv\Scripts\python manage.py migrate
# Obtain the actual employer attachment and place it at the path below.
.\.venv\Scripts\python manage.py import_stations data/fuel-prices-for-be-assessment.csv
# Bundled coordinates/provenance reproduce the accepted subset without provider calls.
.\.venv\Scripts\python manage.py enrich_stations --coordinates data/station-coordinates.json
.\.venv\Scripts\python manage.py runserver 127.0.0.1:8002
```

Open [the planner](http://127.0.0.1:8002/) or use `delivery/backend.postman_collection.json`. Port 8000 is occupied by an unrelated application in this workspace; the root launcher defaults to 8002. The original file was copied from `C:\Users\Azeem\Downloads\fuel-prices-for-be-assessment.csv`, preserving the original. It is not committed. Reviewers need that employer attachment; source code and coordinate-only crosswalk are committed.

`.env.example` documents debug, secret, allowed hosts, OSRM URL, timeout and station corridor. No API key is needed. For production use a strong secret, `DJANGO_DEBUG=0`, appropriate hosts and a WSGI server such as Waitress. Backend hosting is optional; GitHub and a Ã¢â€°Â¤5-minute Loom are required. A Loom has not been supplied or recorded.

## Actual source inspection and import policy

The supplied file is a **577,081-byte UTF-8 comma-delimited CSV**, inspected 2 November 2026, with **8,151 data rows** and exact headings:

```text
OPIS Truckstop ID,Truckstop Name,Address,City,State,Rack ID,Retail Price
```

There are no empty fields, coordinate columns or unparsable/nonpositive prices. Prices have up to **eight decimal places**, preserved with Decimal and an eight-place database field. The file includes US states and Canadian province codes. **620 Canadian rows** are excluded. The remaining rows contain **6,626 distinct US OPIS IDs**, plus **905 duplicate US rows**. **891 duplicates differ from their first retained row** in normalized fields such as name/price. No timestamp or fuel-type discriminator resolves competing observations. The explicit policy is **first valid US row per OPIS ID in file order**; later duplicates are counted/skipped. It does not assume the cheapest conflicting observation is available. Reimports update retained records and preserve enrichment.

No source columns explicitly establish currency, price denominator or fuel grade. The assessment's convention is implemented by interpreting Retail Price as **USD per US gallon**, fuel grade unspecified. Canadian observations are excluded instead of mixing possible currencies/units. Confirm any different employer clarification before submission.

The importer reports actual mappings, rows, created/updated/duplicate/conflicting/non-US/invalid/unlocated counts. It validates prices after quantization, rejects invalid supplied coordinates, preserves quoted multiline fields and supports alternate encodings/delimiters. `--columns` accepts JSON mapping for changed headings; `--encoding cp1252` is available. OPIS ID is the stable identity; a source without IDs uses a normalized name/address/city/state hash.

## Coordinate provenance

Coverage increased from 79 to 105 by accepting 26 additional truck-fuel POIs after exact brand/store-number/city/state matching. This is still only 1.58% of the imported US stations and is not nationwide complete. See [the coverage review](data/osm-coordinate-provenance.md) for evidence, rejection rules, remaining work and route checks.

`data/station-coordinates.json` is a reproducible **105-row coordinate-only crosswalk with provenance**, without employer prices. API fuel stops expose `coordinate_source`.

- **75 Census Exact matches:** `Public_AR_Current` address-batch results, additionally checked against source city/state. These are street-address interpolations; station property position/access remain approximate.
- **4 official Love's POIs:** OPIS 67284 / Love's 390 North Platte,69177 / Love's 426 Shelby,66236 / Love's 309 Aurora,69710 / Love's 625 Sidney. Official pages identify OPIS/store number; coordinates come from their linked maps. See [source evidence](data/verified-i80-coordinate-provenance.md).

The US Census batch returned 75 Exact, 451 Non_Exact, 5,857 No_Match and 243 Tie results. Non_Exact highway descriptors sometimes matched unrelated numbered streets or different cities and are **all rejected**. No city centroids or guessed highway junctions are used.

Optional future preparation: `python manage.py enrich_stations --census` submits up to 10,000 unlocated addresses in one batch and persists only Exact results matching source city/state. `--refresh` reruns all stations. The raw response is saved locally as ignored `data/census-last-response.csv`; `--census-results <response.csv>` reapplies it offline. An external CSV crosswalk `source_id,latitude,longitude` is supported too. Run preparation separately from serving traffic with SQLite. Enrichment never runs inside customer requests. Further coverage requires additional verified locations; unresolved rows remain excluded.

## API

`POST /api/route-plan/`, content type `application/json`:

```json
{"origin":"Chicago, IL","destination":"Denver, CO","initial_fuel_gallons":50}
```

Cities require a state when ambiguous. Coordinates are also accepted as `{"latitude":41.85,"longitude":-87.65}` and verified against US Census state/DC boundaries; territories are excluded. Initial fuel defaults to 50 and accepts 0Ã¢â‚¬â€œ50. A nonstation origin cannot sell fuel.

Responses contain resolved locations, road GeoJSON/distance/duration, ordered stops with coordinate source/price/route mile/purchases/tank balances, every leg's arrival balance, gallons/cost/consumption/destination balance, assumptions, saved `map_url` and metadata. Money is a decimal string. Metadata measures provider calls, cache hits, milliseconds, corridor candidates and located/unlocated dataset counts. Saved maps persist at `GET /map/<id>/`; `GET /` is the planner and `GET /api/health/` reports dataset readiness/counts.

Errors use `{"error":{"code":"...","message":"..."}}`: bad input/ambiguous city 400, method 405, content type 415, infeasible subset/no road route 422, upstream 502, missing dataset/database/rate limit 503. Infeasibility in the loaded subset does not prove no real refueling trip exists. Calls have configurable timeouts and no hidden retries.

## Algorithm and assumptions

1. Resolve/cache cities with Open-Meteo or verify coordinates with US Census; geocodes persist in SQLite.
2. Request one OSRM driving route with full geometry/road annotations, cached for one hour. A cold named route uses two geocoding calls plus one routing call; cached repeats need zero.
3. Bounding-box filter located stations, use a spatial grid to narrow polyline segments, and project candidates within the **2-mile corridor** onto cumulative road distance. Without annotations, scale geometric lengths to the provider's total and report that approximation.
4. Sort stations; a monotone stack finds the next cheaper station. Buy enough to reach it when within full-tank range; otherwise target capacity capped at remaining trip consumption, subtracting carried fuel. Verify every leg. Sorting O(n log n), fuel planning O(n).

The optimizer is exact for continuous fuel purchases on **one fixed route, zero station detour costs and the available located subset**. It does not search all road routes. Station detours, exit connectivity, hours and commercial-truck restrictions are unverified. The map shows the base route/markers, not exact detour roads. Initial fuel has economic value but is excluded from new purchase totals. Decimal accounting uses a 0.000001-gallon tolerance; line items round half-up to cents and their displayed sum defines the displayed total. An unrounded total is also returned.

## Verified real demonstration

Chicago, IL Ã¢â€ â€™ Denver, CO, initial 50 gallons, default 2-mile corridor, after rejecting Non_Exact results:

| Result | Observed value |
|---|---:|
| Road distance | 1,004.765 miles |
| Love's 426 Shelby IA, OPIS 69177 | mile430.854; buy8.821614gal; $32.19 |
| Love's 309 Aurora NE, OPIS 66236 | mile588.216; buy41.654922gal; $137.00 |
| New fuel purchases | **$169.19** |
| Both purchase coordinate sources | official_loves_station_page |

Geometry has 9,369 points / 9,368 road annotations. The initial live provider-only spike took **3,032.04 ms**,3 calls; a repeated provider-only pipeline took **4.59 ms**,0 calls. After actual station preparation, a complete warm HTTP API request took **27.98 ms**,0 calls,12 examined stations / 3 corridor candidates. These are single local observations, not throughput guarantees. Every response measures its own complete timing/calls. Provider route changes and accepted station coverage can change results.

## Fresh route checks - 2 November 2026, 23:55-23:57 PKT

| Trip | Result | Miles | New purchases, starting with 50 gal |
|---|---|---:|---:|
| Chicago to Denver | Feasible, two stops | 1,004.765 | $169.19 |
| Denver to Chicago | Feasible, two stops | 1,005.874 | $169.61 |
| Chicago to Cleveland | No new purchases needed | 344.075 | $0.00 |
| Las Vegas to Salt Lake City | No new purchases needed | 419.544 | $0.00 |
| Atlanta to Dallas | HTTP 422 in located subset | - | - |
| Chicago to New York | HTTP 422 in located subset | - | - |

All successful routes passed leg/tank-balance assertions. Chicago to Denver used one route-provider call and 908.21 ms on the first run (two geocode cache hits), then zero provider calls and 23.40 ms on repetition. These are measured server times; client times were 970.28 ms and 77.15 ms. HTTP 422 now explicitly describes the incomplete located subset and returns its coverage counts; it does not establish real-world infeasibility.

## Checks and submission

```powershell
.\.venv\Scripts\python manage.py check
.\.venv\Scripts\python manage.py makemigrations --check --dry-run
.\.venv\Scripts\python manage.py test
```

**25 tests pass**, covering fuel boundaries, multi-stop costs, infeasible gaps, 108 exhaustive oracle comparisons, road projection, API validation/maps, geocode/country checks, malformed locations/huge numbers, actual-style schema import, 8-place prices, duplicate/non-US policy, multiline addresses, coordinate persistence, Non_Exact rejection and Exact locality mismatch rejection. Providers are mocked in automated tests; live routing/geocoding/coordinate-country checks and the real multi-stop API were verified separately.

Use the committed Postman collection and `delivery/WALKTHROUGH.md` for the Ã¢â€°Â¤5-minute Loom. Submit the actual [GitHub link](https://github.com/azeemamjad/spotter-backend-fuel-assessment) and a working Loom through the **backend** questionnaire. No Loom was fabricated or assessment form submitted.

## Attribution

[Django stable release](https://www.djangoproject.com/download/) Ã‚Â· [OSRM](https://project-osrm.org/docs/v5.24.0/api/#route-service) Ã‚Â· [Open-Meteo/GeoNames](https://open-meteo.com/en/docs/geocoding-api) Ã‚Â· [US Census](https://geocoding.geo.census.gov/geocoder/Geocoding_Services_API.html) Ã‚Â· [OpenFreeMap](https://openfreemap.org/quick_start/) Ã‚Â· MapLibre GL JS 5.6.1. OpenFreeMap styles include OpenMapTiles/OpenStreetMap attribution. Check service availability/terms for production; public demo services carry no availability guarantee. The map requires internet/WebGL.

## Reviewer access

This repository was made **public on 3 November 2026**, after the owner explicitly approved public visibility following source/history review. Anonymous GitHub API and web requests returned HTTP 200. The original employer CSV, databases, caches, virtual environments and `.env` files remain excluded. Public read access requires no collaborator invitation.
