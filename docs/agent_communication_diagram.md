# RESTO — Agent communication

Who talks to whom: the Coordinator dispatches typed tasks to each specialist agent; every
specialist (and the plain-code Runner) uses the MCP servers as tools. Solid arrows = orchestration
(labeled with the task type sent). Dotted arrows = tool use / persistence (unlabeled — direction
and node name say enough).

```mermaid
flowchart TD

User(["User"])
Coordinator(["Coordinator"])

subgraph AGENTS["LLM agents (ToolAgent)"]
  NetworkAuthor("Network Author")
  DemandGenerator("Demand Generator")
  ScenarioBuilder("Scenario Builder")
  NetworkExpert("Network Expert")
  OutputComposer("Output Composer")
end

Runner["Simulation Runner<br/>(no LLM)"]

subgraph SERVERS["MCP / tool servers"]
  NetworkMCP["NetworkMCP"]
  DatabaseMCP[("DatabaseMCP")]
  TraciMCP["TraciMCP"]
end

User <--> Coordinator

Coordinator -->|NetworkTask| NetworkAuthor
Coordinator -->|DemandTask| DemandGenerator
Coordinator -->|ScenarioTask| ScenarioBuilder
Coordinator -->|seed| Runner
Coordinator -->|ExpertTask| NetworkExpert
Coordinator -->|Study| OutputComposer
OutputComposer -->|Report| Coordinator

NetworkAuthor -.-> NetworkMCP
NetworkAuthor -.-> Runner
NetworkAuthor -.-> DatabaseMCP

DemandGenerator -.-> Runner
DemandGenerator -.-> DatabaseMCP

ScenarioBuilder -.-> NetworkMCP
ScenarioBuilder -.-> DatabaseMCP

NetworkExpert -.-> NetworkMCP
NetworkExpert -.-> DatabaseMCP

Runner -.-> TraciMCP
Runner -.-> DatabaseMCP
```
