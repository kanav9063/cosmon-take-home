# Agent build plan for discussion

This is the short companion to [SDK_PLAN.md](SDK_PLAN.md). Setup is complete;
the agent tools and loop below are proposed, not implemented. The latest
offline recheck passed on October 23, 2026 (America/New_York): Python 3.12.3,
dependency consistency, SDK tool schema/local invocation, PartLab baseline
workflow (SF 1.428), and a closed-session solve returning StateError. No model
request was made. See [SDK_SETUP.md](SDK_SETUP.md) for reproduction commands.

The selected provider/model is **OpenRouter / `openai/gpt-6.1-sol` with medium
reasoning**, explicitly chosen by Kanav. The ignored local `.env` stores the
key and selected settings; [.env.example](../.env.example) contains nonsecret
placeholders. Live access and tool-calling compatibility remain to be tested.

## What we want to build

One agent receives a named part, reports its baseline safety factor under its
default load, and searches for a valid single-parameter repair if needed. It
stops at the first verified fix, saves it, and reports the evidence. If search
does not find a fix, its report explains the bounded search without claiming
impossibility. Each candidate starts from the original baseline.

## Proposed initial tools

These are model-visible signatures; the Python functions also receive a local
`ToolContext[RunState]` containing the assigned part, working directory,
original values, policy, current state, budgets and trace writer. The model
cannot choose those internal objects.

| Tool signature | Result and code responsibility |
| --- | --- |
| `open_part()` | Open the assigned original part; return identity, parameters, default load and constraints. A later call restores the baseline for a new trial. |
| `get_parameters()` | Return current effective parameters for explicit inspection. |
| `set_parameter(name: str, value: float)` | Record the proposal, validate the full resulting state and trial rules, execute if allowed, invalidate the previous analysis. |
| `mesh()` | Build the mesh with configured settings; clear previous load/solve evidence. |
| `apply_load(face_id: str, force_N: float, direction: str)` | Validate the explicit selection against the part's original default load, then apply it. |
| `solve()` | Require mesh and load, execute the solver, return exact SF/stress/convergence and evidence references. |
| `save_part()` | Require a valid one-parameter repair and fresh qualifying solve; write and verify the code-selected output file. |

`solve()` already returns SF, so a separate model call to read it is optional.
The runner can use `get-active-part` internally for state verification; expose
it as another tool only if needed for recovery. A tool may perform readback
checks, but it does not secretly execute the next mesh/load/solve action.

Keeping the assigned part and save path in context removes unnecessary model
choices. Keeping the load tuple explicit makes correct and incorrect load
selection observable. This signature choice is a recommendation for discussion.

## What happens inside a tool

1. Persist the original tool request, including its call ID and arguments.
2. Validate argument types and semantics: finite numbers, known parameters,
   manufacturing limits, default load, required phase and remaining budget.
3. Record allow/block separately from actual execution. A blocked proposal
   returns an actionable error and never launches the mutation.
4. Call the shared subprocess runner with an argument array and fixed executable
   in a private working directory. Record exact output bytes and process status.
5. Update state only from verified results and invalidate stale solve references.
6. Return the fields needed for the next model decision, retaining the full
   output separately. In particular, do not put the verbose solve log into
   every model response.

The SDK supplies the model/tool loop and JSON argument schema. Python still
enforces domain rules; a numeric JSON schema alone does not establish a valid
manufacturing change. All tools share one runner so command execution, timeout
handling, error parsing and raw capture are consistent.

## Build order and exit checks

| Stage | Work | Ready when |
| --- | --- | --- |
| 1 — Done | Isolated environment and starter health | Offline SDK and CLI checks pass without credentials or shared state changes |
| 2 — Discuss | Tool signatures, model responsibilities and limits | Candidate-selection method, numerical bounds, budgets and policies are explicit |
| 3 — Agree interface | Reconcile the producer trace proposal with the eval track | Both sides explicitly accept a version and compatible evidence fixtures; current status is not yet agreed |
| 4 — Implement foundation | Private run lifecycle, one CLI runner, raw capture, named wrappers and guards | Offline checks demonstrate ordering, constraint rejection, baseline restoration, solve freshness and verified saves |
| 5 — Add agent | Prompt, chosen model configuration, loop and final outcome validation | A scripted offline model exercises the loop; its evidence is labeled synthetic |
| 6 — Run and demonstrate | Configure provider credentials locally, run bracket_v3 and flange_v1, inspect traces and outputs | Real persisted traces and artifacts support the reported outcomes; eval consumes them offline |

Stages 4–6 are exercise work, with the recorded one-hour time-box and approximately
30 minutes for the agent. The detailed plan includes the eval half and handoff.
Docker, Harbor, ATIF and Scout remain conditional follow-on work.

## First decision to discuss

Recommendation: let the model choose the parameter and its numerical value
inside the configured exploration bounds. Python checks legality, maintains
state and limits the number of attempts. The alternative is for Python to
generate a finite candidate list and let the model choose from it.

The former gives the model a meaningful engineering decision; the latter makes
the search domain easier to enumerate. Neither establishes global infeasibility
when the exploration bounds do not cover the whole legal design space.

Exact numerical bounds, candidate ordering, budgets, retry/timeout
settings and the trace interface remain open. API credentials are not needed
to settle the tool design or test the wrappers offline.
