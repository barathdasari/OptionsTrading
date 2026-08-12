# What Is This Project? (Plain English)

---

## The One-Line Version

We're trying to answer a single question with math instead of gut feeling:

> **"Does the stock market actually bounce off certain price levels — or do traders just believe it does?"**

---

## The Problem With Most Trading Advice

You've probably heard things like:

- *"Bank Nifty always bounces off 50,000."*
- *"That's a strong support level — buy there."*
- *"OI wall at 48,000 — it won't break through."*

Every trader on YouTube, every WhatsApp group, every "pro" on Twitter says these things with total confidence.

But here's the uncomfortable question nobody asks:

**Has anyone actually measured whether this is true?**

Not anecdotally. Not "I saw it bounce three times." Measured properly. With statistics. On thousands of historical examples. Accounting for the fact that if you look hard enough at any chart, you'll find patterns that look meaningful but are actually random noise.

This project exists to answer that question properly.

---

## A Simple Analogy

Imagine you run a chai stall near a traffic signal.

You notice that during the 11 AM to 12 PM hour, you seem to sell more cutting chai. So you stock up every day during that window.

A scientist would ask: *Is that actually true, or did you just happen to notice a few busy days and assume it's always like that?*

To answer properly, you'd need to:
1. Record every single hour of sales for a year
2. Compare 11 AM to every other hour — not just the ones you remember
3. Make sure you're not fooling yourself by cherry-picking examples
4. Account for the fact that some days are naturally busier (weekends, festivals)
5. After all that — does 11 AM *actually* sell more, or was it luck?

That's exactly what we're doing with Bank Nifty support and resistance levels.

---

## What Is Bank Nifty?

Bank Nifty is an index — a single number that tracks the health of India's 12 biggest banks (HDFC Bank, ICICI Bank, SBI, Kotak, etc.) all rolled into one score.

It's one of the most actively traded things on the NSE (National Stock Exchange). Millions of traders buy and sell Bank Nifty futures and options every day, betting on whether the number will go up or down.

The index currently sits somewhere around 50,000–55,000 points. A move of 500 points in a day is normal. A move of 1,500 points in a day happens during big events like RBI policy announcements or election results.

---

## What Is "Support and Resistance"?

Think of it like a rubber ball bouncing on the floor.

**Support** is the floor. Price falls, hits this level, and bounces back up.

**Resistance** is the ceiling. Price rises, hits this level, and gets pushed back down.

The idea is that certain price levels have "memory" — lots of traders previously bought or sold there, and they'll do so again when price returns to that level.

Some examples of why these levels might exist:
- **Round numbers** (50,000, 51,000) — humans psychologically cluster their orders at round numbers
- **Yesterday's high** — many traders automatically set their stop-losses or entry orders at these visible levels
- **Weekly high/low** — swing traders reference these every week
- **Heavy options activity** — if millions of rupees of options contracts are sitting at 49,000, options sellers have financial incentive to defend that level

Here's the thing though: *might exist* is doing a lot of work in that sentence. These are theories. Plausible stories. Not proven facts.

---

## What We're Actually Building

Think of it like a scientific lab for trading ideas.

Instead of:
> "I think 50,000 is a strong support. Let me trade it."

We do:
> "Let me scan 19 years of Bank Nifty data, find every single time price touched a level like 50,000, and measure what happened next — did it bounce or did it crash through?"

Then we compare that to: what would have happened if we'd picked *random* price levels instead of the "special" ones?

If the special levels bounce more than random levels — we've found something real.
If they bounce the same amount — it's just a story traders tell each other.

---

## The Six Stages of This Project

Think of it like building a restaurant from scratch — you wouldn't open to customers before you've tested the recipes.

**Stage 0 — Research (we are here)**
Does the phenomenon even exist? Test on historical data. Zero real money. This is the lab stage. Like a chef experimenting in the kitchen before the restaurant opens.

**Stage 1 — Strategy Design**
If Stage 0 says "yes, it works" — build the exact rules. When to enter. Where to put the stop-loss. How much to risk. Like writing the official recipe card.

**Stage 2 — Paper Trading**
Run the strategy on live market data, but with *fake money*. Like doing a full dry run of the restaurant with staff and food, but no paying customers yet.

**Stage 3 — Real Money, Tiny Size (₹50,000)**
First time using real money. But at the smallest possible size to make sure nothing breaks. Like opening the restaurant to 5 friends first before launching to the public.

**Stage 4 — Automation**
Build a computer system that executes trades automatically. No human needed to click buttons.

**Stage 5 — Scale**
Grow the capital. Add more strategies. Run the full restaurant.

---

## What Has Actually Been Built So Far

### The Data Pipeline

We download Bank Nifty's entire price history — 19 years of daily prices, from 2007 to today — and store it in a database on the computer.

Think of this like building the ingredient pantry. Before you can cook anything, you need to know what ingredients you have, whether they're fresh, and whether any are missing.

We automatically check the data for problems:
- Are there any missing days? (19 years × ~250 trading days = ~4,600 bars — we have 4,652, looks clean)
- Are there any obviously wrong prices? (like Bank Nifty suddenly showing 500 when it should be 50,000)
- Are there any duplicate entries?

**Result: Data is clean. Ready for research.**

---

### The Zone Detection Engine

We built software that automatically identifies the "special" price levels — the ones traders claim are support and resistance.

For now it finds four kinds:
1. **Yesterday's high and low** — the most basic levels every trader watches
2. **Last week's high and low** — slightly longer-term levels
3. **Swing pivot points** — local peaks and valleys in recent price history
4. **Volume Profile levels** — price levels where the most trading happened (requires more data)

The key engineering challenge here is something called the **look-ahead problem**.

Here's a simple version of why it matters:

Imagine you're told to predict tomorrow's weather, but you accidentally peek at tomorrow's actual weather before making your prediction. Your predictions would look amazing — but they're useless in the real world.

The same thing happens in trading research. A lot of people accidentally use tomorrow's price data to identify "yesterday's" levels. It makes the strategy look brilliant in backtesting, but it's completely fake.

We built strict rules to prevent this: every level identified at 9 AM can only use data from *before* 9 AM. No peeking forward.

**Result: 29,116 zone-bar entries detected across 4,638 days.**
That means on the average day, there are about 6 active "special" price levels.

---

### The Event Engine

Now we ask: each time price touched one of those special levels, what happened next?

We defined three possible outcomes — like a coin that can land on three sides:

- **Bounce** — price moved favorably by 1 ATR (Average True Range, a measure of typical daily movement) before moving against you by 0.5 ATR. This is what S&R believers claim will happen.
- **Break** — price crashed through the level. The "support" failed.
- **Inconclusive** — neither happened within 6 days. The level just didn't matter.

We scanned all 19 years of data and logged every single zone touch.

**Result from 2,884 touch events:**
- Bounce: 1,008 (35%)
- Break: 1,635 (57%)
- Inconclusive: 241 (8%)

So price broke through the level more often than it bounced. Interesting. But is 35% bounce rate *good*? Is it better than random?

---

### The Matched Controls

This is the most important part — and the part most traders skip entirely.

We can't just look at "35% bounce rate at zones" and call it meaningful. We need to compare it to something.

Think of it like a drug trial. You can't just give 1,000 people a new pill and say "800 of them got better!" — because maybe 800 of them would have gotten better *without the pill too*. You need a control group.

So for every zone touch event, we found a "matched control" moment in the same time period — a day that looked similar (same volatility, same trend, same day of week) but where price was *not* near any special level.

Then we asked: what's the bounce rate at those random moments?

**Control group bounce rate: 41.5%**

So random non-zone moments bounced 41.5% of the time.
Zone touches bounced only 35% of the time.

**The zones actually performed worse than random.**

---

### The Statistical Tests

We ran four formal tests to make sure we weren't imagining things:

**1. Bootstrap Test** (like rolling the dice 10,000 times)
We randomly resampled our data 10,000 times to build a confidence interval.
Result: We're 95% confident the true lift is between -8.2pp and -1.8pp.
Negative. Zones are worse than random.

**2. Permutation Test** (could this result happen by chance?)
We randomly shuffled which moments were "zone touches" 10,000 times.
The result we observed (-5pp lift) is well within what you'd expect by pure chance.
The zones add no signal.

**3. Return Distribution Test**
We compared the full distribution of 6-day returns after zone touches vs after control moments.
The distributions look nearly identical (p=0.34 on the main test).

**4. Economic Edge Test**
Even if there were a small signal, after transaction costs, the strategy loses money.
Net expectancy: -0.10 ATR per trade. Not tradable.

---

## What Does This Mean?

**The S&R hypothesis, as tested on daily Bank Nifty data, does not hold up.**

Price does not bounce off our identified zones more than it bounces off random price levels.

This is a *good* result, not a bad one. Here's why:

The point of this project is not to prove that S&R works. The point is to find out the *truth*, whatever it is.

Finding out that a hypothesis is wrong before putting real money on it is exactly the right outcome.

We spent zero rupees finding this out. Traders who skip the research phase spend ₹50,000–₹5,00,000 in real losses to learn the same lesson.

---

## But Wait — Is It Definitely Dead?

Not quite. There's one big caveat.

This test used **daily price bars** — one data point per day.

The original experiment was designed for **5-minute bars** — 75 data points per day. That's 15x more resolution.

Why does this matter? Support and resistance is an intraday phenomenon. The bounce happens at 10:32 AM and is over by 10:45 AM. Looking at daily closing prices is like trying to see a ripple in a swimming pool by photographing it once a day. The ripple happened — you just can't see it in your photos.

We used daily data because it was freely available (via Yahoo Finance). The better data — 5-minute intraday bars — requires setting up a trading account with Shoonya (Finvasia), which is in progress.

**The plan:**
1. Open Shoonya account (free, zero brokerage)
2. Download 18 months of 5-minute Bank Nifty bars
3. Re-run the exact same experiment at intraday resolution
4. *Then* make the GO/KILL decision

The daily-bar result is useful: it built and validated the entire research pipeline. Every piece of code — data download, zone detection, event engine, statistical tests, chart generation — is now working and tested. When 5-minute data arrives, it's just a data swap.

---

## Summary: Where We Stand

| What | Status |
|---|---|
| Research framework designed | Done |
| Experiment formally pre-registered | Done |
| Data pipeline built | Done |
| 19 years of daily data downloaded | Done |
| Zone detection engine | Done |
| Event engine (touch/bounce/break) | Done |
| Statistical tests + charts | Done |
| **Daily-bar EXP-001 result** | **FAIL — no edge found** |
| 5-minute data (Shoonya) | **Pending account setup** |
| Intraday EXP-001 re-run | Waiting on data |

**Total real money spent on research: ₹0**

**Total real money at risk: ₹0**

That's exactly how it should be at this stage.

---

## Files You Can Look At

- [quant_trading_framework.md](quant_trading_framework.md) — the full research blueprint
- [M0_EXPERIMENT_001.md](M0_EXPERIMENT_001.md) — the pre-registered experiment (frozen before any data was looked at)
- [SHOONYA_SETUP.md](SHOONYA_SETUP.md) — how to set up the trading account for real data
- [reports/EXP-001/exp001_summary_report.txt](reports/EXP-001/exp001_summary_report.txt) — the statistical test results
- [reports/EXP-001/charts/](reports/EXP-001/charts/) — 11 charts showing the data visually

---

*This document will be updated as the project progresses.*
