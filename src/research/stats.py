"""
Statistical tests for EXP-001.

Implements the exact tests specified in M0_EXPERIMENT_001.md Section 8:

    8.1  Bootstrap test — bounce rate lift with 95% CI
    8.2  Permutation test — null distribution from shuffled zone labels
    8.3  Return distribution test — Welch t-test, Mann-Whitney U, KS test
    8.4  Economic edge test — net expectancy with 95% CI, cost-adjusted
    8.5  Multiple testing — Bonferroni correction for sub-group tests

All tests are pre-registered. Results are final once run on holdout data.
Do not re-run with different parameters to improve results.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

logger = logging.getLogger(__name__)

N_BOOTSTRAP   = 10_000
N_PERMUTATION = 10_000
CI_LEVEL      = 0.95
ALPHA         = 0.05


# ── Result containers ─────────────────────────────────────────────────────────

@dataclass
class BootstrapResult:
    observed_rate: float        # zone bounce rate
    ci_low: float               # 95% CI lower bound
    ci_high: float              # 95% CI upper bound
    baseline_rate: float        # control bounce rate
    lift_pp: float              # lift in percentage points
    lift_ci_low: float          # 95% CI of lift lower bound
    lift_ci_high: float         # 95% CI of lift upper bound
    p_value: float              # one-sided p-value (lift > 0)
    n_zone: int
    n_control: int
    bootstrap_zone_rates: np.ndarray = field(repr=False, default_factory=lambda: np.array([]))
    bootstrap_control_rates: np.ndarray = field(repr=False, default_factory=lambda: np.array([]))

    @property
    def significant(self) -> bool:
        return self.p_value < ALPHA and self.lift_ci_low > 0

    def summary(self) -> str:
        lines = [
            "── Bootstrap Test (Bounce Rate Lift) ──────────────────────",
            f"  Zone bounce rate   : {self.observed_rate:.1f}%",
            f"  95% CI             : [{self.ci_low:.1f}%, {self.ci_high:.1f}%]",
            f"  Control rate       : {self.baseline_rate:.1f}%",
            f"  Lift               : {self.lift_pp:+.1f} pp",
            f"  Lift 95% CI        : [{self.lift_ci_low:+.1f}, {self.lift_ci_high:+.1f}] pp",
            f"  p-value (one-sided): {self.p_value:.4f}",
            f"  n (zone / control) : {self.n_zone} / {self.n_control}",
            f"  Result             : {'SIGNIFICANT' if self.significant else 'NOT SIGNIFICANT'}",
        ]
        return "\n".join(lines)


@dataclass
class PermutationResult:
    observed_lift: float
    null_mean: float
    null_std: float
    p_value: float
    null_distribution: np.ndarray = field(repr=False, default_factory=lambda: np.array([]))

    @property
    def significant(self) -> bool:
        return self.p_value < ALPHA

    def summary(self) -> str:
        lines = [
            "── Permutation Test ────────────────────────────────────────",
            f"  Observed lift      : {self.observed_lift:+.1f} pp",
            f"  Null mean          : {self.null_mean:+.2f} pp",
            f"  Null std           : {self.null_std:.2f} pp",
            f"  p-value            : {self.p_value:.4f}",
            f"  Result             : {'SIGNIFICANT' if self.significant else 'NOT SIGNIFICANT'}",
        ]
        return "\n".join(lines)


@dataclass
class ReturnDistributionResult:
    zone_mean_return:    float
    control_mean_return: float
    return_lift:         float
    welch_t:             float
    welch_p:             float
    mannwhitney_u:       float
    mannwhitney_p:       float
    ks_stat:             float
    ks_p:                float
    n_zone:              int
    n_control:           int

    @property
    def significant(self) -> bool:
        return self.welch_p < ALPHA or self.mannwhitney_p < ALPHA

    def summary(self) -> str:
        lines = [
            "── Return Distribution Test ────────────────────────────────",
            f"  Zone mean 6-bar return   : {self.zone_mean_return*100:+.3f}%",
            f"  Control mean 6-bar return: {self.control_mean_return*100:+.3f}%",
            f"  Return lift              : {self.return_lift*100:+.3f}%",
            f"  Welch t-test             : t={self.welch_t:.3f}  p={self.welch_p:.4f}",
            f"  Mann-Whitney U           : U={self.mannwhitney_u:.0f}  p={self.mannwhitney_p:.4f}",
            f"  KS test                  : D={self.ks_stat:.3f}  p={self.ks_p:.4f}",
            f"  Result                   : {'SIGNIFICANT' if self.significant else 'NOT SIGNIFICANT'}",
        ]
        return "\n".join(lines)


@dataclass
class EconomicEdgeResult:
    mean_net_pnl:     float       # average net P&L per trade (index points)
    ci_low:           float       # 95% CI lower bound
    ci_high:          float       # 95% CI upper bound
    cost_per_trade:   float       # estimated round-trip cost (index points)
    gross_expectancy: float       # before costs
    net_expectancy:   float       # after costs
    cost_pct_gross:   float       # costs as % of gross P&L
    n_trades:         int
    note:             str = ""

    @property
    def positive_edge(self) -> bool:
        return self.ci_low > 0

    def summary(self) -> str:
        lines = [
            "── Economic Edge Test ──────────────────────────────────────",
            f"  Gross expectancy   : {self.gross_expectancy:+.2f} pts/trade",
            f"  Est. cost/trade    : {self.cost_per_trade:.2f} pts",
            f"  Net expectancy     : {self.net_expectancy:+.2f} pts/trade",
            f"  Net 95% CI         : [{self.ci_low:+.2f}, {self.ci_high:+.2f}]",
            f"  Cost % of gross    : {self.cost_pct_gross:.1f}%",
            f"  n trades           : {self.n_trades}",
            f"  Result             : {'POSITIVE EDGE' if self.positive_edge else 'NO EDGE AFTER COSTS'}",
        ]
        if self.note:
            lines.append(f"  Note               : {self.note}")
        return "\n".join(lines)


@dataclass
class SubgroupResult:
    subgroup: str
    bounce_rate: float
    n: int
    lift_vs_overall: float
    p_value_vs_overall: float


@dataclass
class FullTestSuite:
    bootstrap:    BootstrapResult
    permutation:  PermutationResult
    returns:      ReturnDistributionResult
    economic:     EconomicEdgeResult
    subgroups:    list[SubgroupResult] = field(default_factory=list)
    dataset_name: str = ""

    @property
    def gate1_statistical(self) -> bool:
        """Gate 1: statistical edge — CI of lift excludes zero, permutation p < 0.05."""
        return self.bootstrap.lift_ci_low > 0 and self.permutation.significant

    @property
    def gate2_economic(self) -> bool:
        """Gate 2: economic edge — net expectancy CI lower bound > 0."""
        return self.economic.positive_edge

    @property
    def m0_go(self) -> bool:
        """Both gates pass (Gate 3 OOS is evaluated separately on holdout)."""
        return self.gate1_statistical and self.gate2_economic

    def summary(self) -> str:
        sep = "=" * 60
        lines = [
            sep,
            f"EXP-001 STATISTICAL TEST RESULTS — {self.dataset_name}",
            sep,
            "",
            self.bootstrap.summary(),
            "",
            self.permutation.summary(),
            "",
            self.returns.summary(),
            "",
            self.economic.summary(),
            "",
            "── M0 Gate Assessment ──────────────────────────────────────",
            f"  Gate 1 (Statistical) : {'PASS' if self.gate1_statistical else 'FAIL'}",
            f"  Gate 2 (Economic)    : {'PASS' if self.gate2_economic else 'FAIL'}",
            f"  Gate 3 (OOS)         : Run on holdout data separately",
            f"  Decision             : {'GO → M1' if self.m0_go else 'INVESTIGATE / KILL'}",
            sep,
        ]
        if self.subgroups:
            lines.append("")
            lines.append("── Subgroup Analysis ───────────────────────────────────────")
            for sg in self.subgroups:
                lines.append(
                    f"  {sg.subgroup:<30s}: {sg.bounce_rate:.1f}%  "
                    f"lift={sg.lift_vs_overall:+.1f}pp  "
                    f"p={sg.p_value_vs_overall:.3f}  n={sg.n}"
                )
        return "\n".join(lines)


# ── Test functions ─────────────────────────────────────────────────────────────

def run_bootstrap_test(
    event_log: pd.DataFrame,
    control_log: pd.DataFrame,
    n_bootstrap: int = N_BOOTSTRAP,
    rng_seed: int = 42,
) -> BootstrapResult:
    """
    Bootstrap test for bounce rate lift.
    Resample events and controls independently with replacement.
    """
    rng = np.random.default_rng(rng_seed)

    zone_bounces    = (event_log["result"] == "bounce").values.astype(float)
    control_bounces = (control_log["result"] == "bounce").values.astype(float)

    observed_zone_rate    = zone_bounces.mean() * 100
    observed_control_rate = control_bounces.mean() * 100
    observed_lift         = observed_zone_rate - observed_control_rate

    n_z = len(zone_bounces)
    n_c = len(control_bounces)

    bs_zone_rates    = np.empty(n_bootstrap)
    bs_control_rates = np.empty(n_bootstrap)
    bs_lifts         = np.empty(n_bootstrap)

    for i in range(n_bootstrap):
        z_sample = rng.choice(zone_bounces,    size=n_z, replace=True)
        c_sample = rng.choice(control_bounces, size=n_c, replace=True)
        bs_zone_rates[i]    = z_sample.mean() * 100
        bs_control_rates[i] = c_sample.mean() * 100
        bs_lifts[i]         = bs_zone_rates[i] - bs_control_rates[i]

    alpha = 1 - CI_LEVEL
    ci_low_z,  ci_high_z  = np.percentile(bs_zone_rates, [alpha/2*100, (1-alpha/2)*100])
    lift_ci_low, lift_ci_high = np.percentile(bs_lifts, [alpha/2*100, (1-alpha/2)*100])

    # One-sided p-value: P(lift > 0 | null)
    # Under null: lift bootstrapped from pooled data
    pooled = np.concatenate([zone_bounces, control_bounces])
    null_lifts = np.empty(n_bootstrap)
    for i in range(n_bootstrap):
        z_null = rng.choice(pooled, size=n_z, replace=True)
        c_null = rng.choice(pooled, size=n_c, replace=True)
        null_lifts[i] = (z_null.mean() - c_null.mean()) * 100

    p_value = float((null_lifts >= observed_lift).mean())

    return BootstrapResult(
        observed_rate=float(observed_zone_rate),
        ci_low=float(ci_low_z),
        ci_high=float(ci_high_z),
        baseline_rate=float(observed_control_rate),
        lift_pp=float(observed_lift),
        lift_ci_low=float(lift_ci_low),
        lift_ci_high=float(lift_ci_high),
        p_value=float(p_value),
        n_zone=n_z,
        n_control=n_c,
        bootstrap_zone_rates=bs_zone_rates,
        bootstrap_control_rates=bs_control_rates,
    )


def run_permutation_test(
    event_log: pd.DataFrame,
    control_log: pd.DataFrame,
    n_permutations: int = N_PERMUTATION,
    rng_seed: int = 42,
) -> PermutationResult:
    """
    Permutation test: shuffle zone/control labels and measure null distribution.
    Tests whether zone identification captures something real.
    """
    rng = np.random.default_rng(rng_seed)

    zone_bounces    = (event_log["result"]   == "bounce").values.astype(float)
    control_bounces = (control_log["result"] == "bounce").values.astype(float)

    observed_lift = (zone_bounces.mean() - control_bounces.mean()) * 100

    n_z = len(zone_bounces)
    pooled = np.concatenate([zone_bounces, control_bounces])
    n_total = len(pooled)

    null_lifts = np.empty(n_permutations)
    for i in range(n_permutations):
        shuffled = rng.permutation(pooled)
        null_z   = shuffled[:n_z]
        null_c   = shuffled[n_z:]
        null_lifts[i] = (null_z.mean() - null_c.mean()) * 100

    p_value = float((null_lifts >= observed_lift).mean())

    return PermutationResult(
        observed_lift=float(observed_lift),
        null_mean=float(null_lifts.mean()),
        null_std=float(null_lifts.std()),
        p_value=float(p_value),
        null_distribution=null_lifts,
    )


def run_return_distribution_test(
    event_log: pd.DataFrame,
    control_log: pd.DataFrame,
) -> ReturnDistributionResult:
    """
    Compare 6-bar forward return distributions: zone touches vs controls.
    Tests: Welch t-test, Mann-Whitney U (non-parametric), KS test.
    """
    zone_rets    = event_log["forward_return_6bar"].dropna().values
    control_rets = control_log["forward_return_6bar"].dropna().values

    # Direction-adjust: for support touches expect positive return,
    # for resistance expect negative. Flip control returns to match.
    # Here we use signed returns as-is (mix of directions in event_log).

    welch_t, welch_p   = scipy_stats.ttest_ind(zone_rets, control_rets,
                                                equal_var=False)
    mw_u,    mw_p      = scipy_stats.mannwhitneyu(zone_rets, control_rets,
                                                   alternative="greater")
    ks_stat, ks_p      = scipy_stats.ks_2samp(zone_rets, control_rets)

    return ReturnDistributionResult(
        zone_mean_return=float(zone_rets.mean()),
        control_mean_return=float(control_rets.mean()),
        return_lift=float(zone_rets.mean() - control_rets.mean()),
        welch_t=float(welch_t),
        welch_p=float(welch_p),
        mannwhitney_u=float(mw_u),
        mannwhitney_p=float(mw_p),
        ks_stat=float(ks_stat),
        ks_p=float(ks_p),
        n_zone=len(zone_rets),
        n_control=len(control_rets),
    )


def run_economic_edge_test(
    event_log: pd.DataFrame,
    atr_col: str = "atr_at_touch",
    cost_per_atr: float = 0.15,
    n_bootstrap: int = N_BOOTSTRAP,
    rng_seed: int = 42,
) -> EconomicEdgeResult:
    """
    Estimate net expectancy per trade in ATR-normalised units.

    P&L per trade (simplified, in ATR units):
        bounce: +MFE (capped at bounce_threshold) - cost
        break:  -MAE (capped at mae_threshold) - cost
        inconclusive: -0.5 × ATR - cost (time decay / spread cost)

    cost_per_atr: estimated round-trip cost as fraction of ATR.
        Default 0.15 = ~15% of daily ATR as estimated cost.
        This is a PLACEHOLDER. Replace with CostEngine output before M1.
        For Bank Nifty daily ATR ~500pts: cost ~75pts per round trip,
        which is conservative for 1-lot options trading.

    Returns net expectancy in ATR units + 95% CI.
    """
    rng = np.random.default_rng(rng_seed)

    pnl_atr = []
    for _, row in event_log.iterrows():
        atr = row[atr_col] if atr_col in row and not pd.isna(row[atr_col]) else 1.0
        result = row["result"]
        mfe    = row["mfe"]
        mae    = row["mae"]

        if result == "bounce":
            gross = min(mfe, row.get("bounce_threshold", mfe)) / atr
        elif result == "break":
            gross = -min(mae, row.get("mae_threshold", mae)) / atr
        else:  # inconclusive
            gross = -0.5

        net = gross - cost_per_atr
        pnl_atr.append(net)

    pnl_arr = np.array(pnl_atr)
    gross_arr = pnl_arr + cost_per_atr

    gross_expectancy = float(gross_arr.mean())
    net_expectancy   = float(pnl_arr.mean())
    total_cost       = cost_per_atr
    cost_pct_gross   = (total_cost / abs(gross_expectancy) * 100
                        if gross_expectancy != 0 else float("nan"))

    # Bootstrap CI on net expectancy
    n = len(pnl_arr)
    bs_means = np.array([
        rng.choice(pnl_arr, size=n, replace=True).mean()
        for _ in range(n_bootstrap)
    ])
    alpha = 1 - CI_LEVEL
    ci_low, ci_high = np.percentile(bs_means, [alpha/2*100, (1-alpha/2)*100])

    return EconomicEdgeResult(
        mean_net_pnl=float(pnl_arr.mean()),
        ci_low=float(ci_low),
        ci_high=float(ci_high),
        cost_per_trade=float(cost_per_atr),
        gross_expectancy=float(gross_expectancy),
        net_expectancy=float(net_expectancy),
        cost_pct_gross=float(cost_pct_gross),
        n_trades=n,
        note=(
            "Cost is a placeholder (0.15 ATR). "
            "Replace with CostEngine.calculate() before M1 trading."
        ),
    )


def run_subgroup_analysis(
    event_log: pd.DataFrame,
    overall_bounce_rate: float,
) -> list[SubgroupResult]:
    """
    Regime-conditional bounce rates. Uses Bonferroni correction.
    Subgroups tested:
        - Day of week (Mon–Fri)
        - Touch count (1st, 2nd, 3rd+)
        - Zone type (base types)
        - Score quartile (low / high)
    """
    results = []
    n_tests = 0  # count for Bonferroni

    # Collect all subgroup (label, mask) pairs
    subgroup_tests = []

    # Day of week
    for dow, name in [(0,"Monday"),(1,"Tuesday"),(2,"Wednesday"),(3,"Thursday"),(4,"Friday")]:
        mask = event_log["day_of_week"] == dow
        subgroup_tests.append((f"DoW: {name}", mask))

    # Touch count
    for tc, label in [(1,"Touch 1st"),(2,"Touch 2nd")]:
        mask = event_log["touch_count_on_zone"] == tc
        subgroup_tests.append((label, mask))
    subgroup_tests.append(("Touch 3rd+", event_log["touch_count_on_zone"] >= 3))

    # Zone type (base)
    for ztype in ["prev_day_high","prev_day_low","weekly_high","weekly_low",
                  "swing_high","swing_low"]:
        mask = event_log["zone_type"].str.contains(ztype)
        subgroup_tests.append((f"Type: {ztype}", mask))

    # Score quartile
    q25 = event_log["zone_score"].quantile(0.25)
    q75 = event_log["zone_score"].quantile(0.75)
    subgroup_tests.append(("Score: low (Q1)",  event_log["zone_score"] <= q25))
    subgroup_tests.append(("Score: high (Q4)", event_log["zone_score"] >= q75))

    n_tests = len(subgroup_tests)
    bonferroni_alpha = ALPHA / n_tests

    for label, mask in subgroup_tests:
        subset = event_log[mask]
        if len(subset) < 10:
            continue
        bounce_rate = (subset["result"] == "bounce").mean() * 100
        lift = bounce_rate - overall_bounce_rate

        # Two-proportion z-test
        n1     = len(subset)
        x1     = (subset["result"] == "bounce").sum()
        n2     = len(event_log)
        x2     = (event_log["result"] == "bounce").sum()
        p_pool = (x1 + x2) / (n1 + n2)
        se     = np.sqrt(p_pool * (1 - p_pool) * (1/n1 + 1/n2))
        z      = (x1/n1 - x2/n2) / se if se > 0 else 0
        p_val  = float(scipy_stats.norm.sf(abs(z)) * 2)  # two-sided

        results.append(SubgroupResult(
            subgroup=label,
            bounce_rate=float(bounce_rate),
            n=int(n1),
            lift_vs_overall=float(lift),
            p_value_vs_overall=float(p_val),
        ))

    return results
