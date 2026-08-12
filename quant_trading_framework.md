# Bank Nifty Quantitative Research Framework — Indian Markets
## From Research Hypothesis to Systematic Execution

**Author context:** Retail trader applying quantitative research discipline to systematic trading.
**Target market:** NSE — Bank Nifty options, Nifty 50 futures.
**Starting capital:** ₹50,000 — deployed at M3 (live micro) only, after research validates edge.
**Broker:** Shoonya (Finvasia) — zero F&O brokerage, free API.
**Research objective:** Determine whether identifiable price zones in Bank Nifty exhibit statistically significant conditional reversal probabilities that can be converted into positive net trading expectancy, net of all costs. S&R is the hypothesis, not the conclusion.

---

# PART 1 — RESEARCH PHILOSOPHY & DISCIPLINE

## 1.1 The Core Research Standard

Retail traders ask: "Does this strategy make money?"
Rigorous quantitative traders ask: "Is there a statistically significant, economically explainable edge here, and can I prove it is not a data artifact?"

The difference is the entire discipline. Serious quantitative trading operations do not trade on intuition. Every strategy deployed has passed through:

- A formal hypothesis with an economic rationale
- Rigorous statistical testing against null models
- Adversarial stress testing (try to break the strategy before deploying it)
- Risk-adjusted return analysis (not just raw returns)
- Cost-adjusted simulation (slippage, fees, taxes)
- Out-of-sample validation on data the model never saw
- Position sizing derived from mathematics, not gut feel
- Live monitoring with pre-defined kill conditions

The goal of this project is to adopt that research discipline — not to replicate institutional infrastructure. A ₹50K retail system with rigorous research process is better than a ₹50K retail system with institutional-sounding architecture but untested assumptions.

You are not trying to be right. You are trying to build a process that is right more often than random, by a measurable and repeatable margin, net of all costs.

## 1.2 The Research Mindset

Treat every strategy idea as a null hypothesis to be rejected. Your default assumption is that the strategy has no edge. Your job is to find evidence strong enough to overturn that assumption.

If you cannot clearly state:
- Why this edge exists (economic rationale)
- How it would disappear if too many people traded it (crowding risk)
- Under what market conditions it fails (regime dependency)
- How you would know it has stopped working (monitoring criteria)

...then you do not understand the strategy well enough to trade it.

## 1.3 Capital Reality & Project Milestones

₹50,000 is not the starting point of trading. It is available for live micro-validation only after the research phase proves the phenomenon exists.

**The critical mistake to avoid:** Committing live capital to test an unvalidated hypothesis. Every rupee lost during this phase is tuition paid to the market before knowing whether the edge is real. Research costs almost nothing. Live trading costs real money.

The project follows six milestones (detailed in Part 10):

- **M0 — Research:** Prove or disprove the phenomenon on historical data. Zero live capital. This is the most important milestone.
- **M1 — Strategy:** If M0 shows edge, convert findings into a tradable strategy with defined entry, stop, target, and sizing rules.
- **M2 — Paper trading:** Run strategy logic against live market data with simulated orders. Minimum 30 days.
- **M3 — Micro-live (₹50K):** Deploy real capital at minimum size. Validate that paper results transfer to live execution.
- **M4 — Automation:** Build full execution infrastructure once the edge is confirmed live.
- **M5 — Scale:** Grow capital and add uncorrelated strategies.

Skipping milestones in order is the single most common way systematic trading projects fail.

---

# PART 2 — INFRASTRUCTURE & TECHNOLOGY STACK

## 2.1 Core Infrastructure Components

The system has five layers. Build and validate each independently. Do not build Layer 4 or 5 before Layer 2 has demonstrated a real edge — this is the most common trap.

**Layer 1 — Data Infrastructure**
Raw market data is the foundation of everything. Garbage data produces garbage signals, garbage backtests, and false confidence.

Data types by milestone:

*M0 (Research — minimum viable):*
- Historical OHLCV, 5-minute bars (Bank Nifty futures/index)
- Historical options chain snapshots (OI per strike, IV, premium per strike, per expiry) — daily end-of-day is sufficient to start
- FII/DII daily activity (free from NSE website)
- Economic calendar

*M2+ (Paper trading onward — add):*
- Tick-by-tick trade data (each individual trade: price, volume, direction)
- Intraday options chain at regular intervals

*M4+ (Automation — add):*
- Order book snapshots (bid/ask depth, minimum 5 levels)
- Live WebSocket feed

You do not need tick data or order book data to answer M0's research questions. Starting with them adds data engineering complexity before you know whether the research question is worth answering.

Data sources for Indian markets:
- Shoonya API: live data, historical OHLCV (limited depth), options chain
- True Data: paid service, clean tick data, extensive history
- Global Data Feed (GDF): paid, institutional quality
- NSE website: free end-of-day data, FII/DII data, options chain snapshots
- Kite Connect (Zerodha): usable for historical data even if executing elsewhere

Data storage:
- Raw data in flat files (Parquet format — columnar, compressed, fast to query)
- Organized by date, instrument, timeframe
- Never modify raw files. Derive all processed versions separately.
- Maintain checksums to detect corruption
- Automated daily download jobs

**Layer 2 — Research Environment**
Where hypotheses are developed, tested, and validated. The most important layer. A strong Layer 2 saves months of wasted execution work.

Tools: Python 3.10+, Jupyter notebooks for exploration, structured scripts for production research, Git for all code.

Libraries: numpy, pandas (or polars for speed), scipy, statsmodels, matplotlib/plotly, DuckDB (fast SQL queries on Parquet files without a database server), vectorbt or backtesting.py for backtesting.

Critical discipline: Every notebook must be reproducible — seeded random states, pinned library versions, documented data sources. If you cannot re-run it and get identical results six months later, the research is not trustworthy.

**Layer 3 — Backtesting Engine**
Simulates strategy performance on historical data. The most dangerous layer because it is easy to deceive yourself here.

Requirements:
- Event-driven architecture (process each bar as if time is moving forward, never look ahead)
- Realistic transaction cost modeling (brokerage, STT, exchange charges, slippage)
- Position sizing logic
- Risk management rules (stop-loss, daily loss limits)
- Performance metric calculation

**Layer 4 — Paper Trading System**
Runs strategy logic against live market data with simulated orders. Bridge between backtest and real money.

Purpose: Detect everything backtesting cannot show — API latency, order rejection cases, data feed gaps, execution code bugs.

**Layer 5 — Live Execution Engine**
Production system. Real orders, real positions, real risk. Only built after Layer 2 confirms edge and Layer 4 confirms paper performance.

## 2.2 Technology Stack by Milestone

Do not build the full stack upfront. Match tools to what the current milestone actually requires.

**M0 — Research stack (minimum):**
- Python 3.10+, Jupyter, pandas/polars, scipy, statsmodels
- Parquet files for data storage
- DuckDB for fast SQL queries on Parquet without a database server
- matplotlib/plotly for visualization
- Git for all code

**M2–M3 — Paper and micro-live (add):**
- SQLite for trade logging and position tracking
- Shoonya API (paper mode, then live)
- Streamlit for a simple monitoring dashboard
- Telegram bot for alerts

**M4+ — Full automation (add):**
- PostgreSQL with TimescaleDB extension for time-series at scale
- Redis for message passing between signal generation and execution (decouples the two processes)
- Structured logging to a persistent store

**Broker API:** Shoonya (Finvasia) — zero brokerage on F&O, free API, REST for orders, WebSocket for live data.

**Version control:** Git + GitHub/GitLab. Every line of code, every notebook, every config file is version controlled. No exceptions. If your laptop dies, you must be able to reconstruct everything from the repository.

**Alerting:** Telegram bot for critical events — daily loss limit hit, strategy error, API disconnection, position mismatch.

## 2.3 Repository Structure

Organize the codebase from day one. Research grows fast; a flat structure becomes unnavigable within weeks.

```
banknifty-quant/
│
├── data/
│   ├── raw/                  # Immutable. Never modify.
│   ├── processed/            # Derived from raw. Reproducible.
│   └── metadata/
│       ├── data_quality/     # Gap logs, checksum records, source records
│       ├── contract/         # Date-aware contract specs (lot size, expiry rule, tick size)
│       └── cost_rates/       # Historical STT, exchange charges by effective date
│
├── research/
│   ├── 01_data_quality/      # Validate data before using it
│   ├── 02_zone_detection/    # Zone identification algorithms
│   ├── 03_touch_events/      # Formal event engine experiments
│   ├── 04_bounce_break/      # Bounce/breakout classification
│   ├── 05_baselines/         # Null and benchmark models
│   ├── 06_statistical_tests/ # Hypothesis tests, permutation tests, CIs
│   ├── 07_regime_analysis/   # Regime detection and filtering
│   └── 08_oos_validation/    # Out-of-sample and walk-forward tests
│
├── src/
│   ├── data/                 # Data download, storage, retrieval
│   ├── features/             # Feature engineering
│   ├── zones/                # Zone detection engine
│   ├── events/               # Event engine (touch, bounce, break)
│   ├── strategies/           # Strategy logic
│   ├── risk/                 # Risk management module
│   └── execution/            # Order management and broker adapter
│
├── backtests/                # Backtest runs with versioned configs
├── configs/                  # Strategy and system configuration files
├── tests/                    # Unit and integration tests
├── reports/                  # Generated performance reports
└── README.md
```

Each research notebook is numbered sequentially with an experiment ID. Experiment configs are versioned in `configs/`. This creates an audit trail of what was tested, what parameters were used, and what the result was.

## 2.4 System Architecture — Six Engines

The production system (M4+) is composed of six engines that build on each other sequentially. Critically: do not build Engine 5 or 6 until Engine 3 has demonstrated an edge in research.

```
Market Data Engine
      |
      v
Feature Engine      (compute indicators, zones, options metrics)
      |
      v
Zone Engine         (identify and score S&R zones)
      |
      v
Event Engine        (detect touches, classify bounce/break)
      |
      v
Research Engine     (statistical tests, baseline comparisons — M0/M1 only)
      |
      v
Strategy Engine     (signal generation, position sizing)
      |
      v
Risk / Execution Engine   (risk gate, order management, monitoring)
```

In M0 and M1, the system stops at the Research Engine. No execution code is written until the Research Engine produces a validated edge.

---

# PART 3 — MARKET KNOWLEDGE (INDIA-SPECIFIC)

## 3.1 Bank Nifty — Why This Instrument

Bank Nifty is one of the most actively traded index derivatives on NSE by contract volume. Properties relevant to this research:

- High retail participation volume — a potential behavioral mechanism for observed price clustering at round numbers and prior structural levels. Whether this produces measurable predictive power is an empirical question.
- Options expiry concentrates activity — gamma effects near expiry may amplify or dampen S&R behavior. Test days-to-expiry as a regime variable. Verify the current expiry schedule from NSE contract specs before research.
- High volatility (Beta typically 1.3–1.5x Nifty) produces larger ATR-normalized moves, which improves the signal-to-noise ratio for zone detection
- Options market depth allows defined-risk strategies without futures margin requirements

Constituents: 12 banking stocks (HDFC Bank, ICICI Bank, Kotak Bank, SBI, Axis Bank, etc.). Bank Nifty moves are driven by banking sector news, RBI policy, credit events, and NPA concerns — all of which follow identifiable patterns.

## 3.2 Indian Market Microstructure

**Exchange:** NSE is the dominant exchange for F&O. BSE F&O volume is negligible. All your work will be NSE-focused.

**Trading hours:** 9:15 AM – 3:30 PM IST. No pre/post-market for derivatives.

**Settlement:** Daily MTM for futures. Options premium paid upfront.

**Expiry schedule:** Do not assume any specific expiry day or frequency. Bank Nifty contract structure has changed multiple times — expiry day moved from Thursday to Wednesday, and weekly Bank Nifty contracts have been discontinued at various points. Current NSE specifications show index derivative expiry on Tuesday. Treat all expiry information as requiring verification from current NSE contract metadata before use. Historical research must use the expiry schedule applicable on each trade date, sourced from `data/metadata/contract/`.

**Lot size:** Lot size must always be retrieved from the applicable NSE contract specification for the instrument and trade date. Never hard-code it anywhere — not in research code, not in backtests, not in position sizing formulas. SEBI adjusts lot sizes periodically. Historical backtests must use the lot size that was in effect on the date of each trade. Do not use any numerical reference in this document as a default — it will be stale.

**Tick size:** ₹0.05 for F&O. Minimum bid-ask spread is ₹0.05, but in practice ATM options spread ₹1–5 depending on conditions.

**Price controls:** Index futures and options do not have stock-style circuit breakers that halt trading. However, the exchange does operate dynamic price bands and operating range limits for F&O contracts — these are distinct from stock circuit filters. Bank Nifty can move 5%+ in minutes during major events without triggering a halt. Know the difference between "no circuit breaker" (stock-style halt) and the operating controls that do exist.

## 3.3 Cost Structure — This Will Make or Break Your Strategy

Every strategy must survive these costs or it has no real edge.

**Critical implementation requirement:** Do not hard-code tax rates into your backtester. Tax rates change. Your cost engine must apply rates applicable on the trade date, not the rates as of today.

Build a CostEngine with the following components:

```
CostEngine.calculate(date, instrument, side, quantity, price, action)
    ├── STT(date, instrument, side, action)       # rate lookup by date
    ├── ExchangeTransactionCharge(date, turnover)
    ├── SEBITurnoverFee(date, turnover)
    ├── GST(brokerage_amount)
    ├── StampDuty(side, value)
    ├── Slippage(instrument, size, market_conditions)
    └── SpreadCost(bid_ask_spread, lots)
```

Backtest P&L validity depends entirely on accurate cost modeling. A strategy that appears profitable at outdated STT rates may be a loser at current rates.

**Current rates — do not reproduce rates in this document:**

Store all applicable rates in `data/metadata/cost_rates/` as versioned files, e.g.:
```
cost_rates/
    nse_stt_2026-04-01.yaml
    nse_transaction_charges_2026-04-01.yaml
    sebi_fees_2026-04-01.yaml
```

The CostEngine loads the applicable rate file based on trade date. Every backtest run must record which cost schedule version was used in its experiment log (`cost_schedule_version: "2026-04-01"`). Source current rates from official NSE/SEBI notifications before each research run. Do not derive rates from any prose in this document — it will go stale.

**How to estimate round-trip cost:**
Use the CostEngine to compute per-trade costs dynamically based on actual instrument parameters (lot size from contract metadata, premium from historical data). Do not use illustrative percentage estimates for actual backtest validation — those mask the true cost burden at different price levels and premium sizes.

**The STT trap at expiry:**
If you hold an ITM long option to expiry, STT is charged on full intrinsic value, not just premium paid. On a deep ITM option this can wipe out the entire profit. Always close long options before expiry. This rule must be a hard exit condition in your execution logic, not a guideline.

## 3.4 Key Market Events That Break All Models

These dates require you to either stop trading or apply completely different logic:

- **RBI Monetary Policy Committee (MPC) meetings:** 6 per year. Announcement day sees 2–3x normal volatility. S&R levels become meaningless during the announcement window (typically 10:00 AM).
- **Union Budget:** Once per year (usually February 1). Single largest volatility event of the year. Do not trade on Budget day until post-announcement stabilization.
- **Quarterly earnings of major Bank Nifty constituents:** HDFC Bank, ICICI Bank, Kotak Bank earnings move the index 1–3%.
- **Global events:** US Fed meetings, geopolitical events, global banking crises all transmit to Bank Nifty within minutes.
- **Expiry days:** Different microstructure on expiry days — gamma-driven moves, elevated volatility, unusual OI behavior. Strategy must have an expiry-day mode or exclude expiry days entirely. Expiry day is determined from contract metadata, not assumed to be any fixed weekday.

Maintain an economic calendar. Flag all these dates in your system. Either switch off or switch to an event-specific strategy.

## 3.5 FII Behavior — A Regime Signal Worth Testing

Foreign Institutional Investors (FIIs) are widely considered a dominant price-setting force in Indian equity markets. NSE publishes daily FII activity in index futures (long vs. short contracts outstanding). The hypothesis is that FII net positioning is a useful regime signal: when FIIs are heavily net short futures, support levels may fail more often; when net long, support may hold more often.

This is free data, published daily at approximately 6 PM on the NSE website. Build a pipeline to collect and store it from day one.

Important: whether FII positioning actually improves your strategy's predictive power is a research question, not an assumption. Include it as a feature in your dataset and test its incremental contribution rigorously. It may be a strong regime filter — or it may add noise.

---

# PART 4 — RESEARCH: SUPPORT & RESISTANCE AS A TESTABLE HYPOTHESIS

## 4.1 The Correct Framing

Retail definition: "Price bounced from this level before, so it will bounce again."

Research definition: "Do identifiable price zones in Bank Nifty create a statistically significant deviation from baseline reversal probability, after controlling for volatility, trend, time-of-day, and regime, that survives transaction costs and out-of-sample testing?"

The second framing makes S&R falsifiable. It has an explicit rejection condition. If the research finds that proximity to identified zones does not change the conditional return distribution, the project still succeeds — it has scientifically eliminated a hypothesis.

**Critical distinction: Observable vs. Inferred**

Much S&R language blurs the line between what can be measured from historical data and what is being inferred about market mechanics. This distinction matters in quantitative research.

Observable (directly measurable from available data):
- Trade prices, volumes, OHLC bars
- Options OI, IV, premium per strike
- Futures positioning (FII data)
- Bid/ask if order book data is available

Inferred (hypotheses about underlying mechanics, not directly observable from OHLCV):
- Supply/demand imbalance
- Institutional defense of a level
- Stop-loss clustering
- Dealer gamma hedging flows
- Market maker positioning

When building models, use observables as inputs. State clearly when a feature is a proxy for something inferred. Do not conflate "we see high volume at this level" (observable) with "institutions are defending this level" (inferred). The observable is real; the inference is a hypothesis that needs its own testing.

## 4.2 Categories of S&R Levels in Indian Markets

**Type 1: Volume-Based Levels (Point of Control)**
Price regions with the greatest executed trading volume. The hypothesis is that high-volume nodes represent price levels at which the market spent significant time and participants built positions — creating a potential anchor for future price behavior. Whether this produces measurable mean-reversion tendency is what Experiment 001 tests.

How to compute: Construct a Volume Profile — a histogram of total traded volume at each price level over a chosen time window (session, week, month). The highest-volume node is the Point of Control (POC). The range containing 70% of all volume is the Value Area (Value Area High = VAH, Value Area Low = VAL).

Time windows for different uses:
- Daily session profile: for intraday S&R
- Weekly composite profile: for swing levels
- Monthly composite profile: for major structural levels

**Type 2: Options-Based Levels (OI Concentration & Max Pain)**

Options Open Interest (OI) concentrated at specific strikes is an observable fact. Whether that OI concentration creates support or resistance is a hypothesis that requires testing.

Key questions to test empirically, not assume:
- Does high call OI at a strike actually correlate with price reversal near that strike?
- Does high put OI at a strike actually correlate with support behavior?
- Does the answer depend on who holds the OI (retail vs. institutions vs. market makers)? You cannot determine this from aggregate OI data alone.
- Does OI change (buildup vs. unwinding) matter more than absolute OI level?

**The OI wall hypothesis:** The claim is that options sellers delta-hedge as price approaches concentrated OI strikes, creating order flow that resists price movement. This is a plausible mechanism. It is not a proven causal force. Test it: measure reversal probability at high-OI strikes vs. equivalent low-OI strikes, controlling for other variables.

**Max Pain:** The strike at which total options holder P&L is most negative (sellers most profitable). The hypothesis is that price migrates toward max pain as expiry approaches. Treat this as an experimental feature. Test whether distance-to-max-pain predicts reversal probability, terminal price, or intraday volatility — controlling for price level, volatility, trend, OI, and days-to-expiry. If it adds no incremental predictive power after those controls, remove it. Do not encode it as a primary strategy input before testing.

**What aggregate OI cannot tell you:** Aggregate OI does not reveal whether a position belongs to a market maker, institution, retail trader, hedger, spread position, or arbitrage position. The hedging behavior that creates OI walls only applies to specific participant types. This is a fundamental limitation of using aggregate OI as a proxy for dealer positioning.

**Type 3: Structural Pivot Levels**
Historically significant highs and lows where price reversed with conviction. The significance of a pivot increases with: the magnitude of the reversal from that level, the number of times price has tested and respected that level, and the volume transacted at the level during the reversal.

Quantifying pivot significance: A turning point requires a minimum price reversal of at least N x ATR (Average True Range) from the pivot to be considered structurally significant. N is a parameter to be calibrated per instrument.

**Type 4: Psychological Round Numbers**
50,000, 50,500, 51,000 — round numbers concentrate retail orders (stop-losses, targets, entry orders) simply because human psychology rounds to convenient numbers. This self-fulfilling mechanism is measurable and exploitable.

## 4.3 The Look-Ahead Prohibition — Non-Negotiable System Invariant

Before any zone detection or feature computation: **any feature or zone used for an intraday trading decision must be computable exclusively from data available at or before the signal timestamp.**

This is the single most common source of backtesting fraud (intentional or accidental) in S&R research. Two specific violations that must be eliminated:

**Violation 1 — Swing pivot look-ahead:**
Identifying a swing high using N bars before AND N bars after the pivot uses future information. You only know that bar at time t was a pivot after observing bars t+1 through t+N. Any backtest that identifies today's levels using today's subsequent price action is look-ahead contaminated.

Solution — Zone Engine must have two explicit modes:

*Research discovery mode:* Can use full-history hindsight. Used only for descriptive analysis — understanding what zones existed. Never used as input to a signal that drives a P&L calculation.

*Causal/tradable mode:* Only uses information available at time t. This is the mode used for all backtesting, paper trading, and live trading. Pivot detection uses only bars up to t-N (trailing window only). This is the only valid mode for any performance metric.

All backtesting code must enforce causal mode. A code review gate should check that no signal computation accesses data with a future timestamp.

**Violation 2 — Volume Profile look-ahead:**
If trading at 10:00 AM, you do not know the full session's volume profile — it is not complete until 3:30 PM. Using the current day's full session profile for an intraday decision is look-ahead.

Correct approach:
- Use the previous session's complete profile for today's intraday decisions
- Or use a developing real-time profile that only includes bars up to signal timestamp t
- Never use the end-of-day session profile for any decision made intraday

## 4.4 Zone Construction — Moving From Price Points to Zones

Price rarely reverses at exactly the same tick twice. Levels must be treated as zones with defined width.

Zone construction methodology:
1. Identify candidate levels using each of the four types above
2. Define zone width as a multiple of ATR: `zone_width = k × ATR(N)` where k and N are research parameters, not fixed constants. A percentage-based width (e.g., ±0.2%) behaves very differently under low vs. high volatility, on expiry days, or during RBI events. ATR-normalized width scales with current market conditions.
3. Merge overlapping zones — confluence of multiple level types in the same zone is a hypothesis that this increases significance. Test it.
4. Score each zone: Volume concentration score + OI concentration score + Number of historical touches + Recency weight

**Zone width parameter:** The value of k is a research parameter to be determined from data, not chosen arbitrarily. Test a range of k values. Do not optimize k on the same dataset you will use for final validation — calibrate on a training set, fix k, then test on held-out data.

**Zone potency decay — hypothesis, not fact:**
The claim that "every test weakens a zone" is a plausible microstructure story. It is not universally true. Some zones strengthen with repeated testing because more participants recognize them, liquidity replenishes, or positioning accumulates around them.

Test this empirically before encoding it into the model:
- P(bounce | 1st touch of this zone)
- P(bounce | 2nd touch of this zone)
- P(bounce | 3rd touch of this zone)
- P(bounce | 4th+ touch of this zone)

If the data shows P(bounce) declining monotonically with touch count, encode decay. If P(bounce) is flat or non-monotonic, do not. Report what the data shows, not what the theory predicts.

## 4.5 Formal Event Definitions

Before any statistical testing, every event must be defined precisely. Vague definitions produce unmeasurable results. The following definitions must be fixed before running any analysis — changing them after seeing results is data snooping.

**Zone Touch:**
A touch event occurs when:
```
abs(price - zone_midpoint) <= zone_width / 2
```
Where zone_midpoint and zone_width are pre-computed from the zone detection algorithm. Price is the close of the bar (for bar-based analysis).

If multiple consecutive bars satisfy this condition, they count as one continuous touch — not multiple separate touches. A new touch begins only after price has moved at least 1 ATR away from the zone and returned.

**Bounce:**
After a touch event, a bounce is defined as:
```
Maximum Favorable Excursion (MFE) >= +X ATR
BEFORE
Maximum Adverse Excursion (MAE) >= -Y ATR
within N bars after touch
```
Where X, Y, and N are research parameters fixed before the analysis run.

**Breakout:**
A breakout is defined as:
```
close > zone_high + buffer  (for resistance breakout)
close < zone_low - buffer   (for support breakdown)
```
Where buffer = Z × ATR, also a pre-fixed research parameter.

The following must also be explicitly defined before coding the event engine:
- Does a "touch" use bar close, bar high/low (wick), or intrabar print? (Each gives a different event count)
- Does an event use the underlying index price or the futures price? (They diverge near expiry)
- Are overlapping events allowed? (e.g., if price re-enters a zone within 3 bars of exiting)
- Is the first touch only measured, or every entry into the zone?
- What price series is used for MFE/MAE measurement: 5-min close, or intrabar high/low?

Define these choices before running any analysis. Document them in the experiment config. Changing them after seeing results is data snooping.

**Pre-registered primary parameters for Experiment 001:**

These are fixed before any data analysis. They cannot be changed after seeing results. A robustness grid may test adjacent values, but the primary reported result uses these exact parameters.

```
Experiment: EXP-001
Touch definition:    bar close enters zone (not wick)
Price series:        Bank Nifty index (not futures — avoid roll/expiry distortion)
Bounce primary:      MFE >= 1.0 × ATR(14) before MAE >= 0.5 × ATR(14), within 6 bars
Break primary:       close beyond zone + 0.25 × ATR(14) and remains beyond for 2 bars
Inconclusive:        neither condition occurs within 6 bars
Overlapping events:  not allowed — new touch requires 1 ATR distance and return
ATR lookback:        14 bars
Zone width:          k = 0.5 × ATR(14)  [primary], tested at 0.25 and 0.75 for robustness
```

Robustness grid (secondary reporting only — not for parameter selection):
- Bounce thresholds: 0.75/1.0/1.25 ATR
- Horizon: 4/6/9 bars
- Zone width k: 0.25/0.50/0.75

Report: "The edge survives across all reasonable parameter variants" — not "parameter X=Y gives the best result."

**Why this matters:** Without formal definitions, "price bounced off the level" is a post-hoc visual judgment that cannot be computed systematically. The formal definition allows scanning 50,000 historical zone touches programmatically and measuring bounce/break rates with statistical precision.

## 4.6 Bounce vs. Breakout — Feature Candidates

These are candidate features to test for predictive power. They are hypotheses, not confirmed predictors. Each must be tested for incremental contribution beyond a simple baseline.

Feature hierarchy by data source:

**Price features:**
- Distance to zone (ATR-normalized)
- Approach velocity (price change per bar in last N bars)
- ATR at time of touch
- VWAP distance at time of touch
- Opening range distance
- Momentum (rate of change over M bars)

**Volume features:**
- Relative volume (current vs. N-day average)
- Volume acceleration near zone (volume in last 5 bars vs. prior 5 bars)
- Volume profile concentration at zone level
- Volume trend as price approached zone (expanding vs. contracting)

**Options features (hypotheses — test each independently):**
- OI at nearest strike
- OI change (buildup vs. unwind) at nearest strike
- IV at nearest strike
- IV percentile (current IV vs. historical range)
- PCR (Put-Call Ratio)
- Strike distance (how far price is from nearest round-number strike)
- Days to expiry (gamma effects are stronger near expiry)

**Positioning features (hypotheses — test each independently):**
- FII futures net position (long - short contracts)
- FII net position change (day-over-day)

**Regime features:**
- Trend strength (ADX or similar)
- Volatility regime (high vs. low VIX percentile)
- Gap direction at open
- Time of day (morning vs. afternoon session)
- Day of week
- Days to expiry

Test each feature's incremental information value. A feature that appears predictive in isolation may add nothing after controlling for more basic features like price momentum and volatility.

## 4.7 Sequenced Research Experiments

Do not combine all features into one model on day one. Build complexity incrementally. Each experiment answers a specific question and provides a gate: if the question fails, the next experiment becomes irrelevant.

**Experiment 001 — Does S&R phenomenon exist at all?**
Question: Do structural price zones (previous day high/low, weekly high/low, swing pivots, VWAP, volume profile levels) produce abnormal reversal probability compared to random price levels?
Data: Bank Nifty 5-minute OHLCV. No options data yet.
Method: Detect zones, log all touch events, measure P(bounce) at zones vs. P(bounce) at random controls. Bootstrap significance test.
Gate: If P(bounce | zone) is not significantly higher than P(bounce | random), stop. S&R as a phenomenon may not be real in this instrument.

**Experiment 002 — Does OI improve prediction beyond price-derived zones?**
Question: Do high-OI strikes predict reversal probability beyond what price-derived structural levels already capture?
Data: Add options chain OI.
Method: Same touch/bounce framework. Add OI as a feature. Measure incremental lift over Experiment 001 baseline.
Gate: If OI adds no lift, it is not worth the data pipeline complexity.

**Experiment 003 — Do IV, PCR, and OI change add further signal?**
Question: Do options flow metrics (IV, PCR, OI change) improve the bounce/break classification?
Data: Add IV, PCR, OI change.
Method: Incremental feature testing. Each feature tested individually first, then combined.

**Experiment 004 — Does regime filtering improve strategy performance?**
Question: Does strategy edge concentrate in specific market regimes (low trend, high volatility, etc.)?
Data: Add regime indicators (trend strength, VIX percentile, FII positioning).
Method: Stratify results by regime. Measure edge within each regime class.

**Experiment 005 — Build the actual trading strategy.**
Only reached if Experiments 001-004 show a robust, cost-surviving edge.
Build entry, stop, target, sizing. Backtest properly. Run OOS validation.

This sequencing is more defensible than combining everything into one model and hoping it works.

---

# PART 5 — STATISTICAL VALIDATION FRAMEWORK

## 5.1 Why Backtesting Alone Is Not Validation

Backtesting is necessary but not sufficient. It answers: "Did this strategy work on this historical data?" It does not answer: "Does this strategy have a genuine, repeatable edge?"

The gap between those two questions is where most traders get destroyed.

Common backtesting failures:
- **Overfitting:** Strategy parameters tuned to fit past data perfectly, generating false confidence. Works on historical data, fails on new data.
- **Lookahead bias:** Code accidentally uses future information (e.g., using end-of-day data to make intraday decisions, or using a level identified only after the fact)
- **Survivorship bias:** Testing only on instruments that existed throughout the period, ignoring those that were delisted
- **Data snooping bias:** Testing 50 variations of a strategy and presenting only the best result
- **Ignoring market impact:** Assuming you can buy/sell at exact historical prices with unlimited size

## 5.2 The Proper Validation Sequence

Step 1 — Hypothesis formation (before any data analysis)
Write down in plain language exactly what edge you expect to find and why. Write this before touching the data. This prevents retrofitting explanations to whatever pattern you happen to find.

Example: "Bank Nifty options OI walls at round number strikes create measurable support/resistance because options sellers delta-hedge their positions as price approaches those strikes, creating order flow that arrests price movement. This effect should be most pronounced within 0.5% of the strike price and should diminish as expiry approaches and gamma increases."

Step 2 — Define measurable prediction
From the hypothesis, derive a testable prediction. Example: "Price reversal probability within 0.5% of high-OI strike levels will be statistically significantly higher than reversal probability at equivalent distance from low-OI strike levels."

Step 3 — Design the test before looking at full dataset
Define: time window for analysis, minimum data requirements, what statistical test to use, what p-value threshold, what effect size is economically meaningful. Fix all these parameters before running any analysis.

Step 4 — Statistical testing
Run the analysis. Apply the pre-specified test. Report the result honestly including if it fails.

Step 5 — Out-of-sample test
Split your data before all analysis. Hold back the last 20–30% as an untouched test set. Validate the same strategy on data it has never influenced. If it works in-sample but fails out-of-sample, it was overfit.

Step 6 — Walk-forward validation
Simulate how the strategy would have actually been traded: train on past data, test on the next period, roll forward, repeat. This is the most realistic historical simulation.

## 5.3 Statistical Tests Specific to S&R

**Test for non-random reversal at identified levels:**
Null hypothesis: Price reversal rate at identified S&R zones equals price reversal rate at randomly selected price levels of equal width.

Method — Bootstrap test with stratified matching: Identify all S&R zones. Log all touch events. Measure reversal rate (bounce as defined formally in Section 4.5). For each zone touch event, sample a matched control from the same time period with similar characteristics. Compare reversal rates. The difference must be statistically significant and economically meaningful.

**Matched control methodology (required, not optional):**
Simple random sampling is insufficient as a control. Zone touches may systematically cluster near market open, during high volatility, or following large moves. If random controls don't reflect this distribution, you're comparing apples to oranges and can get a false positive simply because zone touches occur at "easy" moments for mean reversion.

Match controls on pre-event confounders only. Distinguish:

**Safe matching variables (pre-event, not generated by the zone algorithm):**
- Time of day (±30 minute window)
- Prior realized volatility (same percentile bin, measured over preceding N bars)
- Prior trend state (same ADX bin measured before the touch, not at the touch)
- Prior return (same return-magnitude bin over preceding M bars)
- Prior bar range (same range percentile)
- Gap direction (gap-up day vs. gap-down vs. flat open)
- Day type (expiry day vs. non-expiry, event-day flag)
- Expiry distance (same expiry-distance bucket — not "same week" since weekly contracts may not exist)

**Variables to use with caution (potentially endogenous — may be downstream of zone formation):**
- Current distance from recent swing high/low: if the zone itself is defined by swing structure, matching on this variable can condition away the phenomenon being measured. Use prior swing distance (before the zone was formed), not current.
- Current OI: if any zone type uses OI for its definition, current OI at the touch moment is endogenous to the zone classification.
- Volume at touch: could be a feature you're testing, not a confounder to control for.

Rule: only match on variables that were determined before the zone was identified and before the touch event began.

Implementation: stratified sampling. Divide non-zone moments into bins by safe matching variables. Sample controls from the same bin as each zone touch.

**How to report results (required format):**
Do not report only the point estimate and p-value. Report:
```
bounce rate at zones = 63%
95% CI = [59%, 67%]
baseline rate (random controls) = 51%
lift = +12 percentage points
p-value = 0.018
minimum effect size for profitability at current costs = +8 pp
conclusion: statistically significant, economically meaningful
```
The confidence interval is as important as the point estimate. A wide CI on a small sample can look impressive as a point estimate but is not actionable.

**Permutation test:**
Shuffle zone labels randomly (randomly reassign which price levels are "zones") and measure bounce rate on the shuffled labels. Repeat 10,000 times. Build a null distribution. Your observed lift should fall in the top 5% of this null distribution to be considered significant. This tests whether your zone identification algorithm is capturing something real, or whether any set of price levels would produce similar results.

**Multiple testing correction:**
This project will likely test many parameters: zone width k, ATR lookback N, bounce thresholds X and Y, holding period, features, regime filters. Each additional test increases the probability of finding a false positive by chance.

Manage this with:
- A trial registry: before each experiment, write down what you are testing and what result would constitute success. Log it. Do not add post-hoc tests.
- Experiment IDs: number each experiment. Reference the ID when reporting results.
- Parameter versioning: each parameter set gets a version number. Never quietly change parameters after seeing results.
- Bonferroni correction or Benjamini-Hochberg procedure for multiple comparisons.
- Deflated Sharpe Ratio (López de Prado) for strategy Sharpe adjusted for the number of trials tested.
- Reserve a holdout dataset that is never touched until final validation. Do not use it for any parameter selection.

**Multiple baseline comparisons (required — not optional):**
A single "random entry" baseline is insufficient. Your S&R strategy must outperform all of these:

- Baseline 1: Random entry (same holding period, same stop, same sizing)
- Baseline 2: Random entry conditioned on same time of day
- Baseline 3: Simple momentum (enter in direction of last N bars)
- Baseline 4: Simple mean reversion (enter against last N bars)
- Baseline 5: VWAP mean reversion (enter when price deviates from VWAP by X%)
- Baseline 6: Previous-day high/low strategy (no options data, just simple structural levels)
- Baseline 7: Opening range strategy

If sophisticated S&R adds no predictive power beyond Baseline 6 (previous-day high/low), then the complex zone detection machinery is unnecessary overhead.

**The real alpha question:**
Instead of asking "does S&R work?", test:

Does proximity to a quantitatively defined zone change the conditional distribution of future returns after controlling for volatility, trend, time-of-day, and market regime?

Formally:
```
P(return > +X | near zone) vs. P(return > +X | not near zone)
E[return | near zone] - E[return | matched control]
```
The matched control is critical: compare zone touches to non-zone moments with similar volatility, trend, and time-of-day. This controls for confounding variables.

**Regime-conditional analysis:**
Run all tests separately for trending and mean-reverting regimes. S&R edge is expected to concentrate in mean-reverting regimes. This tells you whether a regime filter is needed, not a simple assumption to bake in from the start.

## 5.4 Performance Metrics — Priority Order

Do not optimize for Sharpe ratio. Do not use fixed Sharpe targets as pass/fail gates. A Sharpe of 1.2 from 500 trades with stable OOS performance and low drawdown is better than a Sharpe of 2.5 from 27 trades. The number of trades, consistency, and out-of-sample stability matter more than the ratio itself.

Evaluate metrics in this priority order:

**1. Net trading expectancy per trade** (gross edge minus all costs)
The single most important number. If E[P&L per trade] after STT, brokerage, slippage is negative, nothing else matters.

**2. Out-of-sample stability**
Does the strategy perform similarly in periods it was never trained on? A 40% drop in performance OOS indicates overfitting. Some degradation is normal; large degradation is disqualifying.

**3. Maximum drawdown**
Largest peak-to-trough decline. This is what you will feel in real money. Target: <20% of capital. Know the expected maximum drawdown before going live — if the realized drawdown exceeds 2x the historical maximum, the strategy is broken.

**4. Tail loss (Worst single-trade loss)**
What is the worst case trade? Is it within the expected distribution? A strategy with average loss ₹200 but one outlier loss of ₹5,000 is a different risk profile than stated.

**5. Profit Factor**
Gross profit / Gross loss. Must be >1.5 to have meaningful cushion. Below 1.3 and transaction cost variation can easily push it below 1.0.

**6. Sharpe Ratio**
Risk-adjusted return. Annualized return divided by annualized standard deviation of returns. Useful for comparison, but context-dependent. A viable intraday options strategy can have Sharpe 1.0–1.5 and still be worth trading. Do not discard a strategy solely for missing an arbitrary threshold.

**7. Calmar Ratio**
Annualized return divided by maximum drawdown. Useful for comparing strategies with similar return profiles but different drawdown characteristics. Target: >1.0.

**8. Capacity**
How much capital can this strategy absorb before market impact erodes the edge? At ₹50K this is not a concern, but factor it into the scaling roadmap.

**Additional metrics to track:**
- Win rate and payoff ratio (report both — never report win rate alone)
- Average trade duration (shorter = higher cost drag)
- Trades per month (frequency × cost per trade = total cost burden)
- Transaction costs as % of gross P&L (if >25%, re-examine trade frequency)
- Deflated Sharpe Ratio (corrects for multiple testing — use when reporting strategy results after testing many variations)

---

# PART 6 — RISK MANAGEMENT SYSTEM

## 6.1 Risk Management Philosophy

Risk management is not a constraint on profit. It is the mechanism that keeps you in the game long enough for your edge to manifest.

Even a profitable strategy will experience extended losing streaks. Real trading returns are not independent Bernoulli trials — loss clustering can be significantly worse than a simple probability model suggests due to volatility regime shifts, trend regimes, event clustering, and execution failures. Without a risk management system, a losing streak at aggressive position sizes can destroy an account before the edge has a chance to recover.

The goal of risk management: Ensure that no single event, no series of losses, and no system malfunction can take you out of the game.

## 6.2 Position Sizing

**Phase M3 (micro-live): Fixed fractional risk**

Kelly Criterion is not appropriate at this stage. Kelly requires knowing your true win rate and payoff ratio. At M3, those estimates come from research and early paper trading — they carry substantial uncertainty. If your true win rate is 48% but your estimate is 55%, Kelly sizing becomes dangerously wrong and can accelerate drawdown exactly when the strategy is underperforming.

Use fixed fractional risk instead:
- Risk 0.5–1.0% of account per trade
- At ₹50K: ₹250–₹500 per trade
- Position size = (Account × risk %) / (Entry price - Stop price)
- This is simple, conservative, and does not depend on an accurate edge estimate

Increase position size only after sufficient out-of-sample evidence. Do not scale up during paper trading or within the first 50 live trades.

**Kelly Criterion — a Phase M4+ research experiment:**
Once you have 200+ live trades with consistent performance, Kelly becomes worth researching as an optimization tool. At that point you have a realistic estimate of your edge. Even then, use fractional Kelly (half or quarter) — full Kelly maximizes long-run growth mathematically but produces extreme equity curve volatility in practice.

Kelly formula for reference (use later, not now):
```
Kelly fraction = (Win Rate × Avg Win - Loss Rate × Avg Loss) / Avg Win
```

Note: per-trade risk and daily loss limit are different concepts. Kelly determines position size per trade. The daily loss limit is a separate circuit breaker on total daily exposure. Do not conflate them.

## 6.3 Layered Risk Controls

Every institutional trading system has multiple independent risk layers:

**Layer 1 — Per-trade stop-loss:**
Maximum loss on any single trade. For options buying, this is typically defined as: exit if premium falls by 40–50% from entry. This prevents a single bad trade from consuming too much capital.

**Layer 2 — Daily loss limit:**
Hard kill: 2–3% of account. At ₹50K this is ₹1,000–₹1,500. Once hit, ALL trading stops for the day. No exceptions. No recovery attempts.

Soft warning: 1.5–2% of account. System logs the warning and reduces allowed position size for any remaining trades.

Note: The original target of ₹2,500–₹5,000 per day (5–10% of account) is too aggressive for a ₹50K account. A 10% daily loss hits repeatedly can destroy the account in days before the edge has a chance to manifest. The exact numbers should ultimately come from your strategy's expected loss distribution (derived from backtesting), but 2–3% daily is the appropriate starting constraint before that data exists.

Mechanism: System checks current day P&L before every order submission. If cumulative loss exceeds the limit, order is rejected and a human alert is sent.

**Layer 3 — Weekly drawdown limit:**
If cumulative weekly loss exceeds 5% of account, reduce position sizes by 50% for remainder of week. If cumulative weekly loss exceeds 8%, stop trading for the week.

**Layer 4 — Monthly circuit breaker:**
If monthly drawdown exceeds 10–12%, the strategy goes into paper trading mode for 2 weeks. Investigate what changed before resuming live trading.

**Layer 5 — Strategy invalidation criteria:**
Pre-define the conditions under which a strategy is considered broken and must be paused for review. Example: "If 30-day rolling Sharpe ratio falls below 0.5, or if win rate over last 50 trades falls below 40%, trigger a strategy review." This prevents the psychological trap of continuing to run a strategy that has stopped working because you cannot admit it.

## 6.4 Correlation & Concentration Risk

Do not run multiple strategies that are effectively the same trade. If all your strategies are long Bank Nifty in different ways, a single large directional move wipes them all simultaneously.

At your starting capital, this is not an immediate concern — you will likely run one strategy. But as you scale, ensure your strategy portfolio contains uncorrelated edges.

---

# PART 7 — PAPER TRADING PROTOCOL

## 7.1 Purpose of Paper Trading

Paper trading is not practice for when you "feel ready." It is a mandatory validation gate that serves a specific scientific purpose: detecting the gap between backtest performance and live performance.

This gap exists because:
- Backtests assume perfect execution at historical prices. Live trading has latency, partial fills, and price impact.
- Backtests do not capture API downtime, data feed gaps, or software bugs.
- Backtests do not capture your own behavioral response to seeing red P&L in real time.
- Market conditions change. A strategy that worked historically may face different microstructure now.

## 7.2 Paper Trading Rules

Paper trading must be run with the same discipline as live trading, or it tells you nothing.

Rule 1: Use live market data, not historical. Paper trading on historical data is just more backtesting.

Rule 2: Log ALL valid signals — not just the ones you chose to trade. This is the paper event log (see below). If you only log trades you actually took, you introduce selection bias and cannot measure true strategy performance.

Rule 3: Run for minimum 30 trading days before drawing any conclusions. Markets cycle through different regimes. 1–2 weeks catches nothing.

Rule 4: Simulate realistic execution. If your signal fires at 9:32 AM but your system would take 2 seconds to process and submit the order, record the fill at the price 2 seconds later, not at the signal price.

Rule 5: Track paper P&L separately from backtest P&L. Paper P&L measures execution quality in live conditions. Backtest P&L measures signal quality. The gap between them is your implementation shortfall. If implementation shortfall is large, investigate before going live.

**Paper Event Log — required format:**

Every valid signal must be logged with these fields:

| Field | Description |
|---|---|
| signal_timestamp | Exact time signal was generated |
| underlying_price | Bank Nifty level at signal time |
| zone_level | Midpoint of the S&R zone that triggered |
| zone_type | Volume / OI / Structural / Round number |
| zone_touch_count | How many times this zone has been touched |
| direction | Long / Short |
| strike | Options strike selected |
| expiry | Expiry date |
| option_type | CE / PE |
| entry_price | Price at signal time |
| stop_level | Pre-defined stop |
| target_level | Pre-defined target |
| expected_R | Target / Risk ratio |
| result | Bounce / Break / Inconclusive / Expired |
| MFE | Maximum Favorable Excursion (best price reached) |
| MAE | Maximum Adverse Excursion (worst price reached) |
| exit_price | Actual exit price |
| regime | Trending / Mean-reverting / Unknown |
| notes | Any qualitative observation |

Evaluate performance on all logged signals, not a cherry-picked subset.

## 7.3 Transition Criteria from Paper to Live

Do not go live based on calendar time. Go live based on validated performance criteria.

**Primary gate — signal and execution integrity (required):**
- Minimum 30 trading days completed
- ALL valid signals were logged in paper event log — no selection bias
- Implementation shortfall is understood and within acceptable range (see below)
- Zero unresolved system bugs or unexpected behaviors in final 2 weeks
- All risk controls tested and confirmed functioning (deliberately trigger the daily loss limit)
- API order flow tested end-to-end: entry, stop, target, cancel, partial fill, reconnection

**Secondary gate — performance distribution (not hard Sharpe target):**
Instead of requiring Sharpe > 1.0 as a binary pass/fail, compare the paper trading distribution to the backtest distribution across these dimensions:

| Metric | Backtest | Paper | Acceptable Gap |
|---|---|---|---|
| Expectancy per trade (₹) | X | Y | Y/X ≥ 0.75 |
| Win rate (%) | W | V | abs(W-V) ≤ 5 pp |
| Average win (₹) | AW | BW | BW/AW ≥ 0.80 |
| Average loss (₹) | AL | BL | BL/AL ≤ 1.25 |
| Average slippage (₹) | S_bt | S_paper | Document, no threshold |
| Trade frequency | F_bt | F_paper | F_paper/F_bt ≥ 0.80 |

The implementation ratio (paper expectancy / backtest expectancy) should be ≥ 0.75. If it is below 0.75, decompose the shortfall — is it slippage? missed signals? execution latency? Fix the specific component before going live.

A paper Sharpe of 0.9 from 22 trades with clean execution and matching distribution is better evidence than a Sharpe of 1.2 from 240 trades that were highly concentrated in one favorable week.

---

# PART 8 — LIVE EXECUTION ARCHITECTURE

## 8.1 Execution System Components

A production execution system has distinct modules that communicate with each other but operate independently:

**Data Feed Module:**
Connects to broker WebSocket. Receives live tick data and order book updates. Stores to in-memory ring buffer (fast) and persistent storage (durable). Detects and handles feed disconnections automatically. Sends heartbeat alerts if feed is silent for more than N seconds.

**Signal Generation Module:**
Reads from data feed. Computes indicators (volume profile, OI levels, momentum, regime). Detects when price approaches identified S&R zones. Scores signal quality. Outputs a signal object containing: instrument, direction, zone level, signal quality score, recommended entry price, stop-loss level, target level, position size.

**Risk Gate Module:**
Receives signal from Signal Generation. Checks: Is daily loss limit reached? Is position size within parameters? Is this instrument already in a position? Is current time within allowed trading hours? Is market regime appropriate for this strategy? Only if all checks pass does the signal proceed.

**Order Management Module:**
Receives approved signal from Risk Gate. Submits order to broker API. Manages open orders (modify, cancel). Tracks fills and partial fills. Manages position lifecycle (entry, stop-loss, target, time-based exits). Updates position and P&L records.

**Monitoring Module:**
Runs independently. Watches overall system health — data feed alive, modules running, daily P&L, open positions, API connectivity. Sends Telegram alerts on critical events. Provides dashboard for human oversight.

## 8.2 Order Execution Logic for S&R Strategies

When price approaches an identified S&R zone, the execution decision is not simply "send a limit order at the zone." Execution quality has a significant impact on P&L.

**Entry execution:**
For bounce strategy (expecting price to reverse at zone): Place a passive limit order slightly inside the zone (for support, buy a few ticks above the support level, not right at it). This improves fill probability while still capturing the zone trade. Do not chase price if zone is breached — cancel the order.

For breakout strategy (expecting price to break through zone): Wait for price to close a full bar above/below the zone with elevated volume before entering. Do not pre-empt — breakout confirmation is critical. Enter with a limit order near the current bid/ask, not a market order.

**Stop-loss execution:**
Use exchange-level stop-loss orders placed immediately after fill confirmation where possible. Do not rely solely on software to detect a stop condition and then submit a market order — this introduces latency and failure risk.

Important: bracket orders and co-linked stop orders are not universally available across all brokers and may be subject to regulatory change. Do not design your execution engine around a specific broker order type. Instead, build an abstraction layer (see Section 8.3) that allows switching stop management logic without rewriting the strategy.

**Exit execution:**
For profit targets: place a limit order at target immediately after entry fill. For time-based exits (e.g., always exit before 3:15 PM to avoid end-of-day volatility): use a scheduled check in the monitoring module that cancels open orders and submits market orders to flatten positions at specified time.

## 8.3 Execution Abstraction Layer

Design the execution engine with a clean abstraction between strategy logic and broker-specific implementation. Broker APIs change. Regulatory requirements change. Order types available today may not be available tomorrow.

Structure:

```
OrderManager (strategy-facing interface)
    ├── submit_entry(instrument, direction, size, entry_price, order_type)
    ├── submit_stop(position_id, stop_price)
    ├── submit_target(position_id, target_price)
    ├── cancel_order(order_id)
    ├── modify_order(order_id, new_price)
    └── emergency_flatten(all=True)

BrokerAdapter (broker-specific implementation)
    └── ShoonyaAdapter
            ├── Translates OrderManager calls to Shoonya API calls
            ├── Handles Shoonya-specific order types and responses
            └── Normalizes order statuses to common format
```

When you add a second broker or Shoonya changes its API, only the BrokerAdapter changes. Strategy logic and OrderManager interface remain untouched.

## 8.4 Handling Edge Cases

These situations will occur in live trading and must be pre-planned:

**API disconnection during open position:** System must detect disconnection, log the event, send an alert, attempt reconnection. If reconnection fails within 30 seconds, submit a manual cancel-all-orders via backup method (mobile app) and flatten the position manually.

**Partial fill:** Strategy sized for 1 lot, only partial fill received. System must track partial fill, decide whether to wait for remainder or cancel rest. Define this behavior in advance — do not make ad-hoc decisions during live trading.

**Data feed gap:** Historical data suddenly unavailable for a period. System must detect the gap, not compute signals using stale data, wait for data recovery before resuming.

**Extreme volatility / circuit-breaker events:** If India VIX spikes by more than a threshold in minutes, automatically suspend new entries and manage existing positions defensively. Do not wait for stop-losses to trigger — proactively reduce exposure.

**System crash during market hours:** All systems crash. The critical question is: what state are you in when you come back up? System must be able to query broker API on startup to determine current positions, open orders, and P&L before doing anything else.

---

# PART 9 — PERFORMANCE MONITORING & STRATEGY MAINTENANCE

## 9.1 Live Monitoring vs. Research Monitoring

Two distinct monitoring activities:

Live monitoring (real-time): Is the system working? Are positions correct? Are risk limits intact? Has anything broken?

Strategy monitoring (periodic): Is the strategy still working? Is edge decaying? Are performance metrics still in acceptable range?

Never conflate these two. Checking live P&L every 5 minutes during market hours is not productive monitoring — it is anxiety. Schedule separate time blocks for each.

## 9.2 Strategy Health Dashboard

Build a simple dashboard (can be a spreadsheet initially) tracking these metrics on a rolling basis:

Daily: P&L, number of trades, win rate, max intraday drawdown, largest single loss
Weekly: Rolling Sharpe (use 20-day), total trades, win rate trend (is it improving or declining?)
Monthly: Return vs. benchmark (Nifty), drawdown analysis, transaction cost as % of gross return, strategy vs. paper trading expectation

Threshold alerts:
- 30-day Sharpe falls below 0.8: investigate
- Win rate in last 30 trades falls more than 8 percentage points below backtest estimate: investigate
- Transaction costs exceed 25% of gross P&L: review trade frequency and sizing
- Any single day loss exceeds 75% of daily loss limit three consecutive times: strategy is struggling in current regime, reduce size

## 9.3 When to Stop a Strategy

One of the hardest decisions is knowing when a strategy has stopped working vs. when it is in a temporary drawdown.

Every strategy has drawdown periods. The question is whether the current drawdown is within the expected range of the strategy's historical drawdown distribution, or whether it indicates something fundamental has changed.

Signals that indicate fundamental change (not just normal drawdown):
- Market microstructure change: exchange rule changes, new participants, lot size changes
- Crowding: your signals are now widely used (strategy appears in retail trading forums extensively)
- Regime shift: the market has moved from mean-reverting to strongly trending for an extended period
- Strategy invalidation: the economic mechanism you identified no longer applies (e.g., options market structure change)

Signals that indicate normal drawdown:
- Performance decline coincides with a known regime shift (high trending period) that the strategy was expected to underperform
- Individual trade losses are within historical distribution (no unusually large losses)
- No change in signal quality metrics — levels are still being identified correctly, just the market is not respecting them

Default rule: If cumulative drawdown reaches 2x the historical maximum drawdown observed in backtesting, suspend the strategy regardless. Something unexpected is happening.

---

# PART 10 — SCALING ROADMAP

The most important structural change from the original plan: ₹50K live capital enters at M3, not day one. This is not excessive caution — it is the difference between paying research costs (negligible) and paying tuition to the market (real money) before knowing if the hypothesis is real.

## M0 — Prove or Disprove the Phenomenon (no live capital)

Goal: Determine whether Bank Nifty price zones produce statistically significant conditional reversal probabilities. This is a pure research milestone.

Activities:
- Build data pipeline: historical Bank Nifty OHLCV (5-min), options chain snapshots, FII data
- Build zone detection engine using structural levels and volume profile
- Build formal event engine (touch, bounce, break as defined in Section 4.5)
- Run Experiments 001-004 from Section 4.6 sequentially
- Compare against 7 baseline models
- Run OOS validation on held-out data

Success criteria to proceed to M1 — ALL three must be satisfied:

1. **Statistical edge:** P(bounce | zone) is statistically significantly higher than matched controls. 95% CI of the lift excludes zero. Permutation test p-value < 0.05.

2. **Economic edge:** 95% CI of net expectancy per trade (after STT, exchange charges, slippage, spread) excludes zero on the lower bound. Statistical edge is necessary but not sufficient — a +10% bounce lift with tiny average winners that options decay and spread cost consume is not a tradable edge.

3. **OOS edge:** Both statistical and economic edge hold on the held-out OOS dataset. Some degradation is expected (10–20% drop in effect size is acceptable). A large collapse OOS means in-sample result was overfit.

Kill condition: If any of the three fail, do not proceed to M1. Investigate whether a different hypothesis or instrument is worth testing. This is a research success, not a failure.

Kill condition: If OOS net expectancy is negative or not significantly better than Baseline 6 (previous-day high/low), the S&R hypothesis does not survive. Do not proceed to M1. Investigate whether a different hypothesis (momentum, opening range, etc.) might be worth testing instead. This outcome is a research success, not a failure.

## M1 — Build a Tradable Strategy (no live capital)

Goal: Convert M0 findings into a concrete strategy with defined rules.

Activities:
- Define entry conditions, stop-loss placement, target levels
- Define position sizing (fixed fractional, 0.5–1.0% risk per trade)
- Build full backtest with realistic costs, slippage, and liquidity constraints
- Run walk-forward validation
- Document strategy rules completely — no ambiguity that requires human judgment at execution time

Success criteria to proceed to M2:

Required (hard gates):
- Walk-forward backtest shows positive OOS expectancy (net of all costs)
- Maximum drawdown does not exceed 15% of capital
- No catastrophic tail events (no single trade loss > 3× average loss)
- Sufficient independent trades in OOS window (minimum 50)
- All strategy rules fully specified with no discretionary components

Supporting metrics (evaluate, do not use as hard gates):
- Profit Factor > 1.4 (PF is sensitive to outliers and trade frequency — treat as signal, not gate)
- Sharpe Ratio > 1.0
- Calmar Ratio > 0.8

## M2 — Paper Trading (no live capital, minimum 30 days)

Goal: Validate that backtest performance transfers to live market conditions.

Activities:
- Build live data feed (Shoonya API)
- Deploy strategy logic against live data with simulated orders
- Log ALL valid signals in paper event log (Section 7.2)
- Monitor system health, API stability, execution logic

Success criteria to proceed to M3: see Section 7.3 (implementation ratio ≥ 0.75, signal integrity, zero open bugs, all controls tested).

## M3 — Micro-Live: ₹50,000 (minimum 3 months)

Goal: Validate that paper results transfer to real execution at minimum size. Discover everything paper trading could not reveal.

Activities:
- Deploy live with fixed fractional sizing at minimum (0.5% risk per trade = ₹250)
- Hard daily loss limit: 2% (₹1,000)
- Maintain paper event log alongside live log — track implementation shortfall at every trade
- Do not increase position size during this phase regardless of performance
- Human supervises every session: can kill the system but cannot override individual signals except under pre-defined emergency procedures (e.g., API malfunction, extreme event)

**M3 is human-supervised execution, not autonomous execution.**
Full autonomy is M4. At M3, a human must be able to observe every decision and intervene at the system level. The strategy runs its own logic without human discretion on individual trades, but the human is present and monitoring.

Success criteria to proceed to M4:
- 3 months live trading completed
- Live performance within 25% of paper expectancy (implementation ratio ≥ 0.75 paper-to-live)
- No single risk limit breach
- Implementation shortfall sources identified (slippage, latency, missed fills)
- All edge cases handled without unplanned manual intervention

## M4 — Full Automation (₹2–10 Lakhs)

Goal: Complete execution system running without human intervention in the trade loop.

Activities:
- Deploy full system architecture (all 6 engines from Section 2.4)
- Build Redis message passing layer
- Migrate database to PostgreSQL + TimescaleDB
- Add second uncorrelated strategy if M0-level research supports one
- Build comprehensive monitoring dashboard
- Upgrade alerting and system health monitoring

Success criteria: System runs without intervention. Human role is oversight, strategy research, and risk monitoring only.

## M5 — Portfolio Scale (₹10L+)

Goal: Multiple uncorrelated edges, portfolio-level risk management.

At this scale:
- Multiple strategies across instruments (Bank Nifty, Nifty, potentially stock F&O)
- Portfolio-level risk budgeting (allocate risk budget across strategies, not just capital)
- Evaluate whether latency-sensitive strategies are in scope (co-location at NSE only relevant if holding period is sub-minute — unlikely for S&R mean reversion)
- Review regulatory obligations based on current SEBI framework at that time

---

# PART 11 — REGULATORY & COMPLIANCE (INDIA)

## 11.1 SEBI Algorithmic Trading Regulations

**Important caveat:** Do not treat this section as current legal guidance. Verify directly with your broker and a qualified professional before going live.

SEBI has been actively reforming the retail algorithmic trading framework. As of the September 2025 extension, SEBI's retail algo framework had an implementation date of April 1, 2026. Before M4 automation, verify:
- Your broker's (Shoonya) specific implementation of the SEBI retail algo framework requirements
- Current NSE operational requirements for API-based trading
- Whether Shoonya's API capabilities match your execution architecture design (bracket orders, stop types, WebSocket stability)

Do not design your execution architecture around assumed broker capabilities. Verify against the broker's current API documentation and compliance requirements before building.

General principles (verify before relying on):
- Algorithmic trading must be executed through a SEBI-registered stockbroker
- Brokers are responsible for risk controls on their platform
- Complete audit trail of all orders is mandatory

**The regulatory distinction that actually matters** is not about capital size. It is about what you are doing:

- Trading your own capital using automated tools: generally permissible through a registered broker's API, subject to their terms and any exchange/SEBI requirements at the time
- Managing someone else's capital: requires SEBI registration as a Portfolio Manager regardless of amount
- Offering your strategy as a product or service to others: requires registration as an Investment Adviser or Portfolio Manager
- Providing execution infrastructure to third parties: separate regulatory obligations apply

The threshold is not "₹25L+ requires registration." The threshold is "whose money are you trading, and are you offering advice or a service to others?"

Consult a qualified professional with current knowledge of SEBI's algorithmic trading regulations before going live, especially before M4 automation.

## 11.2 Tax Implications

Trading income in India:
- Futures and options trading income is classified as Business Income, not Capital Gains
- You must file ITR-3
- Trading losses can be carried forward for 8 years and set off against future trading profits
- Maintain complete trade records — broker statements, trade logs, all documentation

Consult a CA with trading experience before your first tax filing.

---

# PART 12 — LEARNING ROADMAP

## 12.1 Essential Knowledge Areas

**Statistics & Probability (Foundation):**
Without solid statistics, you cannot validate strategies. Focus on: hypothesis testing, probability distributions, time-series analysis (stationarity, autocorrelation), regression analysis, bootstrap methods.

Resources: "Statistics for Business and Economics" for foundations. "Advances in Financial Machine Learning" by Marcos López de Prado for quant-specific statistics.

**Market Microstructure:**
How markets actually work at the tick level. Order types, matching engines, market making, adverse selection, price discovery. This is the most underestimated area of knowledge.

Resources: "Trading and Exchanges" by Larry Harris. Academic papers by Thierry Foucault, Albert Menkveld.

**Options Theory:**
Greeks (Delta, Gamma, Theta, Vega), volatility surface, options pricing intuition (not necessarily Black-Scholes math but the intuition). This is essential for Bank Nifty options trading.

Resources: "Option Volatility and Pricing" by Sheldon Natenberg.

**Python for Finance:**
pandas, numpy, scipy, matplotlib are the minimum. Also learn: vectorbt or backtesting.py for backtesting, TA-Lib for indicators, plotly for interactive visualization.

**Indian Markets Specific:**
Read NSE circulars and SEBI notifications regularly. Follow NSE's market statistics publications. Understand index methodology (how Bank Nifty is calculated, rebalancing schedule).

## 12.2 What to Build First (Sequenced by Milestone)

**M0 — Research (Weeks 1–12)**

Week 1–2: Data pipeline. Download historical Bank Nifty OHLCV (5-min minimum). Store as Parquet. Validate data quality — check for gaps, bad ticks, outliers. Do not proceed with research until you trust the data.

Week 2–3: Collect FII/DII daily data (NSE website). Build automated daily downloader.

Week 3–5: Zone detection engine. Implement structural level detection (previous day high/low, weekly high/low, swing pivots). Implement volume profile (POC, VAH, VAL). Visualize zones on historical price charts to sanity-check detection logic.

Week 5–6: Formal event engine. Implement touch detection, bounce/break classification using definitions from Section 4.5. Enforce causal mode (Section 4.3). Log all events to a dataset.

Week 7–9: Experiment 001. Run statistical tests. Compare against baseline models. Check significance and effect size.

Week 9–11: Experiments 002–004. Add options chain OI data. Test incremental lift of each feature class.

Week 12: OOS validation. Run full walk-forward analysis on held-out data. Make proceed/kill decision.

**M1 — Strategy (Weeks 13–16)**

Build full backtest with realistic costs. Define all strategy rules explicitly. Validate walk-forward performance.

**M2 — Paper Trading (Months 5–6)**

Build live data feed. Deploy signal logic. Begin logging paper event log. Run minimum 30 trading days.

**M3 — Micro-live (Month 7+)**

First real money at minimum size. Only if M0-M2 criteria are met.

---

# APPENDIX A — KEY TERMS REFERENCE

**ATR (Average True Range):** Measure of volatility. Average of the true range (max of: high-low, abs(high-prev close), abs(low-prev close)) over N periods.

**CVD (Cumulative Volume Delta):** Running sum of (aggressive buy volume - aggressive sell volume). Measures directional pressure.

**DBSCAN:** Density-Based Spatial Clustering of Applications with Noise. Clustering algorithm that groups nearby points. Useful for clustering historical pivot points into zones.

**HMM (Hidden Markov Model):** Statistical model where the system being modeled is assumed to be a Markov process with hidden states. Used to detect market regimes.

**KDE (Kernel Density Estimation):** Non-parametric way to estimate the probability density function of a variable. Used on volume data to find high-density price levels.

**Max Pain:** The strike price at which the total value of all expiring options (both calls and puts) is minimized for option buyers, maximized for option sellers.

**OFI (Order Flow Imbalance):** Measure of directional pressure in the order book. Difference between buy-side and sell-side order flow.

**OI (Open Interest):** Number of outstanding options contracts. High OI at a strike = significant market interest and potential S&R level.

**PCR (Put-Call Ratio):** Total put OI divided by total call OI. Extreme readings are contrarian indicators.

**POC (Point of Control):** Price level with highest traded volume in a volume profile.

**Sharpe Ratio:** (Annualized Return - Risk Free Rate) / Annualized Standard Deviation of Returns. Risk-adjusted performance measure.

**STT (Securities Transaction Tax):** Indian tax on securities transactions. Must be modeled in all backtests.

**VAH/VAL (Value Area High/Low):** The price range containing 70% of the session's traded volume, above and below the POC.

**VPIN (Volume-synchronized Probability of Informed Trading):** Measure of toxic order flow. High VPIN suggests informed traders are active.

---

# APPENDIX B — DAILY TRADER OPERATING PROCEDURE

This is the checklist for operating your system professionally once live.

**Pre-market (8:30–9:00 AM):**
- Check overnight global market moves (SGX Nifty, Dow futures, Asian markets)
- Review FII/DII data from previous day (NSE website)
- Calculate current week's Bank Nifty max pain and high-OI strikes
- Identify key S&R levels for the day (volume profile from previous sessions + OI walls)
- Check economic calendar — any RBI/Fed/earnings events today?
- Verify system health: data feed running, broker API connected, risk limits reset

**Market open (9:15–9:45 AM):**
- Observe opening range. Do not trade in first 15 minutes unless strategy explicitly uses opening range breakout.
- Assess whether market is trending or rotating (gap direction, volume profile developing)
- Verify your pre-identified levels are still relevant (major overnight gaps can invalidate them)

**Intraday:**
- Let signals come to you. Do not force trades.
- Monitor open positions only — do not watch every tick
- Check system health at 11:00 AM and 1:00 PM

**Pre-close (3:00–3:15 PM):**
- Close all options positions (avoid STT trap and liquidity risk at close)
- System should handle this automatically once built

**Post-market (after 3:30 PM):**
- Record all trades in trade journal
- Calculate day's P&L and update performance dashboard
- Note any observations about market behavior — what worked, what did not, and why
- Download and store the day's data

**Weekly (Friday evening):**
- Review week's performance against benchmarks
- Update rolling metrics
- Review strategy health indicators
- Plan next week (upcoming events, expiry schedule)

---

---

# APPENDIX C — RESEARCH DATASET SCHEMA

The M0 research dataset must be structured precisely before running any statistical tests. Define the schema upfront so all experiments use identical data structures and results are reproducible.

**Base table (one row per 5-minute bar):**

| Column | Type | Description |
|---|---|---|
| timestamp | datetime | Bar close time (IST) |
| underlying_price | float | Bank Nifty index level (close) |
| future_price | float | Near-month futures close |
| future_volume | int | Futures volume for bar |
| future_oi | int | Futures open interest (end of day) |
| india_vix | float | India VIX at bar time |
| fii_index_future_long | int | FII long contracts (daily, forward-filled intraday) |
| fii_index_future_short | int | FII short contracts (daily, forward-filled intraday) |
| session_time | int | Minutes since 9:15 AM |
| day_of_week | int | 0=Monday, 4=Friday |
| days_to_expiry | int | Calendar days to current expiry |

**Options table (one row per strike per snapshot):**

| Column | Type | Description |
|---|---|---|
| timestamp | datetime | Snapshot time |
| expiry | date | Options expiry date |
| strike | int | Strike price |
| option_type | str | CE or PE |
| option_price | float | LTP |
| option_volume | int | Volume |
| option_oi | int | Open interest |
| option_oi_change | int | OI change from previous snapshot |
| option_iv | float | Implied volatility |
| option_delta | float | Delta (if available) |
| option_gamma | float | Gamma (if available) |
| pcr | float | Put-call ratio at this expiry snapshot |

**Derived features (computed, not stored raw — always reproducible from above):**

| Feature | Description |
|---|---|
| distance_to_zone | ATR-normalized distance from price to nearest zone midpoint |
| zone_width | Zone width in ATR units |
| touch_count | Number of previous touches of this zone |
| zone_age | Bars since zone was first identified |
| volume_at_zone | Total historical volume transacted within zone bounds |
| oi_at_nearest_strike | OI at nearest options strike |
| delta_oi | OI change at nearest strike |
| atr_14 | 14-bar ATR |
| realized_vol_20 | 20-bar realized volatility (annualized) |
| vwap | VWAP from session open |
| vwap_distance | ATR-normalized distance from VWAP |
| trend_adx | ADX (14) — trend strength |
| regime | Trending / Mean-reverting / High-vol (derived from ADX + VIX) |

---

*Document version 3.1 — Bharath Dasari — FROZEN*
*Created: August 2026 (v1.0)*
*Revised: August 2026 (v2.0) — hypothesis reframing, options theory correction, risk sizing, M0-M5 milestone restructure, formal event definitions, multiple baselines, permutation testing, OrderManager abstraction, regulatory caveat*
*Revised: August 2026 (v3.0) — CostEngine with date-aware rates, contract metadata structure, look-ahead prohibition + causal/research zone engine modes, volume profile look-ahead fix, stratified matched-control methodology, M0 gate requires statistical + economic + OOS edge simultaneously, implementation shortfall decomposition, M3 human-supervised, SEBI April 2026 framework reference*
*Revised: August 2026 (v3.1) — FINAL: removed weekly options premise (Bank Nifty weekly contracts discontinued), all expiry references made date-dependent from contract metadata, illustrative STT rates removed from prose (authoritative source: data/metadata/cost_rates/), pre-registered EXP-001 event parameters (X=1.0, Y=0.5, N=6, k=0.5 ATR), matched-control variables separated into safe confounders vs. endogenous, Profit Factor demoted from hard gate to supporting metric, consecutive-loss explanation corrected for regime dependence*
*Framework status: FROZEN at v3.1. Next step: create M0_EXPERIMENT_001.md and start building.*
