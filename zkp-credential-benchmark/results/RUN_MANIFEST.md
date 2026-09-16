# Experiment Run Manifest

This run closes the Chapter 3 experiment gap: all four benchmark scenarios were executed
for real, matching the methodology in Chapter 3 exactly (Sections 3.6-3.11).

## Actual execution environment (supersedes the placeholder text in the current §3.4 draft)

- Host machine: Windows 11 Pro, Intel(R) Core(TM) i5-5300U @ 2.30GHz, 2 cores / 4 logical
  processors, 8 GB physical RAM (host total)
- Benchmark environment: WSL2, Ubuntu 26.04.3 LTS, 6 GB RAM allocated to the WSL2 VM
  (`.wslconfig`: memory=6GB, processors=4, swap=2GB), 4 logical processors visible to the VM
- Noir compiler: nargo version = 1.0.0-beta.22
  (noirc version = 1.0.0-beta.22+c57152f91260ecdb9faad4efc20abb14b6d2ece7)
- Barretenberg backend: 5.0.0-nightly.20260522
- Foundry: forge 1.8.1 (982849d3140c01fd3b72905759581a132df7aa98)
- Python: 3.14.4, with pandas/scipy/matplotlib/numpy
- hardware_id used in benchmark_results.csv: `i5-5300U-8GB-WSL2Ubuntu26.04`
- Run date: 2026-09-15

**Note for §3.4 / Chapter 4 write-up:** the current thesis draft describes the study
environment as bare-metal "Linux Ubuntu 24.04 LTS" with "8 GB DDR5." The real machine is a
Windows 11 host running the benchmark inside WSL2 Ubuntu 26.04 LTS; DDR5 is also not
physically possible on this 2015-era CPU. §3.4 should be corrected to the description above
before Chapter 4 is finalized, for reproducibility accuracy.

## Pipeline executed (Chapter 3, Section 3.6.1 stages)

1. `nargo test` on all four circuits — 6/6 tests passed.
2. `nargo info` circuit-size check — ACIR opcodes: Scenario 1 = 26, Scenario 2 = 80,
   Scenario 3 = 606, Scenario 4 = 3,409 (confirmed against the README's claim).
3. Feasibility/pilot check (1 trial/scenario) — all 4 passed; CRS reachable; peak memory
   73-121 MB (well under the 8 GB budget).
4. Full off-chain benchmark: `run_benchmark.py --runs 30` — **120/120 trials valid, 0 failures.**
5. EVM artifact generation: `generate_evm_artifacts.py --trials-per-scenario 3` — 4 real
   Solidity verifiers, 12 real proof fixtures.
6. Gas benchmark: `forge test --match-contract RealVerifierGasTest --gas-report` — 5/5 tests
   passed, including the flat-gas-across-trials check for Scenario 1.
7. `run_gas_benchmark.py` -> `results/gas_results.csv` (6 real on-chain measurements).
8. `merge_gas_results.py` -> merged into `results/benchmark_results.csv`.
9. `analyze_results.py` -> `results/descriptive_stats.csv`, `results/correlations.csv`,
   `results/figures/figure_3_1.png` .. `figure_3_8.png`.

## Files in this directory

- `benchmark_results.csv` — the full 120-row dataset (Section 3.9.2 schema), gas columns
  merged in for the 6 trials that were also gas-benchmarked.
- `gas_results.csv` — the 6 raw on-chain gas measurements.
- `descriptive_stats.csv`, `correlations.csv` — Section 3.11.1 / 3.11.3 outputs.
- `figures/figure_3_1.png` .. `figure_3_8.png` — Section 3.11.6 outputs (renumbered
  Figure 4.1-4.8 in the Chapter 4 draft, per Chapter 3's own output-mapping table).
- `pilot_results.csv` — the 4-row feasibility-check output (Section 3.6.1), kept for the
  reproducibility appendix.
- `_pre_experiment_backup/` — the original placeholder CSVs from before this run, kept
  rather than deleted (dev-time fabricated/partial data, explicitly flagged as such in the
  original README).
