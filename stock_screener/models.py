from dataclasses import dataclass


@dataclass(slots=True)
class Stock:
    code: str
    name: str
    industry: str
    price: float
    change_pct: float
    market_cap: float
    turnover_rate: float
    volume_ratio: float
    pe_ttm: float
    pb: float
    roe_ttm: float
    revenue_growth: float
    profit_growth: float
    debt_ratio: float
    momentum_20d: float
    momentum_120d: float
    volatility_20d: float
    cashflow_quality: float
    heat_score: float
    score: float
    is_st: int = 0
    is_suspended: int = 0

