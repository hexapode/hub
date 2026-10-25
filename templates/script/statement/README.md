# Problem Statement — Fast Integer Sort (`{{slug}}`)

Given a list `data: list[int]` of $N$ unsigned 32-bit integers generated deterministically from a fixed pseudorandom seed, return a newly sorted list in ascending order.

## Interface

Your submission must provide `solution.py` defining:

```python
def sort_integers(data: list[int]) -> list[int]:
    ...
```

## Verification

`verifier/score.py` generates the dataset with a fixed seed, invokes `sort_integers(list(data))`, verifies that the returned list is a valid ascending permutation of the input, and reports wall-clock execution time in seconds (`{"value": <seconds>}`).
