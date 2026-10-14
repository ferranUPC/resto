"""Constants shared across the SUMO adapter."""

APPLIED_ACTIONS_FILE = "applied_actions.json"
"""File the harness writes the applied actions to, in the run directory."""

DRY_RUN_STEPS = 50
"""Steps a dry run lets `run()` take before it forces every rule once."""

TRACI_API_MODULE = "resto.traci_api"
"""The one module a generated script imports from."""
