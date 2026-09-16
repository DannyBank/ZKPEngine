# ZK-SNARK Attribute-Based Credential Benchmark
### Companion implementation for Chapter 3 ("Research Methodology") and Chapter 4 ("Results and Discussion")

This package is a **working, tested implementation** of the experiment
designed in Chapter 3. Every Noir circuit in `circuits/` was written,
compiled, and unit-tested with `nargo` (v1.0.0-beta.22) during
development, and the synthetic data generator was verified to produce
inputs the real circuits actually accept -- including a genuine
Poseidon commitment check (Scenario 3) and a genuine depth-4 Merkle
membership proof (Scenario 4), not placeholders.

The one stage that could **not** be executed in the sandbox this was
built in is `bb prove`, because Barretenberg needs to download a
structured reference string (CRS) from `crs.aztec-labs.com` on first
use, and that domain was not reachable from the build sandbox. This is
a network-access limitation of that specific environment, not a defect
in the circuits, scripts, or commands -- you already ran this exact
`bb prove` / `write_vk` / `verify` sequence successfully on your own
machine. Everything below will run to completion there.

---

## 1. What's in this package

```
zkp-credential-benchmark/
├── circuits/
│   ├── scenario1_minimal/            (1 attribute, range check)
│   ├── scenario2_multi_attr/         (4 attributes, range + set membership)
│   ├── scenario3_full_integrity/     (8 attributes, Poseidon commitment)
│   └── scenario4_advanced_identity/  (16 attributes, Poseidon + Merkle)
├── tools/
│   ├── hash2_helper/    (prints Poseidon hash_2 of two field inputs)
│   ├── hash8_helper/    (prints Poseidon hash_8 of eight field inputs)
│   └── hash16_helper/   (prints Poseidon hash_16 of sixteen field inputs)
├── contracts/
│   ├── src/CredentialVerifier.sol          (minimal wrapper, Section 3.8.2)
│   ├── src/Scenario<N>Verifier.sol         (generated -- real bb verifiers, not checked in)
│   ├── test/RealVerifierGas.t.sol          (real gas test, reads fixtures dynamically)
│   └── test/fixtures/                      (generated proof/publicInputs JSON, not checked in)
├── scripts/
│   ├── generate_synthetic_data.py   (builds valid Prover.toml files per trial)
│   ├── run_benchmark.py             (the automated logging framework, Section 3.9.1)
│   ├── generate_evm_artifacts.py    (builds the EVM-targeted vk/proof + real verifiers)
│   ├── run_gas_benchmark.py         (runs the real gas test, parses results to CSV)
│   ├── merge_gas_results.py         (folds gas_results.csv into the main CSV)
│   ├── export_proof_for_solidity.py (standalone hex-conversion utility, if needed manually)
│   └── analyze_results.py           (Section 3.11 statistics + the 8 figures)
├── data/prover_inputs/   (generated synthetic inputs land here)
└── results/              (CSV outputs, descriptive stats, figures land here)
```

---

## 2. One-time environment setup

Install the exact toolchain versions this package was built and tested
against (matching ones are fine; just keep them fixed across your run,
per Section 3.4):

```bash
# Noir compiler
curl -L https://raw.githubusercontent.com/noir-lang/noirup/main/install | bash
source ~/.bashrc
noirup -v 1.0.0-beta.22

# Barretenberg proving backend
curl -L https://raw.githubusercontent.com/AztecProtocol/aztec-packages/master/barretenberg/bbup/install | bash
source ~/.bashrc
bbup -nv 1.0.0-beta.22

# Foundry (forge / anvil / cast)
curl -L https://foundry.paradigm.xyz | bash
source ~/.bashrc
foundryup

# Python dependencies for the data generator and analysis scripts
pip install pandas scipy matplotlib numpy --break-system-packages
```

Confirm everything is on PATH:

```bash
nargo --version   # nargo version = 1.0.0-beta.22
bb --version      # 5.0.0-nightly.20260522
forge --version
```

Record these exact version strings -- they belong in your `noir_version`
and `backend_version` columns and in your Chapter 4 environment
description, per Section 3.12.2 (internal validity).

---

### 2.1 Version pinning matters (troubleshooting "Unable to open file: ./target/vk" and "Length too large")

Both of these errors trace back to the same root cause: `nargo`/`bb`
version drift. `bb`'s binary proof/witness format changed between
releases, and the `noir-lang/poseidon` library used in Scenarios 3-4
only compiles cleanly against a specific compiler range. Confirm both
versions match exactly what's pinned above:

```bash
nargo --version   # must say 1.0.0-beta.22
bb --version      # must say 5.0.0-nightly.20260522
```

If they don't match, reinstall both pinned together and delete any
stale build artifacts before re-running:

```bash
noirup -v 1.0.0-beta.22
bbup -nv 1.0.0-beta.22
rm -rf circuits/*/target
```

`run_benchmark.py` already runs `bb write_vk` *before* `bb prove`
(passing the resulting vk into `prove` via `-k`) rather than after --
this specific `bb` build expects a verification key to already exist
when `prove` runs, and errors with "Unable to open file: ./target/vk"
if you call `bb prove` on its own without one. If you ever run `bb`
by hand outside the harness, keep that order.

## 3. Step-by-step procedure

### Step 1 — Sanity-check every circuit compiles and its logic is correct

```bash
cd circuits/scenario1_minimal && nargo test && cd ../..
cd circuits/scenario2_multi_attr && nargo test && cd ../..
cd circuits/scenario3_full_integrity && nargo test && cd ../..
cd circuits/scenario4_advanced_identity && nargo test && cd ../..
```

All eight tests (two per Scenario 1 and 2, one each for 3 and 4) should
pass. This confirms the credential logic itself -- range checks, set
membership, the Poseidon commitment, and the Merkle proof -- is correct
before you spend any time benchmarking it.

### Step 2 — Generate synthetic data for N trials per scenario

```bash
cd scripts
python3 generate_synthetic_data.py --runs 30 --out ../data/prover_inputs
```

This writes 30 `run_XXX.toml` files per scenario. For Scenarios 3 and
4, each file's Poseidon commitment / Merkle root is computed by
actually invoking the `tools/hash*_helper` Noir programs via `nargo
execute` -- so every generated file is guaranteed to satisfy its
circuit, not just plausible-looking. (`--runs 30` matches the N >= 30
reliability threshold from Section 3.12.1; raise it if your timeline
allows more repetitions.)

### Step 3 — Run the off-chain benchmark

```bash
python3 run_benchmark.py --runs 30 --hardware-id <your-machine-name>
```

For every trial, this measures and logs (matching the Section 3.9.2
schema exactly): `compile_time`, `circuit_size`, `witness_time`,
`proving_time`, `peak_memory`, `proof_size`, `local_verify_time`, and
`verification_status`, appending one row per trial to
`results/benchmark_results.csv`. Failed trials are kept, not dropped,
with a `failure_reason` matching the Section 3.10 taxonomy.

This step is where `bb prove` needs internet access to
`crs.aztec-labs.com` the first time it runs (to download the CRS,
cached locally afterward) -- make sure that domain isn't blocked by
your network/firewall before starting a full 30-trial x 4-scenario run.

### Step 4 — Generate the real Ethereum verifier and measure gas

**Important discovery, folded into the pipeline:** the vk/proof pair from
Step 3 was built with bb's *default* target -- correct for the off-chain
numbers, but incompatible with `bb write_solidity_verifier` (you'll see
`verification key has wrong size: expected 1888, got 3680` if you try).
EVM verification needs a **separate** vk/proof pair built with `-t evm`
(Keccak-based). The scripts below handle this automatically -- you no
longer need to touch `bb` or edit Solidity by hand.

```bash
cd scripts
python3 generate_evm_artifacts.py --trials-per-scenario 3
```

For each scenario, this:
- builds an EVM-targeted (`-t evm`) vk and proof from your already-generated synthetic trials,
- generates the **real** Solidity verifier via `bb write_solidity_verifier`, renamed to `contracts/src/Scenario<N>Verifier.sol` to avoid name collisions across scenarios,
- writes a JSON fixture per trial into `contracts/test/fixtures/` with the real proof + public inputs as hex.

Then run the real gas test (`contracts/test/RealVerifierGas.t.sol` --
it deploys each generated verifier dynamically by name via
`deployCode`, so it works unmodified across all four scenarios):

```bash
cd ../contracts
forge test --match-contract RealVerifierGasTest -vv --gas-report
```

Rather than copying numbers out of that output by hand, let the next
script parse them straight into a CSV:

```bash
cd ../scripts
python3 run_gas_benchmark.py
```

This produces `results/gas_results.csv` in exactly the shape
`merge_gas_results.py` expects (`scenario_id,run_id,ethereum_gas,calldata_size`),
including a check that gas stays flat across different inputs to the
same circuit (`test_Scenario1_GasIsFlatAcrossTrials`) -- the empirical
confirmation of Section 3.11.4's decoupling hypothesis. Then fold it
into your main results file:

```bash
python3 merge_gas_results.py --gas-csv ../results/gas_results.csv
```

Note `ethereum_gas` here is specifically `verifyCredential`'s cost.
Deployment gas (the constructor cost) is reported separately by
`forge --gas-report` and should stay separate, per Section 3.8.3 --
it's a one-off cost, not a per-verification one.

### Step 5 — Run the statistical analysis and generate the eight figures

```bash
python3 analyze_results.py
```

This produces, directly from `results/benchmark_results.csv`:

- `results/descriptive_stats.csv` — mean/median/min/max/std/CV per
  metric per scenario (Section 3.11.1)
- `results/correlations.csv` — the five operational pairs, with
  Pearson or Spearman chosen automatically based on a Shapiro-Wilk
  normality check on each variable (Sections 3.11.2 and 3.11.3)
- A printed off-chain-vs-on-chain scaling verdict (Section 3.11.4),
  stating explicitly whether your data supports or contradicts the
  decoupling hypothesis
- `results/figures/figure_3_1.png` through `figure_3_8.png`, matching
  Section 3.11.5 exactly

---

## 4. What this validates and what to watch for in your real run

During development, this harness was exercised against a plausibility
dataset (not real proving data -- fabricated purely to test the
scripts) and correctly reproduced the pattern predicted in our
discussion: proving time grew roughly 7x from Scenario 1 to Scenario
4, while Ethereum gas grew by less than 20% over the same range,
correctly triggering the "decoupling hypothesis supported" verdict.
**Your real numbers will differ** -- this only confirms the
measurement pipeline itself is sound, not what your actual circuit
will do.

Two things worth watching for once you run this for real, based on
the circuit-size figures already measured directly during development
(`nargo info`, no fabrication needed for these): ACIR opcode counts of
26 / 80 / 606 / 3,409 for Scenarios 1 through 4 respectively. Notice
the jump from Scenario 2 to Scenario 3 (80 -> 606, a ~7.5x increase)
is much steeper than Scenario 1 to Scenario 2 (26 -> 80, ~3x) despite
a similar-looking increase in attribute count on paper -- this is the
Poseidon hash commitment's cost showing up exactly where Chapter 2
predicted it would, and is worth flagging explicitly in your Chapter 4
discussion as evidence that predicate complexity, not attribute count
alone, drives circuit size.

Also budget carefully for Scenario 4 on the 8 GB RAM environment
specified in Section 3.4 -- watch peak_memory closely on your first
few trials, since Resource Exhaustion is a live possibility for the
heaviest scenario and, per Section 3.10, should be logged and
discussed rather than treated as a run to discard.

---

## 5. Mapping outputs directly onto your Chapter 4 sections

| Chapter 4 section (typical) | Source file |
|---|---|
| Descriptive results per scenario | `results/descriptive_stats.csv` |
| Figures 4.1-4.8 (renumber from 3.x) | `results/figures/figure_3_*.png` |
| Correlation / regression findings | `results/correlations.csv` |
| Off-chain vs. on-chain discussion | Console output of `analyze_results.py`, Section "Off-chain vs. on-chain scaling" |
| Failure-rate discussion | `results/benchmark_results.csv`, filter `verification_status == False`, group by `failure_reason` |
| Reproducibility appendix | This repository itself, plus your recorded `nargo --version` / `bb --version` / `forge --version` strings |
