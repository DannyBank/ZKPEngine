#!/usr/bin/env python3
"""
analyze_results.py

Implements the statistical analysis plan from Chapter 3, Section 3.11,
directly against results/benchmark_results.csv. Produces:

  - Descriptive statistics per scenario (3.11.1) -> results/descriptive_stats.csv
  - Distribution/normality checks per metric (3.11.2) -> printed + used to
    choose Pearson vs. Spearman automatically (3.11.3)
  - Correlation table for the five operational pairs (3.11.3) -> results/correlations.csv
  - Off-chain vs. on-chain scaling comparison (3.11.4) -> printed summary
  - The eight figures specified in 3.11.5 -> results/figures/figure_3_*.png

Usage:
    python3 analyze_results.py --csv ../results/benchmark_results.csv
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ImportError:
    plt = None

SCRIPT_DIR = Path(__file__).resolve().parent
RESULTS_DIR = SCRIPT_DIR.parent / "results"


def load_data(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df = df[df["verification_status"] == True].copy()  # noqa: E712
    numeric_cols = [
        "attribute_count", "circuit_size", "compile_time", "witness_time",
        "proving_time", "peak_memory", "proof_size", "local_verify_time",
        "calldata_size", "ethereum_gas", "onchain_proof_size",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def descriptive_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Section 3.11.1: mean, median, min, max, std, coefficient of variation
    per scenario, for every core metric."""
    metrics = ["compile_time", "witness_time", "proving_time", "peak_memory",
               "proof_size", "local_verify_time", "ethereum_gas", "calldata_size",
               "onchain_proof_size"]
    rows = []
    for scenario, group in df.groupby("scenario_id"):
        for metric in metrics:
            if metric not in group.columns or group[metric].dropna().empty:
                continue
            values = group[metric].dropna()
            mean = values.mean()
            std = values.std(ddof=1) if len(values) > 1 else float("nan")
            cv = (std / mean * 100) if mean else float("nan")
            rows.append({
                "scenario_id": scenario, "metric": metric, "n": len(values),
                "mean": round(mean, 4), "median": round(values.median(), 4),
                "min": round(values.min(), 4), "max": round(values.max(), 4),
                "std": round(std, 4) if not np.isnan(std) else "",
                "coefficient_of_variation_pct": round(cv, 2) if not np.isnan(cv) else "",
            })
    return pd.DataFrame(rows)


def normality_ok(series: pd.Series) -> bool:
    """Section 3.11.2: Shapiro-Wilk normality check (used here to decide
    Pearson vs. Spearman automatically for 3.11.3). Requires n >= 8 for a
    meaningful Shapiro-Wilk result; smaller samples default to Spearman
    (the conservative choice, since normality cannot be established)."""
    series = series.dropna()
    if len(series) < 8:
        return False
    stat, p_value = stats.shapiro(series)
    return p_value > 0.05  # fail to reject normality at alpha = 0.05


def correlation_analysis(df: pd.DataFrame) -> pd.DataFrame:
    """Section 3.11.3: the five operational pairs, using Pearson where
    both variables pass the normality check, Spearman otherwise."""
    pairs = [
        ("attribute_count", "proving_time"),
        ("attribute_count", "peak_memory"),
        ("circuit_size", "proving_time"),
        ("circuit_size", "proof_size"),
        ("circuit_size", "local_verify_time"),
    ]
    rows = []
    for x_col, y_col in pairs:
        if x_col not in df.columns or y_col not in df.columns:
            continue
        sub = df[[x_col, y_col]].dropna()
        if len(sub) < 3:
            continue
        both_normal = normality_ok(sub[x_col]) and normality_ok(sub[y_col])
        if both_normal:
            corr, p_value = stats.pearsonr(sub[x_col], sub[y_col])
            method = "Pearson"
        else:
            corr, p_value = stats.spearmanr(sub[x_col], sub[y_col])
            method = "Spearman"
        rows.append({
            "pair": f"{x_col} vs {y_col}", "method": method,
            "n": len(sub), "correlation": round(corr, 4), "p_value": round(p_value, 6),
        })
    return pd.DataFrame(rows)


def offchain_onchain_summary(df: pd.DataFrame) -> str:
    """Section 3.11.4: compares the percentage growth in proving_time
    against the percentage growth in ethereum_gas, from the least to the
    most complex scenario with data available, and reports whether the
    decoupling hypothesis holds."""
    if "ethereum_gas" not in df.columns or df["ethereum_gas"].dropna().empty:
        return ("No ethereum_gas data present yet -- run the Foundry gas "
                "measurement step and merge it in before this comparison "
                "can be computed (see scripts/merge_gas_results.py).")

    by_scenario = df.groupby("scenario_id").agg(
        mean_proving_time=("proving_time", "mean"),
        mean_ethereum_gas=("ethereum_gas", "mean"),
        mean_circuit_size=("circuit_size", "mean"),
    ).sort_values("mean_circuit_size")

    if len(by_scenario) < 2:
        return "Need at least two scenarios with valid data to compare scaling."

    simplest = by_scenario.iloc[0]
    most_complex = by_scenario.iloc[-1]
    proving_growth_pct = (most_complex.mean_proving_time / simplest.mean_proving_time - 1) * 100
    gas_growth_pct = (most_complex.mean_ethereum_gas / simplest.mean_ethereum_gas - 1) * 100

    verdict = (
        "SUPPORTS the decoupling hypothesis (proving cost grew far faster than gas)"
        if proving_growth_pct > 3 * gas_growth_pct
        else "does NOT clearly support decoupling -- gas grew nearly as fast as proving cost"
    )
    return (
        f"From {by_scenario.index[0]} to {by_scenario.index[-1]}:\n"
        f"  Proving time grew by {proving_growth_pct:.1f}%\n"
        f"  Ethereum verification gas grew by {gas_growth_pct:.1f}%\n"
        f"  -> This {verdict}."
    )


def make_figures(df: pd.DataFrame, out_dir: Path):
    if plt is None:
        print("matplotlib not available -- skipping figure generation. "
              "Install with: pip install matplotlib --break-system-packages")
        return
    out_dir.mkdir(parents=True, exist_ok=True)

    def scatter(x, y, title, filename, logy=False):
        if x not in df.columns or y not in df.columns:
            return
        sub = df[[x, y, "scenario_id"]].dropna()
        if sub.empty:
            return
        fig, ax = plt.subplots(figsize=(7, 5))
        for scenario, group in sub.groupby("scenario_id"):
            ax.scatter(group[x], group[y], label=scenario, alpha=0.7)
        ax.set_xlabel(x)
        ax.set_ylabel(y)
        ax.set_title(title)
        if logy:
            ax.set_yscale("log")
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(out_dir / filename, dpi=150)
        plt.close(fig)

    scatter("attribute_count", "proving_time", "Figure 3.1: Attribute Count vs. Proof-Generation Time", "figure_3_1.png")
    scatter("attribute_count", "peak_memory", "Figure 3.2: Attribute Count vs. Peak Memory Usage", "figure_3_2.png")
    scatter("circuit_size", "proving_time", "Figure 3.3: Circuit Size vs. Proof-Generation Time", "figure_3_3.png")
    # NOTE: proof_size is the OFF-CHAIN (default/Poseidon2-target) proof
    # from run_benchmark.py -- used here correctly, against the off-chain
    # circuit_size. It is a different artifact from the ON-CHAIN
    # (EVM/Keccak-target) proof that determines calldata (see
    # scripts/fix_calldata_measurement.py); do not compare proof_size
    # against calldata_size directly, they were built with different `bb`
    # targets and are not the same bytes.
    scatter("circuit_size", "proof_size", "Figure 3.4: Circuit Size vs. Off-Chain Proof Size", "figure_3_4.png")
    scatter("circuit_size", "local_verify_time", "Figure 3.5: Circuit Size vs. Local Verification Time", "figure_3_5.png")
    scatter("circuit_size", "ethereum_gas", "Figure 3.6: Circuit Size vs. Ethereum Verification Gas", "figure_3_6.png")
    scatter("onchain_proof_size", "calldata_size", "Figure 3.7: On-Chain Proof Size vs. Transaction Calldata Size", "figure_3_7.png")

    # Figure 3.8: off-chain vs on-chain scaling trend, normalized to the
    # simplest scenario so both series can share one axis.
    if "ethereum_gas" in df.columns and not df["ethereum_gas"].dropna().empty:
        by_scenario = df.groupby("scenario_id").agg(
            proving_time=("proving_time", "mean"),
            ethereum_gas=("ethereum_gas", "mean"),
            circuit_size=("circuit_size", "mean"),
        ).sort_values("circuit_size")
        base = by_scenario.iloc[0]
        normalized = by_scenario.assign(
            proving_time_norm=by_scenario.proving_time / base.proving_time,
            ethereum_gas_norm=by_scenario.ethereum_gas / base.ethereum_gas,
        )
        fig, ax = plt.subplots(figsize=(7, 5))
        ax.plot(normalized.index, normalized.proving_time_norm, marker="o", label="Proving time (normalized)")
        ax.plot(normalized.index, normalized.ethereum_gas_norm, marker="s", label="Ethereum gas (normalized)")
        ax.set_ylabel("Fold-increase over simplest scenario")
        ax.set_title("Figure 3.8: Off-Chain Proving vs. On-Chain Verification Scaling")
        ax.legend()
        plt.xticks(rotation=20, ha="right")
        fig.tight_layout()
        fig.savefig(out_dir / "figure_3_8.png", dpi=150)
        plt.close(fig)
    else:
        print("Skipping Figure 3.8 -- no ethereum_gas data merged in yet.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=str, default=str(RESULTS_DIR / "benchmark_results.csv"))
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"ERROR: {csv_path} not found. Run run_benchmark.py first.")
        return

    df = load_data(csv_path)
    if df.empty:
        print("No successful (verification_status == True) rows found -- nothing to analyze.")
        return

    print(f"Loaded {len(df)} successful trials across {df['scenario_id'].nunique()} scenarios.\n")

    desc = descriptive_stats(df)
    desc.to_csv(RESULTS_DIR / "descriptive_stats.csv", index=False)
    print("=== Descriptive statistics (Section 3.11.1) ===")
    print(desc.to_string(index=False))
    print(f"\nSaved to {RESULTS_DIR / 'descriptive_stats.csv'}\n")

    corr = correlation_analysis(df)
    corr.to_csv(RESULTS_DIR / "correlations.csv", index=False)
    print("=== Correlation analysis (Section 3.11.3, Pearson/Spearman chosen automatically) ===")
    print(corr.to_string(index=False))
    print(f"\nSaved to {RESULTS_DIR / 'correlations.csv'}\n")

    print("=== Off-chain vs. on-chain scaling (Section 3.11.4) ===")
    print(offchain_onchain_summary(df))
    print()

    make_figures(df, RESULTS_DIR / "figures")
    print(f"Figures (where data allowed) saved to {RESULTS_DIR / 'figures'}")


if __name__ == "__main__":
    main()
