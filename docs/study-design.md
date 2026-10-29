# Study design

**Status:** accepted by the maintainer, 2026-10-28. The experiment design (section 9) still waits for the
approval of the three supervisors.

This document is the source of truth of the TFM from the plan v1.0 commit on. It replaces the architecture
document, which moves to `docs/_old/`. `docs/tfm-work-plan.md` v1.0 schedules the work this document
describes; where the two disagree, this document wins and the plan is corrected.

Values that are not fixed yet appear as `[OPEN: <name>]`. Each one is listed in
[Open values](#open-values) with the plan task that fixes it. Nobody guesses them in the meantime.

## 1. Question

### Main question

Starting from the same polygon and the same sources, does the fidelity to reality of a SUMO network
increase when an LLM takes part in generating it, compared with the best deterministic pipeline? By how
much, in which aspects and at what cost?

Fidelity to reality is the distance from a network to the golden network of its area, measured aspect by
aspect. The metric exists because the main question needs it, and the thesis presents it that way.

### Sub-questions

They may change during development and are fixed when the experiment design is approved (section 9).

- **SQ0, deterministic ceiling.** What fidelity does the best deterministic pipeline reach? B0 gives
  context; B1 is the reference every hypothesis is stated against (section 5).
- **SQ1, metric.** How is the fidelity of a SUMO network to a golden network measured per aspect when ids
  differ, and does the metric respond to the errors it must detect? Answered by the metric (section 7) and
  its validation by error injection (section 8).
- **SQ2, reasoning.** With the same data as B1, does fidelity rise when the LLM takes part, and how does it
  change with the starting point and the model?
- **SQ3, data.** Do extra sources (street evidence, official layers) raise fidelity, and how much of the
  gain comes from the data and how much from the reasoning?
- **SQ4, cost.** What does each arm cost (USD, tokens, run time), and what is its cost per point of network
  fidelity gained over B1?

### What counts as a result

"The LLM does not help" is a valid result: the contribution is the measurement. Every aspect and every arm
is reported in the same tables, including those that do not win. A low score on a sound test set is a
result and is reported as one.

## 2. Terms

These terms go into the new glossary. The v0.4 `GLOSSARY.md` uses "arm" and "golden" in another sense.

| Term | Meaning |
|---|---|
| Fidelity to reality | How close a network is to the golden network of its area, per aspect |
| Golden network | The corrected network of an area, as it is on the day it is corrected. No agent sees it |
| Conventions | The written modelling rules every golden follows and every arm is told |
| B0, B1, B1w | `netconvert` defaults on OSM; DLR's pipeline (the reference); B1 plus official layers (conditional) |
| Aspect | One part of a network the metric scores on its own, from 0 to 1 |
| Network fidelity | The weighted sum of the twelve aspect scores of a network against its golden network |
| Matching | The geometric correspondence between a candidate and its golden, computed once and shared by every aspect |
| Error list | The per-run file of every discrepancy the metric finds |
| Split junction, over-joined junction | One real junction imported as several SUMO junctions; several real junctions imported as one |
| δ_Y | The minimum improvement on aspect Y that counts, fixed before the test run. Twelve values, one per aspect |
| δ_NF | The minimum improvement on network fidelity that counts. One value, fixed with the δ_Y |
| Development, validation, test set | Section 3 |
| Metric validation network | An uncorrected OSM import used only to inject errors into, to validate and tune the metric. Not a golden, in no set. Always written in full |
| Error injection | Changing a network on purpose with errors of known type, number and position |
| Neutral perturbation | A change that does not alter a network's meaning (ids, intermediate nodes, small shifts) |
| Arm | One combination of starting point, street evidence and official layers, run with one model |
| Starting point | What the agent starts from: from zero, from zero with DLR's pipeline available, or repair B1 |
| Street evidence | Orthophotos, Mapillary pictures and Mapillary's detected objects, asked for small areas in conflict |
| Official layers | A region's official vector road data (signals, direction, lanes, speed, markings) |
| Snapshot | The local copy of every input for a polygon, taken on one date; tools read only it |
| Stage 1, stage 2 | Selection of the starting point without extra data; then of the data on the best starting point |
| Best starting point, best data arm | The winner of stage 1; the winner of stage 2. Both reach the test |
| Winning arm | Whichever of the best starting point and the best data arm scores higher on development and validation. It carries the main hypothesis |
| Experiment design | The approved part of this document that fixes arms, models, sources, hypotheses, δ and weights |

## 3. Networks

### Types

- **Interurban trunk road.** Motorway or autovía stretches count.
- **Small urban network.** About one Berlin Ortsteil.
- **Large urban network.** Bezirk scale. It must contain a station with tracks.

There are no size limits for now. Each test network is reported on its own.

### Sets

Twelve golden networks. No polygon overlaps another.

| Type | Development (2 per type) | Validation (1 per type) | Test (1 per type) |
|---|---|---|---|
| Interurban | B-23, from Francesc Macià to the Sant Just Desvern roundabout; `[OPEN: areas]` | another stretch, `[OPEN: areas]` | A-2, km 15 to 25, both carriageways and service roads |
| Small urban | Adlershof; Johannisthal | `[OPEN: areas]` | one area in Berlin or Barcelona, `[OPEN: areas]` |
| Large urban | `[OPEN: areas]` (two) | `[OPEN: areas]` | one Berlin Bezirk other than Treptow-Köpenick, with a station with tracks, `[OPEN: areas]` |

- **Development.** The Network Author is improved here and results are analysed in full.
- **Validation.** Run as often as wanted. Only the number is looked at, never why. It warns early if the
  agent does not generalise.
- **Test.** Runs once, at the end, with the approved experiment design. Results on development and
  validation are exploratory and never confirm or reject a hypothesis.

The B-23 stretch, Adlershof and Johannisthal stay in development because the agent has already seen them.

Region is not a criterion. Validation is "same type, another area", in any region; the tool is meant to
generalise. Each network records its region and which extra sources exist there (section 13).

The whole of Berlin is not a test network: every Berlin development and validation area lies inside it.
If it runs at all, it is an exploratory scale run outside the sets and the hypotheses, and dropping it
changes no hypothesis. `[OPEN: whole-Berlin run]`.

A network DLR has already corrected goes to test if it fits a type, otherwise to development. That it was
not picked blind is written as a limitation. The plan assumes none exists until DLR's lead engineer says so.

### Fixing the sets

The maintainer picks the remaining areas by eye. Before any area is imported, this document records for
each area its set, its polygon, one sentence of why, and the request a user would type for that network in
natural language (for example "the A-2 between km 15 and 25, both carriageways, with service roads"). The
commit that adds them fixes the sets. The request line lets the conditional natural-language epic use the
test areas without anyone looking at them again.

| Area | Type | Set | Region | Polygon | Why | Request |
|---|---|---|---|---|---|---|
| `[OPEN: areas]` | | | | | | |

### Metric validation network

One more area, outside the sets: an OSM import of a Berlin area where all twelve aspects appear, not
corrected (section 8). Its polygon is fixed here together with the sets and overlaps none of the 12 areas.
`[OPEN: metric validation network polygon]`.

### Snapshots

Every arm and every reference reads the same local snapshot of its polygon: OSM extract, official layers,
orthophotos and Mapillary data, downloaded on one day. Tools read only that copy; no run goes to the
internet.

| Snapshot | Taken | Used by | Date and hash |
|---|---|---|---|
| Development and validation | the day golden work on those sets starts | every reported run on those sets; development may download again while building tools | `[OPEN: snapshot dev+val]` |
| Test | after the Network Author freeze, just before the test goldens are corrected | the test goldens and the test run | `[OPEN: snapshot test]` |

## 4. Golden networks

### What a golden is

The clean, corrected network of an area, as it should be for simulation, on the day it is corrected.
Outdated networks are corrected to that day. Golden networks come from DLR engineers or are corrected by
hand, without agents. No agent ever sees one; an algorithm compares.

No golden is corrected, and no convention tried on one, until the sets are fixed.

### Conventions

There is no step-by-step protocol. The corrector looks at the network and at the sources and does the best
they can. What makes the result defensible is a one-page conventions document, a log per golden and a
second review.

The maintainer writes the conventions, shows them to DLR's engineers ("does this match how you correct a
network?") and the agent reviews them. Settled content so far:

- **Scope.** Roads for motor vehicles (cars, motorbikes), from residential upwards, plus connecting service
  roads. No parking aisles, tracks or private roads; no separate cycle or foot paths. Rail is included and
  scored apart (aspect 10); tram counts as rail. Sidewalks (aspect 9) and bus and bicycle lanes inside a road
  (aspect 4) stay.
- **Junction joining.** A real junction may be held as one SUMO junction (`<join>`, `--junctions.join`) or as
  several nodes under one traffic-light program (same `tl`, `--tls.join`). Which form the goldens use, and
  whether aspect 12 treats both as equal, is `[OPEN: junction joining form]`.
- The same conventions go into the task description every arm receives.

The document carries a version and a date and freezes together with `METRIC_VERSION`, before the first
agent measurement. A later change means re-checking the affected goldens and measuring again.
`[OPEN: conventions version]`.

### Starting point and sources

The starting network is free. Each golden records its origin when known: B1 on the OSM import, B0, "DLR",
or "unknown" for networks sent by engineers. B1 applied to the OSM import is the first result whatever the
origin.

The corrector works as DLR's engineers do today: the import in netedit on one screen, Google Maps and Street
View on the other, local knowledge, and a site visit where imagery is not enough. No arm can use Google
(section 13), so the golden holds information no arm has. The thesis's method section says how the goldens
were made: corrected by hand by an engineer, against street-level imagery and local knowledge, following the
conventions.

DLR-corrected networks (for example `sumo-berlin/Doerpfeldstr/Doerpfeldstr_edit.net.xml.gz`, in Adlershof)
are reviewed against the conventions, fixed where they deviate, and logged with origin "DLR".

### Storage and log

- A `golden/` folder in the repo, untracked (never committed), named in `CLAUDE.md`. A `deny` read rule in
  `.claude/settings.json` covers the validation and test goldens; development goldens stay readable.
- Format: the `.net.xml` as netedit saves it, SUMO 1.27.1. The maintainer keeps a backup outside the repo.
- Each golden's `content_hash` is written below, and every result cites the hash it was measured against.
- Log per golden: origin and hash of the starting network, conventions version, corrector, sources used,
  reference date, and a short list of doubtful decisions with the source that settled them.

| Area | Origin | Corrector | Reference date | `content_hash` |
|---|---|---|---|---|
| `[OPEN: golden hashes]` | | | | |

The large urban golden: cut from a DLR network or corrected by hand, and how big it can be if corrected by
hand, is `[OPEN: large urban golden]`.

### Second review

A second person checks that each golden is well built and matches the task description and what they see on
the map and in street-level imagery. Every test golden gets it before the test run. There is no inter-rater
measurement.

### Publication

Golden networks are not published for now; the maintainer decides after the thesis. They are ODbL
derivatives of OSM corrected with Street View, which Google's terms forbid. Results measured against them,
the metric code and the conventions are published.

## 5. References

- **B0.** `netconvert` with default options on the OSM snapshot. Context only.
- **B1.** The street part of `netpatch/berlin.netccfg` from DLR's `sumo-berlin`
  (https://github.com/DLR-TS/sumo-berlin, EPL-2.0), pinned to a commit, applied with the same configuration in
  Berlin, Barcelona and Madrid, on the same polygon snapshot as the arms. `sumo-berlin`'s manual patches are
  commented out, so DLR's published Berlin network is B1 output, not a golden. B1 uses neither official
  layers nor images. Automatic steps DLR's lead engineer names join B1; manual netedit steps do not. No
  clean-up heuristics invented by the maintainer are added. `[OPEN: B1 confirmation]`.
- **B1w** (conditional). B1 plus the official layers matched to its edges. Built only if the official-layer
  tool has to return matched data (section 6); then it is an extra reference.

B1 is deterministic: it has one value per network and costs no LLM call.

## 6. Arms

### Factors

An arm is one combination of three factors. The model is a fourth factor (section 11).

| Factor | Levels |
|---|---|
| Starting point | (1) **From zero.** Base tools only; the prompt never mentions DLR. (2) **From zero, DLR pipeline available.** A tool runs DLR's pipeline; its description summarises the options of `berlin.netccfg` and says the output is DLR's reference network; the agent decides whether to use it. (3) **Repair B1.** The run starts with B1 built and the agent is told so. It has no tool to fetch OSM or rebuild and, by construction, does not know it could discard the network |
| Street evidence | No or yes. Yes is one tool: for a small area where it has a conflict, the agent chooses the region's official orthophoto or a Mapillary street picture, or first asks Mapillary's detected objects near a point (traffic lights, arrows, stop lines, signs). Each call states its approximate cost |
| Official layers | No or yes. Yes is one abstract tool over the region's official vector data, whatever the transport (WFS or download), with one integration per region behind it. It answers a layer over a small box with a few features and their coordinates, no matching. If in development the agent cannot relate them to its edges, the tool returns matched data (the metric's matching) and B1w is built |

The three factors make a grid of 3 × 2 × 2 = 12 arms. Layer content differs by region, so this factor is
read per region. No arm is "not applicable" on any network; each network records which layers and which
Mapillary coverage it has. `[OPEN: sources per network]`.

### Selection in two stages

The full grid does not run. Six arms run on development and validation, in two stages that add up instead
of multiplying:

1. **Stage 1, starting point.** The three starting points run without street evidence or official layers.
   The best is the best starting point.
2. **Stage 2, data.** On the best starting point, three arms: with street evidence, with official layers,
   with both. The best is the best data arm.
3. **Test.** B1, the best starting point and the best data arm.

The winning arm is whichever of the two test arms scores higher on development and validation, fixed in the
experiment design before the test. If no data arm beats the best starting point, the winning arm runs
without extra data. The winning arm against B1 answers the main question. The best starting point against
B1 answers SQ2. The best data arm against the best starting point answers SQ3, whichever wins. The selection criterion of each stage (network
fidelity on development and validation) is fixed before stage 1 starts. `[OPEN: stage selection criterion]`.

Data and reasoning are told apart through these twin pairs and through the per-aspect report. The extra
data is a product of this project on top of B1, and a gain on an aspect a layer gives almost directly (speed
from Berlin's `tempolimits`) is reported as data.

### Prompt and tools

- One common base prompt. Each tool adds its own description; starting point 3 adds context on where it
  starts. Each configuration is a distinct agent.
- In development the prompt may get general hints for general failures, never named areas or cases.
- The input is the area's polygon, the same as its golden's, plus the area's name. The agent does not search
  or geocode. Its output is always one network.
- Edit tools start as today's (`add_edge`, `remove_edge`, `set_lanes`, `set_speed`, `join_junctions`,
  `keep_largest_component`, `keep_vclass`, `remove_isolated`). The improvement loop (section 10) completes
  them. A new edit tool reaches every arm at once. Data tools (street evidence, official layers, DLR's
  pipeline) stay where their factor puts them.

### What the agent never sees

The golden, the score, the error list, other runs' outputs (each run starts clean), and any area-specific
hint in the prompt.

### Budget, stopping and failures

- Every turn the agent sees its remaining steps and USD.
- A run stops when the agent delivers its network or at a cap: 40 steps or $0.5 for now (section 11). At the
  cap the last network built is scored and the run is flagged.
- No network is a failure: 0 on every aspect, documented as an error. The failure rate per arm is published.

## 7. The metric

### Aspects

Twelve aspects, each scored from 0 to 1, where 1 is identical to the golden. "Does it exist" aspects use F1:
precision is the share of the candidate's elements found in the golden, recall the share of the golden's
elements found in the candidate. Attribute aspects use the share of correct values over matched elements.
Road attributes count by km, so a 20 m stretch weighs less than a 500 m one; junction aspects count by unit.

| # | Aspect | What is compared | Score |
|---|---|---|---|
| 1 | Graph structure | junctions (3 or more roads), dead ends and the edges between them | mean of node F1 (by unit) and edge F1 (by km) |
| 2 | Driving direction | directions present on each matched edge, roundabout edges excluded | share of km correct |
| 3 | Lanes | number of motor-vehicle lanes per direction, bus lanes included, bicycle lanes and sidewalks excluded | share of km with the exact number |
| 4 | Lane permissions | the special lanes each edge has (bus, bicycle) | share of km with the same special lanes |
| 5 | Lane-to-lane connections | pairs entry lane to exit lane through each matched junction, only on edge pairs whose lane counts match | F1 |
| 6 | Junction type | SUMO type of each matched junction, only where neither network has a traffic light | share of junctions correct |
| 7 | Roundabouts | a golden roundabout is correct when the candidate has it as a closed ring, driven in the right direction (anticlockwise in Germany and Spain), marked as a roundabout in SUMO, with the same number of entries and exits | F1 |
| 8 | Traffic lights | presence at matched junctions, and which connections each one controls | mean of presence F1 and controlled-connection F1 |
| 9 | Sidewalks | sidewalk on each side of each matched edge | share of km per side correct |
| 10 | Rail | as aspect 1, restricted to rail tracks (tram included) | as aspect 1 |
| 11 | Speed limit | maximum speed of each matched edge | share of km with the exact value |
| 12 | Junction joining | whether each real junction is exactly one SUMO junction, both directions (split and over-joined) | F1 by unit; result tables give both counts |

- **Graph structure.** Only junctions and dead ends are nodes. Intermediate nodes (where the lane count
  changes, for example) count neither for nor against.
- **Junction joining.** Aspect 1 asks whether the junction is there: a group of candidate nodes matched to
  one golden junction is one hit. Aspect 12 asks whether it is one junction: a golden junction is a hit only
  if it maps to exactly one candidate node, and the other way round. Without aspect 12 a split junction would
  score almost nothing, because the matching groups the two nodes and the phantom edge is millimetres long.
- **Out of the metric.** Traffic-light programs (phases, durations), unless DLR holds real signal plans.
  Pedestrian crossings. Behavioural checks (teleports, travel times), since demand is out of scope.

The definitions of aspects 2, 3, 5 and 6 above already carry the changes validation required so that each
error lowers one aspect only (section 8). The matching prototype and the validation may still change
details, always before the freeze.

### Rules

- **Each error counts in one aspect only.** Attribute aspects are measured on matched elements only. A road
  the candidate leaves out counts against graph structure and nowhere else.
- **Aspects a network does not have.** If neither the golden nor the candidate has the aspect (no rail, no
  roundabouts), it is not scored on that network and the other weights are rescaled to add up to 1. If only
  the candidate has it (an invented roundabout), it scores 0.
- **Border.** Elements in a band along the polygon's border are ignored by every aspect, because the cut
  leaves dead ends and stray junctions in both networks.

### Matching

- Geometry only. Edges match by common length and angle; junctions match through their matched incident
  edges, so a group of nodes in one network can map to one junction in the other. OSM ids are never used: the
  golden is corrected by hand, and an id hint would reward a candidate that attaches the right OSM way to the
  wrong geometry.
- One matching per comparison, shared by every aspect.
- Starting point: SUMO's `remap_network.py`, with one-to-one assignment instead of its greedy one, and the
  1:n matching literature (Mustière and Devogele 2008).
- The matching is the highest risk of the metric. The metric epic starts with a matching prototype on two
  development networks, one simple and one complex, shown as a sumo-gui overlay (green matched, red only in
  the golden, blue only in the candidate). If it does not convince the maintainer, the epic is replanned
  before any aspect is built on it.

### Network fidelity

Network fidelity is the weighted sum of the twelve aspect scores. It is what the thesis calls "the metric".

The weights come from a ranking: DLR engineers who use the networks rank the twelve aspects by importance
for simulation, and the weights follow from the ranking. They are fixed in the experiment design next to
the δ values and approved by the same three supervisors. The final result is also published with equal
weights (1/12); if the conclusion changes with the weights, the thesis says so. `[OPEN: aspect weights]`.

Weights as estimated correction minutes per error type were rejected: who decides the minutes per edit is
no firmer than a weight.

### Output

- Twelve aspect scores and network fidelity per run, each stored with the golden version and the
  `METRIC_VERSION` it was computed with.
- An error list per run: aspect, position, expected value, found value (for example "lanes, Frankfurter Tor
  eastbound: golden 3, candidate 2"), exportable as a sumo-gui or netedit selection. A flag turns it off to
  run faster; scores are identical either way. On the validation set the list is written but nobody opens it.

### Parameters and freeze

Match radius, angle tolerance, border width and any other parameter are tuned only on the metric validation
network, the golden networks, error injection and the B0 and B1 outputs, never on agent outputs. They are
frozen as `METRIC_VERSION` before the first measurement of the agent. `[OPEN: metric parameters]`.

After the freeze, a change to the metric or to a golden re-scores every stored run. Each run keeps its
`.net.xml`, so re-scoring makes no LLM call.

## 8. Validation of the metric (SQ1)

The metric is shown to measure what it claims before any agent is measured with it. Template: Citraro et al.
(ECCV 2020).

### Error catalogue

At least one error type per aspect; F1 aspects get one that removes and one that adds, so recall and
precision move separately.

| # | Aspect | Injected errors |
|---|---|---|
| 1 | Graph structure | drop a road, add a false road, cut a road into two dead ends, double a road in parallel |
| 2 | Driving direction | two-way to one-way, one-way to two-way, flip a one-way |
| 3 | Lanes | ±1 lane in one direction |
| 4 | Lane permissions | add or remove a bus lane, add or remove a bicycle lane |
| 5 | Lane-to-lane connections | remove a connection (turn ban), add a connection |
| 6 | Junction type | change `priority` ↔ `right_before_left` ↔ `allway_stop` |
| 7 | Roundabouts | remove the roundabout marking, open the ring, remove an entry |
| 8 | Traffic lights | remove the traffic light of a junction, add one, change which connections it controls |
| 9 | Sidewalks | drop the sidewalk on one side, add one |
| 10 | Rail | drop a track, add one, cut one |
| 11 | Speed limit | change to another legal value (30 ↔ 50, 80 ↔ 100) |
| 12 | Junction joining | split a junction in two, over-join two neighbouring junctions |

Neutral perturbations must leave every aspect at 1: shift nodes below the match radius, split an edge with
an intermediate node, rename every id, round trip through `netconvert` with no change. They show the metric
uses no ids and does not punish geometric noise. One more perturbation shifts nodes above the radius, so
aspect 1 degrades gradually.

### One error, one aspect

With the first definitions four errors also lowered a second aspect, so one real error would count twice in
network fidelity. The definitions changed so that each error lowers exactly one aspect:

| Error | Its aspect | Aspect it also hit | Change |
|---|---|---|---|
| Remove a lane | 3 Lanes | 5 Connections | connections compared only on edge pairs whose lane counts match |
| Add a traffic light | 8 Traffic lights | 6 Junction type | junction type compared only where neither network has a traffic light |
| Reverse a roundabout | 7 Roundabouts | 2 Driving direction | roundabout edges do not count in aspect 2 |
| General lane to bus lane | 4 Lane permissions | 3 Lanes | aspect 3 counts every motor-vehicle lane, bus lanes included |

### Injection

- Export the base network with `--plain-output-prefix` (`nod`, `edg`, `con`, `tll`), edit the plain XML in
  code with a seed, rebuild with `netconvert`. Connections and traffic lights stay explicit.
- Rebuild with every guess turned off. In SUMO 1.27.1 `--roundabouts.guess` is on by default, so removing a
  roundabout marking would be undone silently; any other guess on by default is turned off the same way.
- After each injection a check reads the rebuilt network and confirms the error is there; if not, the
  injection fails loudly.
- An error type that does not survive the round trip is injected by editing the `.net.xml` directly. If that
  fails too, the type is dropped and the thesis says why. netedit by hand is not used.

### Metric validation network

- Injection compares a network with itself plus errors, so the base needs no golden. It is an OSM import of a
  real Berlin area, not corrected, where all twelve aspects appear: S-Bahn or tram, a roundabout, signalised
  junctions, multi-lane streets with bus and bicycle lanes, 30 and 50 km/h limits. Two areas if no single
  small one has everything.
- A script counts each aspect and requires at least 20 elements per aspect and 2 roundabouts.
- Imported with a versioned `.netccfg` that turns every aspect on (`--osm.sidewalks`, `--osm.bike-access`,
  rail, OSM traffic lights, bus lanes, speeds), not B0's defaults.
- It uses no Street View, so it is versioned in git with ODbL attribution, and the pass criteria run in CI as
  pytest tests. Validation does not wait on golden networks.
- A `netgenerate` grid is optional for small unit tests. It has no roundabouts or rail and does not replace
  the metric validation network.

### Severity

Each error type at 0, 1, 2, 5, 10 and 20 % of the elements it applies to. Levels are nested (the 5 % level
holds the 2 % errors plus new ones), so monotonicity can be required per seed. Five seeds per level. A few
hundred metric evaluations, no LLM call.

### Pass criteria

Tolerance 1e-9 in criteria 1 to 4.

1. **Identity.** The base against itself scores 1 on every aspect, with an empty error list.
2. **Neutral.** Every neutral perturbation scores as the identity.
3. **Expected value.** The affected aspect scores exactly the value computed from the injected errors (10 %
   of the km wrong on aspect 11 gives 0.90; F1 aspects use the F1 formula). This implies monotonicity. If the
   matching makes it impossible on some aspect, that aspect falls back to monotonicity only and the thesis
   says so.
4. **One aspect.** The other eleven aspects stay at exactly 1.
5. **Exact error list.** Every injected error appears once, with its aspect and its position (within the
   match radius), and nothing else appears.
6. **Shift above the radius.** Aspect 1 falls as the shift grows; the others stay at 1.

### Check against real errors

Synthetic errors only show the metric reacts to errors someone foresaw. Once, before the freeze, the
maintainer opens 50 error-list entries of B1 against one development golden, stratified by aspect, in
sumo-gui and marks each a real error or a false alarm. The precision of the error list per aspect is
published. Errors the list misses are not estimated.

### Failures and reporting

A failure before the freeze fixes the definition or the code and re-runs everything. Each fix is logged
with its reason and gives a new metric version. The thesis has an appendix table per metric version before
the final one. No existing metric (APLS, TOPO, `netdiff.py`) is implemented; the thesis cites which aspects
each metric family sees. `netdiff.py` matches by id, and injection keeps ids, so it would score perfectly
and show nothing.

## 9. Hypotheses and experiment design

### Hypotheses

- **Per aspect.** "On every test network, arm X scores higher than B1 on aspect Y by at least δ_Y." The
  criterion is per network, so that the networks cover the types. The mean over networks is reported and
  confirms nothing.
- **Network fidelity.** One hypothesis of the same form on network fidelity, with threshold δ_NF.
- **No harm.** One per arm: "arm X scores no lower than B1 by more than δ_Y on any aspect Y."
- The concrete list covers the two arms that reach the test (the best starting point and the best data
  arm) and the models the experiment design picks. It is written in the experiment design.

### Decision rule

The test runs 5 repetitions per arm and network. B1 has one value. Per network and aspect, an improvement
hypothesis is:

- **confirmed** if the minimum of the 5 is at least B1 + δ;
- **rejected** if the maximum of the 5 is below B1 + δ;
- **inconclusive** otherwise.

A no-harm hypothesis uses the same rule against B1 − δ: confirmed if the minimum is at least B1 − δ,
rejected if the maximum is below B1 − δ, inconclusive otherwise.

Over the three test networks, a hypothesis is confirmed if it is confirmed on every one, rejected if it is
rejected on at least one, and inconclusive otherwise. Each network is still reported on its own. The
median and the
min to max range are reported; no confidence intervals or statistical tests, since with 5 runs they would
not hold. If a result falls short of δ, the real number is reported next to it.

### δ

One number per aspect, δ_Y. It is both the goal of the improvement loop and the threshold of the
hypotheses. A task of its own fixes it after B1 has been measured on the development set. It is never below
the score change caused by one injected error of that aspect's type, measured on each development golden;
the largest of the six values is the floor.

The same task fixes δ_NF, the threshold of the network-fidelity hypothesis, with the same floor rule: never
below the change in network fidelity caused by one injected error, measured on each development golden,
the largest of the six values. The head of DLR's research group, the
maintainer's DLR supervisor and the UPC supervisor approve the δ_Y and δ_NF together. `[OPEN: δ]`.

### Experiment design and approval

The experiment design comes after a first development version the maintainer is satisfied with. It fixes the
arms that reach the test, the models, the data sources, the list of hypotheses, each δ, the aspect weights
and the caps for the test. The same three people approve it, and the approval is recorded below with the
date and the role of each. The test set does not run before that approval. The design may be iterated,
always on the development and validation sets.

| Role | Name | Date |
|---|---|---|
| Head of DLR's research group | `[OPEN: approval]` | |
| Maintainer's DLR supervisor | `[OPEN: approval]` | |
| UPC supervisor | `[OPEN: approval]` | |

## 10. Development

### Improvement loop

Fixed-size iterations on the development set: run, analyse why each result is what it is, then add the
missing tool, fix the input context, or fix the development golden. If nothing helps, try a stronger model
or a larger token margin. Each iteration is logged in `docs/tuning/network-author-tuning-log.md`. Validation
milestones run between iterations. Cross-validation was rejected: it multiplies runs and cost.

### Goldens during the loop

Nobody looks at why a validation golden scored what it scored. When a defect found in a development golden
may also be in a validation golden, the maintainer checks that golden for that defect explicitly and fixes
it if present. Every change goes to the golden's log, and every stored output is re-scored against the new
version, so the loop's curves always compare against the same golden.

## 11. Models, repetitions and caps

- **Development model.** Only `deepseek/deepseek-v4.1-flash`: the cheapest model with image input, and it
  reasons well enough. Spending stays low and tracked until the real cost of an iteration is known.
- **Models of the experiment.** Models with different reasoning capacity are a factor of the study. Which and
  how many is decided in the experiment design, once the cost per iteration and the funding are known.
  `deepseek-v4-pro` is out: it has no image input. `reasoning_effort` of one model is a cheap way to vary
  capacity, untested. `[OPEN: models]`.
- **Repetitions.** Development: 1 per iteration. Validation milestones: 3. Test: 5.
- **Temperature.** The provider's default, recorded with each run.
- **Caps.** 40 steps and $0.5 per run for now. The experiment design may revise them for the test from what
  validation shows. `[OPEN: test caps]`.
- **Before iterating in earnest.** Stop after repeated `length` steps with no tool call, and cap reasoning
  with `reasoning_effort` if the provider honours it.

## 12. Cost (SQ4) and budget

### What SQ4 reports

Per arm: its cost (USD, tokens, run time), the network fidelity it gains over B1, and from those the cost per
point of network fidelity gained over B1. This compares arms and models and traces the cheapest
configuration for a given gain. The share of the B1-to-golden distance an arm recovers is also reported:
with B1 at 0.70 and arm X at 0.85, arm X recovers 50 %. The golden is the reference (score 1), not an arm,
and has no cost.

No manual correction time is recorded. Hours depend on the engineer's skill, are subjective and can be bent
towards a result. The comparison with human correction effort stays qualitative, in the discussion.

### Budget

$30 in total, paid by the maintainer: $20 for development and validation, $10 kept for the test (the expected
test plus the one re-run section 14 allows after a golden defect). The maintainer presents the replan and
these costs to the coordinators the week of 2 November 2026. More can be spent later if funding arrives. If
it does, the first addition is another model on the two test arms. `docs/llm-cost-policy.md` holds the rules
for spending.

### Cost estimate

Written 2026-10-28 with `deepseek-v4.1-flash` only. It is redone with real costs when each stage closes and
after the conversation with DLR's lead engineer, since the size of the large urban network moves it most.

Prices from OpenRouter's public model list, read 2026-10-28, USD per million tokens:

| Model | Input | Output | Cached | Image input |
|---|---|---|---|---|
| `deepseek/deepseek-v4.1-flash` | 0.14 | 0.42 | 0.004 | yes |
| `anthropic/claude-haiku-5.5` | 0.10 | 0.50 | 0.01 | yes |
| `openai/gpt-5.6-luna` | 0.20 | 1.20 | 0.02 | yes |
| `google/gemini-3.8-flash` | 0.825 | 4.125 | 0.083 | yes |
| `anthropic/claude-sonnet-5.5`, `google/gemini-4-argon` | 2 | 10 | 0.1 | yes |
| `openai/gpt-5.6-terra` | 2 | 12 | 0.2 | yes |
| `anthropic/claude-opus-5.5` | 4 | 20 | 0.2 | yes |
| `openai/gpt-5.6-sol` | 4 | 20 | 0.4 | yes |
| `deepseek/deepseek-v4-pro` | 0.894 | 1.788 | 0.075 | no |

Observed runs (tuning log, small areas): $0.005 to $0.06 per run, 5 to 36 steps, up to 800k input tokens;
recent runs $0.03 to $0.05, most of the output in reasoning tokens. Per-run model: 800k input tokens with
85 % cache hits, 50k output tokens, 20 images of about 1,500 tokens. A large urban run is assumed to cost 4
times a small one; a whole Bezirk may be 10 times. `[OPEN: large network cost factor]`.

| Model | Small or interurban run | Large urban run (×4) |
|---|---|---|
| `deepseek-v4.1-flash` | $0.045 | $0.17 |
| `claude-haiku-5.5` | $0.047 | $0.18 |
| `gpt-5.6-luna` | $0.10 | $0.40 |
| `gemini-3.8-flash` | $0.39 | $1.47 |
| `claude-sonnet-5.5`, `gemini-4-argon` | $0.87 | $3.29 |
| `gpt-5.6-terra` | $1.04 | $3.96 |
| `claude-opus-5.5`, `gpt-5.6-sol` | $1.7 to 1.9 | $6.6 to 7.1 |

Run counts: one iteration is 3 arms × 6 development networks = 18 runs (the full grid would be 216). A
validation milestone is 3 arms × 3 networks × 3 repetitions. The test is 2 arms × 3 networks × 5 repetitions
= 30 runs.

| Scenario | Assumptions | Stage 1 | Stage 2 | Test | Total |
|---|---|---|---|---|---|
| Low | $0.03 per run, large ×4, 6 + 3 iterations, 1 validation milestone per stage | $8 | $5 | $2 | $15 |
| Central | $0.045 per run, large ×4, 8 + 5 iterations, 2 + 1 milestones | $18 | $11 | $3 | $31 |
| High | $0.06 per run, large ×10, 12 + 8 iterations, 3 + 2 milestones | $71 | $48 | $7 | $126 |

Another model on the two test arms (a check on validation, then the test):

| Extra model | Large ×4 | Large ×10 |
|---|---|---|
| Mid (`gemini-3.8-flash`) | +$28 | +$56 |
| Strong (`claude-sonnet-5.5`) | +$63 | +$125 |

The $10 test reserve covers the expected test ($2 to 7) and one re-run. It does not cover the worst case at
the caps (30 runs × $0.5 = $15 per test run).

## 13. Data sources and licences

Accessed 2026-10-26 (Berlin) and 2026-10-28 (Spain). Each network records which of them exist in its polygon.

### Usable by the arms

| Source | Content | Licence |
|---|---|---|
| Berlin Geoportal orthophotos (`gdi.berlin.de`, WMS and WMTS, no key) | TrueDOP 2026 and two 2025 flights, 20 cm. Lane lines, crossings, cycle lanes and junction shape visible; dashed lines faint; shadows hide parts of roads. 10 cm is for official use only | dl-de/zero-2-0, any use, no attribution |
| Berlin WFS layers | traffic signals (LSA, 2,305 junctions, 2023), Detailnetz with direction of travel, Straßenbefahrung 2014/15 (marking lines, arrows, tram beds; no markings in Mitte), bus and cycle lanes, `tempolimits` (every limit other than 50 km/h) | dl-de/zero-2-0 |
| PNOA orthophotos (IGN, national) | 25 cm; Barcelona and the B-23 flown 2024-07, the A-2 and Madrid 2023-07 | CC BY 4.0 |
| ICGC orthophotos (Catalonia) | 25 cm 2025, provisional 2026 flight, AMB 10 cm 2020 | CC BY 4.0 |
| Comunidad de Madrid orthophotos | true orthophoto 25 cm 2025, the best for the A-2 | CC BY 4.0 |
| Ayuntamiento de Madrid orthophoto | true orthophoto 10 cm 2023, city area | CC BY 4.0 |
| IGN transport network (IGR-RT, INSPIRE WFS) | lane count and direction of travel per link; the only vector source on the outer B-23 and the A-2. Accuracy unverified | CC BY 4.0 |
| Barcelona open data | traffic-light inventory (118,829 elements, 1,819 controllers), bike lanes with direction | CC BY 4.0 |
| Madrid city open data | 2,509 signalised junctions, lanes per section (2021), about 198,000 current signs (one-way, no entry, speed limits) | CC BY 4.0 |
| Mapillary API v4 | street pictures and detected objects (traffic lights, arrows, stop lines, signs). Free with a registered `client_id`; coverage per network checked at snapshot time | CC BY-SA, attribution |

What the official layers give per region:

| Layer content | Berlin | Barcelona city | B-23 outer | Madrid city | A-2 km 15 to 25 |
|---|---|---|---|---|---|
| Signalised junctions | yes | yes | no | yes | no |
| Direction of travel | yes | IGR-RT only | IGR-RT | yes, and IGR-RT | IGR-RT |
| Lane counts | partial | IGR-RT | IGR-RT | yes, and IGR-RT | IGR-RT |
| Road markings as vectors | yes (2014/15) | no | no | no | no |
| Speed limits | yes | statutory rule only | no | yes | no |
| Bus lanes | yes | no | no | no | not applicable |

### Ruled out

- **Google Maps, Street View and Earth**, for the agent and for publishable data. The terms forbid tracing
  and "creating data from Street View images", and OSM forbids Google as a source. A human corrector uses
  them anyway (section 4), which is why the goldens are not published.
- **Mapbox** (bans AI use and automated queries), **Esri** (tracing allowed for OSM editing only), **Bing**
  (retired for free accounts), **KartaView** (no usable API).
- **Panoramax.** Free and CC BY-SA, but the maintainer's own check found few pictures and most of poor
  quality.
- AMB cartography has no stated licence and is not used.

No public DLR lane-level data for Berlin was found. Whether DLR holds internal lane or signal data is asked
of the lead engineer.

## 14. Test run

Order: Network Author freeze (`PROMPT_VERSION`, tools, commit), test snapshot, test golden correction,
pre-test checks, test run.

The test goldens are corrected after the freeze, by the maintainer or by a person DLR provides.

### Pre-test checks

They look at no agent output.

1. The metric scores each test golden against itself as perfect.
2. Errors injected into the test goldens move the metric as they do on the metric validation network.
3. Each test golden loads in SUMO without errors and passes `netcheck`.
4. A second person reviews each test golden against the conventions.
5. A blind smoke run of the full pipeline on the test polygons reports only finished or failed, never a
   score.

### Re-run after a golden defect

If a defect in a test golden is found after the test run, by one of these checks and not by looking at the
agent's score, the golden is fixed, the test runs once more, and both runs are reported with the defect.

## 15. Limitations

Written down as decided; the thesis states each one.

- Correcting a golden from B1 can leave B1's unnoticed errors in it. That favours B1 and works against the
  hypotheses.
- The golden holds information no arm has (Street View, local knowledge, site visits), so the ceiling is
  below 1 for every arm.
- The official layers differ by region, so the official-layers factor is read per region.
- The starting points that lose stage 1 never run with extra data, so the interaction of starting point and
  data is not measured.
- A DLR-corrected network in the test set was not picked blind.
- The 50-entry check estimates the precision of the error list, not the errors it misses.
- With 5 repetitions the results carry no statistical tests, only the decision rule of section 9.

## Open values

| Name | What | Fixed by |
|---|---|---|
| `areas` | The remaining areas of the sets: polygon, region, why, natural-language request | The task that fixes the sets, before any import |
| `metric validation network polygon` | The Berlin area (or two) the metric is validated on | The same task |
| `snapshot dev+val` | Date and hash of the development and validation snapshot | The task that starts golden work on those sets |
| `snapshot test` | Date and hash of the test snapshot | The task right after the Network Author freeze |
| `sources per network` | Which official layers and which Mapillary coverage each network has | The snapshot tasks |
| `golden hashes` | Origin, corrector, reference date and `content_hash` of each golden | Each golden correction task |
| `large urban golden` | Whether the large urban golden is cut from a DLR network or corrected by hand, and how big it can be | The conversation with DLR's lead engineer, then the plan |
| `whole-Berlin run` | Whether the exploratory whole-Berlin run happens and what it reports | The conversation with DLR's lead engineer, then the plan |
| `B1 confirmation` | The pinned `sumo-berlin` commit and any automatic steps the lead engineer adds | The conversation with DLR's lead engineer, then the B1 build task |
| `junction joining form` | Which form the goldens use for a joined junction, and whether aspect 12 treats both as equal | The conventions task, with the lead engineer's answer |
| `conventions version` | Version and date of the conventions document | The conventions task, frozen with the metric |
| `metric parameters` | Match radius, angle tolerance, border width, `METRIC_VERSION` | The closing task of the metric epic |
| `stage selection criterion` | How network fidelity on development and validation picks the winner of each stage | Before stage 1 starts |
| `δ` | δ_Y per aspect, and δ for network fidelity | The δ task, after B1 is measured on development |
| `aspect weights` | The weights of network fidelity, from the DLR engineers' ranking | The experiment design |
| `models` | The models of the experiment | The experiment design |
| `test caps` | Step and USD caps per test run | The experiment design |
| `approval` | Date and approver of the experiment design | The approval milestone |
| `large network cost factor` | Cost of a large urban run against a small one | The first large development run; the estimate is redone then |
