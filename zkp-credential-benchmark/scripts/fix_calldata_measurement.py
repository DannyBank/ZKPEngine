#!/usr/bin/env python3
"""
fix_calldata_measurement.py

CORRECTIVE SCRIPT -- documents and fixes a real measurement defect caught
in thesis review, in results/gas_results.csv and its merge into
results/benchmark_results.csv.

THE BUG
-------
Two genuinely different proof artifacts exist per trial:

  1. The OFF-CHAIN proof: built by `bb prove` with the DEFAULT (Poseidon2)
     target inside run_benchmark.py. Its size is logged as the
     `proof_size` column in benchmark_results.csv (14,656 bytes, constant
     across all four scenarios). This proof is used ONLY for the
     off-chain proving-time / local-verification-time measurements
     (RQ1/RQ2) and is NEVER submitted to Ethereum.

  2. The ON-CHAIN proof: built by generate_evm_artifacts.py with the
     `-t evm` (Keccak) target, specifically so a Solidity verifier can
     check it. THIS is the proof whose size actually determines calldata.
     Its size was never logged as its own column anywhere.

`calldata_size` in gas_results.csv was computed (in RealVerifierGas.t.sol)
as `proof.length + publicInputs.length * 32` -- using the ON-CHAIN proof
correctly, but omitting the 4-byte function selector and the 128 bytes of
ABI head/length words that `verifyCredential(bytes,bytes32[])` calldata
actually requires. Chapter 4's draft then compounded this by comparing
`calldata_size` (on-chain proof based, minus 132 bytes) against
`proof_size` (the OFF-CHAIN 14,656-byte artifact) in Figure 4.7 and
Table 4.8 -- two different proofs, presented as if directly comparable.
That is the contradiction the review caught.

THE FIX
-------
For each real proof fixture in contracts/test/fixtures/, this script:
  1. Reads the actual on-chain (EVM-target) proof and public inputs.
  2. Records the genuine on-chain proof size (onchain_proof_size).
  3. Computes the TRUE ABI-encoded calldata length for a call to
     `verifyCredential(bytes,bytes32[])`, using Python's own manual ABI
     encoding of that exact signature (independently re-derived here,
     not copied from the earlier Node/ethers check, as a second
     confirmation) -- this is the "single source of truth" the review
     asked for: the actual bytes that would be transmitted.
  4. Verifies the consistency check the review specified:
       calldata >= 4 (selector) + proof_bytes + sum(public_input_bytes)
  5. Writes results/gas_results.csv (CORRECTED), backing up the original
     understated version alongside it for transparency.

Requires only the Python standard library.
"""

import csv
import json
import shutil
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
FIXTURES_DIR = PROJECT_ROOT / "contracts" / "test" / "fixtures"
RESULTS_DIR = PROJECT_ROOT / "results"
BACKUP_DIR = RESULTS_DIR / "_pre_correction_backup"

# verifyCredential(bytes,bytes32[]) selector = first 4 bytes of
# keccak256("verifyCredential(bytes,bytes32[])"). Hardcoded here (rather
# than computed, since this script has no keccak dependency) and cross-
# checked against the selector actually present in the real fixture-based
# transaction built independently via ethers.js during review (0x628c46d8).
SELECTOR_HEX = "628c46d8"


def abi_encode_verify_credential(proof_hex: str, public_inputs_hex: list[str]) -> bytes:
    """Manually ABI-encodes a call to verifyCredential(bytes,bytes32[]),
    independently of any JS/ethers tooling, as a second confirmation of
    the true calldata length."""
    proof = bytes.fromhex(proof_hex[2:] if proof_hex.startswith("0x") else proof_hex)
    public_inputs = [
        bytes.fromhex(pi[2:] if pi.startswith("0x") else pi) for pi in public_inputs_hex
    ]
    assert all(len(pi) == 32 for pi in public_inputs), "public inputs must be 32-byte words"

    n = len(public_inputs)
    # Head: two offsets (one per dynamic parameter), 32 bytes each.
    offset_proof = 64  # right after the two head words
    proof_len_padded = ((len(proof) + 31) // 32) * 32
    offset_array = offset_proof + 32 + proof_len_padded  # + length word + padded data

    head = offset_proof.to_bytes(32, "big") + offset_array.to_bytes(32, "big")
    proof_tail = len(proof).to_bytes(32, "big") + proof.ljust(proof_len_padded, b"\x00")
    array_tail = n.to_bytes(32, "big") + b"".join(public_inputs)

    return bytes.fromhex(SELECTOR_HEX) + head + proof_tail + array_tail


def main():
    gas_csv_path = RESULTS_DIR / "gas_results.csv"
    with open(gas_csv_path) as f:
        original_rows = list(csv.DictReader(f))

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy(gas_csv_path, BACKUP_DIR / "gas_results_UNDERSTATED_calldata.csv.bak")

    corrected_rows = []
    print(f"{'scenario':28} {'run':>3} {'onchain_proof':>13} {'old_calldata':>12} {'true_calldata':>13} {'check':>7}")
    for row in original_rows:
        scenario_id = row["scenario_id"]
        run_id = int(row["run_id"])
        fixture_path = FIXTURES_DIR / f"{scenario_id}_run_{run_id:03d}.json"
        fixture = json.loads(fixture_path.read_text())

        proof_hex = fixture["proof"]
        public_inputs_hex = fixture["publicInputs"]
        onchain_proof_bytes = (len(proof_hex) - 2) // 2

        encoded = abi_encode_verify_credential(proof_hex, public_inputs_hex)
        true_calldata_bytes = len(encoded)

        minimum_required = 4 + onchain_proof_bytes + 32 * len(public_inputs_hex)
        old_calldata = int(row["calldata_size"])
        check = "PASS" if true_calldata_bytes >= minimum_required else "FAIL"

        print(f"{scenario_id:28} {run_id:>3} {onchain_proof_bytes:>13} {old_calldata:>12} {true_calldata_bytes:>13} {check:>7}")

        corrected_rows.append({
            "scenario_id": scenario_id,
            "run_id": run_id,
            "ethereum_gas": row["ethereum_gas"],
            "onchain_proof_size": onchain_proof_bytes,
            "calldata_size": true_calldata_bytes,
            "calldata_size_understated_original": old_calldata,
        })

    fieldnames = [
        "scenario_id", "run_id", "ethereum_gas",
        "onchain_proof_size", "calldata_size", "calldata_size_understated_original",
    ]
    with open(gas_csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(corrected_rows)

    print(f"\nWrote corrected {gas_csv_path}")
    print(f"Original (understated) version preserved at {BACKUP_DIR / 'gas_results_UNDERSTATED_calldata.csv.bak'}")


if __name__ == "__main__":
    main()
