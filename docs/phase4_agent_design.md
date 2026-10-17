# Phase 4: Agent Design

> **Status:** Design complete. Skeleton in `app/workers/execute_task.py`. Full implementation Week 2–3.

## LangGraph Agent (8 Nodes)

```
START
  │
  ▼
CheckCancellation ──(cancelled)──► END
  │ (continue)
  ▼
Reasoning          ← Plan the task using LLM
  │
  ▼
ToolSelection      ← Choose which tool to call next
  │
  ▼
ToolExecution      ← Call the tool, capture output
  │
  ▼
ObservationProcessing ← Summarise tool output
  │
  ▼
StepCompletion     ← Mark step done, check if more steps remain
  │ (more steps)
  ├──────────────────► CheckCancellation (loop)
  │ (all steps done)
  ▼
Verification       ← Check result quality (5 criteria)
  │ (pass)
  ▼
FinalResponse      ← Format and persist final answer
  │
  ▼
END
```

## Tool Registry

| Tool | Description | Week |
|------|-------------|------|
| `duckduckgo_search` | Web search | 2 |
| `python_repl` | Execute Python code | 2 |
| `file_tool` | Read/write files | 2 |
| `mock_tool` | Testing stub | 1 |

## Agent State (TypedDict)

```python
class AgentState(TypedDict):
    task_id: str
    goal: str
    plan: list[Step]
    current_step: int
    observations: list[str]
    final_answer: str | None
    cancelled: bool
    errors: list[str]
```

## Verification Criteria

1. `section_completeness` — Required sections present
2. `json_validity` — JSON output is parseable
3. `step_completion` — All plan steps executed
4. `truncation_check` — Response not cut off
5. `hallucination_check` — No obvious fabrications
