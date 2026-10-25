"""Milestone 1 tests: JSON Schemas and `sar validate` for all §4 formats."""

from __future__ import annotations

import unittest

from sar.validate import (
    ValidationError,
    validate_leaderboard_dict,
    validate_registry_dict,
    validate_spec_dict,
    validate_submission_dict,
)


class TestMilestone1SchemasAndValidate(unittest.TestCase):
    def test_valid_and_invalid_registry_entry(self) -> None:
        valid_native = {
            "repo": "alice/3sum-exponent",
            "kind": "native",
            "owners": ["alice"],
            "tags": ["lean", "algorithms"],
            "listed": True,
            "added": "2026-10-25",
            "statement_hash": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            "ref": "main",
        }
        validate_registry_dict(valid_native, slug="3sum-exponent")

        # Invalid slug
        with self.assertRaises(ValidationError):
            validate_registry_dict(valid_native, slug="INVALID_SLUG!")

        # Missing owners
        invalid_no_owners = dict(valid_native)
        invalid_no_owners["owners"] = []
        with self.assertRaises(ValidationError):
            validate_registry_dict(invalid_no_owners, slug="3sum-exponent")

        # External entry without [spec] must fail
        invalid_ext = {
            "repo": "KellerJordan/modded-nanogpt",
            "kind": "external",
            "owners": ["KellerJordan"],
        }
        with self.assertRaises(ValidationError):
            validate_registry_dict(invalid_ext, slug="nanogpt")

    def test_valid_and_invalid_challenge_spec(self) -> None:
        valid_spec = {
            "schema": 1,
            "slug": "3sum-exponent",
            "title": "3SUM exponent",
            "summary": "Lower the exponent of 3SUM.",
            "owners": ["alice"],
            "tags": ["lean", "algorithms"],
            "template": "lean@1",
            "hub": "superautoresearch/hub",
            "metric": {
                "name": "exponent",
                "unit": "",
                "direction": "min",
                "scale": "linear",
                "display": "n^{value}",
            },
            "baseline": {"value": 2.0, "label": "Classic O(n^2)"},
            "verifier": {
                "type": "lean",
                "timeout": "30m",
                "runner": "ubuntu-latest",
                "statement": "statement/Statement.lean",
                "theorem_name": "Submission.main",
            },
            "submission": {"required_files": ["Submission.lean"], "max_size_mb": 20},
            "tracks": [
                {"id": "derandomize", "title": "Derandomize step 2"},
                {"id": "formalize-record-4", "title": "Lean-verify record #4"},
            ],
        }
        validate_spec_dict(valid_spec)

        # Duplicate track IDs must fail
        dup_tracks = dict(valid_spec)
        dup_tracks["tracks"] = [
            {"id": "dup", "title": "Track 1"},
            {"id": "dup", "title": "Track 2"},
        ]
        with self.assertRaises(ValidationError):
            validate_spec_dict(dup_tracks)

        # Invalid metric direction must fail
        bad_metric = dict(valid_spec)
        bad_metric["metric"] = {"name": "exp", "direction": "sideways"}
        with self.assertRaises(ValidationError):
            validate_spec_dict(bad_metric)

    def test_valid_and_invalid_submission(self) -> None:
        valid_sub = {
            "schema": 1,
            "title": "Fused band decomposition",
            "author": "alice",
            "claimed": 1.9203,
            "builds_on": "bob-band-split",
            "track": "derandomize",
            "agent": "Claude Code",
            "model": "claude-opus-5-5",
            "description": "Short explanation of the idea.",
        }
        validate_submission_dict(valid_sub)

        # Invalid model string (contains disallowed characters)
        bad_model = dict(valid_sub)
        bad_model["model"] = "bad/model$name!"
        with self.assertRaises(ValidationError):
            validate_submission_dict(bad_model)

        # Missing required description
        no_desc = {k: v for k, v in valid_sub.items() if k != "description"}
        with self.assertRaises(ValidationError):
            validate_submission_dict(no_desc)

    def test_valid_and_invalid_leaderboard(self) -> None:
        valid_lb = {
            "schema": 1,
            "slug": "3sum-exponent",
            "metric": {"name": "exponent", "unit": "", "direction": "min", "scale": "linear"},
            "baseline": {"value": 2.0, "label": "Classic O(n^2)"},
            "records": [
                {
                    "id": "carol-first-break",
                    "value": 1.9992,
                    "evidence": "verified",
                    "author": "carol",
                    "date": "2026-10-08T07:01:00Z",
                }
            ],
            "claims": [],
            "contributors": 1,
            "attempts": 5,
            "updated": "2026-10-25T15:17:00Z",
        }
        validate_leaderboard_dict(valid_lb)

        bad_lb = dict(valid_lb)
        bad_lb["contributors"] = -3
        with self.assertRaises(ValidationError):
            validate_leaderboard_dict(bad_lb)


if __name__ == "__main__":
    unittest.main()
