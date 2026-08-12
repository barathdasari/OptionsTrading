# F&O Trading — Quantitative Research Framework

## Project Purpose
Determine whether Bank Nifty price zones exhibit statistically significant conditional reversal probabilities convertible into positive net trading expectancy, net of all costs. S&R is the **hypothesis**, not the conclusion.

**Instrument:** NSE Bank Nifty options, Nifty 50 futures
**Capital:** ₹50,000 — deployed at M3 only, after research validates edge
**Broker:** Shoonya (Finvasia) — zero F&O brokerage, free API
**Framework doc:** [quant_trading_framework.md](quant_trading_framework.md) (v3, ~9/10 quality, frozen)

---

## Current Status
Framework reviewed 3x (Review1–3.md). Ready to start **M0 implementation**.
Next deliverable: `M0_EXPERIMENT_001.md` — pre-registered experiment spec, then code.

### Milestone Sequence
```
M0  Research       — prove/disprove phenomenon (CURRENT)
M1  Strategy       — convert M0 findings into tradable rules
M2  Paper trading  — 30+ days live data, simulated orders
M3  Micro-live     — ₹50K at minimum size, human-supervised
M4  Automation     — full autonomous execution
M5  Scale          — multiple uncorrelated strategies
```
Do not build execution code until M0 Research Engine demonstrates a real edge.

---

## Repository Structure (planned)
```
F&O_Trading/
├── data/
│   ├── raw/                   # Immutable. Never modify.
│   ├── processed/             # Derived from raw. Reproducible.
│   └── metadata/
│       ├── contract/          # Date-aware: lot_size, expiry_rule, tick_size, effective dates
│       └── cost_rates/        # Versioned YAML: nse_stt_YYYY-MM-DD.yaml, etc.
├── research/
│   ├── 01_data_quality/
│   ├── 02_zone_detection/
│   ├── 03_touch_events/
│   ├── 04_bounce_break/
│   ├── 05_baselines/
│   ├── 06_statistical_tests/
│   ├── 07_regime_analysis/
│   └── 08_oos_validation/
├── src/
│   ├── data/
│   ├── features/
│   ├── zones/
│   ├── events/
│   ├── strategies/
│   ├── risk/
│   └── execution/
├── backtests/
├── configs/                   # Versioned experiment configs with IDs
├── tests/
└── reports/
```

---

## Non-Negotiable System Invariants

### 1. No Look-Ahead (CRITICAL)
Any feature or zone used for a trading decision must be computable **exclusively from data at or before the signal timestamp**.

- Swing pivot detection using N bars before AND after = look-ahead contamination
- Volume Profile: use **previous session's complete profile** for intraday decisions, not current day's end-of-day profile
- Zone Engine has two explicit modes: **research-discovery** (hindsight OK, never drives P&L) and **causal/tradable** (time t data only, used in all backtests)

### 2. Never Hard-Code Contract Parameters
- **Lot size**: always retrieved from `data/metadata/contract/` by trade date. SEBI adjusts periodically.
- **Expiry schedule**: date-dependent, from contract metadata. Bank Nifty changed Thursday → Wednesday → discontinued weekly contracts. Current: Tuesday monthly expiry. Historical research must use applicable schedule per trade date.
- **Tick size**: ₹0.05 — safe to hard-code.

### 3. Never Hard-Code Cost Rates
Cost rates change (STT changed materially April 1, 2026). CostEngine loads from versioned YAML files:
```
data/metadata/cost_rates/
    nse_stt_YYYY-MM-DD.yaml
    nse_transaction_charges_YYYY-MM-DD.yaml
    sebi_fees_YYYY-MM-DD.yaml
```
Every backtest run records `cost_schedule_version` in its experiment log. Source current rates from NSE/SEBI notifications — do not derive from any prose in this repo.

### 4. Observable vs. Inferred
Code and comments must distinguish:
- **Observable**: trade prices, OHLCV, volume, OI, IV, FII positioning
- **Inferred** (hypothesis, not fact): supply/demand imbalance, institutional defense, stop clustering, dealer gamma hedging

Aggregate OI does not reveal position holder type (market maker, institution, retail, hedger, spread, arb).

---

## Pre-Registered Experiment Parameters (EXP-001)
These are fixed. Cannot change after seeing results.
```
Touch:       bar close enters zone (not wick)
Price series: Bank Nifty index (not futures)
Bounce:      MFE >= 1.0 × ATR(14) before MAE >= 0.5 × ATR(14), within 6 bars
Break:       close beyond zone + 0.25 × ATR(14), holds for 2 bars
Inconclusive: neither within 6 bars
Overlapping: not allowed — new touch requires 1 ATR distance and return
ATR lookback: 14 bars
Zone width:  k = 0.5 × ATR(14) [primary]; k = 0.25, 0.75 for robustness only
```
Robustness grid tests adjacent values but **primary reported result uses above parameters only**.

---

## M0 Research Stack (Current Milestone)
```
Python 3.10+, Jupyter, pandas/polars, scipy, statsmodels
Parquet files for data storage
DuckDB for SQL queries on Parquet (no database server needed)
matplotlib/plotly for visualization
Git for all code
```
Do NOT add Redis, PostgreSQL, TimescaleDB, WebSocket, or execution code at M0.

---

## Statistical Validation Rules

**Multiple baselines required** — S&R must outperform ALL of:
1. Random entry (same period, stop, sizing)
2. Random entry conditioned on same time of day
3. Simple momentum
4. Simple mean reversion
5. VWAP mean reversion
6. Previous-day high/low (no options)
7. Opening range strategy

If sophisticated S&R adds no lift over Baseline 6, the complex zone machinery is unnecessary.

**Required result reporting format:**
```
bounce rate at zones = X%
95% CI = [lo%, hi%]
baseline rate (matched controls) = Y%
lift = +Z pp
p-value = 0.0XX
min effect for profitability at current costs = N pp
conclusion: [significant / not significant] [economically meaningful / not]
```

**M0 gate — ALL three required:**
1. Statistical edge: 95% CI of lift excludes zero; permutation test p < 0.05
2. Economic edge: 95% CI of net expectancy per trade (after all costs) excludes zero on lower bound
3. OOS edge: both hold on held-out dataset (10–20% degradation acceptable)

Kill condition: if any fail, do not proceed to M1.

---

## Matched Controls
Match on **pre-event confounders only** (determined before zone formation and before touch):
- Time of day (±30 min window)
- Prior realized volatility (same percentile bin, measured over preceding N bars)
- Prior trend state (ADX measured before touch)
- Prior return (same magnitude bin)
- Prior bar range
- Gap direction at open
- Day type (expiry day vs non-expiry, event flag)
- Expiry distance bucket

**Use with caution (potentially endogenous):**
- Distance from recent swing high/low (if zone is defined by swing structure, this can condition away the phenomenon)
- Current OI (endogenous if zone type uses OI)
- Volume at touch (may be a feature being tested)

---

## Risk Parameters (M3)
- Per-trade risk: 0.5–1.0% of account (₹250–₹500 at ₹50K)
- Hard daily loss limit: 2–3% (₹1,000–₹1,500)
- Soft warning: 1.5–2%
- Weekly limit: 5%; reduce size 50% if hit
- Weekly kill: 8%
- Monthly circuit breaker: 10–12% → paper trading mode for 2 weeks
- Kelly Criterion: M4+ only, after 200+ live trades with consistent performance

---

## Key Market Events (Flag in Calendar)
- RBI MPC meetings (6/year): 2–3x normal volatility
- Union Budget (Feb 1): largest annual volatility event
- HDFC Bank, ICICI Bank, Kotak Bank quarterly earnings
- Expiry days: different microstructure; strategy needs expiry-day mode or exclusion

---

## Code Quality Rules
- Every notebook must be reproducible: seeded random states, pinned library versions, documented data sources
- Experiment IDs are sequential (EXP-001, EXP-002...)
- Each experiment config versioned in `configs/` — never quietly change parameters after seeing results
- Trial registry: write down hypothesis and success condition before running any analysis
- Raw data files are immutable — never modify, derive all processed versions separately
- All backtesting code must enforce causal mode — no signal computation accesses future timestamps

---

## Architecture (M4+, Build Later)
```
Market Data Engine
      |
Feature Engine      (indicators, zones, options metrics)
      |
Zone Engine         (identify + score S&R zones)
      |
Event Engine        (touch, bounce, break detection)
      |
Research Engine     (stats tests, baseline comparisons)  <-- M0/M1 stops here
      |
Strategy Engine     (signal generation, position sizing)
      |
Risk / Execution Engine
```

Execution uses abstraction layer:
```
OrderManager (strategy-facing)
    └── BrokerAdapter
            └── ShoonyaAdapter
```
Strategy logic never directly calls broker API.
