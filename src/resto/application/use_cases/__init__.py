"""Use cases. Each is a class with an `execute` method and its collaborators as constructor
fields; `interface/dependencies.py` builds the instances and nothing in `application/` wires
objects. `RunStudy` is the entry point for a whole study, and the Executor calls the others.
`RunSimulation` and `ScaleDemand` are deterministic. `BuildScenario` takes a finished `AgentRun` and
promotes the returned draft into a domain entity (validate, identity, persist, trace). The Expert
answer, the notes and the report are promoted by the promoters of `application/promoters/`
(ADR-0042 §5), which are not use cases. The modules `derive_network`,
`generate_demand`, `generate_network` and `reroute_demand` are placeholders until E6.1 and E7.1.
`tests/unit/test_use_case_convention.py` enforces the class shape.
"""
