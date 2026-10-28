"""Constants shared across the SUMO adapter."""

APPLIED_ACTIONS_FILE = "applied_actions.json"
"""File the harness writes the applied actions to, in the run directory."""

DRY_RUN_STEPS = 50
"""Steps a dry run lets `run()` take before it forces every rule once."""

TRACI_API_MODULE = "resto.traci_api"
"""The one module a generated script imports from."""

EDGEDATA_PERIOD_S = 300.0
"""Aggregation period of the run's edgedata output, in seconds."""

EDGEDATA_FILE = "edgedata.xml"
"""Name of the edgedata output in the run directory."""

SCRIPT_NAME = "script.py"
"""Name of the generated script in the run directory."""

RUN_CFG_NAME = "run.sumocfg"
"""Name of the run configuration in the run directory."""

DEFAULT_TIMEOUT_S = 600.0
"""Wall-clock limit of an online or dry run: twice the DoD's 5-minute threshold."""

OUTPUT_FILES: dict[str, tuple[str, str]] = {
    "tripinfo-output": ("tripinfo.xml", "tripinfo"),
    "statistic-output": ("statistics.xml", "statistics"),
    "summary-output": ("summary.xml", "summary"),
}
"""SUMO output option -> (file name in the run directory, artifact kind)."""

SUMO_REPORT = {"duration-log.statistics": "true", "no-step-log": "true"}
"""The run cfg's report options."""
