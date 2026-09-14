#!/usr/bin/env bash
# Rebuilds DEV-NET from scratch. See README.md for the design rationale.
#
# DEV-NET is a synthetic 5x5 grid (200 m blocks, 25 junctions, 80 directed
# edges) with three hand-designed features on top of the plain netgenerate
# output:
#   - a signalised corridor: the middle east-west row (A2-B2-C2-D2-E2) is
#     traffic-light controlled, every other junction stays priority-controlled.
#   - a 2->1 lane merge bottleneck: edge B0->C0 is hand-edited to 2 lanes
#     while its straight continuation C0->D0 stays at 1 lane, on row 0 (fully
#     separate from the signalised corridor on row 2).
#   - no U-turns at any junction: every turnaround connection is stripped
#     before recompiling.
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

# --- Step 1: netgenerate the plain 5x5 grid ----------------------------------
# TLS placement is deferred to step 4 (netconvert), not set here, so junction
# types in dev-net.nod.xml stay plain `priority` and there is nothing for a
# later --tls.set to conflict with. Plain XML (nod/edg/con) is written for
# steps 2-3 to hand-edit and step 4 to recompile; the directly-written
# .net.xml is discarded.
tmp_net="$(mktemp -t dev-net-unused-XXXX).net.xml"
netgenerate --grid \
  --grid.number 5 \
  --grid.length 200 \
  --default.lanenumber 1 \
  --default.speed 13.89 \
  --default.junctions.type priority \
  --plain-output-prefix dev-net \
  --output-file "$tmp_net"
rm -f "$tmp_net"

# --- Step 2: hand edit - widen B0->C0 to 2 lanes -----------------------------
# The plain edge file is hand-edited here. C0->D0 (and every other edge) is
# untouched, so lane 1 of B0->C0 ends up with no forward connection at C0 once
# recompiled: a mandatory-lane-change merge, i.e. a designed 2->1 bottleneck
# (see README.md "Bottleneck" section).
python3 - <<'PY'
import xml.etree.ElementTree as ET

path = "dev-net.edg.xml"
tree = ET.parse(path)
root = tree.getroot()
edge = next((e for e in root.findall("edge") if e.get("id") == "B0C0"), None)
if edge is None:
    raise SystemExit("edge B0C0 not found - did the grid layout change?")
edge.set("numLanes", "2")
tree.write(path, xml_declaration=True, encoding="UTF-8")
PY

# --- Step 3: hand edit - drop every turnaround (U-turn) connection ----------
# netgenerate's plain connection file lists an explicit connection back onto
# an edge's own reverse at every junction where that movement exists (every
# edge except the 8 arriving at a grid corner, which never got one). Explicit
# connections override netconvert's own --no-turnarounds guessing, so they
# must be removed from the plain XML itself for no junction to allow a U-turn.
python3 - <<'PY'
import xml.etree.ElementTree as ET

edg = ET.parse("dev-net.edg.xml").getroot()
edge_nodes = {e.get("id"): (e.get("from"), e.get("to")) for e in edg.findall("edge")}
reverse_of = {}
for eid, (f, t) in edge_nodes.items():
    for oid, (of, ot) in edge_nodes.items():
        if of == t and ot == f:
            reverse_of[eid] = oid
            break

path = "dev-net.con.xml"
tree = ET.parse(path)
root = tree.getroot()
removed = 0
for conn in list(root.findall("connection")):
    if reverse_of.get(conn.get("from")) == conn.get("to"):
        root.remove(conn)
        removed += 1
print(f"removed {removed} turnaround connections")
tree.write(path, xml_declaration=True, encoding="UTF-8")
PY

# --- Step 4: recompile the hand-edited plain XML into the final network -----
# TLS is built fresh here (--tls.set) rather than reusing a pre-generated
# dev-net.tll.xml, since the turnaround removal in step 3 changes the link
# count at the row-2 junctions and a stale tlLogic would no longer match it.
# --no-turnarounds is kept as a defence-in-depth default even though step 3
# already removes every explicit turnaround connection. --plain-output-prefix
# rewrites dev-net.{nod,edg,con}.xml as netconvert's canonicalised view of the
# same network and writes a fresh, consistent dev-net.tll.xml.
netconvert \
  --node-files dev-net.nod.xml \
  --edge-files dev-net.edg.xml \
  --connection-files dev-net.con.xml \
  --tls.set A2,B2,C2,D2,E2 \
  --no-turnarounds \
  --plain-output-prefix dev-net \
  --output-file dev-net.net.xml

echo "dev-net.net.xml rebuilt."
