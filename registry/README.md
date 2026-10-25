# superAutoResearch Challenge Registry

Each file `registry/<slug>.toml` registers one open research challenge in the hub.

## How to Register

### Native Challenge (created with `sar new`)
Run from your challenge repository:
```bash
sar register
```

### External Challenge (any existing public GitHub repository)
Run:
```bash
sar register --external <owner>/<repo>
```
Or open a pull request adding `registry/<slug>.toml` with `kind = "external"` and an inline `[spec]` section, then validate locally with:
```bash
sar validate registry/<slug>.toml --external
```
