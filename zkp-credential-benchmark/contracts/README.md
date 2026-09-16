# Ethereum Gas-Measurement Harness

This Foundry project implements the Ethereum verification environment
described in Chapter 3, Section 3.8.

**Update:** the manual "generate a vk, copy a .sol file, hand-edit a
test" workflow that used to live in this README has been replaced by
one script, `scripts/generate_evm_artifacts.py`, plus one fixture-based
Foundry test, `test/RealVerifierGas.t.sol`. The steps below are all
you need now.

## Why this exists as a SEPARATE step from `run_benchmark.py`

The off-chain benchmark (`run_benchmark.py`) uses `bb`'s default proving
target, which is not Ethereum-compatible. Feeding that vk into
`bb write_solidity_verifier` fails with an error like:

```
verification key has wrong size: expected 1888, got 3680
```

because Solidity verification needs the `evm` target specifically
(Keccak-based hashing, cheap on-chain; the default target uses
Poseidon2, cheap for off-chain/recursive verification, but useless on
an EVM). So the on-chain half of the experiment needs its own vk and
proof, built with `-t evm`. Your existing `results/benchmark_results.csv`
data is unaffected by any of this -- it's a genuinely separate artifact
set, not a replacement.

## 1. Generate the real on-chain artifacts

From the project root:

```bash
cd scripts
python3 generate_evm_artifacts.py
```

For each of the 4 scenarios, this:
- Runs `nargo execute` on a few already-generated synthetic trials
  (default 3 -- see `--trials-per-scenario`)
- Runs `bb write_vk ... -t evm` and `bb prove ... -t evm` for each trial
- Runs `bb write_solidity_verifier ... -t evm` **once** per scenario
  (the vk, and therefore the verifier contract, is identical across
  trials of the same circuit -- only the proof differs per trial),
  writing `contracts/src/Scenario<N>Verifier.sol` with the contract
  renamed to `Scenario<N>Verifier` so all four can coexist without a
  name clash
- Writes a JSON fixture per trial to `contracts/test/fixtures/`
  (e.g. `scenario1_minimal_run_001.json`) containing the real proof and
  public inputs as hex, plus which contract name to deploy

If you only need to redo one scenario (e.g. after fixing something),
add `--scenario scenario3_full_integrity`.

## 2. Run the real gas measurement

```bash
cd ../contracts
forge test --match-contract RealVerifierGasTest -vv --gas-report
```

`RealVerifierGas.t.sol` doesn't statically `import` the generated
verifier contracts (they don't exist until step 1 has run) -- it
deploys each one dynamically via Foundry's `deployCode` cheatcode,
referencing it only by name, and calls it through the same minimal
`IHonkVerifier` interface every bb-generated verifier implements. Each
scenario gets its own test function (`test_Scenario1_RealVerificationGas`,
etc.), plus `test_Scenario1_GasIsFlatAcrossTrials`, which runs every
generated trial fixture for Scenario 1 back-to-back so you can confirm
gas is genuinely flat across different private inputs to the same
circuit -- the empirical check for Section 3.11.4's decoupling
hypothesis. If a fixture for a scenario hasn't been generated yet, its
test logs `[skip]` and still passes, rather than blocking the whole
suite.

## 3. Turn the results into a CSV

```bash
cd ../scripts
python3 parse_forge_gas_output.py
```

This re-runs the Foundry test, parses its logged `fixture:` /
`verification_gas_used:` / `calldata_size_bytes:` lines, and writes
`results/gas_results.csv` in exactly the format `merge_gas_results.py`
expects (`scenario_id,run_id,ethereum_gas,calldata_size`).

## 4. Merge into the main results CSV

```bash
python3 merge_gas_results.py --gas-csv ../results/gas_results.csv
```

This fills in the `ethereum_gas` and `calldata_size` columns in
`results/benchmark_results.csv` for the trials you measured on-chain,
leaving every off-chain column (proving_time, peak_memory, etc.)
untouched.

## What was actually validated in this environment

Everything mechanical was tested end to end using a hand-built fixture
and a stand-in verifier contract (since the sandbox this project was
built in can't reach `crs.aztec-labs.com` for the real CRS download):

- `generate_evm_artifacts.py`'s command construction, path handling,
  and contract-renaming logic all run correctly up to the point of the
  CRS-dependent `bb write_vk -t evm` call.
- `RealVerifierGas.t.sol` compiles cleanly, correctly deploys a
  dynamically-named contract via `deployCode`, correctly parses a JSON
  fixture via `stdJson.readBytes` / `readBytes32Array`, correctly
  measures and logs gas, and correctly skips (rather than failing) a
  scenario whose fixture doesn't exist yet.
- `parse_forge_gas_output.py` correctly parses multiple fixtures' worth
  of `forge test` log output into a clean CSV, verified against 3
  fake trials.

## What you still need to do yourself

Run step 1 on a machine with normal network access to
`crs.aztec-labs.com` (you already confirmed your machine can reach it,
back when your manual `bb prove` / `write_vk` commands succeeded).
Everything downstream of that (steps 2-4) is now automated.

## Original mock-verifier plumbing test

`src/MockHonkVerifierForPlumbingTest.sol` and
`test/CredentialVerifier.gas.t.sol` are kept as-is -- they were the
original plumbing check before the real fixture-based workflow above
existed, and still work as a quick sanity test of `CredentialVerifier`
itself (`forge test --match-contract CredentialVerifierGasTest -vv`).
They are not part of the real experiment; `RealVerifierGasTest` is.
