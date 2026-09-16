#!/usr/bin/env python3
"""
generate_synthetic_data.py

Generates valid, randomized synthetic Prover.toml input files for each of
the four benchmark scenarios described in Chapter 3 (Section 3.7), so that
the benchmarking harness (run_benchmark.py) has fresh, varying, but always
VALID inputs for every trial.

Why this script exists (and why it shells out to Noir):
----------------------------------------------------------------
Scenarios 3 and 4 require a private set of attributes to hash to a
PUBLIC Poseidon commitment (Scenario 3) or to a public Merkle registry
root (Scenario 4). You cannot fabricate a "random" commitment or root by
hand -- it has to be the *actual* Poseidon hash of the randomly generated
attributes, computed with the exact same hash function and parameters the
real circuit uses. Rather than re-implementing BN254 Poseidon in Python
(a significant undertaking, and a fresh source of bugs), this script calls
three tiny helper Noir programs under tools/hash2_helper, tools/hash8_helper,
and tools/hash16_helper via `nargo execute`, which print the correct hash
using the exact same library (noir-lang/poseidon v0.3.0) the real circuits
depend on. This guarantees the synthetic data is always cryptographically
consistent with what the circuit will check.

Usage:
    python3 generate_synthetic_data.py --runs 30 --out ../data

Requires `nargo` to be on PATH.
"""

import argparse
import os
import random
import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
TOOLS_DIR = PROJECT_ROOT / "tools"

HASH_RE = re.compile(r"HASH(?:8|16)?=0x([0-9a-fA-F]+)")


def run_hash_helper(helper_name: str, prover_toml_body: str) -> int:
    """Writes Prover.toml for a hash helper, runs nargo execute, parses the
    printed hash value, and returns it as a Python integer (field element)."""
    helper_dir = TOOLS_DIR / helper_name
    prover_path = helper_dir / "Prover.toml"
    prover_path.write_text(prover_toml_body)

    result = subprocess.run(
        ["nargo", "execute"],
        cwd=helper_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"{helper_name} failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    match = HASH_RE.search(result.stdout)
    if not match:
        raise RuntimeError(f"Could not find HASH= output from {helper_name}: {result.stdout}")
    return int(match.group(1), 16)


def hash2(a: int, b: int) -> int:
    body = f'a = "{a}"\nb = "{b}"\n'
    return run_hash_helper("hash2_helper", body)


def hash8(fields8) -> int:
    body = "fields = [" + ", ".join(f'"{f}"' for f in fields8) + "]\n"
    return run_hash_helper("hash8_helper", body)


def hash16(fields16) -> int:
    body = "fields = [" + ", ".join(f'"{f}"' for f in fields16) + "]\n"
    return run_hash_helper("hash16_helper", body)


def gen_scenario1(rng: random.Random) -> dict:
    minimum_age = 18
    age = rng.randint(minimum_age, minimum_age + 60)  # always valid
    return {"age": age, "minimum_age": minimum_age}


def gen_scenario2(rng: random.Random) -> dict:
    minimum_age = 18
    minimum_income = 3000
    allowed_countries = [1, 44, 233]
    allowed_tiers = [1, 2, 3]
    return {
        "age": rng.randint(minimum_age, minimum_age + 60),
        "income": rng.randint(minimum_income, minimum_income + 20000),
        "country_code": rng.choice(allowed_countries),
        "membership_tier": rng.choice(allowed_tiers),
        "minimum_age": minimum_age,
        "minimum_income": minimum_income,
        "allowed_countries": allowed_countries,
        "allowed_membership_tiers": allowed_tiers,
    }


def gen_scenario3(rng: random.Random) -> dict:
    minimum_age = 18
    minimum_income = 3000
    minimum_credit_score = 600
    attrs = [
        rng.randint(minimum_age, minimum_age + 60),        # age
        rng.randint(minimum_income, minimum_income + 20000),  # income
        rng.choice([1, 44, 233]),                          # country_code
        rng.choice([1, 2, 3]),                             # membership_tier
        rng.randint(minimum_credit_score, 850),            # credit_score
        rng.randint(0, 40),                                # years_employed
        rng.randint(1, 5),                                 # education_level
        rng.randint(0, 30),                                # residency_years
    ]
    commitment = hash8(attrs)
    return {
        "age": attrs[0], "income": attrs[1], "country_code": attrs[2],
        "membership_tier": attrs[3], "credit_score": attrs[4],
        "years_employed": attrs[5], "education_level": attrs[6],
        "residency_years": attrs[7],
        "minimum_age": minimum_age, "minimum_income": minimum_income,
        "minimum_credit_score": minimum_credit_score,
        "credential_commitment": commitment,
    }


def gen_scenario4(rng: random.Random) -> dict:
    minimum_age = 18
    minimum_income = 3000
    fields16 = [rng.randint(1, 100000) for _ in range(16)]
    fields16[0] = rng.randint(minimum_age, minimum_age + 60)         # age
    fields16[1] = rng.randint(minimum_income, minimum_income + 20000)  # income

    leaf = hash16(fields16)

    # Build a depth-4 Merkle path with random sibling values, walking a
    # random left/right direction at each level, using the SAME hash2
    # helper the circuit uses -- guaranteeing the root is genuinely valid.
    siblings = [rng.randint(1, 10 ** 9) for _ in range(4)]
    index_bits = [rng.choice([True, False]) for _ in range(4)]

    current = leaf
    for sib, bit in zip(siblings, index_bits):
        current = hash2(current, sib) if not bit else hash2(sib, current)
    registry_root = current

    return {
        "fields": fields16,
        "minimum_age": minimum_age,
        "minimum_income": minimum_income,
        "merkle_path": siblings,
        "merkle_index_bits": index_bits,
        "registry_root": registry_root,
    }


def to_toml(data: dict) -> str:
    lines = []
    for key, value in data.items():
        if isinstance(value, bool):
            lines.append(f"{key} = {str(value).lower()}")
        elif isinstance(value, list):
            if len(value) > 0 and isinstance(value[0], bool):
                inner = ", ".join(str(v).lower() for v in value)
            else:
                inner = ", ".join(f'"{v}"' for v in value)
            lines.append(f"{key} = [{inner}]")
        else:
            lines.append(f'{key} = "{value}"')
    return "\n".join(lines) + "\n"


SCENARIOS = {
    "scenario1_minimal": gen_scenario1,
    "scenario2_multi_attr": gen_scenario2,
    "scenario3_full_integrity": gen_scenario3,
    "scenario4_advanced_identity": gen_scenario4,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=30, help="Trials per scenario (N >= 30 recommended)")
    parser.add_argument("--out", type=str, default=str(PROJECT_ROOT / "data" / "prover_inputs"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    out_root = Path(args.out)

    for scenario, generator in SCENARIOS.items():
        scenario_dir = out_root / scenario
        scenario_dir.mkdir(parents=True, exist_ok=True)
        print(f"Generating {args.runs} valid trials for {scenario} ...")
        for run_id in range(1, args.runs + 1):
            data = generator(rng)
            toml_text = to_toml(data)
            (scenario_dir / f"run_{run_id:03d}.toml").write_text(toml_text)
        print(f"  -> wrote {args.runs} files to {scenario_dir}")

    print("\nDone. Each file is a ready-to-use Prover.toml for one trial.")
    print("run_benchmark.py copies each of these into the scenario's Nargo project in turn.")


if __name__ == "__main__":
    sys.exit(main())
