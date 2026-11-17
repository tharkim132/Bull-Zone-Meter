"""
Bull Zone Meter - Nifty 500
Roz chalne par data.json update karta hai.

Bull Zone % = Nifty 500 ke kitne % stocks apne DMA ke upar band hue.
"""
import io
import json
import os
import sys
from datetime import datetime, timedelta

import pandas as pd
import requests
import yfinance as yf

# ---------- Settings (aap yaha badal sakte ho) ----------
DISPLAY_FROM = "2024-01-01"      # chart kis date se dikhana hai
DMA_PERIODS = [200, 50]          # dono calculate honge
MIN_STOCKS = 300                 # isse kam stocks ka data aaya to file overwrite nahi hogi
BATCH_SIZE = 100
CSV_URL = "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv"
LOCAL_CSV = "nifty500.csv"       # NSE se download na ho to ye file repo me daal do
# ---------------------------------------------------------


def get_symbols():
    """Nifty 500 ki list: pehle NSE se, nahi to local nifty500.csv se."""
    df = None
    try:
        headers = {"User-Agent": "Mozilla/5.0", "Accept": "text/csv,*/*"}
        r = requests.get(CSV_URL, headers=headers, timeout=30)
        r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.text))
        print("NSE se list download hui.")
    except Exception as e:
        print(f"NSE se list nahi mili ({e}).")
        if os.path.exists(LOCAL_CSV):
            df = pd.read_csv(LOCAL_CSV)
            print(f"{LOCAL_CSV} use kar raha hu.")
    if df is None:
        sys.exit("Nifty 500 ki list nahi mili. nifty500.csv repo me daalo.")
    return [s.strip() + ".NS" for s in df["Symbol"].dropna()]


def download_prices(symbols, start):
    frames = []
    for i in range(0, len(symbols), BATCH_SIZE):
        batch = symbols[i:i + BATCH_SIZE]
        print(f"Download: {i + 1}-{i + len(batch)} / {len(symbols)}")
        try:
            data = yf.download(batch, start=start, auto_adjust=True,
                               progress=False, threads=True)["Close"]
            if isinstance(data, pd.Series):
                data = data.to_frame(batch[0])
            frames.append(data)
        except Exception as e:
            print(f"Batch fail: {e}")
    if not frames:
        sys.exit("Koi data download nahi hua.")
    prices = pd.concat(frames, axis=1)
    prices = prices.loc[:, ~prices.columns.duplicated()]
    return prices.dropna(axis=1, how="all")


def bull_percent(prices, period):
    dma = prices.rolling(period, min_periods=period).mean()
    valid = dma.notna() & prices.notna()
    above = (prices > dma) & valid
    pct = above.sum(axis=1) / valid.sum(axis=1).replace(0, float("nan")) * 100
    return pct


def zone(v):
    if v >= 70:
        return "Euphoria"
    if v >= 50:
        return "Optimism"
    if v >= 30:
        return "Pessimism"
    return "Panic"


def main():
    symbols = get_symbols()
    # DMA warm-up ke liye extra ~1.5 saal pehle ka data
    start = (datetime.fromisoformat(DISPLAY_FROM) - timedelta(days=550)).strftime("%Y-%m-%d")
    prices = download_prices(symbols, start)
    print(f"Total stocks with data: {prices.shape[1]}")
    if prices.shape[1] < MIN_STOCKS:
        sys.exit("Bahut kam stocks ka data aaya, purani data.json same rakhi.")

    prices = prices.sort_index()
    out = {"updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
           "stocks": int(prices.shape[1]), "dates": [], "series": {}}

    table = pd.DataFrame({f"dma{p}": bull_percent(prices, p) for p in DMA_PERIODS})
    table = table.loc[DISPLAY_FROM:].dropna()
    out["dates"] = [d.strftime("%Y-%m-%d") for d in table.index]
    for col in table.columns:
        out["series"][col] = [round(float(v), 1) for v in table[col]]
        last = float(table[col].iloc[-1])
        print(f"{col}: {last:.1f}% ({zone(last)}) on {table.index[-1].date()}")

    with open("data.json", "w") as f:
        json.dump(out, f)
    print("data.json ban gayi.")


if __name__ == "__main__":
    main()
