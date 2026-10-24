# Inspectable evaluation inputs

The complete current manifest is `fixtures/all-inputs.json`: the original 16
examples plus three unchanged SDK producer captures under `producer/`.
Two are completed live model runs (bracket and flange); the third is a scripted
guard check. [producer-provenance.json](producer-provenance.json) records the
source locations, IDs, origins and completion hashes. These captures were
created in the SDK track and copied here after inventory validation; no new
model call was made by this evaluator. The original `inputs.json` still selects
only the original 16 examples for backwards-compatible reproduction.

Run these bundles with `python3 evaluate.py --inputs fixtures/inputs.json
--output-dir /tmp/new-eval-reports` from the `evaluation/` directory. The input manifest
enumerates every requested run; no directory discovery or filename inference is
used. Generated checked outputs are indexed in
[reports/eval-verification/REPORTS.md](../reports/eval-verification/REPORTS.md).

Each example retains manifest, event ledger, raw CLI stdout/stderr, original
part bytes, task/policy snapshots, final visible message, structured outcome,
completion inventory, and any immutable saved/published artifact bytes. Some
negative examples deliberately omit or corrupt evidence; that is their test.

Fourteen examples have `evidence_kind=synthetic_fixture`. Solver values are
invented to isolate conditions: already safe, repaired, blocked proposal,
recovered CLI error, forbidden mutation then restoration, historical selection,
stale solve, wrong load, multiple parameters, overwritten publication, missing
artifact/result, partial tail, and honest search exhaustion.

`scripted_bracket_v3` and `scripted_flange_v1` have
`evidence_kind=preparation_check`. Their raw CLI outputs were captured by running
the pinned local binary against copies of the original parts in isolated
temporary sessions. Neither used a model. The bracket repair is delivered;
the flange example exhausts one candidate without finding a repair. It does
not prove that every allowed flange modification is infeasible.

Use `python3 scripts/build_examples.py --output /tmp/new-examples --real` to
create a fresh set and input manifest. Existing bundle destinations are refused.
The older simplified packaging examples remain in source history at `cadf11e`
under `eval_preparation/`; they are not part of the current runnable evaluator.
