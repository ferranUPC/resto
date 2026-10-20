# Network Author tuning log

- Status: living document, started 2026-10-15
- Purpose: record each real run of the Network Author with the prompt version it used, its cost and
  the result, and every test made without a model along the way (checks on stored snapshots,
  experiments from a code review), with its numbers. Same role as the [Composer's log](composer-tuning-log.md).
- Related: E6.1 ticket 08 (`.scratch/e6-1-network-author-minimal/issues/08-real-path-golden-path-and-dev-run.md`).

Running total spent: **about $0.27** (first run $0.0048, the six costed runs of 2026-10-15 add $0.2128, experiment
12 adds $0.0243, the two Diagonal runs of 2026-10-19 add $0.018, the `v4` run of 2026-10-19 adds $0.0147; the run
that ended in a 502 printed no cost and is not counted).

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

Prompt `v3` (ticket 09, ADR-0046) adds `locate_place`, `list_streets`, `select_streets` and `verify_coverage`.

## 2026-10-19, the Diagonal with prompt `v3`

Same request, work directory `~/resto-runs/adl-01`. This entry was written after the fact, from ticket 10 and the
files the run left. The cost, the number of steps and the tool sequence were not noted at the time, so they are
missing here and the running total does not include this run.

- **Result:** the network ends at Zona Universitària (41.38194, 2.10305). The agent selected by name and put in
  `unresolved[]` that the stretch to Sant Just "does not exist in OSM".
- **Cause:** at Zona Universitària the Diagonal continues as the B-23. Six ways carry both `name=Avinguda Diagonal`
  and `ref=B-23` (372 m); the 31 ways of the B-23 beyond them have no name (8,516 m). Selecting
  `["Avinguda Diagonal"]` with `["B-23"]` and `links` on `osm-900faa27efcb7d01.osm` gives one piece of 18.7 km that
  reaches the Sant Just exit (41.3764, 2.07716).
- **Box:** south 41.377, so the hospital (41.37402) was outside it. A narrower download
  (`osm-8787bda10fe6452e.osm`) leaves the hospital by the N-340, not the B-23.
- **Files:** six snapshots and six selections between 13:09 and 13:56. The selections at 13:09, 13:49 and 13:55 hold
  the Diagonal with its laterals and the six Diagonal/B-23 ways in one piece. The one at 13:11 adds Carretera Reial
  (N-340) and Avinguda de Cornellà (C-245) and has 4 pieces.
- **Next:** ticket 10, below.

## 2026-10-19, `trace_corridor` on the snapshots of the Diagonal runs (no LLM)

Ticket 10 adds `trace_corridor` and prompt `v4`. The run of `v3` (`~/resto-runs/adl-01`) put in `unresolved[]` that
the Diagonal "does not exist in OSM" west of Zona Universitària. There the road continues as the B-23, whose ways carry
`ref=B-23` and no name, so a selection by name missed it. The check below calls the tool on the stored snapshots,
from the Hospital Broggi (41.37402, 2.07157) to Francesc Macià (41.3925, 2.1441), with no model.

- **`osm-900faa27efcb7d01.osm`, the `v3` run.** `OsmMap.trace` takes 0.3 s and suggests `names=["Avinguda
  Diagonal"]`, `refs=["B-23"]`, `connectors="links"`, with `joins_at` (41.3764, 2.07716), the B-23 exit for Sant
  Just. The road is 7,048 m long and takes 7.6 minutes: about 630 m of access streets from the hospital, a 416 m
  ramp, 1,812 m of B-23, 802 m of links to the lateral, then 3,389 m of Diagonal. The start is 8 m from the
  hospital and the end 1 m from the square.
- **The same snapshot through the tool, with the `v3` run's box (south 41.377).** The hospital lies outside the box,
  so the tool traces nothing. It answers `not_reached`, "outside the fetched area", and asks to fetch south 41.37123,
  west 2.0646, north 41.4, east 2.14782 (22 km², under the 25 km² limit). With a box that holds the hospital (south
  41.369) the answer is the one above.
- **The suggested selection built.** `select_streets` with that selection gives 3 pieces (the largest 18.7 km, from
  Macià to past Sant Just). `netconvert` keeps one component that reaches Macià (10 m to its nearest end). Its
  nearest junction is 321 m from the hospital (`verify_coverage` measures to junctions). The network still runs west
  to lon 2.0576, past the hospital. Cutting the recipe to the corridor needs an ADR and is out of scope.
- **`osm-8787bda10fe6452e.osm`, the narrow download.** `OsmMap.trace` alone puts the start on a road 316 m from the
  hospital and takes the N-340 (Carretera Reial, Carrer de Laureà Miró), as the ticket expected. The box of that
  download is not stored with it. Ticket 10 reports that it left the hospital out, and with such a box the tool
  answers `not_reached` before tracing, so the agent fetches again instead of selecting the N-340.
- **The narrow download's suggestion built.** On `osm-8787bda10fe6452e.osm` the trace suggests `names=["Avinguda
  Diagonal", "Carretera Reial"]`, `refs=["N-340"]`. `select` with it and `links` gives 5 pieces. The largest (10.2 km)
  ends at Zona Universitària, 2,770 m from the hospital. The trace goes through an unnamed `trunk_link` of 764 m,
  longer than the 300 m a connector may be (`MAX_CONNECTOR_M`), so the selection does not join there. Open point:
  a trace through a long unnamed link gives a selection that the link does not join.

### The box `not_reached` asks for (code review of ticket 10, no model, $0)

- **Hypothesis (spec reviewer):** the box held each point with exactly 300 m around it. Rounding its edges to 5
  decimals can move an edge about half a metre toward the point, and the tool rejects a point less than 300 m from the
  edge. So the box it proposes could fail its own check, and the agent would fetch the same box again and again.
- **Test:** 2,000 random points between lat 41.370 and 41.380 and lon 2.07 and 2.14, near the south edge of the `v3`
  box (south 41.377), each paired with Francesc Macià. For each pair, the proposed box was built and the check run on
  it again.
- **Result before the fix:** 989 of the 2,000 proposed boxes failed their own check (the reviewer got 973 on its own
  sample). The real hospital passed only because it was 300.23 m inside the box.
- **Fix (commit `00f2baf`):** the box holds the points with 310 m around them. On the same 2,000 points, none fail.
  The test `test_the_box_a_point_outside_asks_for_holds_it_once_fetched` fetches the proposed box and traces again.
- **Effect on the real case:** the box for the hospital is now south 41.37123, east 2.14782 (22 km²).

The run of `v4` with the model is the maintainer's, with a budget announced first (`docs/llm-cost-policy.md`).

## 2026-10-19, the Diagonal with prompt `v4`

Same request as `v2` and `v3`, plus "the entrances and exits of Sant Just Desvern to that part of the Diagonal".
Work directory `~/resto-runs/adl-01`, `RESTO_LLM_MAX_OUTPUT_TOKENS=8192`, 3 rounds, `--online --gui`.

- **Cost:** $0.0147, 14 steps, 230,531 input and 14,560 output tokens. Stop `output`.
- **Tools:** `find_network`, two `locate_place`, `fetch_osm` (`osm-b26b4bfed6818bbd.osm`, box south 41.3695, west
  2.0656, north 41.397, east 2.1508), `trace_corridor`, two `list_streets`, `select_streets`, `netconvert`,
  `verify_coverage`, `sanity_check`, `inspect_network`, `join_junctions`, `sanity_check`, a second `select_streets`
  with `all`, `netconvert`, `sanity_check`, `verify_coverage` (refused: the 3 rounds were spent), `submit_output`.
- **Result:** one component from Francesc Macià to the B-23 west of Sant Just, 331 edges, largest SCC 0.777 (below
  0.95). `join_junctions` lowered it to 0.67. The draft has three `unresolved[]`: the SCC, 636 m of Diagonal east of
  Macià, and the 30 m of Carrer de Calvet.
- **What the user saw:** none of the Sant Just entrances and exits are in the network.
- **Selections:** `selected-959e77b57caa6465.osm` (187 ways) holds the Diagonal, both laterals, the B-23 (`ref`) and
  the links between them. `selected-4d3495a165d24510.osm` (200 ways) adds the streets around Macià that `all` joins.
  Neither holds a way that leaves the corridor toward Sant Just.
- **Cause (no model, on the stored snapshot):** the Sant Just interchange is four unnamed `motorway_link` ways on the
  B-23 between lon 2.067 and 2.077 (`28117160`, `28117165`, `28117172`, `28117177`; 146 m to 483 m). Followed through
  other unnamed ways they make 2,223 m of `motorway_link` and 299 m of unnamed `primary`, and reach Avinguda Ricardo
  Bofill i Levy and Avinguda del Baix Llobregat. `select_streets` cannot reach them: a way with no name and no ref
  matches no `names` or `refs`, and a connector must join two pieces of the selection within 300 m, while a ramp
  leaves the selection and ends on a street that is not in it. `verify_coverage` compares the network with the
  selected snapshot, not with the downloaded one, so it reports nothing missing. The agent wrote "the B-23 Sant Just
  Desvern accesses" in its rationale, but it selected only the B-23 itself.
- **Do the ramps lower the SCC ratio? (no model, same snapshot):** no, they close loops. Following the ways'
  direction through the unnamed ways only, the exit `28117160` leads back to the entry `28117165`, and the exit
  `28117172` to the entry `28117177`, without using the B-23. Once selected, the four ramps fall in the largest SCC.
  Only the first stretch of a named street the ramps lead to, cut where the selection ends, stays out of it.
- **Does the trace find the accesses? (no model, same snapshot, `prefer=["B-23", "Avinguda Diagonal"]`):** yes, but
  the selection it suggests loses them. B-23 point used: (41.37976, 2.085).
  - B-23 to Sant Just (geocoded centre): 2,784 m, takes the 434 m `motorway_link` at 2.07707, then Ricardo Bofill,
    Carretera Reial and the Rambla de Sant Just. Suggested: `names=["Rambla de Sant Just", "Carretera Reial"]`,
    `refs=["B-23"]`. The ramp has no name and no ref, so the suggestion drops it.
  - B-23 to the Broggi: 1,641 m, the 354 m ramp and 99 m of unnamed `primary`. Suggested: only `refs=["B-23"]`.
  - Broggi to the B-23: 4,065 m. It enters by the 416 m ramp, leaves at 2.0919 and enters again at 2.097, because
    the point snapped to the westbound carriageway. Suggested: only `refs=["B-23"]`.
  - Sant Just to the B-23: 4,184 m by the N-340 and the C-245 to the Esplugues entrance. Suggested: four names
    (all of Carretera Reial and Laureà Miró, not only the traced stretch) and three refs.
  - Same gap as the open point of ticket 10 (the 764 m `trunk_link`): the trace knows the ways it drives, the
    selection only names and refs.
- **A box around the interchange, pruned (no model, same snapshot, same `netconvert` options as the run):** the
  maintainer's idea. Keep the corridor selection (`selected-4d3495a165d24510.osm`) and add every road of a box around
  the two B-23 roundabouts (41.3755, 2.0731 and 41.3768, 2.0726): south 41.3735, west 2.0655, north 41.38, east
  2.08. A way counts as inside when one of its nodes is, and it is kept whole (not cut at the box).
  - Corridor only: 442 edges, SCC 0.785, none of the four ramps.
  - Plus every road in the box: +250 ways, 936 edges, SCC 0.771, all four ramps. Most of what it adds is
    residential streets of Sant Just and 37 unnamed `service` ways.
  - Plus the box without `residential`, `service`, `living_street` and `unclassified`: +99 ways, 589 edges, SCC
    0.847, all four ramps. Left to prune: Carretera Reial whole (40 ways, because ways are not cut at the box),
    Rambla de Modolell, Carrer Major.
- **Next:** a way to select the ramps that leave the selection near a point, up to the first named road. To be
  decided. Options under discussion instead: `select_streets` keeps the ways of a trace; or a box kept whole and
  pruned.

## 2026-10-19, zone and pruning in `select_streets` (ticket 11, no model, $0)

Same snapshot as the `v4` run (`osm-b26b4bfed6818bbd.osm`, box south 41.3695, west 2.0656, north 41.397, east 2.1508).
`names=["Avinguda Diagonal"]`, `refs=["B-23"]`, `connectors="all"` gives the 200 ways of `selected-4d3495a165d24510.osm`,
so that is the selection of the run. Built with the default `netconvert` options through the tools. The zone is a
circle, not the box of the earlier test: centre (41.37675, 2.07275), 650 m, which holds the box (361 m by 600 m
half-sides). The pruning is `residential`, `service`, `living_street` and `unclassified` in that zone.

| Selection | Ways | Edges | SCC | Ramps | Pieces |
|---|---|---|---|---|---|
| Corridor only | 200 | 439 | 0.777 | 0 of 4 | 1 |
| + zone | 527 | 1,039 | 0.752 | 4 of 4 | 3 |
| + zone, pruned | 313 | 601 | 0.810 | 4 of 4 | 2 |

- The zone adds 327 ways (25,358 m). The pruning removes 214 of them (17,264 m).
- Carretera Reial: 34 of its 56 ways stay, 3 of them cut at the edge of the zone, 2,024 m of 2,631 m. In the earlier box
  test it entered whole (40 ways).
- 9 ways of the 313 are cut at the edge of the zone. Each is an edge that enters or leaves and does not come back,
  which is why the SCC stays under 0.95 (an open question of ADR-0047).
- The pruned selection builds one component (the pieces count ignores direction and finds 2, so a stretch of the zone
  joins through a one-way link only).

## 2026-10-19, the Diagonal with prompt `v5` (zones and drop available, first run with a transcript)

Same request as `v4`. Work directory `~/resto-runs/adl-01`, `RESTO_LLM_MAX_OUTPUT_TOKENS=12500`, 3 rounds, `--online --gui`.
Tool schemas inlined (no `$defs`) and `transcript.json` saved by the script.

- **Cost:** $0.0284, 17 steps, 363,772 input and 29,711 output tokens. Stop `output`.
- **Tools:** `find_network`, `list_import_profiles`, three `locate_place`, `fetch_osm` (box south 41.369, west 2.065,
  north 41.397, east 2.151), `trace_corridor`, three `list_streets`, two `select_streets`, `netconvert`, `sanity_check`,
  `verify_coverage`, `inspect_network`, `join_junctions`, `sanity_check`, `remove_isolated`, four `inspect_edge`,
  `netconvert`, `sanity_check`, `verify_coverage` (refused: the 3 rounds were spent), `submit_output`.
- **Result:** one component, 441 edges, 22,956 m, largest SCC 0.736 (below 0.95). Sant Just Desvern's centre is 1,039 m
  from the network and the hospital 321 m. No ramp of the Sant Just link in it.
- **`areas` never used.** The two `select_streets` calls are by name and ref (`Avinguda Diagonal` with its two lateral
  lanes, `B-23`), one with `links` and `drop` of footways, paths and the like, one with `all`. The `drop` call was
  well formed, so the nested schema is understood.
- **Why, from the transcript:**
  - The agent lists near Sant Just's centre (41.3858, 2.0758, 500 m), 1.2 km from the link (41.374, 2.0716).
  - Every `list_streets` call opens with `footway` 104,644 m and `service` 45,544 m: unnamed rows group by class over
    the whole snapshot, with or without `near`.
  - It writes that a new selection "was no longer available" for lack of rounds, but a selection costs none
    (ADR-0046 §7); the rounds went on `join_junctions`, `remove_isolated` and `netconvert`.
  - Its last `unresolved[]` asks for `select_streets` "with the Sant Just Desvern street grid as area": it wants a zone
    and does not see `areas` as the way to ask for it.
- **Next:** ticket 12 (`list_streets` near counts only what is inside, `trace_corridor` suggests zones for unnamed
  roads of the main hierarchy, prompt `v6`).

## 2026-10-19, reaching the zone (ticket 12, no model, $0)

Prompt `v6`; `list_streets` near counts the stretch inside the radius; `trace_corridor` suggests `areas`. Checked on
`osm-b26b4bfed6818bbd.osm` (the `v4` and `v5` snapshot).

- **`trace_corridor` from the B-23 (41.37666, 2.0782) to Sant Just (41.3858, 2.0758).** The route takes 95 m of
  motorway, the 434 m `motorway_link`, 126 m of unnamed `primary`, a 65 m `primary_link` and then named streets. The
  suggestion has one zone, centre (41.37703, 2.07478), 248 m, that holds the ramp and the unnamed `primary` after it.
  `select_streets` with the suggestion as given keeps 9 `motorway_link` ways (24 to 288 m each).
- **From the Broggi (41.37402, 2.07157) to Sant Just's centre.** Three zones (85, 72 and 69 m): the unnamed
  stretch at the hospital and the two roundabouts of the junction. Their selection has 6 pieces; the ramps are in it,
  the pieces are for the agent to read in `largest_pieces`.
- **`list_streets` near the hospital (41.374, 2.0716, 500 m).** 45 streets. The unnamed rows are now `footway` 4,609 m,
  `service` 2,463 m and `motorway_link` 2,088 m, the length inside the circle; before they were 104,644 m and 45,544 m
  for the whole snapshot. The B-23 shows 1,560 m.
- **Open:** the first run of `v6` is the maintainer's. When it is done, note here which `select_streets` calls
  it made with `areas` and `drop`, and whether it passed the suggested `areas` as they came.

## 2026-10-20, the Diagonal with prompt `v6` (first run that reaches the zone)

Same request as `v4` and `v5`. `~/resto-runs/adl-01`, `RESTO_LLM_MAX_OUTPUT_TOKENS=12500`, 3 rounds, `--online --gui`. The
first attempt failed before any model cost: Overpass answered 502.

- **Cost:** about $0.055 (estimated: the script's output was lost; 701,176 input and 59,876 output tokens, scaled
  from the `v5` run's price). 23 steps, 39 tool calls.
- **Result:** one network, largest SCC 0.714 (below 0.95), `verify_coverage` never run (the 3 rounds were spent). The
  selection has 245 ways in 3 pieces (23,611 m, 82 m and 11 m).
- **`areas` used from the first selection.** `trace_corridor` suggested `names=["Avinguda Diagonal (lateral mar)",
  "Avinguda Diagonal"]`, `refs=["B-23"]` and two zones: 303 m at (41.37462, 2.07527), around the Sant Just link, and
  333 m at (41.3813, 2.09977), around the 567 m unnamed `trunk_link`. The agent passed them as they came in the first
  `select_streets`. From call 16 it added its own circle (500 m at the hospital, 41.374, 2.0716) and in call 32, the
  network it submitted, it kept only that circle with `drop` of `residential` and `service`. The transcript has no
  text between calls and keeps 500 characters of each result, so the reason is not there.
- **What is wrong in the network (maintainer's screenshots, checked on `selected-7df8481019f22605.osm`):**
  - The Sant Just exit from the B-23 is cut. The `motorway_link` ways 28117160 and 28117177 end at 422 and 488 m from
    the circle's centre, and the rest of the ramp up to the B-23 (about 550 m) is outside. `_connectors` skips ways
    already in the selection, so the missing stretch is never added.
  - The roundabout east of the hospital is an arc. Its ways at 552 to 589 m from the centre are not kept, those below
    500 m are. 5 ways of the selection are cut by the circle's edge.
  - The B-23 exit towards Mataró that rejoins the lateral lane is in the network. Not a defect; leaving it out would
    ask for more selection rules.
- **`unresolved[]`:** asks for `prune_edges_without_outgoing_connection` and `remove_disconnected_pieces_after_selection`,
  and reports the SCC. Honest, and the cause is not a missing prune tool but the cut ramp.
- **Next:** ticket 13 (a zone keeps whole the roundabouts and ramps it touches; prompt `v7` says not to replace the
  suggested `areas` with a circle of its own).
