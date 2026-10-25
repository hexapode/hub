/-
  Trusted problem statement for {{title}} ({{slug}}).
  Uses core Lean 4 (no Mathlib download required for fast CI).
-/
namespace Statement

/-- Sum of `0 + 1 + ... + (n - 1)` corresponding to `(Finset.range n).sum id`. -/
def rangeSum : Nat → Nat
  | 0 => 0
  | n + 1 => rangeSum n + n

/-- Parameterized bound objective: prove `Goal c` for as small a natural `c` as possible. -/
def Goal (c : Nat) : Prop :=
  ∀ n : Nat, n ≥ 1 → rangeSum n ≤ c * n * n

end Statement
