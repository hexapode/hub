import Statement

namespace Submission

theorem rangeSum_le_sq (n : Nat) : Statement.rangeSum n ≤ n * n := by
  induction n with
  | zero => simp [Statement.rangeSum]
  | succ k ih =>
    simp [Statement.rangeSum]
    omega

theorem main : Statement.Goal 1 := by
  intro n _
  simp
  exact rangeSum_le_sq n

end Submission
