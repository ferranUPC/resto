# RESTO: Reasoning Experts for SUMO Traffic Orchestration

RESTO — TFM (FIB + DLR). SUMO traffic simulation driven by LLM agents behind typed contracts and MCP tool servers.

See [`docs/tfm-architecture-and-dod.md`](docs/tfm-architecture-and-dod.md) (architecture + per-module Definition of Done) and [`docs/tfm-work-plan.md`](docs/tfm-work-plan.md) (epics, milestones, calendar).

## Layout

```
src/resto/
  domain/         # entities, value objects, pure business rules — no framework deps
  application/     # use cases, ports (abstract interfaces to the MCP adapters)
  adapters/        # NetworkMCP / DatabaseMCP / TraciMCP implementations + I/O DTOs
  interface/       # Input Parser, Output Composer, entrypoints
```

## Development

Requires the `resto` conda environment.

```bash
conda activate resto
pip install -e ".[dev]"
pytest
ruff check .
```
