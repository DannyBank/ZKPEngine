#!/usr/bin/env python3
"""
merge_gas_results.py

The Chapter 3 data schema (Section 3.9.2) has ethereum_gas and
calldata_size columns living in the same row as every off-chain metric
for that trial, but they are actually produced by a different tool
(Foundry, not nargo/bb). This script merges
a simple gas-results CSV (one row per scenario_id + run_id, with
ethereum_gas and calldata_size columns) into results/benchmark_results.csv.

Usage:
    python3 merge_gas_results.py --gas-csv ../results/gas_results.csv
"""

import argparse
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
RESULTS_DIR = SCRIPT_DIR.parent / "results"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark-csv", type=str, default=str(RESULTS_DIR / "benchmark_results.csv"))
    parser.add_argument("--gas-csv", type=str, required=True)
    parser.add_argument("--out", type=str, default=str(RESULTS_DIR / "benchmark_results.csv"))
    args = parser.parse_args()

    benchmark_df = pd.read_csv(args.benchmark_csv)
    gas_df = pd.read_csv(args.gas_csv)

    benchmark_df["run_id"] = benchmark_df["run_id"].astype(int)
    gas_df["run_id"] = gas_df["run_id"].astype(int)

    merged = benchmark_df.merge(
        gas_df[["scenario_id", "run_id", "ethereum_gas", "calldata_size"]],
        on=["scenario_id", "run_id"],
        how="left",
        suffixes=("", "_new"),
    )

    # Prefer the freshly merged gas figures if both existed for some reason.
    for col in ["ethereum_gas", "calldata_size"]:
        new_col = f"{col}_new"
        if new_col in merged.columns:
            merged[col] = merged[new_col].combine_first(merged[col])
            merged.drop(columns=[new_col], inplace=True)

    merged.to_csv(args.out, index=False)
    matched = gas_df.merge(benchmark_df[["scenario_id", "run_id"]], on=["scenario_id", "run_id"]).shape[0]
    print(f"Merged {matched} gas measurements into {args.out}")


if __name__ == "__main__":
    main()
