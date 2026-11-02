# Spotter backend fuel assessment

Django 6.1.2 API for cost-effective fuel purchases along a US road route. It returns an actual OSRM road geometry, a feasible purchase plan, decimal money accounting, request diagnostics and a saved Leaflet map. The tank holds 50 US gallons, economy is 10 miles per gallon and maximum range is 500 miles.

## Run locally

Python 3.12–3.14 is supported; this workspace was verified with Python 3.14.7. From this directory in PowerShell:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-lock.txt
Copy-Item .env.example .env
.\.venv\Scripts\python manage.py migrate
.\.venv\Scripts\python manage.py import_stations data/fuel-prices-for-be-assessment.csv
.\.venv\Scripts\python manage.py enrich_stations --census
.\.venv\Scripts\python manage.py runserver 127.0.0.1:8000
```

Open [the planner](http://127.0.0.1:8000/) or use Postman. Choose another port if 8000 is occupied; the workspace launcher defaults to **8002**. The backend requires no API key. `.env` configures debug, allowed hosts, secret, provider timeout, routing URL and station corridor; the actual names and sample values are in `.env.example`. For production, set a strong secret, `DJANGO_DEBUG=0`, appropriate hosts and serve `config.wsgi:application` through a production server. This project is intentionally independent of the full-stack assessment.

## Real dataset preparation

Obtain **fuel-prices-for-be-assessment.csv** from the employer's backend email and save it under `data/`. The actual file was not yet present when this implementation was tested. No synthetic station prices or guessed coordinates are loaded into the application. Until at least one valid geolocated station is present, the route endpoint returns `503 station_data_unavailable` before making external requests. Unit tests create artificial rows only inside temporary test databases.

The importer accepts UTF-8 with an optional BOM and detects comma, semicolon or tab delimiters. It prints original headers, selected column mappings, total rows, created/updated/invalid/duplicate counts, unlocated count and examples of invalid records. Recognized headings include `OPIS Truckstop ID`, `Truckstop Name`, `Address`, `City`, `State`, `Retail Price`, `Latitude` and `Longitude`. This is a flexible mapping, **not a claim that the absent employer file has those columns**. If needed, supply actual header mappings:

```powershell
.\.venv\Scripts\python manage.py import_stations data/fuel-prices-for-be-assessment.csv --columns '{"name":"Station","price":"USD/Gallon","address":"Street"}'
```

`--encoding cp1252` is available for a differently encoded source. Positive finite prices use Decimal with four stored decimal places. The source station ID is unique; when absent the normalized name/address/city/state tuple is hashed. The first valid row for an ID wins within one file and repeated imports update existing records. Rows without coordinates remain stored for enrichment. Invalid supplied coordinates are rejected. Reimporting a row without coordinates preserves previous enrichment. Verify fuel type, USD/US-gallon price units and source semantics against the actual file before submission; the planner interprets the imported retail price as USD per US gallon.

Coordinate enrichment happens once, never in a route request:

- `enrich_stations --census` submits up to 10,000 missing station street addresses to the US Census batch geocoder in one request. It persists returned matches and reports unmatched addresses. Census geocoding interpolates street-address locations; highway exit descriptions and incomplete addresses may not match. Review accuracy and resolve unmatched rows before a final demo.
- `enrich_stations --coordinates verified-stations.csv` accepts a manually verified crosswalk with `source_id,latitude,longitude`. It updates only known station IDs. Never use city centroids as exact station locations.

The original employer attachment and database are gitignored. Reviewers must obtain that same source file and reproduce preparation, or receive an authorized coordinate crosswalk alongside the submission. No assertion of full dataset coverage is made until the actual import and enrichment have run.

## API

`POST /api/route-plan/`, content type `application/json`:

```json
{"origin":"Chicago, IL","destination":"Denver, CO","initial_fuel_gallons":50}
```

Cities require a state when multiple states match. A location may instead be `{"latitude":41.85,"longitude":-87.65}`; coordinates are checked against US Census state boundaries. US states and DC are accepted; territories are excluded. The initial-fuel field defaults to 50 and accepts 0–50. A nonstation origin cannot sell fuel, so an empty tank requires a priced station projected at mile zero.

Responses contain resolved locations, route geometry/distance/duration, `fuel_stops`, fuel-leg checks, `total_purchased_gallons`, `total_purchase_cost_usd`, `trip_fuel_consumed_gallons`, destination balance, vehicle assumptions, `map_url` and metadata. Each purchase has station identity/location, projected route mile, price, gallons, cost and arrival/departure tank balances. Displayed money is a decimal string. A saved map is persisted in SQLite and can be reopened at `GET /map/<id>/`.

`GET /api/health/` returns station counts and `dataset_ready`; `GET /` is the input/map page. Errors use `{"error":{"code":"...","message":"..."}}`: invalid JSON/input or ambiguous city 400, wrong method 405, wrong content type 415, infeasible fuel/no road route 422, upstream failure 502, missing data/database or provider rate limit 503. Upstream requests have a configurable timeout and no hidden retries.

## Algorithm and scope

1. Resolve/caches cities with Open-Meteo geocoding, or verify coordinates using US Census geographies. Resolved locations persist in SQLite.
2. Make one OSRM driving route request with full GeoJSON geometry and road distance annotations; cache that response for one hour.
3. Filter priced stations by the route bounding box. A local spatial grid narrows candidate polyline segments; project nearby station coordinates onto those segments. The default corridor is **2 miles** on either side. Road annotations determine route positions; if annotations are unavailable, geometric segment distances are scaled to the provider's road total and this approximation is reported.
4. Sort stations by route position. Compute the first strictly cheaper station ahead using a monotone stack. At each station, buy enough to reach that cheaper station if within range; otherwise target a full tank, capped at remaining trip consumption. Subtract carried fuel before purchasing. Check every leg and reject infeasible routes. Zero-purchase stations are omitted from purchase markers.

The purchase optimizer is exact for continuous fuel on this **single fixed route with zero detour costs**. Sorting is O(n log n), fuel planning O(n); it does not find a globally cheapest road route. Nearby stations are assumed accessible at their projected position. Access/return detours, highway exit connectivity and station opening times are omitted. The map draws the base route and station markers, not claimed exact detour roads. OSRM's generic driving profile does not certify commercial-truck legal access.

Initial fuel is **already owned**, excluded from new-purchase cost. Trip consumption is reported separately; zero purchases do not mean zero economic value of consumed fuel. Fuel uses Decimal arithmetic without intermediate rounding, with a 0.000001-gallon feasibility tolerance. Purchase line items round half-up to cents; their displayed sum defines the displayed total. An unrounded purchase total is also available.

## Checks and measured performance

```powershell
.\.venv\Scripts\python manage.py check
.\.venv\Scripts\python manage.py test
```

Fifteen automated tests cover short/exact-range/zero-fuel trips, cheaper stations, multi-stop accounting, infeasible gaps, projection, input/data validation, saved map rendering, country checks, geocode caching, importer handling (including tiny prices and quoted multiline addresses) and coordinate crosswalks. The optimizer is compared against an exhaustive integer-gallon dynamic program for 108 small cases, where integer gallons are sufficient for an exact oracle. External route/geocode integration is mocked in API tests.

Live integration observed on 2 November 2026: Chicago, IL → Denver, CO returned **1,004.77 road miles, 9,369 geometry points, 9,368 distance annotations**. Two uncached geocoding requests plus one route request took **3,032.04 ms**; the repeated provider pipeline used zero external calls and took **4.59 ms**. These are one local provider-pipeline observations, not complete station optimization latency or throughput claims. The actual API reports measured end-to-end timings and provider counts on every successful response. Station matching and real multi-stop live verification remain pending actual dataset availability.

## Providers and submission

- [Django download/version](https://www.djangoproject.com/download/) and [Python compatibility](https://docs.djangoproject.com/en/6.1/faq/install/).
- [OSRM Route API](https://project-osrm.org/docs/v5.24.0/api/#route-service). Public demo endpoint has no availability guarantee; use a suitable provider/self-hosting for production.
- [Open-Meteo geocoding](https://open-meteo.com/en/docs/geocoding-api) uses GeoNames data. Check current service terms for hosted/commercial use.
- [US Census geocoding](https://geocoding.geo.census.gov/geocoder/Geocoding_Services_API.html) for verified US coordinates and batch street-address enrichment.
- Leaflet 1.9.4 and OpenStreetMap tiles/contributors with attribution in the map. Public tile services and CDN access require internet.

GitHub repository and Loom links have not been created by this implementation. Record a ≤5-minute walkthrough using Postman, explain initial fuel and approximation scope, show a real multi-stop request/map, importer/tests and measured request budget, then submit working links through the backend questionnaire. See the root `SUBMISSION.md` and Postman collection for the remaining external deliverables. The employer dataset is the material outstanding local dependency.

## Repository access

GitHub: [azeemamjad/spotter-backend-fuel-assessment](https://github.com/azeemamjad/spotter-backend-fuel-assessment), created private. Grant the hiring team access before submission. A real accessible Loom recording of at most five minutes is still required; it has not been generated or submitted by this repository.

