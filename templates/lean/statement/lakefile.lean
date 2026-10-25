import Lake
open Lake DSL

package «challenge» where
  moreLeanArgs := #["-DautoImplicit=false"]

@[default_target]
lean_lib «Statement» where
  roots := #[`Statement]

lean_lib «Submission» where
  roots := #[`Submission]
