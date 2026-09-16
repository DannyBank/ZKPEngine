#!/usr/bin/env python3
"""
parse_forge_gas_output.py

Runs `forge test --match-contract RealVerifierGasTest -vv` and parses its
logged fixture/gas lines directly into results/gas_results.csv -- the
format merge_gas_results.py expects (scenario_id, run_id, ethereum_gas,
calldata_size).

This closes the loop mentioned in merge_gas_results.py's own docstring
("by parsing `forge test -vvv` console output with a small parser") --
you no longer have to do that step by hand.

It maps each fixture filename like "scenario1_minimal_run_003.json" back
to scenario_id="scenario1_minimal", run_id=3.

Usage:
    python3 parse_forge_gas_output.py --contracts-dir ../contracts --out ../results/gas_results.csv
"""

import argparse
import csv
import re
import subprocess
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

FIXTURE_RE = re.compile(r"fixture:\s*(\w+)_run_(\d+)\.json")
GAS_RE = re.compile(r"verification_gas_used:\s*(\d+)")
CALLDATA_RE = re.compile(r"calldata_size_bytes:\s*(\d+)")


def parse_forge_output(output: str):
    """Walks the log lines in order, associating each fixture: line with
    the verification_gas_used / calldata_size_bytes lines that follow it
    (forge prints each test's Logs: block as consecutive lines, in the
    same order emit was called in RealVerifierGas.t.sol)."""
    rows = []
    current_scenario, current_run = None, None
    current_gas, current_calldata = None, None

    def flush():
        if current_scenario is not None and current_gas is not None:
            rows.append({
                "scenario_id": current_scenario,
                "run_id": current_run,
                "ethereum_gas": current_gas,
                "calldata_size": current_calldata or "",
            })

    for line in output.splitlines():
        fixture_match = FIXTURE_RE.search(line)
        if fixture_match:
            flush()
            current_scenario = fixture_match.group(1)
            current_run = int(fixture_match.group(2))
            current_gas, current_calldata = None, None
            continue
        gas_match = GAS_RE.search(line)
        if gas_match:
            current_gas = int(gas_match.group(1))
            continue
        calldata_match = CALLDATA_RE.search(line)
        if calldata_match:
            current_calldata = int(calldata_match.group(1))
            continue
    flush()
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contracts-dir", type=str, default=str(PROJECT_ROOT / "contracts"))
    parser.add_argument("--out", type=str, default=str(PROJECT_ROOT / "results" / "gas_results.csv"))
    parser.add_argument("--match-test", type=str, default=None,
                         help="Optional: restrict to one test function, e.g. test_Scenario1_GasIsFlatAcrossTrials")
    args = parser.parse_args()

    cmd = ["forge", "test", "--match-contract", "RealVerifierGasTest", "-vv"]
    if args.match_test:
        cmd += ["--match-test", args.match_test]

    result = subprocess.run(cmd, cwd=args.contracts_dir, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        raise SystemExit(
            "forge test failed or found no matching tests -- run "
            "generate_evm_artifacts.py first so fixtures actually exist."
        )

    rows = parse_forge_output(result.stdout)
    if not rows:
        raise SystemExit(
            "No fixture/gas log lines found in forge output. Did you run "
            "scripts/generate_evm_artifacts.py yet? Without real fixtures, "
            "every test just logs '[skip] fixture not found yet' and there's "
            "nothing to parse."
        )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["scenario_id", "run_id", "ethereum_gas", "calldata_size"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nWrote {len(rows)} gas measurement(s) to {out_path}")
    print("Next: python3 merge_gas_results.py --gas-csv", out_path)


if __name__ == "__main__":
    main()
