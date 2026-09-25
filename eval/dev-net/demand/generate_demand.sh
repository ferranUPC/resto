#!/usr/bin/env bash
# Rebuilds DEV-NET's three demand profiles (low/peak/incident) from scratch. See
# README.md for how the insertion rates below were chosen and what they represent.
#
# Requires the `resto` conda env active (SUMO 1.27.1) and SUMO_HOME unset.
set -euo pipefail

if [ -n "${SUMO_HOME:-}" ]; then
  echo "SUMO_HOME is set (${SUMO_HOME}) - unset it before running this script." >&2
  exit 1
fi

version="$(sumo --version | head -1)"
case "$version" in
  *1.27.1*) ;;
  *) echo "Expected SUMO 1.27.1, got: ${version}" >&2; exit 1 ;;
esac

cd "$(dirname "$0")"

RANDOM_TRIPS="$(python3 -c 'import sumo, os; print(os.path.join(os.path.dirname(sumo.__file__), "tools", "randomTrips.py"))')"
NET_FILE="../dev-net.net.xml"
SEED=1
BEGIN=28800  # 08:00 - time of day, ADR-0028
END=32400    # 09:00

gen() {
  local profile="$1" rate="$2"
  shift 2
  python3 "$RANDOM_TRIPS" \
    --net-file "$NET_FILE" \
    --output-trip-file "${profile}.trips.xml" \
    --route-file "${profile}.rou.xml" \
    --insertion-rate "$rate" \
    --seed "$SEED" \
    --begin "$BEGIN" \
    --end "$END" \
    --poisson \
    --validate \
    --random-departpos \
    --random-arrivalpos \
    --prefix "${profile}_" \
    "$@"
  echo "${profile}: $(grep -c '<vehicle' "${profile}.rou.xml") vehicles -> ${profile}.trips.xml / ${profile}.rou.xml"
}

# --- low: light background traffic, comfortably free-flowing everywhere -----
gen low 300

# --- peak: uniform network-wide demand, tuned so ~10-20% of edges are ------
# congested (mean 16.3% across 3 simulation seeds - see verification.ipynb).
gen peak 1200

# --- incident: same total volume class as peak, but every trip is forced ----
# via the bottleneck edge B0C0 (incident.via.xml has weight 1 on B0C0, 0
# elsewhere - see LoadedProps in randomTrips.py: unlisted edges get weight 0,
# so `-i 1` picks B0C0 as the one mandatory intermediate waypoint for every
# trip). B0C0's observed breakdown point (~950-1000 veh/h for this single
# lane) is a metastable capacity drop, not a hard wall: rates right below it
# (e.g. 980) still collapse into gridlock/teleports on an unlucky simulation
# seed (5/20 seeds teleported at 980). 950 leaves enough margin that 20/20
# simulation seeds stay teleport-free (verification.ipynb checks this every
# time it runs) while still saturating the corridor far beyond `peak`.
gen incident 950 --intermediate 1 --weights-prefix incident

echo "Demand profiles rebuilt: low, peak, incident."
