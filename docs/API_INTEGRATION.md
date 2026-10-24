# Connect a producer or model API

The evaluator is synchronous and offline. Connect the new API at the capture
boundary; do not put a provider client inside the grading engine. An integration
can either emit the supported local bundle or provide an explicit adapter that
returns the internal `EvidenceRun` records. The local bundle route is simpler
because it already includes all integrity and identity checks.

## Supported bundle route

1. Preserve the provider-exposed raw request and response objects as immutable
   bytes. Record model-request/return/failure boundaries and a `model_call_id`.
   Do not claim reconstructed objects are original HTTP transport bytes.
2. Preserve each proposed tool's exact argument string, name and provider call
   identity. Give every actual CLI attempt its own `cli_id`. Keep proposals,
   guards, dispatches and CLI results distinct. Log harness initialization,
   resets and retries too, even when the model did not request them.
3. Capture exact stdout/stderr, exit/termination and serialized execution order
   for each CLI attempt. Return bounded tool results to the model and persist
   that exact visible result separately. Retain full CLI output for evaluation.
4. Capture the original part bytes and independently selected case. Record
   original open/readback, baseline, trial restoration, mutations, mesh, actual
   default load and solve IDs. The grader reconstructs these from raw results;
   a producer `verified=true` assertion does not certify the run.
5. After saving, snapshot the actual file and link it to its save/solve IDs.
   Capture the bytes occupying `outputs/<part>.json` at completion. Emit an
   `artifact_published` event. An immutable earlier snapshot does not prove the
   final destination still contains those bytes.
6. Render the supported final `json/1` claim from the same structured outcome
   shown to the user. Emit the terminal `run_finished` event pointing to that
   outcome. Write the completion inventory last, including every referenced
   file's hash and byte count. Interrupted runs remain interrupted.
7. Add the immutable directory to an input manifest and run `evaluate.py`.
   Inspect all dimensions, not its process exit code alone.

Exact required fields and IDs are in
[EVAL_IMPLEMENTATION_CONTRACT.md](EVAL_IMPLEMENTATION_CONTRACT.md).
[The repaired example](../fixtures/examples/repaired/manifest.json), its
[ledger](../fixtures/examples/repaired/events.jsonl),
[outcome](../fixtures/examples/repaired/outcome.json), and
[completion inventory](../fixtures/examples/repaired/completion.json) provide
an inspectable fixture. It is synthetic and therefore does not contain model
requests; live captures additionally require the model/tool boundaries above.
The tests simulate those boundaries without calling a provider.

## Existing capture route

Implement a small trusted Python adapter outside the grading modules:

```python
from evaluate import evaluate_one, load_cases
from trace_adapter import register_adapter

def load_my_capture(path, case, limits):
    # Validate and parse persisted bytes; retain Ref provenance.
    # Return eval_types.EvidenceRun, Action, Event, Artifact and Issue records.
    # Missing/unsupported evidence becomes an issue or unknown state.
    # Do not execute commands, infer missing successful calls, or call a model.
    return my_validated_mapping(path, case, limits)

register_adapter("my-capture-v1", load_my_capture)
cases, policy_digest = load_cases()
report = evaluate_one(
    "captures/run-001", cases["bracket_v3"],
    adapter="my-capture-v1", policy_digest=policy_digest,
)
```

`my_validated_mapping` is the integration code to supply, not an installed
function or a claimed finished adapter. `register_adapter` accepts explicit
host code only; trace data cannot import modules. `evaluate_one` supports a
foreign layout. To use `evaluate_batch` with one, also provide a small local
`manifest.json` with a stable `run_id` for independent duplicate preflight.
CLI deployments register their adapters in their trusted entrypoint before
calling `evaluate.main`. The default CLI accepts only the built-in adapter.
Use a versioned adapter name, as in the example; it is retained in every
evaluated report alongside the case's CLI profile. Keep installed adapter source
and its release/digest with the deployment for reproducible interpretation.

Adapter duties include bounded local reads; SHA/length verification over the
same bytes parsed; no unsafe path traversal; unique IDs; execution pairing and
order; completion; original/binary profile validation; raw result semantics;
immutable save snapshots; final publication; and honest source labels. Merely
returning `complete=True` from an unvalidated summary bypasses those duties.
The engine necessarily trusts its installed adapter code. Reuse the built-in
bundle validator wherever possible instead of reimplementing this surface.

## Acceptance before using real reports

- A real valid run must establish capture completeness without filling gaps
  with synthetic events. Preserve provider failure and interrupted-run evidence.
- Replay persisted inputs through evaluation twice without network access;
  reports should be identical. Permuting independent runs must not change them.
- A copy with a post-solve mutation must fail `STALE_SOLVE`. A blocked forbidden
  proposal must remain diagnostic. Actually executing it must fail compliance.
- Verify reported SF against raw solve output and final artifact bytes. Keep
  repair achievement separate from an honest search-exhaustion result.
- Check all expected model-visible requests/results were captured. Byte metrics
  are not token counts. Unknown provider usage remains null until mapped.

The existing tests cover the internal adapter seam and the concrete local
profile. They cannot certify a future provider's exporter before it exists.
The SDK-owned proposal has not been silently amended or declared mutually
agreed. Map its actual output to this local profile and version that mapping.

Swapping a **model API or agent harness** uses this boundary. Swapping PartLab
for a **different CAD/CAE API** also requires a validated action/state profile,
artifact schema and domain policy tests; raw field renaming cannot establish
equivalent engineering semantics. The current supported binary digest is
`9b202e1ba07861f52f12005108e81815ef14d92f2db3ba322fc51422746ab183`.
