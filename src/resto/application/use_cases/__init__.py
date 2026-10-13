"""Use cases that stand alone (ADR-0042 §1 and §2). Each is a class with an `execute` method and
its collaborators as constructor fields; `interface/dependencies.py` builds the instances and
nothing in `application/` wires objects. `RunStudy`, the entry point for a whole study, has its own
package (`application/run_study/`) and calls the others.
`RunSimulation` and `ScaleDemand` are deterministic. `BuildScenario` takes a finished `AgentRun`,
has the `ScenarioPromoter` promote its draft, checks that SUMO loads the scenario and stores it.
Every agent answer is promoted by a promoter of `application/promoters/` (ADR-0042 §5); promoters
are not use cases. The modules `derive_network`,
`generate_demand`, `generate_network` and `reroute_demand` are placeholders until E6.1 and E7.1.
`tests/unit/test_use_case_convention.py` enforces the class shape.
"""
