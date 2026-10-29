"""Small real networks for the Network Author's inspection tests, built by the real `netconvert`.

Each builder returns the path of a `.net.xml` under `out_dir`, the directory the tools are bound to.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from resto.adapters.sumo.netconvert import SubprocessNetconvertRunner
from resto.domain.value_objects.network_source import GridNetwork

Node = tuple[str, float, float]


def grid_net(out_dir: Path, size: int = 3) -> Path:
    """A `size` x `size` grid of 100 m edges, two-way, no dead ends."""
    return SubprocessNetconvertRunner().generate(GridNetwork(size, size), out_dir / "grid").path


def plain_net(
    out_dir: Path,
    name: str,
    nodes: Iterable[Node],
    edges: Iterable[tuple[str, str, str]],
    *,
    traffic_light: str | None = None,
    tll: str | None = None,
) -> Path:
    """A network from plain XML. `edges` are `(id, from, to)`; `traffic_light` names a node that
    gets that type; `tll` is the `<tlLogics>` document for it."""
    plain = out_dir / f"{name}-plain"
    plain.mkdir(parents=True)
    rows = "".join(
        f'<node id="{i}" x="{x}" y="{y}"'
        + (' type="traffic_light"' if i == traffic_light else "")
        + "/>"
        for i, x, y in nodes
    )
    (plain / "n.nod.xml").write_text(f"<nodes>{rows}</nodes>")
    links = "".join(f'<edge id="{i}" from="{a}" to="{b}"/>' for i, a, b in edges)
    (plain / "n.edg.xml").write_text(f"<edges>{links}</edges>")
    if tll is not None:
        (plain / "n.tll.xml").write_text(tll)
    runner = SubprocessNetconvertRunner()
    return runner.build(None, plain, [], out_dir / name).path


def one_way_chain(out_dir: Path, length: int = 3) -> Path:
    """`length` one-way edges in a row: no cycle, one entry, one dead end."""
    nodes = [(f"n{i}", 100.0 * i, 0.0) for i in range(length + 1)]
    edges = [(f"e{i}", f"n{i}", f"n{i + 1}") for i in range(length)]
    return plain_net(out_dir, "chain", nodes, edges)


def two_loops(out_dir: Path) -> Path:
    """A loop of three edges and a separate loop of two: the small one is cut off."""
    nodes = [
        ("a", 0.0, 0.0),
        ("b", 100.0, 0.0),
        ("c", 50.0, 80.0),
        ("d", 0.0, 500.0),
        ("e", 100.0, 500.0),
    ]
    edges = [
        ("ab", "a", "b"),
        ("bc", "b", "c"),
        ("ca", "c", "a"),
        ("de", "d", "e"),
        ("ed", "e", "d"),
    ]
    return plain_net(out_dir, "loops", nodes, edges)


_ALL_RED = (
    '<tlLogics><tlLogic id="C" type="static" programID="0" offset="0">'
    '<phase duration="100000" state="rr"/></tlLogic></tlLogics>'
)


def jammed_net(out_dir: Path) -> Path:
    """Two-way road through a traffic light that stays red: every vehicle that reaches it waits
    until SUMO teleports it."""
    nodes = [("W", 0.0, 0.0), ("C", 200.0, 0.0), ("E", 400.0, 0.0)]
    edges = [("WC", "W", "C"), ("CW", "C", "W"), ("CE", "C", "E"), ("EC", "E", "C")]
    return plain_net(out_dir, "jammed", nodes, edges, traffic_light="C", tll=_ALL_RED)


def star_net(out_dir: Path, spokes: int) -> Path:
    """`spokes` one-way edges leaving one junction, each ending in a dead end."""
    nodes = [("hub", 0.0, 0.0)] + [(f"t{i}", 100.0 * (i + 1), 30.0 * i) for i in range(spokes)]
    edges = [(f"s{i}", "hub", f"t{i}") for i in range(spokes)]
    return plain_net(out_dir, "star", nodes, edges)
