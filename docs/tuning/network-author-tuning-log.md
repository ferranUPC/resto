# Network Author tuning log

- Status: living document, started 2026-10-15
- Purpose: record each real run of the Network Author with the prompt version it used, its cost and
  the result. Same role as the [Composer's log](composer-tuning-log.md).
- Related: E6.1 ticket 08 (`.scratch/e6-1-network-author-minimal/issues/08-real-path-golden-path-and-dev-run.md`).

Running total spent: **about $0.27** (first run $0.0048, the six costed runs of 2026-10-15 add $0.2128, experiment
12 adds $0.0243, the two Diagonal runs of 2026-10-19 add $0.018; the run that ended in a 502 printed no cost and is
not counted).

## 2026-10-15, Network Author `v1`, first manual run

- **Script:** `scripts/manual_network_author_run.py --run` on branch `e6-1-network-author-minimal`.
  Not part of the suite.
- **Model and budget:** `deepseek/deepseek-v4.1-flash`, 40 steps, 2048 output tokens, 900 s, 3 rounds.
- **Estimate before the run:** at most $0.109. Development run, below the $1 limit in
  `docs/llm-cost-policy.md`. The maintainer approved it before it started.
- **Request:** `"a 5 by 5 grid"`, with Nominatim and Overpass switched off.
- **Result:** 5 tool calls (`find_network`, `generate_grid`, `sanity_check`, `probe_run`,
  `submit_output`), stop reason `output`, 39,260 input and 944 output tokens, cost $0.0048
  (`usage.cost_usd`). The draft had a `GridNetwork(5, 5, 100 m)` recipe, a sanity report of
  1.0 / 0 / true, a probe report with 0 teleports and 0 collisions, and an empty `unresolved[]`.
  `NetworkPromoter.promote` replayed the recipe and got the same `content_hash` (`d8e23de2...`).
- **Reading:** the wiring works from the model to a promoted `Network`. No repair round was needed,
  so this run does not test the repair loop, derivation or `NeedsUser`. Those wait for E6.2.

## 2026-10-15, OpenStreetMap import by hand, eleven experiments

Scripts used: `scripts/manual_network_import_run.py` (no model, real Nominatim, Overpass and `netconvert`) and
`scripts/manual_network_author_run.py --run --online`. Request of experiments 2 to 4: "El barrio de Adlershof en
Berlín, y también la estación de tren de Johannisthal". Experiments 5 to 7 asked for Adlershof with the train
tracks (exact text not kept). Experiment 8 asked for a network for cars (text not kept). Model `deepseek/deepseek-v4.1-flash`, prompt `v1`, 40 steps, 3 rounds.

### 1. A full sentence as the place (import script, no model, $0)

- **Hypothesis:** Nominatim finds a neighbourhood from a descriptive sentence.
- **Result:** `needs the user: Nominatim does not know this place`. `--place` goes to Nominatim as it is.
- **Improvement:** free text belongs to the agent, not to the import script. Places that are not named
  boundaries are the gap that E6.12 (M52, r26) covers.

### 2. Author run online, 2048 output tokens

- **Hypothesis:** the whole path (geocoder, Overpass, `netconvert`, cleanups, promotion) works online.
- **Result:** crash. `fetch_osm` raised `ExternalServiceError: overpass: HTTP 502`. The model had picked the
  area correctly. A direct `curl` with a one-metre query also got 502 on `overpass-api.de` and 500 on a mirror,
  so the public service was down, not the code.
- **Improvements:** retry 502, 503, 504 and 429 with growing waits in `adapters/osm/http.py`; catch
  `ExternalServiceError` in the manual script and show what was spent; optional list of mirrors.

### 3. Same request after Overpass recovered (cost $0.0536)

- **Result:** 14 calls to `submit_output` in a row; the last one was
  `NeedsUser(NetworkNotFound, message='test')`, although a network had been built. 497,443 input and
  37,033 output tokens. Stop reason `output` only means the validation accepted the answer.
- **Gap:** the script did not print why the 13 submissions were rejected.
- **Improvement:** the script now prints the first 600 characters of each failed call.

### 4. Same request again, the model refuses the station ($0.0032)

- **Result:** `Adlershof` resolved to OSM relation 55756 (an administrative boundary, inside 10 km²), the
  snapshot downloaded, and the agent returned `NeedsUser(UnsupportedRequirement)` because a station is a public
  transport stop. It offered the `roads` or `rail` profile instead, in Spanish.
- **Reading:** the refusal follows ADR-0045 and is honest. Experiments 3 and 4 gave different outcomes for the
  same request, so one run proves little; E6.2 measures this over repeated runs.
- **Hypothesis rejected:** an `Ortsteil` such as Adlershof does not resolve in Nominatim.

### 5. Network built, no answer: `stop: budget` ($0.0607)

- **Result:** 10 tool calls in 40 steps, `outcome: None`, 742,218 input and 63,746 output tokens. The
  last tool result was `error: the 3 rounds are spent` (on `inspect_network`): the model had to submit.
- **Hypothesis:** the final `submit_output` is cut at 2048 output tokens.

### 6. Same, with a trace per step ($0.0567)

- **Result:** steps 1 to 9 are tool calls of 70 to 500 output tokens. Steps 10 to 40 all end with
  `finish_reason=length`, 2048 output tokens and no tool call. Input grows by only about 21 tokens per step (the
  reminder to call `submit_output`), so no answer is stored.
- **First reading (wrong):** hidden reasoning that never ends. Experiment 7 corrected it.
- **Improvement:** after two or three `length` steps in a row without a tool call the client should stop with a
  clear reason. Here 31 steps and about $0.045 were spent without any chance of success.

### 7. Same, with 8192 output tokens ($0.0097)

- **Command:** `RESTO_LLM_MAX_OUTPUT_TOKENS=8192`. Worst case rose from $0.109 to $0.257.
- **Result:** finished in 10 steps. `submit_output` alone used **4,066 output tokens**, so experiments 3, 5 and 6
  failed because the answer did not fit in 2048. The draft retypes the polygon (about 130 points) in `source`
  and again in the `--keep-edges.in-geo-boundary` option. `NetworkPromoter` replayed it with the same hash
  (`fafdd5be...`).
- **Quality:** the network is unsound and the draft says so. SCC ratio 0.5466 (minimum 0.95), 30 zero-length
  edges, not reachable from the fringe, with the `rail` profile on the whole boundary. `unresolved[]` lists the
  three problems, so it is not a silent failure.

### 8. Roads for cars only ($0.0289)

- **Hypothesis:** the `roads` profile plus `keep_vclass passenger` removes the fragments of experiment 7 and gives a
  sound network.
- **Result:** the agent finished in 17 steps with a `NetworkDraft` that passes: SCC ratio 0.975, all edges
  reachable from the fringe, 919 edges, 89.9 km. Four zero-length edges and four edges with no outgoing connection
  remain in `unresolved[]`. `submit_output` used **6,166 output tokens** of the 8192 allowed.
- **Maintainer's observation:** real roads of the WISTA science campus are missing from the network.

### 9. Where the roads went (no model, $0)

Rebuilt from the cached snapshot (`/tmp/adl/author/osm/`) with the options of experiment 8 added one at a time,
then compared by geometry (is there an edge within 15 m of the middle of each OSM way?). Ids cannot be used,
because `--geometry.remove` merges edges and keeps one id.

| Variant | Edges | km |
|---|---|---|
| Boundary only | 12,254 | 343.4 |
| Plus `--keep-edges.components 1` | 12,142 | 312.9 |
| Plus `--remove-edges.isolated` and `--junctions.join` | 10,086 | 310.5 |
| Plus `--keep-edges.by-vclass passenger` (experiment 8) | 919 | 89.9 |

- **Major roads are fine.** Of 673 OSM ways of type motorway to residential inside the network, 671 have an edge. The two
  lost are a motorway at the border and the `alte Altglienicker Brücke`.
- **`highway=service` is the loss.** SUMO's `osmNetconvert.typ.xml` (line 16) types it
  `allow="delivery pedestrian bicycle"`, without `passenger`, so `keep_vclass passenger` drops all of it. Of 181
  service ways that are not driveways, parking aisles, emergency access or private, **113 are lost**. The densest
  cells are streets of the WISTA campus (Boveristraße, Brook-Taylor-Straße, Rutherfordstraße, many without a name).
- **The model did nothing wrong.** It applied a correct filter on top of a typemap choice.

### 10. Keeping the service roads (no model, $0)

An overlay typemap added to `--type-files` (the later file wins), applied with the cleanups of experiment 8.

- **Overlay G1:** `highway.service` with `disallow` like `residential` (everything but rail and ships).
- **Overlay G2:** G1 plus `highway.service|service.driveway` and `highway.service|service.parking_aisle` with
  `disallow="all"`. The `|` key combination is the one SUMO's own `osmNetconvertRailUsage.typ.xml` uses.

| Variant | Edges | km | SCC | Zero-length | Dead-end edges | Public service ways lost |
|---|---|---|---|---|---|---|
| Current (experiment 8) | 919 | 89.9 | 0.975 | 4 | 4 | 113 of 181 |
| G1, all service roads | 3,638 | 152.0 | 0.987 | 16 | 5 | 1 |
| **G2, without driveways and aisles** | **1,698** | **121.8** | **0.989** | **6** | **5** | **13** |

- **Reading:** G2 recovers 100 of the 113 lost campus streets, keeps the sanity check passing and adds 32 km. G1
  recovers all of them but adds about 2,000 driveway edges that no study needs.
- **Dead ends:** the four of experiment 8 are one-way edges of Adlergestell, Glienicker Weg and Oberspreestraße that
  leave the polygon, so the cut at the boundary strands them. G2 adds one more, a one-way stub of Neltestraße.
  They are boundary effects, not roads lost in the middle of the cluster.
- **Not tried:** access tags (`access=private`), which SUMO reads by itself, and whether the 13 still-lost ways are
  real streets or noise.

### 11. The overlay shipped in the profiles (no model, $0)

- **Change:** `src/resto/application/typemaps/restoServiceRoads.typ.xml` is the overlay of experiment 10 (variant G2).
  `ImportProfile` has a new field `own_typemaps`, resolved against `OWN_TYPEMAPS` and placed after SUMO's, so
  it overrides them. The four profiles use it, because none of SUMO's other typemaps defines `highway.service`.
- **Check on the Adlershof snapshot** with the cleanups of experiment 8: `roads` 1,698 edges and 121.8 km, SCC
  0.989, 6 zero-length, reachable from the fringe. `rail` gives the same numbers (the passenger filter drops the
  rail), `bicycle` 1,701 and `pedestrian` 1,716.
- **Test:** `test_a_service_street_stays_for_cars_but_a_driveway_and_a_parking_aisle_do_not` on a committed
  fixture (`fixtures/campus.osm`); it fails without the overlay. Whole suite: 2,868 passed; `ruff` and `mypy` clean.
- **Effect on recipes:** `netconvert_options` of a new recipe lists a second `--type-files` path, the repo's own.
  Recipes stored before this change keep their old options and replay as they were.

### 12. Adlershof for private vehicles, with the overlay and 8192 output tokens ($0.0243)

- **Command:** `RESTO_LLM_MAX_OUTPUT_TOKENS=8192 python scripts/manual_network_author_run.py "El barrio de Adlershof en
  Berlín, pero quiero solo vehiculo privado" --work /tmp/adl --run --online --gui`. Prompt `v1`, 40 steps, 3 rounds.
  Worst case $0.257.
- **Result:** 11 steps, stop reason `output`, 157,586 input and 5,314 output tokens. `submit_output` used **3,586**
  output tokens, against 6,166 in experiment 8. The tool sequence was `find_network`, `list_import_profiles`,
  `fetch_osm`, `netconvert`, `sanity_check`, `keep_vclass`, `sanity_check`, `join_junctions`, `sanity_check`,
  `remove_isolated`. `inspect_network` and the first `submit_output` attempt hit `the 3 rounds are spent`, and the
  model then submitted with what it had.
- **Network:** SCC ratio 0.9888, all edges reachable from the fringe, 6 zero-length edges. These are the numbers of
  variant G2 in experiment 10, so the shipped overlay of experiment 11 works end to end with a real model.
  `NetworkPromoter` replayed the recipe and got the same hash (`c11e5666...`).
- **Honest draft:** `unresolved[]` has one entry, the 6 zero-length edges, and names `remove_zero_length_edges` as
  the missing tool (improvement 5). The rationale reads the cause slightly wrong. It says `join_junctions` left the
  6 edges, but they were already there before it ran.
- **Still open:** the boundary in `--keep-edges.in-geo-boundary` is still rounded to about 4 decimals (improvement
  10). The draft still carries the polygon twice, so improvement 3 would cut the answer further.
- **Reading:** this is a good level for E6.1. The request was understood (private vehicles, so `passenger`), the
  service roads of the campus are kept, the result is promotable and the one defect is declared. What is left
  belongs to E6.2 (the zero-length tool, assembling `recipe` in code).

### How the polygon reaches the recipe

The same boundary travels twice in the draft the model retypes. Once as `recipe.source`, a `Polygon` whose `ring` is
the list of about 130 `(lat, lon)` points of the administrative boundary. Once as the value of
`--keep-edges.in-geo-boundary` inside `netconvert_options`, the same points as `lon,lat` text rounded to six
significant digits (about 7 to 11 m). My estimate, not measured, is 3,000 to 3,500 tokens for both, about half of the
6,166 output tokens of experiment 8.

### Proposed improvements

| # | Change | Where | Why |
|---|---|---|---|
| 1 | Stop the loop after repeated `length` steps without a tool call | LLM client, E6.1 or an urgent fix | Burns the whole budget on a case with no way out |
| 2 | Raise the default `max_output_tokens` to 8192 | `docs/llm-cost-policy.md`, `config.py`, maintainer's decision | 2048 cannot hold a draft with a real polygon; the draft already takes 6,166 of 8192 |
| 3 | Assemble `recipe` and `net_artifact` in code; the model only writes `rationale` and `unresolved` | E6.2 | The model retypes the boundary twice, about half of its answer |
| 4 | Retries with growing waits on 502, 503, 504, 429 and catch the error in the script | `http.py`, script | The public Overpass service fails often |
| 5 | Tool to remove zero-length edges; check why the strongly-connected ratio was 0.55 with `rail` | E6.2 | The model named `remove_zero_length_edges` as the missing tool |
| 6 | Resolve vague or complicated places (stations, streets, several places in one request). **Points and single streets done by ticket 09** (`locate_place`, `select_streets`, ADR-0046) | E6.12 (M52) | The agent writes coordinates from memory when the place is not a boundary |
| 7 | Reject a `NeedsUser` of `NetworkNotFound` with a throwaway message after a network was built | E6.2 | Experiment 3 ended with `message='test'` |
| 8 | **Done (experiment 11).** Overlay typemap that lets passenger vehicles use `highway.service` except driveways and parking aisles, shipped with the repo and named in the four profiles | E6.1 (import profiles, ADR-0045) | Experiment 10: 100 of 113 lost campus streets come back and sanity still passes |
| 9 | Leave as is for now: one-way edges that leave the polygon are the dead ends the agent reports (maintainer, 2026-10-15: they have to continue beyond the cut; refine later) | E6.2 | Experiment 10 |
| 10 | Pass the boundary to `netconvert` with full precision, not `:g` | `osm_import.py` | Rounded to 7 to 11 m, it moves the cut at the border |

## 2026-10-19, the Diagonal with prompt `v2` (filter at download, never committed)

Request: the Avinguda Diagonal from Sant Just Desvern (near the Hospital Broggi) to Francesc Macià, main
carriageway and lateral lanes. Model `deepseek/deepseek-v4.1-flash`. Prompt `v2` was `v1` plus the `streets`
filter of `fetch_osm`, which ADR-0046 replaced; it never reached a commit. Numbers taken from ticket 09.

- **Without the filter ($0.011):** the network had the 6,621 edges of the box, SCC 0.909. The agent said in
  `unresolved[]` that it had no tool to cut by street.
- **With the filter on "Diagonal" ($0.007):** SCC 0.676. The ways that join the carriageways (`primary_link`, the
  squares Pius XII, Reina Maria Cristina and Francesc Macià) carry another name, so each large crossing split the
  road. Drivable "Avinguda Diagonal" ways start at lon 2.103; west of it the road is "Carretera de Collblanc",
  "Carrer de Laureà Miró" and "Carretera Reial" (`ref` N-340), so the network stopped short of Sant Just. The box
  was drawn from memory, its east edge at 2.152 when Francesc Macià is near 2.143. The snapshot of that run is in
  `~/resto-runs/adl-01/author/osm/`.

Prompt `v3` (ticket 09, ADR-0046) adds `locate_place`, `list_streets`, `select_streets` and `verify_coverage`. Its
first run on the same request is the manual acceptance check of ticket 09 and goes here when it is made.
