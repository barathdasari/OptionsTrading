"""
Script: EXP-001 full statistical validation.

Runs all pre-registered tests (M0_EXPERIMENT_001.md Section 8):
  8.1  Bootstrap test — bounce rate lift + 95% CI
  8.2  Permutation test — null distribution from shuffled labels
  8.3  Return distribution — Welch t, Mann-Whitney U, KS
  8.4  Economic edge — net expectancy CI vs estimated cost
  8.5  Subgroup analysis — regime breakdown with Bonferroni correction

Saves:
  reports/EXP-001/exp001_results_training.json    (or validation / oos)
  reports/EXP-001/exp001_summary_report.txt
  reports/EXP-001/charts/07_bootstrap_dist.png
  reports/EXP-001/charts/08_permutation_dist.png
  reports/EXP-001/charts/09_return_distributions.png
  reports/EXP-001/charts/10_economic_edge.png
  reports/EXP-001/charts/11_subgroup_heatmap.png

Usage
-----
    python scripts/05_statistical_tests.py
    python scripts/05_statistical_tests.py --split training
    python scripts/05_statistical_tests.py --split oos   # unlocks holdout

IMPORTANT: --split oos should only be run ONCE, when all parameters are frozen.
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.data.storage import read_raw, read_processed
from src.research.stats import (
    run_bootstrap_test,
    run_permutation_test,
    run_return_distribution_test,
    run_economic_edge_test,
    run_subgroup_analysis,
    FullTestSuite,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

REPORTS_DIR = PROJECT_ROOT / "reports" / "EXP-001"
CHARTS_DIR  = REPORTS_DIR / "charts"

# Data splits — 60% train / 20% validation / 20% holdout
SPLIT_DATES = {
    "training":   (None, "2019-06-30"),
    "validation": ("2019-07-01", "2022-12-31"),
    "oos":        ("2023-01-01", None),   # holdout — touch once only
}

COLORS = {
    "zone":    "#3498db",
    "control": "#e67e22",
    "null":    "#95a5a6",
    "observed":"#e74c3c",
    "pass":    "#2ecc71",
    "fail":    "#e74c3c",
}


def main():
    parser = argparse.ArgumentParser(description="EXP-001 statistical tests")
    parser.add_argument(
        "--split", default="training",
        choices=["training", "validation", "oos"],
        help="Data split to evaluate (default: training)",
    )
    parser.add_argument(
        "--cost-per-atr", type=float, default=0.15,
        help="Estimated round-trip cost as ATR fraction (default: 0.15)",
    )
    args = parser.parse_args()

    if args.split == "oos":
        logger.warning(
            "=" * 60 + "\n"
            "WARNING: You are evaluating the HOLDOUT (OOS) dataset.\n"
            "This should only be done ONCE with frozen parameters.\n"
            "Confirm: this is your final, one-time OOS evaluation.\n"
            + "=" * 60
        )

    CHARTS_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("EXP-001 Statistical Tests — %s split", args.split.upper())
    logger.info("=" * 60)

    # ── Load ─────────────────────────────────────────────────────────────────
    start, end = SPLIT_DATES[args.split]
    try:
        event_log   = read_processed("event_log",   experiment_id="EXP-001")
        control_log = read_processed("control_log",  experiment_id="EXP-001")
    except FileNotFoundError as e:
        logger.error("%s\nRun scripts 03 and 04 first.", e)
        sys.exit(1)

    # Reset index if timestamp is index
    for df_name, df in [("event_log", event_log), ("control_log", control_log)]:
        if "touch_timestamp" not in df.columns and "control_timestamp" not in df.columns:
            pass  # already has correct columns

    # Apply split date filter
    ts_col = "touch_timestamp" if "touch_timestamp" in event_log.columns else event_log.index.name
    if ts_col in event_log.columns:
        event_log[ts_col] = pd.to_datetime(event_log[ts_col])
        if start:
            event_log = event_log[event_log[ts_col] >= pd.Timestamp(start, tz="Asia/Kolkata")]
        if end:
            event_log = event_log[event_log[ts_col] <= pd.Timestamp(end, tz="Asia/Kolkata")]
    else:
        if start:
            event_log = event_log[event_log.index >= pd.Timestamp(start, tz="Asia/Kolkata")]
        if end:
            event_log = event_log[event_log.index <= pd.Timestamp(end, tz="Asia/Kolkata")]

    # Filter controls to same date range using touch_timestamp
    if "touch_timestamp" in control_log.columns:
        control_log["touch_timestamp"] = pd.to_datetime(control_log["touch_timestamp"])
        if start:
            control_log = control_log[
                control_log["touch_timestamp"] >= pd.Timestamp(start, tz="Asia/Kolkata")
            ]
        if end:
            control_log = control_log[
                control_log["touch_timestamp"] <= pd.Timestamp(end, tz="Asia/Kolkata")
            ]

    logger.info("Events in split  : %d", len(event_log))
    logger.info("Controls in split: %d", len(control_log))

    if len(event_log) < 50:
        logger.error("Too few events (%d) for reliable statistics.", len(event_log))
        sys.exit(1)

    if len(control_log) < 50:
        logger.error("Too few controls (%d). Re-run scripts/04_detect_events.py.", len(control_log))
        sys.exit(1)

    # ── Run tests ────────────────────────────────────────────────────────────
    logger.info("Running bootstrap test (%d resamples)...", 10_000)
    bootstrap = run_bootstrap_test(event_log, control_log)

    logger.info("Running permutation test (%d permutations)...", 10_000)
    permutation = run_permutation_test(event_log, control_log)

    logger.info("Running return distribution tests...")
    returns = run_return_distribution_test(event_log, control_log)

    logger.info("Running economic edge test...")
    economic = run_economic_edge_test(
        event_log, cost_per_atr=args.cost_per_atr
    )

    logger.info("Running subgroup analysis...")
    subgroups = run_subgroup_analysis(event_log, bootstrap.observed_rate)

    suite = FullTestSuite(
        bootstrap=bootstrap,
        permutation=permutation,
        returns=returns,
        economic=economic,
        subgroups=subgroups,
        dataset_name=args.split.upper(),
    )

    # ── Print summary ────────────────────────────────────────────────────────
    summary_text = suite.summary()
    print("\n" + summary_text.encode("ascii", errors="replace").decode("ascii"))

    # ── Save JSON results ────────────────────────────────────────────────────
    results_path = REPORTS_DIR / f"exp001_results_{args.split}.json"
    _save_json(suite, results_path)
    logger.info("Results saved: %s", results_path)

    # ── Save text report ─────────────────────────────────────────────────────
    report_path = REPORTS_DIR / "exp001_summary_report.txt"
    report_path.write_text(
        summary_text.encode("ascii", errors="replace").decode("ascii")
    )
    logger.info("Report saved: %s", report_path)

    # ── Charts ───────────────────────────────────────────────────────────────
    logger.info("Generating charts...")
    chart07_bootstrap_dist(bootstrap, args.split)
    chart08_permutation_dist(permutation, args.split)
    chart09_return_distributions(event_log, control_log, returns, args.split)
    chart10_economic_edge(economic, args.split)
    chart11_subgroup_heatmap(subgroups, bootstrap.observed_rate, args.split)

    logger.info("Charts saved to: %s", CHARTS_DIR)
    logger.info("")
    logger.info("M0 Gates: Statistical=%s  Economic=%s",
                "PASS" if suite.gate1_statistical else "FAIL",
                "PASS" if suite.gate2_economic    else "FAIL")


# ── Chart functions ───────────────────────────────────────────────────────────

def chart07_bootstrap_dist(result, split_name):
    path = CHARTS_DIR / "07_bootstrap_dist.png"
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # Zone bounce rate distribution
    ax1.hist(result.bootstrap_zone_rates, bins=60,
             color=COLORS["zone"], edgecolor="none", alpha=0.7, density=True,
             label="Zone bootstrap")
    ax1.hist(result.bootstrap_control_rates, bins=60,
             color=COLORS["control"], edgecolor="none", alpha=0.7, density=True,
             label="Control bootstrap")
    ax1.axvline(result.observed_rate, color="navy", lw=2,
                label=f"Zone obs: {result.observed_rate:.1f}%")
    ax1.axvline(result.baseline_rate, color="darkorange", lw=2,
                label=f"Control obs: {result.baseline_rate:.1f}%")
    ax1.axvline(result.ci_low, color=COLORS["zone"], lw=1.5, linestyle="--",
                label=f"95% CI: [{result.ci_low:.1f}, {result.ci_high:.1f}]%")
    ax1.axvline(result.ci_high, color=COLORS["zone"], lw=1.5, linestyle="--")
    ax1.set_title(f"Bootstrap: Bounce Rate Distributions\n({split_name})", fontsize=12)
    ax1.set_xlabel("Bounce Rate (%)")
    ax1.set_ylabel("Density")
    ax1.legend(fontsize=8)
    ax1.grid(alpha=0.3)

    # Lift distribution
    bs_lifts = result.bootstrap_zone_rates - result.bootstrap_control_rates
    color_lift = COLORS["pass"] if result.lift_ci_low > 0 else COLORS["fail"]
    ax2.hist(bs_lifts, bins=60, color=color_lift, edgecolor="none", alpha=0.7, density=True)
    ax2.axvline(result.lift_pp, color="black", lw=2,
                label=f"Observed lift: {result.lift_pp:+.1f}pp")
    ax2.axvline(result.lift_ci_low, color="gray", lw=1.5, linestyle="--",
                label=f"95% CI: [{result.lift_ci_low:+.1f}, {result.lift_ci_high:+.1f}]pp")
    ax2.axvline(result.lift_ci_high, color="gray", lw=1.5, linestyle="--")
    ax2.axvline(0, color="black", lw=1, linestyle="-", alpha=0.4, label="Zero lift")
    ax2.set_title(f"Bootstrap: Lift Distribution\np={result.p_value:.4f}", fontsize=12)
    ax2.set_xlabel("Lift (pp)")
    ax2.set_ylabel("Density")
    ax2.legend(fontsize=8)
    ax2.grid(alpha=0.3)

    fig.suptitle("EXP-001: Bootstrap Test Results", fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Chart 07 saved: %s", path.name)


def chart08_permutation_dist(result, split_name):
    path = CHARTS_DIR / "08_permutation_dist.png"
    fig, ax = plt.subplots(figsize=(9, 5))

    ax.hist(result.null_distribution, bins=80,
            color=COLORS["null"], edgecolor="none", alpha=0.8, density=True,
            label="Null distribution (shuffled labels)")
    ax.axvline(result.observed_lift, color=COLORS["observed"], lw=2.5,
               label=f"Observed lift: {result.observed_lift:+.1f}pp")

    # Shade the tail
    cutoff = np.percentile(result.null_distribution, 95)
    tail_x = result.null_distribution[result.null_distribution >= cutoff]
    if len(tail_x) > 0:
        ax.hist(tail_x, bins=30, color=COLORS["observed"],
                edgecolor="none", alpha=0.4, density=True, label="Top 5% of null")

    ax.axvline(cutoff, color="gray", lw=1.5, linestyle="--",
               label=f"95th pct of null: {cutoff:+.2f}pp")

    sig_text = "SIGNIFICANT" if result.significant else "NOT SIGNIFICANT"
    color    = COLORS["pass"] if result.significant else COLORS["fail"]
    ax.set_title(
        f"EXP-001: Permutation Test — {split_name}\n"
        f"p={result.p_value:.4f}  [{sig_text}]",
        fontsize=12, color=color,
    )
    ax.set_xlabel("Lift under null (pp)")
    ax.set_ylabel("Density")
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Chart 08 saved: %s", path.name)


def chart09_return_distributions(event_log, control_log, result, split_name):
    path = CHARTS_DIR / "09_return_distributions.png"
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    z_rets = event_log["forward_return_6bar"].dropna() * 100
    c_rets = control_log["forward_return_6bar"].dropna() * 100

    # Histogram overlay
    bins = np.linspace(
        min(z_rets.quantile(0.01), c_rets.quantile(0.01)),
        max(z_rets.quantile(0.99), c_rets.quantile(0.99)),
        50,
    )
    ax1.hist(z_rets, bins=bins, color=COLORS["zone"],  alpha=0.6,
             density=True, label=f"Zone (n={len(z_rets)}, mu={z_rets.mean():.2f}%)")
    ax1.hist(c_rets, bins=bins, color=COLORS["control"], alpha=0.6,
             density=True, label=f"Control (n={len(c_rets)}, mu={c_rets.mean():.2f}%)")
    ax1.axvline(z_rets.mean(), color="navy",       lw=2, linestyle="--")
    ax1.axvline(c_rets.mean(), color="darkorange",  lw=2, linestyle="--")
    ax1.set_title(f"6-Bar Forward Returns\n(Welch p={result.welch_p:.4f})", fontsize=12)
    ax1.set_xlabel("6-Bar Return (%)")
    ax1.set_ylabel("Density")
    ax1.legend(fontsize=9)
    ax1.grid(alpha=0.3)

    # CDF comparison
    z_sorted = np.sort(z_rets)
    c_sorted = np.sort(c_rets)
    ax2.plot(z_sorted, np.linspace(0, 1, len(z_sorted)),
             color=COLORS["zone"], lw=2, label="Zone CDF")
    ax2.plot(c_sorted, np.linspace(0, 1, len(c_sorted)),
             color=COLORS["control"], lw=2, label="Control CDF")
    ax2.set_title(
        f"CDF Comparison\n(KS stat={result.ks_stat:.3f}  p={result.ks_p:.4f})",
        fontsize=12,
    )
    ax2.set_xlabel("6-Bar Return (%)")
    ax2.set_ylabel("Cumulative Probability")
    ax2.legend(fontsize=9)
    ax2.grid(alpha=0.3)

    fig.suptitle(f"EXP-001: Return Distributions — {split_name}",
                 fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Chart 09 saved: %s", path.name)


def chart10_economic_edge(result, split_name):
    path = CHARTS_DIR / "10_economic_edge.png"
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    # Net expectancy bar with CI
    color = COLORS["pass"] if result.positive_edge else COLORS["fail"]
    ax1.bar(["Net Expectancy\n(ATR units)"], [result.net_expectancy],
            color=color, edgecolor="white", width=0.4)
    ax1.errorbar(["Net Expectancy\n(ATR units)"],
                 [result.net_expectancy],
                 yerr=[[result.net_expectancy - result.ci_low],
                       [result.ci_high - result.net_expectancy]],
                 fmt="none", color="black", capsize=8, lw=2, capthick=2)
    ax1.axhline(0, color="black", lw=1.5, linestyle="--", alpha=0.6)
    ax1.text(0, result.ci_high + 0.01,
             f"95% CI: [{result.ci_low:+.3f}, {result.ci_high:+.3f}]",
             ha="center", va="bottom", fontsize=10)
    ax1.set_title(
        f"Net Expectancy per Trade\n"
        f"({'POSITIVE EDGE' if result.positive_edge else 'NO EDGE'})",
        fontsize=12,
        color=color,
    )
    ax1.set_ylabel("ATR units")
    ax1.grid(axis="y", alpha=0.3)

    # Gross vs Cost breakdown
    categories = ["Gross\nExpectancy", "Round-trip\nCost", "Net\nExpectancy"]
    values     = [result.gross_expectancy, -result.cost_per_trade, result.net_expectancy]
    bar_colors = [COLORS["zone"], COLORS["fail"], color]
    bars = ax2.bar(categories, values, color=bar_colors, edgecolor="white")
    for bar, v in zip(bars, values):
        ax2.text(bar.get_x() + bar.get_width() / 2,
                 v + (0.005 if v >= 0 else -0.015),
                 f"{v:+.3f}",
                 ha="center", va="bottom" if v >= 0 else "top", fontsize=10,
                 fontweight="bold")
    ax2.axhline(0, color="black", lw=1.5, linestyle="--", alpha=0.6)
    ax2.set_title(f"P&L Breakdown (ATR units)\nCost = {result.cost_pct_gross:.1f}% of gross",
                  fontsize=12)
    ax2.set_ylabel("ATR units")
    ax2.grid(axis="y", alpha=0.3)

    fig.suptitle(f"EXP-001: Economic Edge — {split_name}",
                 fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Chart 10 saved: %s", path.name)


def chart11_subgroup_heatmap(subgroups, overall_rate, split_name):
    path = CHARTS_DIR / "11_subgroup_heatmap.png"
    if not subgroups:
        return

    data = pd.DataFrame([{
        "subgroup": sg.subgroup,
        "bounce_rate": sg.bounce_rate,
        "lift": sg.lift_vs_overall,
        "p_value": sg.p_value_vs_overall,
        "n": sg.n,
    } for sg in subgroups])

    data = data.sort_values("bounce_rate", ascending=False).reset_index(drop=True)
    n_rows = len(data)

    fig, ax = plt.subplots(figsize=(12, max(5, n_rows * 0.4 + 2)))

    # Horizontal bar
    colors = [
        COLORS["pass"] if row["bounce_rate"] > overall_rate else COLORS["fail"]
        for _, row in data.iterrows()
    ]
    bars = ax.barh(data["subgroup"], data["bounce_rate"],
                   color=colors, edgecolor="white", alpha=0.8)

    ax.axvline(overall_rate, color="black", lw=2, linestyle="--",
               label=f"Overall: {overall_rate:.1f}%")

    for bar, (_, row) in zip(bars, data.iterrows()):
        sig_marker = "*" if row["p_value"] < 0.05 else ""
        ax.text(row["bounce_rate"] + 0.3,
                bar.get_y() + bar.get_height() / 2,
                f"{row['bounce_rate']:.1f}%{sig_marker}  (n={row['n']})",
                va="center", fontsize=8)

    ax.set_xlabel("Bounce Rate (%)")
    ax.set_xlim(0, data["bounce_rate"].max() * 1.2)
    ax.set_title(
        f"EXP-001: Subgroup Bounce Rates — {split_name}\n"
        f"* = p < 0.05 (two-proportion z-test, uncorrected)",
        fontsize=12,
    )
    ax.legend(fontsize=9)
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Chart 11 saved: %s", path.name)


# ── JSON serialisation ────────────────────────────────────────────────────────

def _save_json(suite: FullTestSuite, path: Path) -> None:
    out = {
        "run_timestamp": datetime.utcnow().isoformat(),
        "dataset": suite.dataset_name,
        "bootstrap": {
            "observed_zone_rate": suite.bootstrap.observed_rate,
            "ci_95": [suite.bootstrap.ci_low, suite.bootstrap.ci_high],
            "baseline_rate": suite.bootstrap.baseline_rate,
            "lift_pp": suite.bootstrap.lift_pp,
            "lift_ci_95": [suite.bootstrap.lift_ci_low, suite.bootstrap.lift_ci_high],
            "p_value": suite.bootstrap.p_value,
            "n_zone": suite.bootstrap.n_zone,
            "n_control": suite.bootstrap.n_control,
            "significant": suite.bootstrap.significant,
        },
        "permutation": {
            "observed_lift": suite.permutation.observed_lift,
            "null_mean": suite.permutation.null_mean,
            "null_std": suite.permutation.null_std,
            "p_value": suite.permutation.p_value,
            "significant": suite.permutation.significant,
        },
        "returns": {
            "zone_mean_return": suite.returns.zone_mean_return,
            "control_mean_return": suite.returns.control_mean_return,
            "return_lift": suite.returns.return_lift,
            "welch_p": suite.returns.welch_p,
            "mannwhitney_p": suite.returns.mannwhitney_p,
            "ks_p": suite.returns.ks_p,
            "significant": suite.returns.significant,
        },
        "economic": {
            "gross_expectancy_atr": suite.economic.gross_expectancy,
            "cost_per_trade_atr": suite.economic.cost_per_trade,
            "net_expectancy_atr": suite.economic.net_expectancy,
            "net_ci_95": [suite.economic.ci_low, suite.economic.ci_high],
            "cost_pct_gross": suite.economic.cost_pct_gross,
            "positive_edge": suite.economic.positive_edge,
            "note": suite.economic.note,
        },
        "subgroups": [
            {
                "subgroup": sg.subgroup,
                "bounce_rate": sg.bounce_rate,
                "lift_vs_overall": sg.lift_vs_overall,
                "p_value": sg.p_value_vs_overall,
                "n": sg.n,
            }
            for sg in suite.subgroups
        ],
        "gates": {
            "gate1_statistical": suite.gate1_statistical,
            "gate2_economic":    suite.gate2_economic,
            "m0_decision":       "GO" if suite.m0_go else "INVESTIGATE",
        },
    }
    path.write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
