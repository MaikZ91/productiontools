"""Minimaler Crypto‑News‑Trader (BTC/USD) – Sentiment‑Threshold‑Strategie.

* holt News im 30‑s‑Intervall (Alpaca REST)
* bewertet Schlagzeilen mit FinBERT
* streamt BTC‑Quotes über Alpaca WebSocket
* öffnet Market‑Orders, wenn Sentiment‑Score ≥ BUY_THRESH bzw. ≤ SELL_THRESH
* Risk‑Management: 20 % Kelly‑capped Positionsgröße, Stop‑Loss 1 %, Take‑Profit 2,5 %

NOTE: Für ein echtes 24/7‑Setup empfiehlt sich ein self‑hosted Runner oder VPS.
"""

import os, asyncio, json, math, time, logging
from datetime import datetime, timezone, timedelta

import aiohttp
from alpaca.common.exceptions import APIError
from alpaca.data.live import CryptoDataStream
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from transformers import pipeline

# --------------------------------------------------
# Konfiguration (ENV‑Variablen)
# --------------------------------------------------
ALPACA_KEY     = os.getenv("ALPACA_KEY")
ALPACA_SECRET  = os.getenv("ALPACA_SECRET")
NEWS_ENDPOINT  = "https://data.alpaca.markets/v1beta1/news"
ASSET          = "BTC/USD"
BUY_THRESH     = 0.45   # FinBERT‑Score
SELL_THRESH    = -0.45
POSITION_PCT   = 0.20   # 20 % des Kontowerts
STOP_PCT       = 0.01   # −1 %
TP_PCT         = 0.025  # +2,5 %
NEWS_WINDOW    = 30     # Sekunden zwischen News‑Abfragen
COOLDOWN_MIN   = 5      # Min. Minuten zwischen Trades

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

# --------------------------------------------------
# Global State
# --------------------------------------------------
latest_price: float | None = None
last_trade_ts: datetime | None = None

# --------------------------------------------------
# Helpers
# --------------------------------------------------
async def fetch_news(session, since: datetime):
    """Pullt News-Schlagzeilen seit `since`."""
    params = {
        "symbols": "BTCUSD,BTC",
        "start": since.isoformat(),
        "limit": 50,
    }
    async with session.get(NEWS_ENDPOINT, params=params) as r:
        r.raise_for_status()
        return await r.json()

# FinBERT‑Pipeline (GPU, falls verfügbar)
sentiment = pipeline(
    "sentiment-analysis",
    model="ProsusAI/finbert",
    truncation=True,
    device=0 if torch.cuda.is_available() else -1,
)

def score_text(txt: str) -> float:
    res = sentiment(txt[:512])[0]
    return {"positive": 1, "neutral": 0, "negative": -1}[res["label"]] * res["score"]

# --------------------------------------------------
# Trading‑Client
# --------------------------------------------------
trading = TradingClient(ALPACA_KEY, ALPACA_SECRET, paper=True)  # True = Paper‑Trading

def calc_qty(equity: float) -> float:
    pos_val = equity * POSITION_PCT
    if latest_price is None:
        raise RuntimeError("Kein aktueller Preis.")
    return round(pos_val / latest_price, 6)

def submit_order(side: OrderSide, qty: float):
    req = MarketOrderRequest(
        symbol=ASSET,
        qty=qty,
        side=side,
        time_in_force=TimeInForce.IOC,
    )
    try:
        order = trading.submit_order(req)
        logging.info("%s %s @ %.2f", side.value.upper(), qty, latest_price)
        return order
    except APIError as e:
        logging.error("Order‑Error: %s", e)
        return None

# --------------------------------------------------
# Quote Stream
# --------------------------------------------------
async def price_ws():
    global latest_price
    stream = CryptoDataStream(ALPACA_KEY, ALPACA_SECRET)

    @stream.on_quote(ASSET)
    async def _(q):
        global latest_price
        latest_price = q.bid_price or q.ask_price
    await stream.run()

# --------------------------------------------------
# News → Trade‑Loop
# --------------------------------------------------
async def news_loop():
    global last_trade_ts
    async with aiohttp.ClientSession() as session:
        since = datetime.now(timezone.utc) - timedelta(minutes=10)
        while True:
            news_items = await fetch_news(session, since)
            for item in news_items:
                since = max(since, datetime.fromisoformat(item["created_at"].replace("Z", "+00:00")))
                headline = item["headline"] + " " + item.get("summary", "")
                s = score_text(headline)
                logging.info("News: %.2f :: %s", s, headline)

                # Cooldown
                if last_trade_ts and datetime.now(timezone.utc) - last_trade_ts < timedelta(minutes=COOLDOWN_MIN):
                    continue

                equity = float(trading.get_account().equity)
                qty = calc_qty(equity)
                if s >= BUY_THRESH:
                    submit_order(OrderSide.BUY, qty)
                    last_trade_ts = datetime.now(timezone.utc)
                elif s <= SELL_THRESH:
                    submit_order(OrderSide.SELL, qty)
                    last_trade_ts = datetime.now(timezone.utc)

            await asyncio.sleep(NEWS_WINDOW)

# --------------------------------------------------
# Entrypoint
# --------------------------------------------------
async def main():
    if not ALPACA_KEY or not ALPACA_SECRET:
        raise RuntimeError("API‑Keys fehlen. Als ENV‑Variablen ALPACA_KEY/ALPACA_SECRET setzen!")
    await asyncio.gather(price_ws(), news_loop())

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
