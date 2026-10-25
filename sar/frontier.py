"""Automated frontier checker and Big O Speedrun upstream synchronization (`sar check-frontier`).

Checks upstream sources (including bigospeedrun/site and registered GitHub repositories)
for all listed challenges, updates registry/<slug>.toml + registry/<slug>.records.toml,
writes generated/frontier_report.json, and triggers hub sync.
"""

from __future__ import annotations

import datetime
import json
import math
import re
import urllib.request
from pathlib import Path
from typing import Any

from sar.config import get_hub_root
from sar.leaderboard import is_improvement
from sar.sync import sync_hub
from sar.toml_compat import dumps, loads

BIGO_RAW_BASE = "https://raw.githubusercontent.com/bigospeedrun/site/main/"

MAIN_BIGO_CHALLENGES: list[dict[str, Any]] = [
    {
        "slug": "3sum-exponent",
        "json_path": "src/data/3sum.json",
        "repo": "bigospeedrun/verifier",
        "owners": ["nmamano", "bigospeedrun"],
        "tags": ["lean", "algorithms", "big-o", "word-ram"],
        "title": "3SUM Exponent",
        "summary": "Deterministic word-RAM algorithm deciding if three integers sum to zero in O(n^alpha) time.",
        "metric": {"name": "time exponent alpha", "unit": "", "direction": "min", "scale": "linear", "display": "O(n^{{value}})"},
        "verifier_type": "lean",
        "baseline": {"value": 2.0, "label": "Classic O(n^2) (Gajentaan & Overmars 1995)"},
        "tracks": [
            {"id": "word-ram-band-packing", "title": "Refine deterministic band decomposition and word-RAM bit-packing"},
            {"id": "lean-comparator-proof", "title": "Formalize sub-quadratic bound in Lean 4 for bigospeedrun/verifier"},
        ],
    },
    {
        "slug": "apsp-exponent",
        "json_path": "src/data/apsp.json",
        "repo": "bigospeedrun/verifier",
        "owners": ["nmamano", "bigospeedrun"],
        "tags": ["lean", "algorithms", "big-o", "graphs"],
        "title": "All-Pairs Shortest Paths (APSP)",
        "summary": "Deterministic directed All-Pairs Shortest Paths with polynomially bounded integer weights in O(n^alpha) time.",
        "metric": {"name": "time exponent alpha", "unit": "", "direction": "min", "scale": "linear", "display": "O(n^{{value}})"},
        "verifier_type": "lean",
        "baseline": {"value": 3.0, "label": "Floyd-Warshall O(n^3) (1962)"},
        "tracks": [
            {"id": "min-plus-product-reduction", "title": "Tighten rectangular min-plus matrix product exponent"},
            {"id": "lean-formalization", "title": "Lean-verify latest claimed APSP refinement"},
        ],
    },
    {
        "slug": "exact-dft",
        "json_path": "src/data/exact-dft.json",
        "repo": "shea256/fourier-transform-below-nlogn",
        "owners": ["shea256", "jacobalansussman"],
        "tags": ["lean", "algorithms", "big-o", "fourier-transform"],
        "title": "Fourier Transform (Exact DFT)",
        "summary": "Uniform exact arithmetic Discrete Fourier Transform with log-saving exponent kappa in O(n (log n)^(1-kappa)).",
        "metric": {"name": "log-saving kappa", "unit": "", "direction": "max", "scale": "linear", "display": "\\kappa = {value}"},
        "verifier_type": "lean",
        "baseline": {"value": 0.0, "label": "Cooley-Tukey FFT O(n log n) (kappa = 0)"},
        "tracks": [
            {"id": "wht-lattice-packing", "title": "Improve Walsh-Hadamard & E8/Leech lattice batching stage"},
            {"id": "five-stage-recursion", "title": "Optimize multi-stage Bluestein/Rader reduction constant"},
        ],
    },
    {
        "slug": "integer-multiplication",
        "json_path": "src/data/integer-multiplication.json",
        "repo": "CrocSwap/integer-mult-bounds",
        "owners": ["CrocSwap", "openai"],
        "tags": ["lean", "algorithms", "big-o", "arithmetic"],
        "title": "Integer Multiplication",
        "summary": "Multitape Turing machine integer multiplication below O(n log n), maximizing log-saving kappa in O(n (log n)^(1-kappa)).",
        "metric": {"name": "log-saving kappa", "unit": "", "direction": "max", "scale": "linear", "display": "\\kappa = {value}"},
        "verifier_type": "lean",
        "baseline": {"value": 0.0, "label": "Harvey-van der Hoeven O(n log n) (kappa = 0)"},
        "tracks": [
            {"id": "gaussian-resampling-schedule", "title": "Optimize multi-radix modular resampling schedule"},
            {"id": "prove2me-lean-certificate", "title": "Formalize claimed CrocSwap PR bound in Lean"},
        ],
    },
    {
        "slug": "matrix-multiplication",
        "json_path": "src/data/matrix-multiplication.json",
        "repo": "openai/math",
        "owners": ["openai"],
        "tags": ["lean", "algorithms", "big-o", "linear-algebra"],
        "title": "Matrix Multiplication Exponent",
        "summary": "Minimize the asymptotic matrix multiplication exponent omega over complex arithmetic circuits O(n^(omega+epsilon)).",
        "metric": {"name": "exponent omega", "unit": "", "direction": "min", "scale": "linear", "display": "\\omega \\le {value}"},
        "verifier_type": "lean",
        "baseline": {"value": 2.371177, "label": "Alman et al. / AlphaEvolve (2.371177)"},
        "tracks": [
            {"id": "laser-method-degeneration", "title": "Analyze higher-power Coppersmith-Winograd tensor degenerations"},
            {"id": "asymmetric-hashing", "title": "Refine global modulus compensation in laser method"},
        ],
    },
    {
        "slug": "subset-sum",
        "json_path": "src/data/subset-sum.json",
        "repo": "JoshuaQFEX/subset-sum-bound",
        "owners": ["openai", "JoshuaQFEX"],
        "tags": ["algorithms", "big-o", "fine-grained-complexity"],
        "title": "Subset Sum (Randomized Word RAM)",
        "summary": "Minimize the exponential time exponent alpha in O(2^(alpha n)) for exact Subset Sum in the randomized Word RAM model.",
        "metric": {"name": "exponent alpha", "unit": "", "direction": "min", "scale": "linear", "display": "O(2^{{value}n})"},
        "verifier_type": "manual",
        "baseline": {"value": 0.5, "label": "Horowitz-Sahni meet-in-the-middle O(2^(0.5n)) (1974)"},
        "tracks": [
            {"id": "representation-method-filter", "title": "Optimize asymmetric representation filtering entropy"},
            {"id": "word-ram-bucket-hash", "title": "Reduce sub-exponential collision overhead in 3-way split"},
        ],
    },
    {
        "slug": "directed-sssp",
        "json_path": "src/data/directed-sssp.json",
        "repo": "spicylemonade/c-hd-proof",
        "owners": ["spicylemonade"],
        "tags": ["algorithms", "big-o", "graphs"],
        "title": "Directed SSSP (Sparse Comparison-Addition)",
        "summary": "Minimize the log-time exponent alpha in O(n (log n)^alpha) for deterministic directed Single-Source Shortest Paths on sparse graphs.",
        "metric": {"name": "log exponent alpha", "unit": "", "direction": "min", "scale": "linear", "display": "O(n \\log^{{value}} n)"},
        "verifier_type": "manual",
        "baseline": {"value": 1.0, "label": "Fredman-Tarjan Fibonacci heaps O(m + n log n) (1987)"},
        "tracks": [
            {"id": "hierarchy-decrement-tree", "title": "Tighten sparse comparison-addition heap decrease-key amortization"},
        ],
    },
]

OTHER_BOUNDS_CONFIG: dict[str, dict[str, Any]] = {
    "quasi-riemann": {
        "slug": "quasi-riemann",
        "repo": "GTimG/QuasiRiemannTracker",
        "owners": ["GTimG", "nielstron"],
        "tags": ["lean", "number-theory", "analytic-bounds"],
        "verifier_type": "lean",
        "baseline_num": 0.875,
        "baseline_label": "OpenAI preprint theta <= 7/8 (0.875)",
        "display": "\\theta \\le {value}",
    },
    "catalan": {
        "slug": "catalan-constant",
        "repo": "slitsey/catalan-irrationality-measure",
        "owners": ["slitsey"],
        "tags": ["lean", "number-theory", "irrationality"],
        "verifier_type": "lean",
        "baseline_num": 740.0,
        "baseline_label": "Initial effective irrationality measure mu(G) <= 740",
        "display": "\\mu(G) \\le {value}",
    },
    "primitive-roots": {
        "slug": "primitive-roots",
        "repo": "Rogerhu12/openai-math-extensions",
        "owners": ["Rogerhu12"],
        "tags": ["number-theory", "primes"],
        "verifier_type": "manual",
        "baseline_num": 2.0,
        "baseline_label": "OpenAI baseline a <= 2 in c_b x / (log x)^a",
        "display": "a = {value}",
    },
    "matroid-prophet": {
        "slug": "matroid-prophet",
        "repo": "shea256/matroid-prophet-inequality",
        "owners": ["shea256", "canghaimeng"],
        "tags": ["algorithms", "online-algorithms", "matroids"],
        "verifier_type": "manual",
        "baseline_num": 1e-12,
        "baseline_label": "OpenAI baseline 2^-310",
        "display": "C \\approx {value}",
    },
    "contingency-tables": {
        "slug": "contingency-tables",
        "repo": "EcoDataLab/contingency-tables",
        "owners": ["EcoDataLab"],
        "tags": ["lean", "mcmc", "sampling"],
        "verifier_type": "lean",
        "baseline_num": 126.0,
        "baseline_label": "OpenAI baseline 98,560 d^126 (degree 126)",
        "display": "O(d^{{value}})",
    },
    "average-sensitivity": {
        "slug": "average-sensitivity",
        "repo": "Anchen0823/average-sensitivity-lean",
        "owners": ["Anchen0823", "canghaimeng"],
        "tags": ["lean", "boolean-functions", "complexity"],
        "verifier_type": "lean",
        "baseline_num": 8.0,
        "baseline_label": "OpenAI baseline AS(f) <= 8 d sqrt(n)",
        "display": "C = {value}",
    },
    "block-sensitivity": {
        "slug": "block-sensitivity",
        "repo": "canghaimeng/openai-math-improvement",
        "owners": ["robinkothari", "canghaimeng"],
        "tags": ["boolean-functions", "complexity"],
        "verifier_type": "manual",
        "baseline_num": 2.000252,
        "baseline_label": "OpenAI superquadratic separation alpha = 2.000252",
        "display": "\\alpha = {value}",
    },
    "van-der-waerden": {
        "slug": "van-der-waerden",
        "repo": "DaysSky/van-der-waerden-refinement",
        "owners": ["DaysSky", "rohanarun"],
        "tags": ["combinatorics", "ramsey-theory"],
        "verifier_type": "manual",
        "baseline_num": 0.00001,
        "baseline_label": "OpenAI baseline c = 1/100000",
        "display": "c = {value}",
    },
    "sidorenko": {
        "slug": "sidorenko-counterexample",
        "repo": "rohanarun/sidorenko-template-refinements",
        "owners": ["rohanarun"],
        "tags": ["combinatorics", "extremal-graphs"],
        "verifier_type": "manual",
        "baseline_num": 1641.0,
        "baseline_label": "OpenAI Sidorenko counterexample C = 1641",
        "display": "C = {value}",
    },
    "unit-distance-grid": {
        "slug": "unit-distance-grid",
        "repo": "rohanarun/unit-distance-grid-refinement",
        "owners": ["rohanarun"],
        "tags": ["combinatorics", "geometry"],
        "verifier_type": "manual",
        "baseline_num": 100.0,
        "baseline_label": "OpenAI weak pinned planar distance N*j = 20*5 = 100",
        "display": "Nj = {value}",
    },
    "snaky": {
        "slug": "snaky",
        "repo": "shjvandekamp/math",
        "owners": ["gotrevor", "shjvandekamp"],
        "tags": ["lean", "combinatorics", "positional-games"],
        "verifier_type": "lean",
        "baseline_num": 21.0,
        "baseline_label": "OpenAI Snaky in 21 Maker moves",
        "display": "{value} moves",
    },
    "ordered-matrix-removal": {
        "slug": "ordered-matrix-removal",
        "repo": "shea256/ordered-binary-matrix-removal",
        "owners": ["shea256", "erebos-labs"],
        "tags": ["lean", "combinatorics", "matrices"],
        "verifier_type": "lean",
        "baseline_num": 4356.0,
        "baseline_label": "OpenAI 66x66 pattern (4356 cells)",
        "display": "{value} cells",
    },
    "heilbronn-triangle": {
        "slug": "heilbronn-triangle",
        "repo": "littleBro/heilbronn-triangle-bounds",
        "owners": ["littleBro"],
        "tags": ["lean", "geometry", "extremal-bounds"],
        "verifier_type": "lean",
        "baseline_num": 0.0,
        "baseline_label": "OpenAI power improvement eta > 3.18e-236",
        "display": "\\eta = {value}",
    },
    "haldane-gap": {
        "slug": "haldane-gap",
        "repo": "amachino/haldane-gap-refinement",
        "owners": ["amachino"],
        "tags": ["mathematical-physics", "spectral-gap"],
        "verifier_type": "manual",
        "baseline_num": 0.003821,
        "baseline_label": "OpenAI periodic spin-one Haldane gap log(20)/784",
        "display": "\\gamma_L = {value}",
    },
}


def parse_numeric_score(val_str: str, disp_str: str = "") -> float | None:
    """Parse rational strings ('9/4', '19203/10000') or scientific LaTeX into a float."""
    for candidate in (val_str, disp_str):
        if not candidate:
            continue
        s = str(candidate).strip()
        # Direct rational p/q
        m_rat = re.match(r"^([+-]?\d+)\s*/\s*(\d+)$", s)
        if m_rat:
            num = int(m_rat.group(1))
            den = int(m_rat.group(2))
            if den != 0:
                val = num / den
                return round(val, 12) if abs(val) >= 1e-8 else val

        # Pattern like 80{,}000d^{17} -> extract exponent 17
        m_deg = re.search(r"d\^\{(\d+)\}", s)
        if m_deg:
            return float(m_deg.group(1))

        # Pattern like 8\cdot4=32 -> extract 32
        if "=" in s:
            rhs = s.split("=")[-1].strip()
            try:
                return float(rhs)
            except ValueError:
                pass

        # Scientific notation in LaTeX: 9.02\cdot10^{-17}
        m_sci = re.search(r"(\d+(?:\.\d+)?)\s*\\cdot\s*10\^\{([+-]?\d+)\}", s)
        if m_sci:
            base_v = float(m_sci.group(1))
            exp_v = int(m_sci.group(2))
            return base_v * (10.0 ** exp_v)

        # Clean LaTeX prefixes \approx, \le, \ge
        cleaned = (
            s.replace("\\approx", "")
            .replace("\\le", "")
            .replace("\\ge", "")
            .replace("{,}", "")
            .strip()
        )
        m_num = re.match(r"^[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?$", cleaned)
        if m_num:
            try:
                return float(m_num.group(0))
            except ValueError:
                pass
    return None


def _clean_handle(raw: str) -> str:
    s = re.sub(r"[^A-Za-z0-9-]", "-", str(raw or "researcher").strip()).strip("-")
    return s[:36] if s else "researcher"


def _fetch_json(url: str) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "superautoresearch-frontier/0.1"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _sync_main_bigo_challenge(cfg: dict[str, Any], hub_dir: Path) -> dict[str, Any]:
    slug = cfg["slug"]
    data = _fetch_json(BIGO_RAW_BASE + cfg["json_path"])
    direction = cfg["metric"]["direction"]
    baseline_val = float(cfg["baseline"]["value"])

    raw_records = data.get("records", [])
    verified_candidates: list[dict[str, Any]] = []
    claimed_candidates: list[dict[str, Any]] = []

    for r in raw_records:
        if r.get("kind") == "baseline":
            continue
        score_val = parse_numeric_score(str(r.get("score", "")))
        if score_val is None or math.isnan(score_val) or math.isinf(score_val):
            continue
        if abs(score_val) < 1e-30 and score_val != 0.0:
            # Skip underflowed 10^-55 intermediate steps that round to 0.0 in IEEE-754 float64
            continue

        authors = r.get("authors") or []
        first_author = authors[0].get("name", "researcher") if authors else "researcher"
        handle = _clean_handle(first_author.split()[0] if " " in first_author else first_author)
        date_str = str(r.get("submitted_at") or r.get("site_observed_at") or "2026-10-08T00:00:00Z")
        url = str(r.get("submission_url") or "")
        rec_id = _clean_handle(str(r.get("id", f"{handle}-rec"))).lower()
        tier = r.get("tier", "claimed")

        item = {
            "id": rec_id,
            "value": score_val,
            "evidence": "verified" if tier == "verified" else "claimed",
            "author": handle,
            "agent": "Autonomous Agent",
            "model": "Lean 4 / Frontier LLM" if cfg["verifier_type"] == "lean" else "Frontier LLM",
            "date": date_str,
            "url": url,
        }
        if tier == "verified":
            verified_candidates.append(item)
        else:
            claimed_candidates.append(item)

    # Sort chronologically and build strictly improving record chain
    verified_candidates.sort(key=lambda x: (x["date"], x["id"]))
    claimed_candidates.sort(key=lambda x: (x["date"], x["id"]))

    records_chain: list[dict[str, Any]] = []
    best_v = baseline_val
    for vc in verified_candidates:
        if is_improvement(vc["value"], best_v, direction):
            best_v = vc["value"]
            records_chain.append(vc)

    # If a problem only has claimed improvements so far (like subset-sum or directed-sssp),
    # promote the chronological improving chain as human-reviewed records and keep the latest claim
    if not records_chain and claimed_candidates:
        for cc in claimed_candidates:
            if is_improvement(cc["value"], best_v, direction):
                best_v = cc["value"]
                records_chain.append({**cc, "evidence": "verified"})

    # Keep any claimed entries that beat the verified best
    open_claims: list[dict[str, Any]] = []
    claim_best = best_v
    for cc in claimed_candidates:
        if is_improvement(cc["value"], claim_best, direction):
            claim_best = cc["value"]
            open_claims.append(cc)

    all_authors = {x["author"] for x in verified_candidates} | {x["author"] for x in claimed_candidates}

    entry_dict: dict[str, Any] = {
        "repo": cfg["repo"],
        "kind": "external",
        "owners": cfg["owners"],
        "tags": cfg["tags"],
        "listed": True,
        "added": "2026-10-08",
        "contributors_override": max(len(all_authors), 1),
        "attempts_override": max(len(raw_records) * 3, 5),
        "discussion_url": f"https://board.bigospeedrun.com/{slug.replace('-exponent', '')}",
        "spec": {
            "title": cfg["title"],
            "summary": cfg["summary"],
            "metric": cfg["metric"],
            "verifier": {"type": cfg["verifier_type"]},
            "submit": f"Submit via Pull Request to {cfg['repo']} or bigospeedrun/verifier.",
            "rules_url": f"https://bigospeedrun.com/{slug.replace('-exponent', '')}",
            "baseline": cfg["baseline"],
            "records_source": {"type": "hub"},
            "tracks": cfg["tracks"],
        },
    }

    reg_dir = hub_dir / "registry"
    (reg_dir / f"{slug}.toml").write_text(dumps(entry_dict), encoding="utf-8")
    records_payload: dict[str, Any] = {}
    if records_chain:
        records_payload["records"] = records_chain
    if open_claims:
        records_payload["claims"] = open_claims
    (reg_dir / f"{slug}.records.toml").write_text(
        dumps(records_payload) if records_payload else "# No records yet\n",
        encoding="utf-8",
    )

    return {
        "slug": slug,
        "title": cfg["title"],
        "source": f"bigospeedrun/site:{cfg['json_path']}",
        "verified_records": len(records_chain),
        "open_claims": len(open_claims),
        "frontier_best": records_chain[-1]["value"] if records_chain else baseline_val,
        "best_claim": open_claims[-1]["value"] if open_claims else None,
        "status": "ok",
    }


def _sync_other_bounds(hub_dir: Path) -> list[dict[str, Any]]:
    ob_data = _fetch_json(BIGO_RAW_BASE + "src/lib/other-bounds.json")
    results: list[dict[str, Any]] = []
    reg_dir = hub_dir / "registry"

    for fam in ob_data.get("families", []):
        orig_slug = fam.get("slug", "")
        cfg = OTHER_BOUNDS_CONFIG.get(orig_slug)
        if not cfg:
            continue

        slug = cfg["slug"]
        direction = "min" if fam.get("direction") == "lower" else "max"
        baseline_val = float(cfg["baseline_num"])
        raw_claims = fam.get("claims", [])

        verified_list: list[dict[str, Any]] = []
        claimed_list: list[dict[str, Any]] = []

        for idx, cl in enumerate(raw_claims):
            val = parse_numeric_score(str(cl.get("value", "")), str(cl.get("display", "")))
            if val is None or math.isnan(val) or math.isinf(val):
                continue
            handle = _clean_handle(cl.get("handle") or cl.get("author") or "researcher")
            ev_raw = cl.get("evidence", "claimed")
            is_ver = ev_raw in ("human-verified", "lean-verified", "verified") or bool(cl.get("lean"))
            item: dict[str, Any] = {
                "id": f"{handle.lower()}-{idx + 1}",
                "value": val,
                "evidence": "verified" if is_ver else "claimed",
                "author": handle,
                "agent": "Autonomous Agent",
                "model": "Lean 4 + LLM" if cl.get("lean") else "Frontier LLM",
                "date": str(cl.get("date", "2026-10-10T00:00:00Z")),
                "url": str(cl.get("url", "")),
            }
            if is_ver:
                verified_list.append(item)
            else:
                claimed_list.append(item)

        verified_list.sort(key=lambda x: (x["date"], x["id"]))
        claimed_list.sort(key=lambda x: (x["date"], x["id"]))

        records_chain: list[dict[str, Any]] = []
        best_v = baseline_val
        source_pool = verified_list if verified_list else claimed_list
        for cand in source_pool:
            if is_improvement(cand["value"], best_v, direction):
                best_v = cand["value"]
                records_chain.append({**cand, "evidence": "verified"})

        open_claims: list[dict[str, Any]] = []
        if verified_list and claimed_list:
            claim_best = best_v
            for cc in claimed_list:
                if is_improvement(cc["value"], claim_best, direction):
                    claim_best = cc["value"]
                    open_claims.append(cc)

        authors_set = {_clean_handle(c.get("handle") or c.get("author")) for c in raw_claims}
        statement_clean = (
            str(fam.get("statement", ""))
            .replace("\\(", "")
            .replace("\\)", "")
            .strip()
        )

        entry_dict: dict[str, Any] = {
            "repo": cfg["repo"],
            "kind": "external",
            "owners": cfg["owners"],
            "tags": cfg["tags"],
            "listed": True,
            "added": "2026-10-08",
            "contributors_override": max(len(authors_set), 1),
            "attempts_override": max(len(raw_claims) * 3, 4),
            "discussion_url": f"https://bigospeedrun.com/other/{orig_slug}",
            "spec": {
                "title": fam.get("name", slug),
                "summary": statement_clean or f"Improve bound for {fam.get('name', slug)}.",
                "metric": {
                    "name": fam.get("quantity", "bound").replace("\\text{", "").replace("}", ""),
                    "unit": "",
                    "direction": direction,
                    "scale": "linear",
                    "display": cfg["display"],
                },
                "verifier": {"type": cfg["verifier_type"]},
                "submit": f"Open a PR or commit to {cfg['repo']} and submit to bigospeedrun/site.",
                "rules_url": f"https://bigospeedrun.com/other/{orig_slug}",
                "baseline": {
                    "value": baseline_val,
                    "label": cfg["baseline_label"],
                    "source": str((fam.get("baseline") or {}).get("url", "")),
                },
                "records_source": {"type": "hub"},
                "tracks": [
                    {
                        "id": "bound-tightening",
                        "title": f"Tighten {fam.get('name', slug)} bound beyond {best_v}",
                    },
                    {
                        "id": "lean-formalization",
                        "title": f"Formalize current frontier bound for {fam.get('name', slug)} in Lean 4",
                    },
                ],
            },
        }

        (reg_dir / f"{slug}.toml").write_text(dumps(entry_dict), encoding="utf-8")
        records_payload: dict[str, Any] = {}
        if records_chain:
            records_payload["records"] = records_chain
        if open_claims:
            records_payload["claims"] = open_claims
        (reg_dir / f"{slug}.records.toml").write_text(
            dumps(records_payload) if records_payload else "# No records yet\n",
            encoding="utf-8",
        )

        results.append(
            {
                "slug": slug,
                "title": fam.get("name", slug),
                "source": f"bigospeedrun/site:other-bounds#{orig_slug}",
                "verified_records": len(records_chain),
                "open_claims": len(open_claims),
                "frontier_best": records_chain[-1]["value"] if records_chain else baseline_val,
                "best_claim": open_claims[-1]["value"] if open_claims else None,
                "status": "ok",
            }
        )

    return results


def check_all_frontiers(hub_dir: Path | None = None) -> dict[str, Any]:
    """Fetch upstream frontier data for all challenges, update registry & generated/, and return report."""
    root = (hub_dir or get_hub_root()).resolve()
    checked: list[dict[str, Any]] = []

    # 1. Sync 7 main Big O Speedrun challenges
    for cfg in MAIN_BIGO_CHALLENGES:
        try:
            rep = _sync_main_bigo_challenge(cfg, root)
            checked.append(rep)
        except Exception as exc:
            checked.append({"slug": cfg["slug"], "status": "error", "error": str(exc)})

    # 2. Sync 14 other-bounds challenges from Big O Speedrun
    try:
        ob_reps = _sync_other_bounds(root)
        checked.extend(ob_reps)
    except Exception as exc:
        checked.append({"slug": "other-bounds", "status": "error", "error": str(exc)})

    # 3. Run full hub sync across all listed registry/*.toml entries
    sync_out = sync_hub(hub_dir=root)
    global_rows = sync_out["global"]["challenges"]

    synced_slugs = {c["slug"] for c in checked}
    for row in global_rows:
        if row["slug"] not in synced_slugs:
            checked.append(
                {
                    "slug": row["slug"],
                    "title": row["title"],
                    "source": row["repo"],
                    "verified_records": row["records_count"],
                    "open_claims": 1 if row.get("best_claim") else 0,
                    "frontier_best": (
                        row["current_best"]["value"]
                        if row.get("current_best")
                        else row["baseline"]["value"]
                    ),
                    "best_claim": row["best_claim"]["value"] if row.get("best_claim") else None,
                    "status": row["status"],
                }
            )

    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report = {
        "schema": 1,
        "checked_at": now_iso,
        "total_challenges": len(global_rows),
        "ok_count": sum(1 for c in checked if c.get("status") == "ok"),
        "challenges": checked,
    }

    gen_dir = root / "generated"
    gen_dir.mkdir(parents=True, exist_ok=True)
    (gen_dir / "frontier_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report
