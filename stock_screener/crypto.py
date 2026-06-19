from __future__ import annotations

import hashlib
import json
import math
import threading
import time
from datetime import datetime
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class CryptoMarketProvider:
    """CoinGecko market adapter with a short cache and explicit demo fallback."""

    COINS = {
        "bitcoin": ("BTC", "Bitcoin", 68420.0),
        "ethereum": ("ETH", "Ethereum", 3580.0),
        "tether": ("USDT", "Tether", 1.0),
        "binancecoin": ("BNB", "BNB", 612.0),
        "solana": ("SOL", "Solana", 148.0),
        "usd-coin": ("USDC", "USDC", 1.0),
        "ripple": ("XRP", "XRP", 0.53),
        "dogecoin": ("DOGE", "Dogecoin", 0.14),
        "cardano": ("ADA", "Cardano", 0.45),
        "avalanche-2": ("AVAX", "Avalanche", 36.0),
        "tron": ("TRX", "TRON", 0.12),
        "chainlink": ("LINK", "Chainlink", 15.2),
    }
    INTERVALS = {"5m", "15m", "1h", "4h", "1d", "1w"}

    def __init__(self, ttl_seconds: int = 15) -> None:
        self.ttl_seconds = ttl_seconds
        self._cache: dict | None = None
        self._cached_at = 0.0
        self._lock = threading.Lock()
        self._history_cache: dict[tuple[str, str], tuple[float, dict]] = {}

    def get_markets(self) -> dict:
        with self._lock:
            if self._cache and time.time() - self._cached_at < self.ttl_seconds:
                return self._cache
            try:
                payload = self._fetch_live()
            except Exception as exc:
                payload = self._demo_payload(str(exc))
            self._cache = payload
            self._cached_at = time.time()
            return payload

    def _fetch_live(self) -> dict:
        params = urlencode({
            "vs_currency": "usd",
            "ids": ",".join(self.COINS),
            "order": "market_cap_desc",
            "sparkline": "true",
            "price_change_percentage": "1h,24h,7d",
        })
        request = Request(
            f"https://api.coingecko.com/api/v3/coins/markets?{params}",
            headers={"Accept": "application/json", "User-Agent": "Hengjing-Market-Terminal/0.1"},
        )
        with urlopen(request, timeout=6) as response:
            rows = json.loads(response.read().decode("utf-8"))
        if not isinstance(rows, list) or not rows:
            raise RuntimeError("行情服务返回空数据")
        items = []
        for row in rows:
            items.append({
                "id": row["id"], "symbol": row["symbol"].upper(), "name": row["name"],
                "price": row.get("current_price"), "market_cap": row.get("market_cap"),
                "market_cap_rank": row.get("market_cap_rank"), "volume_24h": row.get("total_volume"),
                "high_24h": row.get("high_24h"), "low_24h": row.get("low_24h"),
                "change_1h": row.get("price_change_percentage_1h_in_currency"),
                "change_24h": row.get("price_change_percentage_24h_in_currency"),
                "change_7d": row.get("price_change_percentage_7d_in_currency"),
                "sparkline": (row.get("sparkline_in_7d") or {}).get("price", []),
            })
        return self._with_summary(items, "live", "CoinGecko")

    def get_history(self, coin_id: str, interval: str) -> dict:
        if coin_id not in self.COINS or interval not in self.INTERVALS:
            raise ValueError("不支持的币种或周期")
        key = (coin_id, interval)
        with self._lock:
            cached = self._history_cache.get(key)
            if cached and time.time() - cached[0] < self.ttl_seconds:
                return cached[1]
        try:
            payload = self._fetch_binance_history(coin_id, interval)
        except Exception as exc:
            payload = self._demo_history(coin_id, interval, str(exc))
        with self._lock:
            self._history_cache[key] = (time.time(), payload)
        return payload

    def _fetch_binance_history(self, coin_id: str, interval: str) -> dict:
        symbol = self.COINS[coin_id][0]
        inverse = coin_id == "tether"
        pair = "USDCUSDT" if coin_id in {"tether", "usd-coin"} else f"{symbol}USDT"
        params = urlencode({"symbol": pair, "interval": interval, "limit": 120})
        request = Request(
            f"https://api.binance.com/api/v3/klines?{params}",
            headers={"Accept": "application/json", "User-Agent": "Hengjing-Market-Terminal/0.1"},
        )
        with urlopen(request, timeout=6) as response:
            rows = json.loads(response.read().decode("utf-8"))
        if not isinstance(rows, list) or not rows:
            raise RuntimeError("分钟行情返回空数据")
        points = []
        for row in rows:
            close = float(row[4])
            value = 1 / close if inverse and close else close
            points.append({"time": int(row[0]), "value": round(value, 10)})
        return {
            "coin_id": coin_id, "interval": interval, "points": points,
            "data_mode": "live", "source": "Binance", "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }

    def _demo_history(self, coin_id: str, interval: str, reason: str) -> dict:
        unit_seconds = {"5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400, "1w": 604800}[interval]
        base = self.COINS[coin_id][2]
        slot = int(time.time() // unit_seconds)
        seed = int.from_bytes(hashlib.sha256(f"{coin_id}:{interval}".encode()).digest()[:4], "big")
        points = []
        for offset in range(119, -1, -1):
            index = slot - offset
            wave = math.sin((index + seed % 31) / 8) * .025 + math.sin((index + seed % 17) / 21) * .012
            drift = ((seed % 13) - 6) * offset * .000015
            points.append({"time": index * unit_seconds * 1000, "value": round(base * (1 + wave + drift), 10)})
        return {
            "coin_id": coin_id, "interval": interval, "points": points, "data_mode": "demo",
            "source": f"分钟实时源不可用：{reason[:100]}", "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }

    def _demo_payload(self, reason: str) -> dict:
        now_slot = int(time.time() // 15)
        items = []
        for rank, (coin_id, (symbol, name, base)) in enumerate(self.COINS.items(), 1):
            seed = int.from_bytes(hashlib.sha256(f"{coin_id}:{now_slot // 240}".encode()).digest()[:4], "big")
            change_24h = math.sin((now_slot + seed) / 31) * (0.35 if base == 1 else 6.2)
            change_1h = math.sin((now_slot + seed) / 11) * (0.06 if base == 1 else 1.4)
            change_7d = math.sin((now_slot + seed) / 67) * (0.5 if base == 1 else 14)
            price = base * (1 + change_24h / 100)
            sparkline = [
                round(base * (1 + (math.sin((i + seed % 19) / 8) * 2.2 + change_7d * i / 167) / 100), 8)
                for i in range(168)
            ]
            cap = price * (19_700_000 if symbol == "BTC" else max(40_000_000, 550_000_000 / rank))
            items.append({
                "id": coin_id, "symbol": symbol, "name": name, "price": round(price, 8),
                "market_cap": round(cap), "market_cap_rank": rank, "volume_24h": round(cap * (.025 + rank * .003)),
                "high_24h": round(price * 1.018, 8), "low_24h": round(price * .982, 8),
                "change_1h": round(change_1h, 2), "change_24h": round(change_24h, 2),
                "change_7d": round(change_7d, 2), "sparkline": sparkline,
            })
        return self._with_summary(items, "demo", f"实时源不可用：{reason[:120]}")

    @staticmethod
    def _with_summary(items: list[dict], mode: str, source: str) -> dict:
        return {
            "items": items,
            "summary": {
                "market_cap": sum(item.get("market_cap") or 0 for item in items),
                "volume_24h": sum(item.get("volume_24h") or 0 for item in items),
                "advancers": sum(1 for item in items if (item.get("change_24h") or 0) >= 0),
                "decliners": sum(1 for item in items if (item.get("change_24h") or 0) < 0),
            },
            "data_mode": mode, "source": source,
            "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }

