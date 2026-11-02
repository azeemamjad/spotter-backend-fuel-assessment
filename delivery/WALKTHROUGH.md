# Backend demonstration checklist

Use the original employer CSV, after import and one-time location enrichment. Do not present synthetic test fixtures as the final dataset. Import `backend.postman_collection.json` into Postman and edit its `base_url` if the local API uses a different port; the combined workspace launcher uses `http://127.0.0.1:8002`.

Record at most five minutes:

1. **0:00–0:30:** Explain origin/destination inputs, 500-mile range, 10 mpg, 50-gallon tank and the starting-fuel model. The initial tank is already owned; the total reports new purchases, with consumption reported separately.
2. **0:30–2:00:** Send the Chicago, IL → Denver, CO real-data request in Postman after final coordinate validation, inspect the actual response and open its `map_url`. Demonstrate multiple purchases under the full initial tank model. Do not use the withdrawn preliminary Minneapolis–Dallas result based on non-exact Census matches.
3. **2:00–3:00:** Explain the selected station prices, gallons purchased, costs and fuel on arrival/departure. State that the optimizer minimizes new-purchase cost along one selected road route and omits station access/detour mileage.
4. **3:00–4:15:** Show the importer report, persisted coordinates, optimizer code and meaningful tests, including a manually/exhaustively checked small case.
5. **4:15–5:00:** Repeat a request to show measured request count/cache behavior. State provider limits, any unresolved stations and any unfinished requirements.

Before submission, open the GitHub repository and Loom recording in a clean browser to verify the hiring team's access. Submit the real GitHub and Loom URLs through the **Backend Django Engineer** email's **Show Questions** form. A full-stack submission or ordinary email reply is not a substitute.

The original CSV has now been supplied locally. Verify the importer/enrichment results and a feasible real-data route before recording; unresolved station addresses and corridor-access assumptions must be disclosed. A recording and questionnaire submission have not been created by this repository.
