# Lean 4 Verifier

`sar verify` copies `statement/` into an isolated temporary Lake workspace, places your `Submission.lean` next to `Statement.lean`, generates `Check.lean`:

```lean
import Statement
import Submission

theorem __sar_check : Statement.Goal (<claimed>) := Submission.main
#print axioms __sar_check
```

and verifies that `lake env lean Check.lean` succeeds using only the `allowed_axioms` (`propext`, `Classical.choice`, `Quot.sound`).
