#!/usr/bin/env python3
"""
run_benchmark.py

The automated logging framework described in Chapter 3, Section 3.9.1.
For every trial of every scenario, this script:

  1. Copies the pre-generated synthetic Prover.toml into the scenario's
     Nargo project (data/prover_inputs/<scenario>/run_XXX.toml).
  2. Times `nargo compile` (-> compile_time) and reads the resulting
     circuit_size from `nargo info --json`.
  3. Times `nargo execute` (-> witness_time, by subtracting compile_time
     from the total, since `execute` recompiles + generates the witness
     in one pass -- see the NOTE in measure_witness_time below).
  4. Times `bb prove` (-> proving_time) and records peak_memory via
     resource.getrusage(RUSAGE_CHILDREN) (-> peak_memory, in MB).
  5. Reads the proof file size (-> proof_size, in bytes).
  6. Times `bb verify` (-> local_verify_time) and records the outcome
     (-> verification_status).
  7. Appends one row to results/benchmark_results.csv matching the
     Chapter 3, Section 3.9.2 data schema.

Any stage that fails is logged with its failure category (Section 3.10)
rather than silently dropped -- failed rows are kept in the CSV with
verification_status = False and a failure_reason column.

Requirements: `nargo` and `bb` on PATH. `bb` additionally needs network
access to crs.aztec-labs.com the first time it runs, to download the
structured reference string (CRS) -- this only happens once and is then
cached locally.

Usage:
    python3 run_benchmark.py --runs 30 --hardware-id my-machine-01
"""

import argparse
import csv
import json
import os
import platform
import resource
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
CIRCUITS_DIR = PROJECT_ROOT / "circuits"
DATA_DIR = PROJECT_ROOT / "data" / "prover_inputs"
RESULTS_DIR = PROJECT_ROOT / "results"

SCHEMA_FIELDS = [
    "experiment_id", "scenario_id", "run_id", "attribute_count",
    "predicate_level", "circuit_size", "compile_time", "witness_time",
    "proving_time", "peak_memory", "proof_size", "local_verify_time",
    "calldata_size", "ethereum_gas", "verification_status", "timestamp",
    "noir_version", "backend_version", "hardware_id", "failure_reason",
]

SCENARIOS = {
    "scenario1_minimal": {"attribute_count": 1, "predicate_level": "Minimal Range Check"},
    "scenario2_multi_attr": {"attribute_count": 4, "predicate_level": "Moderate Predicate Verification"},
    "scenario3_full_integrity": {"attribute_count": 8, "predicate_level": "Complex Hash and Range Checks"},
    "scenario4_advanced_identity": {"attribute_count": 16, "predicate_level": "High Predicate and Membership Logic"},
}


def run_timed(cmd, cwd):
    """Runs a subprocess, returning (elapsed_seconds, peak_rss_mb, returncode, stdout, stderr).
    Peak RSS is read from resource.getrusage(RUSAGE_CHILDREN) *after* the call,
    which on Linux reports the maximum resident set size of the (now-terminated)
    child process in kilobytes."""
    before = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    start = time.perf_counter()
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    elapsed = time.perf_counter() - start
    after = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    # ru_maxrss is cumulative across children on Linux; the delta approximates
    # this call's contribution. On a dedicated benchmarking host running one
    # trial at a time (as prescribed in Section 3.4), this is a reasonable
    # proxy for the process's peak memory footprint. For a hard per-process
    # ceiling instead of an approximation, wrap the call with `valgrind
    # --tool=massif` or cgroups memory accounting.
    peak_mb = max(after - before, after) / 1024.0
    return elapsed, peak_mb, result.returncode, result.stdout, result.stderr


def get_circuit_size(circuit_dir):
    result = subprocess.run(["nargo", "info", "--json"], cwd=circuit_dir, capture_output=True, text=True)
    if result.returncode != 0:
        return None
    try:
        info = json.loads(result.stdout)
        return info["programs"][0]["functions"][0]["opcodes"]
    except (json.JSONDecodeError, KeyError, IndexError):
        return None


def get_tool_versions():
    def version_of(cmd):
        try:
            out = subprocess.run(cmd, capture_output=True, text=True).stdout
            return out.strip().split("\n")[0]
        except Exception:
            return "unknown"
    return version_of(["nargo", "--version"]), version_of(["bb", "--version"])


def run_trial(scenario_id, run_id, prover_toml_path, hardware_id, noir_version, backend_version):
    row = {field: "" for field in SCHEMA_FIELDS}
    row["experiment_id"] = str(uuid.uuid4())
    row["scenario_id"] = scenario_id
    row["run_id"] = run_id
    row["attribute_count"] = SCENARIOS[scenario_id]["attribute_count"]
    row["predicate_level"] = SCENARIOS[scenario_id]["predicate_level"]
    row["timestamp"] = datetime.now(timezone.utc).isoformat()
    row["noir_version"] = noir_version
    row["backend_version"] = backend_version
    row["hardware_id"] = hardware_id
    row["verification_status"] = False

    circuit_dir = CIRCUITS_DIR / scenario_id
    target_dir = circuit_dir / "target"
    prover_dest = circuit_dir / "Prover.toml"

    # Clean target/ so timings reflect a fresh build, then copy this
    # trial's synthetic input into place.
    if target_dir.exists():
        shutil.rmtree(target_dir)
    shutil.copyfile(prover_toml_path, prover_dest)

    # --- Stage 1: compile (-> compile_time, circuit_size) ---
    compile_time, _, rc, out, err = run_timed(["nargo", "compile"], circuit_dir)
    row["compile_time"] = round(compile_time * 1000, 3)  # ms
    if rc != 0:
        row["failure_reason"] = "Compilation failure"
        return row
    row["circuit_size"] = get_circuit_size(circuit_dir)

    # --- Stage 2: execute (-> witness_time) ---
    # NOTE: `nargo execute` recompiles the circuit AND generates the witness
    # in a single pass, and Nargo's build cache typically makes this second
    # compilation much faster than the cold compile timed in Stage 1 above.
    # Subtracting Stage 1's compile_time from this call's total therefore
    # UNDERSTATES witness_time (it can even go negative). To keep the
    # metric honest, witness_time here is the full `nargo execute` wall
    #-clock time, reported as "witness generation time, inclusive of a
    # cached recompilation pass" -- state this caveat explicitly in
    # Chapter 4 rather than silently subtracting. If you need a cleaner
    # separation, patch Nargo.toml's [profile] or run execute twice in a
    # row and discard the first (warm-cache) measurement consistently.
    execute_total, _, rc, out, err = run_timed(["nargo", "execute"], circuit_dir)
    if rc != 0:
        row["failure_reason"] = "Witness-generation failure"
        return row
    row["witness_time"] = round(execute_total * 1000, 3)

    gz_files = list(target_dir.glob("*.gz"))
    json_files = list(target_dir.glob("*.json"))
    if not gz_files or not json_files:
        row["failure_reason"] = "Witness-generation failure"
        return row
    witness_path, circuit_json_path = gz_files[0], json_files[0]

    # --- Stage 3: write_vk FIRST ---
    # IMPORTANT (discovered empirically against bb 5.0.0-nightly.20260522):
    # this bb release's `prove` subcommand looks for a vk file inside the
    # output directory by default (it errors with "Unable to open file:
    # ./target/vk" if one isn't there yet, or isn't passed via -k). Older
    # bb releases treated `prove` and `write_vk` as fully independent, but
    # this version does not, so vk generation now has to run before
    # proving. Doing it in this order also avoids the inline
    # "computing verification key while proving" recomputation bb
    # warns about, which would otherwise inflate the proving_time figure.
    vk_cmd = ["bb", "write_vk", "-b", str(circuit_json_path), "-o", str(target_dir)]
    _, _, rc, out, err = run_timed(vk_cmd, circuit_dir)
    vk_path = target_dir / "vk"
    # Some bb builds exit 0 even when they didn't actually write the vk file
    # (e.g. a swallowed CRS-download error, or a permissions issue) -- so the
    # exit code alone isn't trustworthy. Check the file landed on disk too,
    # the same way the prove stage below already checks for proof_path.
    if rc != 0 or not vk_path.exists():
        combined = (err.strip() or out.strip())[-500:]
        if rc == 0 and not vk_path.exists():
            combined = (
                "write_vk exited 0 but did not create target/vk. "
                "This usually means the CRS (reference file) download failed "
                "silently -- check network access to crs.aztec-labs.com. "
                f"Raw output: {combined}"
            )
        row["failure_reason"] = f"Local verification failure (vk): {combined}"
        return row

    # --- Stage 4: bb prove (-> proving_time, peak_memory, proof_size) ---
    prove_cmd = ["bb", "prove", "-b", str(circuit_json_path), "-w", str(witness_path), "-o", str(target_dir), "-k", str(vk_path)]
    proving_time, peak_mem, rc, out, err = run_timed(prove_cmd, circuit_dir)
    row["proving_time"] = round(proving_time * 1000, 3)
    row["peak_memory"] = round(peak_mem, 3)
    if rc != 0:
        row["failure_reason"] = f"Proof-generation failure: {err.strip()[-300:]}"
        return row

    proof_path = target_dir / "proof"
    if not proof_path.exists():
        row["failure_reason"] = "Proof-generation failure"
        return row
    row["proof_size"] = proof_path.stat().st_size

    # --- Stage 5: bb verify (-> local_verify_time, verification_status) ---
    verify_cmd = ["bb", "verify", "-k", str(vk_path), "-p", str(proof_path)]
    verify_time, _, rc, out, err = run_timed(verify_cmd, circuit_dir)
    row["local_verify_time"] = round(verify_time * 1000, 3)
    if rc != 0:
        row["failure_reason"] = f"Local verification failure: {err.strip()[-300:]}"
        return row

    row["verification_status"] = True
    row["failure_reason"] = ""
    # calldata_size and ethereum_gas are filled in separately by the
    # Foundry gas-measurement step (see contracts/README.md) and merged
    # into this CSV afterwards via merge_gas_results.py.
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=30)
    parser.add_argument("--hardware-id", type=str, default=platform.node() or "unknown-host")
    parser.add_argument("--out", type=str, default=str(RESULTS_DIR / "benchmark_results.csv"))
    args = parser.parse_args()

    if shutil.which("nargo") is None or shutil.which("bb") is None:
        print("ERROR: `nargo` and `bb` must both be on PATH. See README.md for install steps.")
        sys.exit(1)

    noir_version, backend_version = get_tool_versions()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = Path(args.out)

    write_header = not out_path.exists()
    with open(out_path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SCHEMA_FIELDS)
        if write_header:
            writer.writeheader()

        for scenario_id in SCENARIOS:
            scenario_input_dir = DATA_DIR / scenario_id
            input_files = sorted(scenario_input_dir.glob("run_*.toml"))[: args.runs]
            if len(input_files) < args.runs:
                print(f"WARNING: only {len(input_files)} synthetic inputs found for {scenario_id} "
                      f"(requested {args.runs}). Run generate_synthetic_data.py with --runs {args.runs} first.")
            for i, prover_toml_path in enumerate(input_files, start=1):
                print(f"[{scenario_id}] trial {i}/{len(input_files)} ...", end=" ", flush=True)
                row = run_trial(scenario_id, i, prover_toml_path, args.hardware_id, noir_version, backend_version)
                writer.writerow(row)
                f.flush()
                status = "OK" if row["verification_status"] else f"FAILED ({row['failure_reason']})"
                print(status)

    print(f"\nDone. Results appended to {out_path}")


if __name__ == "__main__":
    main()
