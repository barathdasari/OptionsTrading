# EXP-001 — Pre-Registered Experiment Specification
## Do Bank Nifty Structural Price Zones Produce Abnormal Reversal Probability?

**Experiment ID:** EXP-001
**Status:** PRE-REGISTERED — parameters frozen before any data analysis
**Created:** 2026-08-12
**Milestone:** M0

> RULE: No parameter below may be changed after data is loaded or any analysis is run.
> Robustness grid tests adjacent values but the primary reported result uses ONLY the primary parameters.

---

## 1. Hypothesis

**H0 (null):** Price reversal rate at identified Bank Nifty structural zones equals reversal rate at matched random controls. The zone identification algorithm captures no real phenomenon.

**H1 (alternative):** Price reversal rate at identified zones is statistically significantly higher than matched controls, and the net expectancy per trade after all costs is positive.

**Economic rationale:** Structural price levels (previous-day high/low, weekly high/low, volume-profile POC/VAH/VAL, swing pivots) may concentrate clustered orders (stops, entries, targets) from market participants who reference the same visible levels. This creates a potential order-flow mechanism for mean-reversion. Whether this concentration is strong enough to survive transaction costs is the empirical question.

**No options data in this experiment.** OI/IV/PCR tested in EXP-002 only after EXP-001 establishes whether price-derived zones have any effect at all.

---

## 2. Dataset

| Parameter | Value |
|---|---|
| Instrument | Bank Nifty **index** (not futures — avoids roll/expiry distortion) |
| Timeframe | 5-minute OHLCV bars |
| Date range | 2018-01-01 to present (verify available history from data source) |
| Minimum bars required | 50,000 bars (~4 years of intraday data) |
| Minimum zone-touch events required | 1,000 events in training set |
| Session filter | 09:15–15:30 IST only |
| Price series for signals | Bar **close** (not high/low/wick) |

**Contract metadata:** Expiry schedule and lot size loaded from `data/metadata/contract/` by date. No hardcoding.

**Cost rates:** Loaded from `data/metadata/cost_rates/` by date. No hardcoding.
Record `cost_schedule_version` in every backtest output.

---

## 3. Data Split

| Split | Period | Purpose |
|---|---|---|
| Training | First 60% of date range | Zone detection, parameter calibration |
| Validation | Next 20% | Walk-forward check during development |
| Final holdout | Last 20% | Touched ONCE — final OOS result only |

**The final holdout is locked.** Do not load, inspect, or query it until all parameters are frozen and the primary analysis on training + validation is complete.

---

## 4. Zone Types (EXP-001 — Price-Derived Only)

All zones use **causal/tradable mode** — computed exclusively from data available at signal timestamp t.

| Zone Type | Definition | Causal rule |
|---|---|---|
| Previous-day high | Prior session's highest close | Available from 09:15 on day D using day D-1 data |
| Previous-day low | Prior session's lowest close | Same |
| Weekly high | Highest close of prior complete week | Available from Monday 09:15 |
| Weekly low | Lowest close of prior complete week | Same |
| Swing pivot high | Local maximum using trailing window only | See Section 4.1 |
| Swing pivot low | Local minimum using trailing window only | See Section 4.1 |
| Volume Profile POC | Price with highest volume — **prior session only** | Prior session's complete profile |
| Volume Profile VAH | Value Area High — prior session | Same |
| Volume Profile VAL | Value Area Low — prior session | Same |

### 4.1 Causal Swing Pivot Detection

A bar at time t is a swing high **only if** it is the highest close in the trailing N=10 bars (bars t-10 through t). No look-forward.

```python
# Causal pivot high — trailing window only
is_pivot_high[t] = (close[t] == max(close[t-10 : t+1]))

# Causal pivot low — trailing window only
is_pivot_low[t] = (close[t] == min(close[t-10 : t+1]))
```

Pivots younger than 10 bars from current time are excluded (not yet confirmed).
Minimum reversal from pivot: 1.0 × ATR(14) to qualify as structurally significant.

### 4.2 Zone Width

```
zone_width = k × ATR(14)    where k = 0.5  [primary]
zone_low   = level - zone_width / 2
zone_high  = level + zone_width / 2
```

ATR(14) computed from bars up to and including bar t-1 only (causal).

Robustness grid (secondary, not for parameter selection): k = 0.25, 0.75

### 4.3 Zone Scoring and Confluence

Each active zone is scored:
```
score = volume_concentration_rank     # 0–1, normalized rank of volume at this level
      + (1 if zone appears in 2+ zone types else 0)   # confluence bonus
      + recency_weight                # 1.0 if formed within 5 days, 0.5 otherwise
```

Score used for analysis — not for filtering. Report results for all zones AND separately for top-quartile zones by score.

### 4.4 Zone Merging

If two zone boundaries overlap, merge into one zone with midpoint = average of midpoints and width spanning both. Apply before event detection.

---

## 5. Event Definitions (PRIMARY — FROZEN)

### 5.1 Touch Event

A touch occurs when:
```
zone_low <= close[t] <= zone_high
```

Using bar **close** only (not wick/high/low).

**Consecutive bar rule:** If bars t, t+1, t+2 all satisfy the condition, this counts as ONE continuous touch — not 3 touches. Touch ends when close moves outside the zone.

**Re-entry rule:** A new touch begins only after close has moved at least 1.0 × ATR(14) away from zone midpoint AND returned. Until then, it remains the same touch event.

**One active zone at a time:** If price is inside multiple overlapping zones simultaneously, treat as one touch of the merged zone.

### 5.2 Bounce (Primary)

After a touch event begins at bar t_touch:
```
Bounce = True  if:
    max(close[t_touch : t_touch + 6]) >= close[t_touch] + 1.0 × ATR(14)   [for support touch]
    AND this condition is met BEFORE:
    min(close[t_touch : t_touch + 6]) <= close[t_touch] - 0.5 × ATR(14)

Break = True  if:
    close[t] <= zone_low - 0.25 × ATR(14)                                  [for support]
    AND close[t+1] <= zone_low - 0.25 × ATR(14)                            [holds for 2 bars]

Inconclusive = neither Bounce nor Break occurs within 6 bars
```

For resistance touch: directions are reversed.

Touch direction determined by: if close[t_touch] is in bottom half of zone → support touch; top half → resistance touch.

**ATR** used for MFE/MAE thresholds = ATR(14) computed at bar t_touch-1.

### 5.3 Primary Parameters Summary

| Parameter | Value |
|---|---|
| Touch definition | Bar close enters zone |
| Price series | Bank Nifty index close |
| Bounce MFE threshold | 1.0 × ATR(14) |
| Bounce MAE threshold | 0.5 × ATR(14) |
| Bounce horizon | 6 bars |
| Break threshold | 0.25 × ATR(14) beyond zone edge |
| Break confirmation | Holds for 2 bars |
| Re-entry gap | 1.0 × ATR(14) from zone midpoint |
| ATR lookback | 14 bars |
| Zone width k | 0.5 |
| Pivot window | 10 bars (trailing) |

### 5.4 Robustness Grid (secondary only)

| Parameter | Values tested |
|---|---|
| Bounce MFE | 0.75, 1.0, 1.25 × ATR |
| Bounce MAE | 0.375, 0.5, 0.75 × ATR |
| Horizon | 4, 6, 9 bars |
| Zone width k | 0.25, 0.50, 0.75 |

Report: "Edge survives across all reasonable variants" — not best-performing variant.

---

## 6. Matched Controls

For each zone-touch event, generate one matched control observation from the same dataset. Control must NOT overlap with any zone by more than 10% of zone width.

**Match on pre-event confounders only** (measured before touch begins):

| Variable | Matching method |
|---|---|
| Time of day | ±30 minute window |
| Prior realized volatility | Same quintile, measured over prior 14 bars |
| Prior trend state (ADX) | Same tertile: low/medium/high, measured over prior 14 bars |
| Prior return | Same quintile of abs(return) over prior 5 bars |
| Prior bar range | Same tertile |
| Gap direction | Same category: gap-up / gap-down / flat (within 0.1%) |
| Day type | Same: expiry day / event day / normal day |
| Expiry distance | Same bucket: 1–3 days / 4–7 days / 8–14 days / 15+ days |

Use **stratified sampling**: divide non-zone moments into bins by the above variables. Sample control from the same bin as the zone touch. If no match found in the same day, sample from the same week.

**Do NOT match on:**
- Current distance from swing high/low (potentially endogenous to zone algorithm)
- Volume at touch moment (feature being tested later)
- OI, IV, PCR (not used in EXP-001)

---

## 7. Baseline Strategies

S&R strategy must outperform ALL baselines. Each baseline uses identical sizing, stops, and holding period.

| Baseline | Logic |
|---|---|
| B1 | Random entry — uniform random from all valid intraday bars |
| B2 | Random entry — conditioned on same time-of-day bucket (±30 min) |
| B3 | Momentum — enter in direction of return over prior 6 bars |
| B4 | Mean reversion — enter against return over prior 6 bars |
| B5 | VWAP mean reversion — enter when price deviates >0.5% from session VWAP |
| B6 | Previous-day high/low — enter at PDH/PDL only (no other zone types) |
| B7 | Opening range — enter at breakout/breakdown of first 15-min range |

Key test: If EXP-001 S&R does not outperform B6 (previous-day high/low alone), complex zone machinery adds no value.

---

## 8. Statistical Tests

### 8.1 Primary Test — Bounce Rate Lift

```
Test: bounce_rate(zones) > bounce_rate(matched controls)
Method: Bootstrap (10,000 resamples with replacement)
Report:
    bounce rate at zones = X%
    95% CI = [lo%, hi%]
    baseline rate (matched controls) = Y%
    lift = (X - Y) pp
    p-value (one-sided)
    minimum lift for profitability at current costs = N pp
```

### 8.2 Permutation Test

Randomly shuffle zone labels (which observations are "zones") 10,000 times.
Build null distribution of lift. Observed lift must fall in top 5% (p < 0.05).
This tests whether zone detection captures something real, or whether any set of price levels would produce similar results.

### 8.3 Return Distribution Test

```
E[return over 6 bars | zone touch] vs E[return over 6 bars | matched control]
Test: Welch's t-test + Mann-Whitney U (non-parametric)
Also compare: full distribution (KS test)
```

### 8.4 Economic Edge Test

Compute net expectancy per trade using CostEngine:
```
gross_pnl = (MFE if bounce else -MAE if break else 0)
net_pnl = gross_pnl - CostEngine.calculate(date, instrument, ...)
E[net_pnl] must have 95% CI lower bound > 0
```

### 8.5 Multiple Testing

- All tests are pre-registered in this document. No post-hoc tests added after seeing results.
- Bonferroni correction applied if more than 3 sub-group tests are run.
- Robustness grid results are reported separately — they do not contribute to the primary result.
- Deflated Sharpe Ratio recorded if any parameter search is performed.

---

## 9. Touch Count Analysis

Measure reversal probability stratified by touch count on the same zone:

```
P(bounce | 1st touch of this zone)
P(bounce | 2nd touch of this zone)
P(bounce | 3rd touch of this zone)
P(bounce | 4th+ touch of this zone)
```

Report monotonic decay, flat, or strengthening pattern. Do not assume decay. Encode into model only if data supports it.

---

## 10. Regime Analysis

Run all primary tests separately for:
- Trending regime (ADX > 25) vs. mean-reverting regime (ADX <= 25)
- High volatility (India VIX > 70th percentile) vs. low volatility
- Expiry day vs. non-expiry day
- Morning session (09:15–11:30) vs. afternoon session (11:30–15:30)

Report whether edge concentrates in specific regime subsets. Used to inform regime filter in EXP-004, not to optimize EXP-001.

---

## 11. Acceptance Criteria

### M0 GO — ALL THREE required to proceed to M1

**Gate 1 — Statistical edge:**
- Bounce rate lift has 95% CI lower bound > 0 pp
- Permutation test p-value < 0.05
- Result holds for at least 4 of 7 baseline comparisons

**Gate 2 — Economic edge:**
- 95% CI of net expectancy per trade (after STT, exchange charges, slippage, spread) has lower bound > ₹0
- Lift over baseline must exceed minimum profitability threshold computed from CostEngine
- Transaction costs < 50% of gross P&L

**Gate 3 — OOS edge (final holdout):**
- Both Gate 1 and Gate 2 conditions hold on final holdout dataset
- Acceptable degradation: effect size drops by no more than 30% vs. training result
- OOS net expectancy lower bound remains > ₹0

### M0 KILL — if ANY gate fails

Do not proceed to M1. Document which gate failed and why.
This is a valid scientific outcome. Investigate alternative hypotheses (momentum, opening range, etc.) or alternative instruments before abandoning the project.

### INCONCLUSIVE — borderline results

If effect exists but is not cost-surviving: document and investigate whether lower-cost execution, fewer trades, or regime filtering changes the economics. Do not proceed to M1 without Gate 2.

---

## 12. Output Artifacts

All outputs saved to `reports/EXP-001/`:

| Artifact | Description |
|---|---|
| `exp001_event_log.parquet` | All zone-touch events with labels |
| `exp001_control_log.parquet` | All matched control observations |
| `exp001_results_training.json` | Primary metrics on training set |
| `exp001_results_validation.json` | Metrics on validation set |
| `exp001_results_oos.json` | Final holdout — populated last |
| `exp001_cost_model_output.json` | Per-trade cost breakdown |
| `exp001_baseline_comparison.json` | All 7 baseline results |
| `exp001_regime_breakdown.json` | Results by regime sub-group |
| `exp001_robustness_grid.json` | Secondary parameter grid results |
| `exp001_summary_report.md` | Human-readable summary |

Config snapshot saved to `configs/EXP-001-v1.yaml` — immutable after experiment begins.

---

## 13. Experiment Log

| Date | Action | Notes |
|---|---|---|
| 2026-08-12 | Pre-registration | Parameters frozen |
| — | Data loaded | |
| — | Training analysis | |
| — | Holdout unlocked | |
| — | GO / KILL decision | |
