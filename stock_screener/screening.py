from __future__ import annotations

from dataclasses import dataclass


ALLOWED_SORTS = {
    "score", "market_cap", "price", "change_pct", "turnover_rate", "volume_ratio",
    "pe_ttm", "pb", "roe_ttm", "revenue_growth", "profit_growth", "debt_ratio",
    "momentum_20d", "momentum_120d", "volatility_20d", "cashflow_quality", "heat_score",
}


@dataclass(slots=True)
class ScreenQuery:
    keyword: str = ""
    industries: tuple[str, ...] = ()
    min_market_cap: float | None = None
    max_market_cap: float | None = None
    min_pe: float | None = None
    max_pe: float | None = None
    min_roe: float | None = None
    min_revenue_growth: float | None = None
    min_profit_growth: float | None = None
    max_debt_ratio: float | None = None
    min_turnover_rate: float | None = None
    min_score: float | None = None
    exclude_st: bool = True
    exclude_suspended: bool = True
    sort: str = "score"
    order: str = "desc"
    page: int = 1
    page_size: int = 20


def parse_screen_query(raw: dict[str, list[str]], max_page_size: int = 100) -> ScreenQuery:
    def first(name: str, default: str = "") -> str:
        return raw.get(name, [default])[0].strip()

    def number(name: str) -> float | None:
        value = first(name)
        if not value:
            return None
        try:
            return float(value)
        except ValueError as exc:
            raise ValueError(f"{name} 必须是数字") from exc

    sort = first("sort", "score")
    if sort not in ALLOWED_SORTS:
        raise ValueError("不支持的排序字段")
    order = first("order", "desc").lower()
    if order not in {"asc", "desc"}:
        raise ValueError("排序方向必须是 asc 或 desc")
    try:
        page = max(1, int(first("page", "1")))
        page_size = min(max_page_size, max(1, int(first("page_size", "20"))))
    except ValueError as exc:
        raise ValueError("分页参数必须是整数") from exc

    return ScreenQuery(
        keyword=first("keyword"),
        industries=tuple(x for x in first("industries").split(",") if x),
        min_market_cap=number("min_market_cap"), max_market_cap=number("max_market_cap"),
        min_pe=number("min_pe"), max_pe=number("max_pe"), min_roe=number("min_roe"),
        min_revenue_growth=number("min_revenue_growth"), min_profit_growth=number("min_profit_growth"),
        max_debt_ratio=number("max_debt_ratio"), min_turnover_rate=number("min_turnover_rate"),
        min_score=number("min_score"), exclude_st=first("exclude_st", "true") != "false",
        exclude_suspended=first("exclude_suspended", "true") != "false", sort=sort, order=order,
        page=page, page_size=page_size,
    )

