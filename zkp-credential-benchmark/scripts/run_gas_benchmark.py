#!/usr/bin/env python3
"""
run_gas_benchmark.py

Runs the RealVerifierGasTest Foundry suite (contracts/test/RealVerifierGas.t.sol)
and parses its decoded logs into results/gas_results.csv, in exactly the
format merge_gas_results.py expects:

    scenario_id,run_id,ethereum_gas,calldata_size

This replaces hand-copying numbers out of `forge test -vv` output: forge's
`--json` output, combined with `-vv`, includes each test's `decoded_logs`
as plain strings (e.g. "verification_gas_used: 17325"), which this script
reads directly.

PREREQUISITE:
    python3 generate_evm_artifacts.py
must have been run first, so the fixtures the Solidity test reads
(contracts/test/fixtures/*.json) actually exist with real proof data.

Usage:
    python3 run_gas_benchmark.py
    python3 ../scripts/merge_gas_results.py --gas-csv ../results/gas_results.csv
"""

import json
import re
import subprocess
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
CONTRACTS_DIR = PROJECT_ROOT / "contracts"
RESULTS_DIR = PROJECT_ROOT / "results"

# fixture log lines look like: "fixture: scenario1_minimal_run_001.json"
FIXTURE_RE = re.compile(r"^(scenario\d+_\w+)_run_(\d+)\.json$")


def parse_decoded_logs(decoded_logs):
    """Splits one test's decoded_logs into separate records.

    A single test (e.g. test_Scenario1_GasIsFlatAcrossTrials) can loop
    over several fixtures and emit several complete "fixture: ... /
    verification_gas_used: ..." blocks back to back. A flat key->value
    dict would let a later block silently overwrite an earlier one --
    each occurrence of the 'fixture' key marks the start of a new
    record, so this returns a LIST of dicts, one per fixture actually
    run in that test.
    """
    records = []
    current = None
    for line in decoded_logs:
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if key == "fixture":
            if current:
                records.append(current)
            current = {}
        if current is not None:
            current[key] = value
    if current:
        records.append(current)
    return records


def main():
    cmd = ["forge", "test", "--match-contract", "RealVerifierGasTest", "-vv", "--json"]
    result = subprocess.run(cmd, cwd=CONTRACTS_DIR, capture_output=True, text=True)

    if not result.stdout.strip():
        print("No output from forge test. STDERR:")
        print(result.stderr)
        raise SystemExit(1)

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        print("Could not parse forge's --json output. Raw stdout follows:\n")
        print(result.stdout[-2000:])
        raise SystemExit(1)

    rows = []
    seen = set()  # (scenario_id, run_id) -- the same fixture can be hit by
                  # more than one test (a dedicated test + the flatness
                  # test), so de-duplicate rather than write it twice.
    for suite_name, suite in data.items():
        for test_name, test_result in suite.get("test_results", {}).items():
            records = parse_decoded_logs(test_result.get("decoded_logs", []))
            for parsed in records:
                fixture = parsed.get("fixture")
                if not fixture:
                    continue  # a skipped-fixture log line, no full record
                match = FIXTURE_RE.match(fixture)
                if not match:
                    print(f"[warn] could not parse scenario/run from fixture name: {fixture}")
                    continue
                scenario_id, run_id = match.group(1), int(match.group(2))
                gas = parsed.get("verification_gas_used")
                calldata = parsed.get("calldata_size_bytes")
                if gas is None:
                    print(f"[warn] {test_name}: fixture {fixture} had no verification_gas_used, skipping")
                    continue
                key = (scenario_id, run_id)
                if key in seen:
                    continue
                seen.add(key)
                rows.append({
                    "scenario_id": scenario_id,
                    "run_id": run_id,
                    "ethereum_gas": int(gas),
                    "calldata_size": int(calldata) if calldata is not None else "",
                })
                print(f"[ok] {scenario_id} run {run_id}: {gas} gas, {calldata} bytes calldata "
                      f"(from {test_name})")

    if not rows:
        print("\nNo gas results were parsed -- this usually means no fixtures exist yet.")
        print("Run: python3 generate_evm_artifacts.py")
        raise SystemExit(1)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "gas_results.csv"
    with open(out_path, "w") as f:
        f.write("scenario_id,run_id,ethereum_gas,calldata_size\n")
        for row in rows:
            f.write(f"{row['scenario_id']},{row['run_id']},{row['ethereum_gas']},{row['calldata_size']}\n")

    print(f"\nWrote {len(rows)} row(s) to {out_path}")
    print("Next: python3 merge_gas_results.py --gas-csv ../results/gas_results.csv")


if __name__ == "__main__":
    main()
