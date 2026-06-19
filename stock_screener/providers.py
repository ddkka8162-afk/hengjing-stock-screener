from __future__ import annotations

import hashlib
import math
from abc import ABC, abstractmethod
from datetime import date, datetime, timedelta

from .models import Stock


class MarketDataProvider(ABC):
    """Implement this interface for Tushare or a licensed quote vendor."""

    @abstractmethod
    def load_snapshot(self) -> list[Stock]:
        raise NotImplementedError

    @abstractmethod
    def load_index_overview(self) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    def load_concepts(self) -> list[tuple[str, str]]:
        """Return (stock_code, concept_name) memberships."""
        raise NotImplementedError


class DemoMarketDataProvider(MarketDataProvider):
    """Deterministic demonstration data; never present it as live market data."""

    STOCKS = [
        ("600519", "贵州茅台", "食品饮料"), ("000858", "五粮液", "食品饮料"),
        ("600036", "招商银行", "银行"), ("601398", "工商银行", "银行"),
        ("601318", "中国平安", "非银金融"), ("600030", "中信证券", "非银金融"),
        ("000333", "美的集团", "家用电器"), ("000651", "格力电器", "家用电器"),
        ("002415", "海康威视", "电子"), ("000725", "京东方A", "电子"),
        ("300750", "宁德时代", "电力设备"), ("601012", "隆基绿能", "电力设备"),
        ("002594", "比亚迪", "汽车"), ("600104", "上汽集团", "汽车"),
        ("600276", "恒瑞医药", "医药生物"), ("300760", "迈瑞医疗", "医药生物"),
        ("600887", "伊利股份", "食品饮料"), ("603288", "海天味业", "食品饮料"),
        ("600900", "长江电力", "公用事业"), ("601985", "中国核电", "公用事业"),
        ("601088", "中国神华", "煤炭"), ("600938", "中国海油", "石油石化"),
        ("600309", "万华化学", "基础化工"), ("601899", "紫金矿业", "有色金属"),
        ("600585", "海螺水泥", "建筑材料"), ("601668", "中国建筑", "建筑装饰"),
        ("000002", "万科A", "房地产"), ("600048", "保利发展", "房地产"),
        ("002230", "科大讯飞", "计算机"), ("600570", "恒生电子", "计算机"),
        ("603259", "药明康德", "医药生物"), ("300059", "东方财富", "非银金融"),
        ("600406", "国电南瑞", "电力设备"), ("002475", "立讯精密", "电子"),
        ("601919", "中远海控", "交通运输"), ("600050", "中国联通", "通信"),
        ("601728", "中国电信", "通信"), ("601857", "中国石油", "石油石化"),
        ("600690", "海尔智家", "家用电器"), ("000568", "泸州老窖", "食品饮料"),
    ]

    CONCEPTS = {
        "人工智能": ["002230", "600570", "002415", "300059"],
        "算力产业链": ["002230", "600050", "601728", "002415"],
        "中特估": ["601398", "601668", "601088", "601919", "601857", "600050"],
        "高股息": ["600900", "601088", "600938", "601398", "601985", "601857"],
        "新能源汽车": ["300750", "002594", "601012", "600104"],
        "机器人": ["000333", "002475", "300760", "002230"],
        "半导体": ["000725", "002415", "002475", "600570"],
        "创新药": ["600276", "603259", "300760"],
        "消费复苏": ["600519", "000858", "600887", "603288", "000568"],
        "一带一路": ["601668", "601919", "601899", "600585"],
        "国企改革": ["600900", "601985", "601857", "601728", "600104"],
        "数字经济": ["002230", "600570", "300059", "600050", "601728"],
    }

    def load_concepts(self) -> list[tuple[str, str]]:
        return [(code, concept) for concept, codes in self.CONCEPTS.items() for code in codes]

    @staticmethod
    def value(code: str, key: str, low: float, high: float) -> float:
        digest = hashlib.sha256(f"{date.today()}:{code}:{key}".encode()).digest()
        ratio = int.from_bytes(digest[:8], "big") / (2**64 - 1)
        return round(low + ratio * (high - low), 2)

    def load_snapshot(self) -> list[Stock]:
        result = []
        for code, name, industry in self.STOCKS:
            v = lambda key, low, high: self.value(code, key, low, high)
            roe = v("roe", -4, 32)
            pe = v("pe", 4, 65)
            debt = v("debt", 18, 88)
            growth = v("growth", -30, 55)
            profit = v("profit", -45, 70)
            momentum = v("m120", -35, 65)
            volatility = v("vol", 8, 42)
            cashflow = v("cash", 0.25, 1.8)
            turnover = v("turnover", .15, 12)
            volume_ratio = v("vr", .4, 3.5)
            change = v("change", -7.5, 8.5)
            momentum_20d = v("m20", -18, 28)
            quality = max(0, min(100, 50 + roe * 1.3 + (cashflow - 1) * 22 - max(0, debt - 60) * .7))
            valuation = max(0, min(100, 110 - pe * 1.5))
            momentum_score = max(0, min(100, 50 + momentum))
            low_vol = max(0, min(100, 110 - volatility * 2.2))
            score = round(quality * .4 + valuation * .3 + momentum_score * .2 + low_vol * .1, 1)
            heat_score = round(
                min(100, turnover * 8) * .30 + min(100, volume_ratio * 30) * .25
                + max(0, min(100, 50 + momentum_20d * 2)) * .30
                + max(0, min(100, 50 + change * 6)) * .15,
                1,
            )
            result.append(Stock(
                code, name, industry, v("price", 4, 860), change,
                v("cap", 80, 21500), turnover, volume_ratio, pe,
                v("pb", .45, 12), roe, growth, profit, debt, v("m20", -18, 28), momentum,
                volatility, cashflow, heat_score, score,
            ))
        return result

    def load_index_overview(self) -> list[dict]:
        """Produce a stable, moving intraday-like series for UI development."""
        now = datetime.now().astimezone()
        definitions = [
            ("000001.SH", "上证指数", 3318.42, 22),
            ("399001.SZ", "深证成指", 10476.18, 105),
            ("399006.SZ", "创业板指", 2176.35, 31),
        ]
        result = []
        for code, name, previous_close, amplitude in definitions:
            seed = int.from_bytes(hashlib.sha256(f"{date.today()}:{code}".encode()).digest()[:4], "big")
            points = []
            for offset in range(60, -1, -1):
                point_time = now - timedelta(minutes=offset)
                slot = int(point_time.timestamp() // 60)
                drift = ((seed % 17) - 8) * 0.018 * (60 - offset)
                wave = math.sin((slot + seed % 23) / 5.4) * amplitude * .34
                wave += math.sin((slot + seed % 11) / 13.1) * amplitude * .18
                micro = ((int.from_bytes(hashlib.sha256(f"{code}:{slot}".encode()).digest()[:2], "big") / 65535) - .5) * amplitude * .18
                value = round(previous_close + drift + wave + micro, 2)
                points.append({"time": point_time.strftime("%H:%M"), "value": value})
            # Add subtle movement within the current minute so five-second polling is visible.
            points[-1]["value"] = round(points[-1]["value"] + math.sin(now.second / 9) * amplitude * .025, 2)
            current = points[-1]["value"]
            change = round(current - previous_close, 2)
            result.append({
                "code": code, "name": name, "value": current, "previous_close": previous_close,
                "change": change, "change_pct": round(change / previous_close * 100, 2), "points": points,
            })
        return result

