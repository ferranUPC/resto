"""Golden paths: a request, the world it starts from and the Expected outcome of a correct study.

A golden path asserts what the study leaves (how it ends, the network, the simulations and the KPIs
the Expert gave), never the route: phases, step order and rounds are not part of it, and the order
of steps is checked in the `RunStudy` tests. See ADR-0043 and `golden/framework`.

Run from the repository root: `python -m golden.run --setup fake`.
"""
