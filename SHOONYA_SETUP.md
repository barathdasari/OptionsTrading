# Shoonya (Finvasia) Account + API Setup

Do this in parallel while the yfinance daily pipeline runs.
Once Shoonya is ready, it unlocks 5-min historical data (~2 years) for EXP-001.

---

## Step 1 — Open Trading Account

1. Go to finvasia.com → Open Account
2. Required documents:
   - PAN card
   - Aadhaar (for e-KYC)
   - Bank account (savings) with IFSC
   - Cancelled cheque or bank statement
3. Complete e-KYC via Aadhaar OTP
4. Account activation: 1–3 business days
5. Zero brokerage on F&O — no hidden charges

---

## Step 2 — Activate API Access

1. Log in to shoonya.finvasia.com
2. Go to: Account → API → Enable API Access
3. Generate your API key (one-time, save securely)
4. Note your:
   - User ID (your client ID)
   - API key
   - TOTP secret (for 2FA login via code, needed for automated login)

Store credentials in a `.env` file at project root — **never commit this file**:

```
SHOONYA_USER=YOUR_CLIENT_ID
SHOONYA_API_KEY=YOUR_API_KEY
SHOONYA_TOTP_SECRET=YOUR_TOTP_SECRET
SHOONYA_PASSWORD=YOUR_PASSWORD
SHOONYA_VENDOR_CODE=YOUR_VENDOR_CODE
SHOONYA_IMEI=YOUR_IMEI_OR_MAC
```

Add `.env` to `.gitignore` immediately.

---

## Step 3 — Install Shoonya Python API

```bash
pip install api-shoonya
```

Official repo: github.com/Shoonya-Dev/ShoonyaApi-py

---

## Step 4 — Test Login

```python
import pyotp
import os
from api_helper import ShoonyaApiPy

api = ShoonyaApiPy()
totp = pyotp.TOTP(os.getenv("SHOONYA_TOTP_SECRET")).now()

ret = api.login(
    userid=os.getenv("SHOONYA_USER"),
    password=os.getenv("SHOONYA_PASSWORD"),
    twoFA=totp,
    vendor_code=os.getenv("SHOONYA_VENDOR_CODE"),
    api_secret=os.getenv("SHOONYA_API_KEY"),
    imei=os.getenv("SHOONYA_IMEI"),
)
print(ret)  # Should return {"stat": "Ok", ...}
```

---

## Step 5 — Verify Historical Data Endpoints

Shoonya provides `get_time_price_series()` for historical OHLCV.

```python
import datetime

# Bank Nifty index symbol on Shoonya: "Nifty Bank" on NSE
# Futures symbol format: "BANKNIFTY24DECFUT" (verify current format)

ret = api.get_time_price_series(
    exchange="NSE",
    token="26009",       # Bank Nifty index token on NSE
    starttime=datetime.datetime(2023, 1, 1).timestamp(),
    endtime=datetime.datetime(2023, 12, 31).timestamp(),
    interval=5,          # 5-minute bars
)
```

Token numbers: verify from Shoonya's symbol master file (downloadable from their API).

**Known limitations:**
- Historical depth: approximately 400 trading days for intraday
- Rate limits: check current API documentation before building batch downloader
- Symbol master changes with expiries — always use current master

---

## Step 6 — What Shoonya Unlocks for This Project

| Data | yfinance (now) | Shoonya (after setup) |
|---|---|---|
| Daily OHLCV | 2000–present | Same |
| 5-min OHLCV | Last 60 days only | ~400 trading days (~18 months) |
| Options chain | Not available | Live + limited history |
| FII/DII | Not available | Not available (use NSE website) |
| Live feed | Not available | WebSocket (M2+) |

5-min history from Shoonya covers roughly 2022–present, sufficient for EXP-001 with proper train/validation/holdout split.

---

## Step 7 — Once Shoonya Is Ready

1. Add `src/data/shoonya_downloader.py` (parallel to `downloader.py`)
2. Download 5-min Bank Nifty data → store as `BANKNIFTY/5min/BANKNIFTY_5min.parquet`
3. Re-run `scripts/02_validate_data.py` with `--timeframe 5min`
4. Update `M0_EXPERIMENT_001.md` experiment log with actual data range
5. Proceed to zone detection code

---

## FII/DII Data (Free, Manual Download)

NSE publishes FII/DII daily activity. Not available via Shoonya or yfinance.

Manual download steps:
1. Go to nseindia.com → Market Data → FII/DII Data
2. Select date range
3. Download CSV
4. Store in `data/raw/FII_DII/1D/`
5. Build automated scraper later (M2+) — NSE website requires session cookies

---

## Security Checklist

- `.env` in `.gitignore` — verify before first commit
- Never log API credentials
- API key rotates if compromised — regenerate from Shoonya dashboard
- TOTP secret is sensitive — treat like a password
