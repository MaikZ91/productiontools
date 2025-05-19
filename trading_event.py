#!/usr/bin/env python3
"""
pareto_dividend_bot.py – BTC‑Monthly‑Payout Grid (v2‑Pareto)
===========================================================
Optimierungen (80 / 20‑Prinzip)
------------------------------
* **Edge­‑Engine** bleibt (ATR‑Grid + EMA‑Breakout).
* **Nur 2 Code‑Tweaks** bringen den größten Hebel:
  1. **Dynamische Positions­größe** – 1 % des aktuellen Equity, gedeckelt auf 15 € (oder `.env`).
  2. **ATR-abhängige Layerzahl** – Ziel: max. 30 % des Portfolios gleichzeitig im Grid.
* Sonstiger Flow (Payout, Draw‑down‑Guard usw.) unverändert.

Neue/angepasste .env‑Keys
-------------------------
```ini
RISK_EUR_MAX = 15      # oberes Hard‑Cap pro Layer
RISK_PCT_EQUITY = 1    # %‑Einsatz vom Equity pro Layer
MAX_PORTFOLIO_GRID_PCT = 30   # gesamte Grid‑Exposure in % des Kontos
```

Short‑Form‑Nutzen
-----------------
* **Kapital wächst ⇒ Einsatz wächst** → Dividende skaliert natürlich mit.
* **Bei hoher Vola weniger Lagen** → Gebühren & Draw‑down sinken.  
  (schont also die 20 % Risiko‑Seite.)

Restliche Nutzung wie bisher.
"""
from __future__ import annotations
import asyncio, os, json, signal, logging, datetime
from decimal import Decimal, getcontext
from pathlib import Path
from dataclasses import dataclass, asdict

import pandas as pd
from dotenv import load_dotenv
from ta.volatility import AverageTrueRange
from ta.trend import EMAIndicator
from alpaca.data.live.crypto import CryptoDataStream
from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest, StopLossRequest

load_dotenv()
# === Config =========================================================================
ASSET = "BTC/USD"
ATR_MULT = Decimal(os.getenv("ATR_MULT", "0.6"))
RISK_EUR_MAX = Decimal(os.getenv("RISK_EUR_MAX", "15"))
RISK_PCT_EQUITY = Decimal(os.getenv("RISK_PCT_EQUITY", "1"))  # 1 % Equity
MAX_PORTFOLIO_GRID_PCT = Decimal(os.getenv("MAX_PORTFOLIO_GRID_PCT", "30"))
MAX_DD_EUR = Decimal(os.getenv("MAX_DD_EUR", "40"))
EMA_FAST, EMA_SLOW = 9, 21
TP_MULT = Decimal(os.getenv("TP_MULT", "3.0"))
TRAIL_MULT = Decimal(os.getenv("TRAIL_MULT", "0.8"))
PAYOUT_DAY = int(os.getenv("PAYOUT_DAY", "1"))
PAYOUT_MIN_EUR = Decimal(os.getenv("PAYOUT_MIN_EUR", "5"))
PAYOUT_PCT = Decimal(os.getenv("PAYOUT_PCT", "50"))
STATE_FILE = Path("state.json")
KEY, SECRET = os.getenv("ALPACA_KEY"), os.getenv("ALPACA_SECRET")
if not KEY or not SECRET:
    raise RuntimeError("ALPACA_KEY / SECRET fehlen")

getcontext().prec = 12
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("dividend_bot")

# === State ==========================================================================
@dataclass
class BotState:
    baseline: Decimal | None = None
    layers: int = 0
    pos_qty: Decimal = Decimal(0)
    cashflow: Decimal = Decimal(0)
    last_payout_ts: float = 0.0

    def save(self):
        STATE_FILE.write_text(json.dumps(asdict(self), default=str))

    @classmethod
    def load(cls):
        if STATE_FILE.exists():
            d = json.loads(STATE_FILE.read_text())
            return cls(baseline=Decimal(d['baseline']) if d['baseline'] else None,
                       layers=d['layers'], pos_qty=Decimal(d['pos_qty']),
                       cashflow=Decimal(d['cashflow']), last_payout_ts=d.get('last_payout_ts',0))
        return cls()

# === Bot =============================================================================
class DividendGridBot:
    def __init__(self):
        self.state = BotState.load()
        self.tc = TradingClient(KEY, SECRET, paper=True)
        self.ws = CryptoDataStream(KEY, SECRET)
        self.hist = CryptoHistoricalDataClient(KEY, SECRET)
        self.df = self._bootstrap_history()

    # bootstrap history
    def _bootstrap_history(self):
        req = CryptoBarsRequest(symbol_or_symbols=ASSET.replace('/',''), timeframe=TimeFrame.Minute, limit=300)
        bars = self.hist.get_crypto_bars(req).df
        bars = bars[bars['symbol']==ASSET.replace('/','')]
        df = bars[['open','high','low','close']].copy(); df.index = pd.to_datetime(bars.index)
        return df

    # update indicators
    def _update_indicators(self, price: float):
        self.df.loc[pd.Timestamp.utcnow()] = dict(open=price,high=price,low=price,close=price)
        if len(self.df)>500: self.df=self.df.iloc[-500:]
        self.df['atr'] = AverageTrueRange(self.df['high'],self.df['low'],self.df['close'],window=14).average_true_range()
        self.df['ema_f'] = EMAIndicator(self.df['close'],window=EMA_FAST).ema_indicator()
        self.df['ema_s'] = EMAIndicator(self.df['close'],window=EMA_SLOW).ema_indicator()

    # broker helpers
    async def _order(self, side: OrderSide, qty: Decimal, tp: Decimal|None=None, sl: Decimal|None=None):
        try:
            req = MarketOrderRequest(symbol=ASSET, qty=float(qty), side=side, time_in_force=TimeInForce.IOC)
            o = self.tc.submit_order(req)
            log.info("%s %.5f (id=%s)", side.name, qty, o.id)
            if tp or sl:
                sl_req = StopLossRequest(stop_price=float(sl) if sl else None, limit_price=float(tp) if tp else None)
                self.tc.replace_order(o.id, stop_loss=sl_req)
        except Exception as e:
            log.error("Order error: %s", e)

    # risk utils
    def _dynamic_qty(self, price: Decimal) -> Decimal:
        equity = Decimal(self.tc.get_account().equity)
        risk_eur = min(RISK_EUR_MAX, equity * (RISK_PCT_EQUITY/Decimal(100)))
        return (risk_eur / price).quantize(Decimal('0.00001'))

    def _max_layers_from_atr(self, step: Decimal, price: Decimal) -> int:
        step_pct = (step/price)*Decimal(100)
        return max(1, int(MAX_PORTFOLIO_GRID_PCT/step_pct))

    # payout
    async def _maybe_payout(self, price: Decimal):
        now = datetime.datetime.utcnow()
        if now.day < PAYOUT_DAY: return
        if self.state.last_payout_ts:
            last = datetime.datetime.utcfromtimestamp(self.state.last_payout_ts)
            if last.year==now.year and last.month==now.month: return
        if self.state.cashflow < PAYOUT_MIN_EUR: return
        payout = (self.state.cashflow*(PAYOUT_PCT/Decimal(100))).quantize(Decimal('0.01'))
        qty = (payout/price).quantize(Decimal('0.00001'))
        if qty>0 and qty<=self.state.pos_qty:
            await self._order(OrderSide.SELL, qty)
            self.state.pos_qty -= qty
            self.state.cashflow -= payout
            self.state.last_payout_ts = now.timestamp()
            log.info("Payout %.2f € (%.5f BTC)", payout, qty)
            self.state.save()

    # main tick
    async def on_price(self, price: Decimal):
        await self._maybe_payout(price)
        self._update_indicators(float(price))
        atr = Decimal(str(self.df['atr'].iloc[-1]))
        step = (atr*ATR_MULT).quantize(Decimal('0.01'))
        if self.state.baseline is None:
            self.state.baseline = price; self.state.save(); return
        # dd guard
        if (self.state.pos_qty*price + self.state.cashflow) <= -MAX_DD_EUR:
            await self._order(OrderSide.SELL, self.state.pos_qty)
            self.state = BotState(baseline=price)
            self.state.save(); return
        dist = price - self.state.baseline
        qty = self._dynamic_qty(price)
        max_layers = self._max_layers_from_atr(step, price)

        # grid logic
        if dist<=-step and self.state.layers<max_layers:
            await self._order(OrderSide.BUY, qty)
            self.state.layers+=1; self.state.pos_qty+=qty; self.state.cashflow-=qty*price; self.state.baseline-=step
        elif dist>=step and self.state.layers>0:
            await self._order(OrderSide.SELL, qty)
            self.state.layers-=1; self.state.pos_qty-=qty; self.state.cashflow+=qty*price; self.state.baseline=price
        # breakout
        if self.df['ema_f'].iloc[-1]>self.df['ema_s'].iloc[-1] and dist>step:
            await self._order(OrderSide.BUY, qty, tp=price+atr*TP_MULT, sl=price-atr*TRAIL_MULT)
        self.state.save()

    # runner
    async def run(self):
        self.ws.subscribe_quotes(self._handle_quote, ASSET.replace('/',''))
        loop = asyncio.get_running_loop()
        for s in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(s, lambda: asyncio.create_task(self._stop()))
        log.info("▶ Dividend‑Grid v2 gestartet")
        await self.ws._run_forever()

    async def _handle_quote(self, quote):
        price = Decimal(str(quote.ask_price or quote.bid_price))
        await self.on_price(price)

    async def _stop(self):
        await self.ws.stop(); asyncio.get_running_loop().stop()

if __name__=='__main__':
    asyncio.run(DividendGridBot().run())
