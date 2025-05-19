import os
import time
import logging
import requests
import yfinance as yf

ALPACA_KEY = os.getenv("ALPACA_KEY")
ALPACA_SECRET = os.getenv("ALPACA_SECRET")
ASSET = "BTC/USD"
ORDERS_URL = "https://api.alpaca.markets/v2/orders"

REFRESH_SEC = 10
POSITION_BTC = 0
SELL_EUR = 0.02
BUY_EUR = -1000

_last_price_ts = 0.0
_cached_price = None
start_price = None
start_value = None
cashflow = 0.0
position_btc = POSITION_BTC

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

def get_price():
    global _last_price_ts, _cached_price
    # eigener Cache
    if time.time() - _last_price_ts < REFRESH_SEC and _cached_price is not None:
        return _cached_price

    try:
        p = yf.Ticker("BTC-USD").fast_info["last_price"]
        _cached_price, _last_price_ts = p, time.time()
        logging.info("BTC/USD price: %.2f", p)
        return p

    except Exception as e:
        if "Too Many Requests" in str(e):
            logging.warning("Yahoo 429 – warte 60 s")
            time.sleep(60)                      # Back-off
        else:
            logging.warning("%s", e)
        return None

def get_btc_position():
    url = "https://api.alpaca.markets/v2/positions/BTC/USD"
    headers = {
        "APCA-API-KEY-ID": ALPACA_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET,
    }
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            pos = r.json()
            qty = float(pos["qty"])
            logging.info("Aktuelle BTC-Position: %.6f", qty)
            return qty
        elif r.status_code == 404:
            logging.info("Keine BTC-Position gefunden.")
            return 0.0
        else:
            logging.error("Fehler beim Abrufen der Position: %s", r.text)
            return 0.0
    except Exception as exc:
        logging.error("Fehler bei Positionsermittlung: %s", exc)
        return 0.0

def alpaca_order(side, qty):
    payload = {"symbol": ASSET, "qty": round(qty, 6), "side": side, "type": "market", "time_in_force": "ioc"}
    headers = {"APCA-API-KEY-ID": ALPACA_KEY, "APCA-API-SECRET-KEY": ALPACA_SECRET, "Content-Type": "application/json"}
    try:
        r = requests.post(ORDERS_URL, headers=headers, json=payload, timeout=10)
        if r.status_code == 200:
            logging.info("ORDER %s %.6f", side.upper(), qty)
        else:
            logging.error("%s: %s", r.status_code, r.text)
    except Exception as exc:
        logging.error("%s", exc)

def run():
    global start_price, start_value, position_btc, cashflow
    while True:
        price = get_price()
        if price is None:
            time.sleep(REFRESH_SEC)
            continue
        if start_price is None:
            start_price = price
            start_value = price * position_btc
            logging.info("Init %.2f", price)
            time.sleep(REFRESH_SEC)
            continue
        value = price * position_btc
        harvest = value - start_value
        logging.info("Harvest %.4f", harvest)
        if harvest >= SELL_EUR:
            delta = harvest / price
            position_btc -= delta
            cashflow += harvest
            alpaca_order("sell", delta)
        elif harvest <= BUY_EUR:
            delta = -harvest / price
            position_btc += delta
            cashflow += harvest
            alpaca_order("buy", delta)
        logging.debug("P=%.2f V=%.2f H=%.2f CF=%.2f", price, value, harvest, cashflow)
        time.sleep(REFRESH_SEC)

if __name__ == "__main__":
    if position_btc == 0:
        position_btc = get_btc_position()
        logging.info("Bestand %.2f", position_btc)

    if not ALPACA_KEY or not ALPACA_SECRET:
        raise RuntimeError("Missing Alpaca keys")
    run()
