# RESTO: Reasoning Experts for SUMO Traffic Orchestration

RESTO — TFM (FIB + DLR). SUMO traffic simulation driven by LLM agents behind typed contracts and MCP tool servers.

See [`docs/tfm-architecture-and-dod.md`](docs/tfm-architecture-and-dod.md) (architecture + per-module Definition of Done) and [`docs/tfm-work-plan.md`](docs/tfm-work-plan.md) (epics, milestones, calendar).

## Layout

```
src/resto/
  domain/          # entities, value objects, invariants, id policy — stdlib only
  application/     # ports (LLM, SUMO, storage), use cases, agent tools, schemas.py (TypeAdapters)
  adapters/        # llm/ (ToolAgent), sumo/ (netconvert, demand, runner, traci_api), sandbox/, web/, persistence/, tracing/
  interface/       # CLI, MCP servers (NetworkMCP, DatabaseMCP, TraciMCP), report rendering
eval/              # evaluation assets and harness (outside the hexagon)
schemas/           # published JSON schemas, generated from the domain (see below)
```

Architecture, domain model and per-module Definition of Done: `docs/tfm-architecture-and-dod.md` (v0.3),
with decisions taken after it was written in its §9 (amendments).
Storage contract for third-party backends: [`docs/DATABASE_MCP_CONTRACT.md`](docs/DATABASE_MCP_CONTRACT.md).
Superseded versions and working notes: `docs/_old/`.

The JSON schemas in `schemas/` are generated, never edited by hand — regenerate them with
`python -m resto.application.schemas schemas` after changing a domain type, or the test that
compares them against the code will fail.

## Development

Requires the `resto` conda environment. **SUMO 1.27.1** is pinned for the whole thesis and is installed
**from PyPI** (`eclipse-sumo`, `sumolib`, `traci`), not from conda-forge: it is a regular dependency in
`pyproject.toml`, so `pip install -e .` brings the `sumo`, `netconvert`, `duarouter` … binaries into the
environment's `bin/` and the Python libraries into `site-packages`.

```bash
conda create -n resto python=3.13
conda activate resto
pip install -e ".[dev]"        # add ",fast" for libsumo
pytest
ruff check .
sumo --version                 # must print 1.27.1
```

Notes:

- `SUMO_HOME` is **not** required: `sumolib`/`traci` are importable directly and the binaries are on the
  environment's PATH. The bundled tools (`randomTrips.py`, `routeSampler.py`, …) live at
  `python -c "import sumo, os; print(os.path.join(sumo.__path__[0], 'tools'))"`.
- If a `SUMO_HOME` from another SUMO install (e.g. the macOS framework under `/Library/Frameworks`) is set
  in your shell profile, unset it inside this environment to avoid mixing versions.
- Other SUMO versions may produce non-reproducible `tripinfo`/`edgedata` output; every `SimulationResult`
  records `sumo_version` and must match 1.27.1.
