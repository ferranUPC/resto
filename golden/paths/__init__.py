"""Golden paths: one module per path, `golden/paths/<name>.py`, defining `PATH: GoldenPath`.

The name of the module is the name of the path and of its fake agent script
(`golden/setups/fake/scripts/<name>.py`). There is no central list. A definition holds the
request, the prior world state and the expected trace, never agent output.
"""
