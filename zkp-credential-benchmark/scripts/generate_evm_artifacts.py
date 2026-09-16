#!/usr/bin/env python3
"""
generate_evm_artifacts.py

Produces everything the ON-CHAIN half of the experiment needs, which
turns out to require a SEPARATE vk/proof pair from the one used for the
off-chain benchmark numbers in results/benchmark_results.csv.

Why this script exists (discovered empirically):
--------------------------------------------------
`bb write_vk` / `bb prove` default to a proving-scheme target that is
NOT Ethereum-compatible. Feeding that default vk into
`bb write_solidity_verifier` fails with an error like:
    verification key has wrong size: expected 1888, got 3680
because the EVM target uses a different internal hash (Keccak, so
Solidity can verify cheaply) while the default target uses Poseidon2
(cheaper for off-chain/Noir-to-Noir verification, but useless on-chain).

So: the off-chain proving/verification numbers you already collected
with run_benchmark.py are valid and untouched by this script. This
script produces a SECOND, distinct set of artifacts -- vk, proof, and
a real Solidity verifier contract -- generated with `-t evm`,
specifically for the Ethereum gas-measurement half of the experiment
(Section 3.8).

For each scenario, this script:
  1. Picks a few already-generated synthetic trials (from
     data/prover_inputs/<scenario>/), default 3, to confirm gas is
     genuinely flat across different inputs to the same circuit (per
     Section 3.11.4's decoupling hypothesis) rather than assuming it
     from a single sample.
  2. Runs nargo execute, then bb write_vk -t evm and bb prove -t evm
     for each of those trials.
  3. Generates ONE real Solidity verifier per scenario (the vk, and
     therefore the verifier contract, is identical across trials of
     the same circuit -- only the proof differs), renamed to avoid
     contract-name collisions when multiple scenarios' verifiers sit
     in contracts/src/ together.
  4. Writes a JSON fixture per trial (contracts/test/fixtures/) with
     the proof and public inputs as hex, ready for the Foundry test in
     contracts/test/RealVerifierGas.t.sol to read via forge-std's
     stdJson cheatcodes.

Usage:
    python3 generate_evm_artifacts.py --trials-per-scenario 3
"""

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
CIRCUITS_DIR = PROJECT_ROOT / "circuits"
DATA_DIR = PROJECT_ROOT / "data" / "prover_inputs"
CONTRACTS_DIR = PROJECT_ROOT / "contracts"
FIXTURES_DIR = CONTRACTS_DIR / "test" / "fixtures"

SCENARIOS = [
    "scenario1_minimal",
    "scenario2_multi_attr",
    "scenario3_full_integrity",
    "scenario4_advanced_identity",
]

# The Solidity contract name bb generates by default. If a future bb
# version changes this, update here -- the rename step below looks for
# this exact identifier.
DEFAULT_GENERATED_CONTRACT_NAME = "HonkVerifier"


def run(cmd, cwd=None):
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(cmd)}\ncwd={cwd}\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result.stdout, result.stderr


def field_hex_words(raw: bytes, word_size: int = 32):
    if len(raw) % word_size != 0:
        raise ValueError(
            f"public_inputs length ({len(raw)} bytes) is not a multiple of {word_size}"
        )
    return ["0x" + raw[i : i + word_size].hex() for i in range(0, len(raw), word_size)]


def scenario_display_name(scenario_id: str) -> str:
    # scenario1_minimal -> Scenario1
    match = re.match(r"(scenario\d+)", scenario_id)
    return match.group(1).capitalize() if match else scenario_id.capitalize()


def generate_for_scenario(scenario_id: str, trials_per_scenario: int, verifier_written: set):
    circuit_dir = CIRCUITS_DIR / scenario_id
    trial_dir = DATA_DIR / scenario_id
    trial_files = sorted(trial_dir.glob("run_*.toml"))[:trials_per_scenario]

    if not trial_files:
        print(f"[skip] {scenario_id}: no generated trials found in {trial_dir}. "
              f"Run generate_synthetic_data.py first.")
        return

    display_name = scenario_display_name(scenario_id)
    contract_name = f"{display_name}Verifier"

    for trial_file in trial_files:
        trial_label = trial_file.stem  # e.g. run_001
        print(f"[{scenario_id}] {trial_label}: generating EVM-targeted artifacts ...")

        shutil.copy(trial_file, circuit_dir / "Prover.toml")
        target_dir = circuit_dir / "target"
        evm_dir = circuit_dir / "target_evm"
        evm_dir.mkdir(exist_ok=True)

        run(["nargo", "execute"], cwd=circuit_dir)
        gz = next(target_dir.glob("*.gz"))
        acir_json = next(target_dir.glob("*.json"))

        # --- EVM-targeted vk (only needs generating once per scenario) ---
        vk_path = evm_dir / "vk"
        if not vk_path.exists():
            run(["bb", "write_vk", "-b", str(acir_json), "-o", str(evm_dir), "-t", "evm"])

        # --- EVM-targeted proof (one per trial, to confirm gas stays flat) ---
        run(["bb", "prove", "-b", str(acir_json), "-w", str(gz),
             "-o", str(evm_dir), "-k", str(vk_path), "-t", "evm"])
        proof_path = evm_dir / "proof"
        public_inputs_path = evm_dir / "public_inputs"

        # --- Real Solidity verifier (generate once per scenario, reused across trials) ---
        if scenario_id not in verifier_written:
            sol_out = CONTRACTS_DIR / "src" / f"{contract_name}.sol"
            run(["bb", "write_solidity_verifier", "-k", str(vk_path),
                 "-o", str(sol_out), "-t", "evm"])
            # Rename the generated contract so multiple scenarios' verifiers
            # can coexist in contracts/src/ without a name collision.
            text = sol_out.read_text()
            text = text.replace(DEFAULT_GENERATED_CONTRACT_NAME, contract_name)
            sol_out.write_text(text)
            verifier_written.add(scenario_id)
            print(f"  -> wrote {sol_out.relative_to(PROJECT_ROOT)} (contract {contract_name})")

        # --- JSON fixture for the Foundry test ---
        proof_hex = "0x" + proof_path.read_bytes().hex()
        public_inputs_hex = (
            field_hex_words(public_inputs_path.read_bytes())
            if public_inputs_path.exists() else []
        )
        fixture = {
            "scenario": scenario_id,
            "contractName": contract_name,
            "trial": trial_label,
            "proof": proof_hex,
            "publicInputs": public_inputs_hex,
        }
        FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
        fixture_path = FIXTURES_DIR / f"{scenario_id}_{trial_label}.json"
        fixture_path.write_text(json.dumps(fixture, indent=2))
        print(f"  -> wrote {fixture_path.relative_to(PROJECT_ROOT)} "
              f"(proof {len(proof_hex[2:]) // 2} bytes, {len(public_inputs_hex)} public inputs)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials-per-scenario", type=int, default=3,
                         help="How many already-generated synthetic trials per scenario to "
                              "turn into EVM proofs, to confirm gas stays flat across inputs.")
    parser.add_argument("--scenario", type=str, default=None,
                         help="Only process this one scenario id (for re-running after a fix).")
    args = parser.parse_args()

    scenarios = [args.scenario] if args.scenario else SCENARIOS
    verifier_written = set()

    for scenario_id in scenarios:
        generate_for_scenario(scenario_id, args.trials_per_scenario, verifier_written)

    print("\nDone. Next: cd ../contracts && forge test --match-contract RealVerifierGasTest -vv --gas-report")


if __name__ == "__main__":
    main()
