# Producer evidence requirements and contract checkpoint

Status: **consumer requirements, proposal only**. The SDK track owns the initial
producer contract. These requirements do not assert that the other chat accepted
this layout. Field names below are semantic names; map them explicitly to the
SDK proposal before implementation. No cross-chat message has been sent.

## Smallest sufficient evidence bundle

Keep the unmodified raw model messages/items, tool arguments and returned values,
plus a local execution ledger and immutable artifact snapshots. A provider trace
URL or a final `RunResult` summary alone is insufficient for offline evaluation.
Capture automatically at execution boundaries, including failures; do not rely
on the model remembering to call a logging tool. Normalized projections are
rebuildable derived files. Do not rewrite existing source evidence to normalize it.

| Evidence | Required contents | Why it is needed / if absent |
| --- | --- | --- |
| Bundle identity | Schema name/version, globally distinct run ID, case/part ID, producer/harness version, runtime, binary digest, run origin (`captured`/`synthetic`), provenance | Choose a supported adapter and prevent examples being counted as actual runs |
| Task case | Immutable task/policy version or digest; requested part, SF target, applicable constraints, output-path requirement | Evaluate against independent task expectations, not the agent's chosen limits |
| Original baseline | Full original part bytes + SHA-256, complete parameters with units, default face/force/direction, name/revision, material and other fields | Detect wrong defaults, cumulative changes, material/physics edits; never infer original from final |
| Raw model data | Ordered provider-exposed system/user/assistant items, exact tool-call arguments, exact tool returns, final displayed text, IDs and full-versus-model-visible links | Preserve what the model actually received/emitted; hidden reasoning is not required |
| Stable ordering | Run/session/trial ID; event ID; monotonic ledger sequence; start/end times for diagnostics; authoritative serialized execution order | Timestamps and model message order are not sufficient to order stateful actions |
| Logical tool call | Stable call ID, exact named action, exact arguments; mapping to provider-native call ID | Distinguish proposals from actual command execution and join returned results |
| Guard | Proposal/call ID; allow/reject/error; rule ID and values/reason; whether execution was dispatched | A guard's claim is not proof of either CLI execution or compliance |
| CLI execution | Distinct execution/attempt ID, parent call ID (or explicit harness actor), exact argv, cwd/session identity, start/completion, exit code or signal/timeout/launch exception, full stdout/stderr | An allowed proposal can fail before or during execution; retries need separate identities |
| CLI JSON | Exact stdout plus independent parse status; parsed envelope may be supplied as a cross-check; retain errors even on nonzero exit | Eval reparses raw stdout; summary cannot overwrite contradictory bytes |
| State evidence | Successful open/reset origin; accepted/effective parameter value, complete original map, actual effective load/direction, mesh arguments; references to preceding execution/state | Reconstruct actual state and distinguish failures with unknown side effects |
| Trial restoration | Trial identity, parameter family, original-baseline restoration operations and results before each new trial | Ensure independent trials and prevent accumulating changes |
| Solve | Successful solve execution ID, raw numerical SF/units/precision and relevant outputs; link any separate SF read to that solve | Reject stale safety factors and handbook estimates used as verification |
| Save/artifact | Producing save execution ID, logical output path, relative snapshot path, bytes/length/SHA-256, artifact ID, state/solve reference, capture time | A success response/path string is insufficient to verify saved content |
| Final result | Declared outcome; original/final SF and cited solves; selected target state/artifact, which may differ from last live session state; reported changed parameter/value; artifact ID/path; termination reason; proof references if claimed | Compare user-visible outcome with executed history and artifact |
| Completion | Started/completed/failed/interrupted marker, last sequence/count, termination reason; identify in-flight calls | Detect valid JSON prefixes that otherwise resemble complete success |

The evaluator should load an independent baseline/case trusted by the exercise
and compare the producer's captured baseline against it. A producer-supplied hash
and matching producer-supplied altered part alone cannot prove original identity.
Use original repository bytes and their known digest as the initial trust anchor.

Recommended but optional: exact model/provider identifier, model settings, seed
when available, package lock digest, SDK tracing IDs, call duration, token usage,
cost with pricing provenance, model-visible response bytes and full-result bytes.
Missing efficiency metadata produces unknown metrics, not a failed repair.
Never capture API credentials or full process environment dumps. If a source
contains a secret unexpectedly, keep a documented redacted derivative for
sharing; do not call it the untouched original or commit the secret.

## Ordering, execution, and numeric rules

- IDs are stable and namespaced by run. Each CLI start has one terminal record or
  is explicitly incomplete. Duplicate/conflicting IDs are errors, not last-write-wins.
- Distinguish model-requested calls from harness initialization, restoration,
  guards, and implicit operations. All state-changing operations, including
  harness actions, belong in the execution ledger.
- One named SDK tool can map to multiple low-level attempts, each logged. Keep
  separate named actions for open, mesh, apply load, solve and save as agreed.
  Do not hide these inside an undocumented combined workflow.
- Either serialize all actions sharing a PartLab session or provide a provable
  ordering. Overlapping stateful operations without such an order leave state
  unknown. Offline grading must not sort them into a convenient success path.
- Require consistent process exit and JSON envelope semantics. `exit=0` with
  `ok=false`, a partial stdout object, timeout, or missing completion cannot
  certify success. A normal failed command must not be treated as an executed
  mutation without documented atomicity or observed post-state.
- Preserve JSON numeric lexemes or exact raw bytes. No pre-evaluation rounding
  or clamping. Record default/effective load direction explicitly; omission is
  acceptable only with a pinned, tested CLI default rule and clear provenance.
- Derived producer state IDs are useful links; the evaluator reconstructs state
  independently and flags contradictions. `verified=true` is not sufficient evidence.
- Final selection must identify the intended saved state. A verified immutable
  artifact from before later exploration remains valid; a new artifact using its
  old solve does not. Capture which bytes remain at the required output path at
  run completion so an overwritten snapshot cannot masquerade as the final file.
- Large stdout may be stored by immutable local reference. Persist full bytes
  even when a smaller projection is returned to the model. Byte counts and
  references identify which form the agent saw.

## Fixture examples and compatibility promise

[../eval_preparation/](../eval_preparation/) contains consumer-semantic examples
with a deliberately provisional `eval-fixture-proposal/0` marker and
`source_kind=synthetic`. They are not OpenAI SDK exports, ATIF, or actual PartLab
observations. A future adapter must preserve their semantics, not copy their
field spelling if the SDK contract supplies a different agreed layout.

The examples cover fresh one-parameter repair, already-safe original, rejected
manufacturing proposal without CLI dispatch, and a schema-valid stale-solve
claim. The packaging checker validates structure, references, and digests only.
Expected findings are a future test oracle, not reports from a working evaluator.

The essential compatible relationship, regardless of layout, is:

```text
run/case + immutable original
  -> original open -> mesh -> effective default load -> baseline solve
  -> parameter proposal -> guard allow -> actual successful mutation
  -> new mesh -> effective default load -> fresh solve
  -> save execution -> immutable artifact bytes
  -> final claim citing that solve and artifact
```

For a rejected proposal, preserve `proposal -> guard reject -> returned rejection`
with **no corresponding CLI mutation**. A complete serialized execution ledger
is required to establish this absence. A missing ledger tail cannot prove the
guard prevented every later mutation.

For the intentionally flawed example, all IDs and JSON remain valid but a new
successful mutation is recorded after the cited solve. The final claim and save
refer to the newer geometry without a new solve. Expected: `STALE_SOLVE=fail`;
unknown evidence or a parser exception is not an adequate substitute for this
specific detection. Add missing-result and malformed-JSON fixtures separately
during implementation, so a syntax failure cannot accidentally satisfy the
semantic defect test.

## Required review before full implementation

Record producer proposal digest/revision, mapped fields, any exceptions, and
explicit review status for each track. Do not silently mark this list completed.

- [ ] Read SDK `docs/TRACE_CONTRACT_PROPOSAL.md` and map every required row above.
- [ ] Agree physical bundle layout, schema/version, field meanings, event ordering,
      call/attempt IDs, and completion semantics.
- [ ] Agree trusted original/policy source and literal default-load handling.
- [ ] Demonstrate separate rejected proposal, allowed-but-failed CLI command,
      actual successful mutation, and harness restoration records.
- [ ] Confirm actual PartLab stdout/save shapes and failed-action atomicity;
      document unknown behavior rather than assume it.
- [ ] Confirm fresh-solve linkage across mutation, reopen/reset, mesh/load, and
      read-only SF queries; include identical-value mutation behavior.
- [ ] Confirm saved bytes/sha256, expected output path, immutable snapshot capture,
      post-save edits, and final structured/text consistency.
- [ ] Producer supplies a complete example and a partial example; consumer parses
      them without importing producer decisions. Adapt consumer fixtures if needed.
- [ ] Preserve stable finding codes/status semantics and the schema-valid deliberate
      defect; define no-fix outcome/proof/budget fields.
- [ ] Both tracks explicitly acknowledge the same contract revision; Kanav settles
      remaining policy decisions. Until then compatibility is proposed only.

At the last preparation check on October 23, 2026 (ET), the SDK producer proposal
file was not yet present. Therefore field mapping and two-way review remain
pending, rather than failed or implicitly approved. The evidence requirements
and examples above are ready for that review; setup did not wait for its arrival.
