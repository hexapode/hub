# Manual Verifier

CI runs `sar verify` to check that the PR only adds a single `submissions/<id>/` directory, leaves frozen paths untouched, validates `submission.toml`, and includes `proof.md` within the size limit. Status is reported as `pending` until a listed reviewer approves or applies `sar:verified`.
