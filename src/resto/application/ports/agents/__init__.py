"""One narrow port per agent (ADR-0025 §6): typed task in, `AgentRun[Draft]` out.

The Executor (`use_cases/run_study.py`) reaches every agent through these, never through
`ToolAgent` directly: `application/` cannot import `adapters/`, and each agent's infrastructure
(writers, paths, repositories, its per-call `Budget`) is bound by the implementation in the
composition root (`interface/cli`). The returned run is still a draft; promotion is the matching use
case's job.
"""
