"""Use cases. Each is a class with an `execute` method and its collaborators as constructor
fields; `interface/dependencies.py` builds the instances and nothing in `application/` wires
objects. `RunStudy` is the entry point for a whole study, and the Executor calls the others.
`RunSimulation` and `ScaleDemand` are deterministic. `AskExpert`,
`BuildScenario`, `ComposeReport` and `WriteNote` take a finished `AgentRun` and promote the returned
draft into a domain entity (validate, identity, persist, trace). The modules `derive_network`,
`generate_demand`, `generate_network` and `reroute_demand` are placeholders until E6.1 and E7.1.
`tests/unit/test_use_case_convention.py` enforces the class shape.
"""
