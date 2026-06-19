from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import fields
from datetime import datetime
from pathlib import Path

from .models import Stock
from .screening import ScreenQuery


class StockRepository:
    def __init__(self, path: Path) -> None:
        self.path = path

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        columns = """
            code TEXT PRIMARY KEY, name TEXT NOT NULL, industry TEXT NOT NULL,
            price REAL, change_pct REAL, market_cap REAL, turnover_rate REAL, volume_ratio REAL,
            pe_ttm REAL, pb REAL, roe_ttm REAL, revenue_growth REAL, profit_growth REAL,
            debt_ratio REAL, momentum_20d REAL, momentum_120d REAL, volatility_20d REAL,
            cashflow_quality REAL, heat_score REAL, score REAL, is_st INTEGER, is_suspended INTEGER
        """
        with self.connect() as db:
            db.execute(f"CREATE TABLE IF NOT EXISTS stocks ({columns})")
            existing = {row[1] for row in db.execute("PRAGMA table_info(stocks)")}
            if "heat_score" not in existing:
                db.execute("ALTER TABLE stocks ADD COLUMN heat_score REAL DEFAULT 0")
            db.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS stock_concepts (code TEXT NOT NULL, concept TEXT NOT NULL, PRIMARY KEY(code, concept))")
            db.execute("CREATE INDEX IF NOT EXISTS idx_concepts_name ON stock_concepts(concept)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_stocks_score ON stocks(score DESC)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_stocks_heat ON stocks(heat_score DESC)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_stocks_industry ON stocks(industry)")

    def count(self) -> int:
        with self.connect() as db:
            return int(db.execute("SELECT COUNT(*) FROM stocks").fetchone()[0])

    def has_heat_scores(self) -> bool:
        with self.connect() as db:
            return bool(db.execute("SELECT 1 FROM stocks WHERE heat_score > 0 LIMIT 1").fetchone())

    def concept_count(self) -> int:
        with self.connect() as db:
            return int(db.execute("SELECT COUNT(*) FROM stock_concepts").fetchone()[0])

    def replace_concepts(self, memberships: list[tuple[str, str]]) -> None:
        with self.connect() as db:
            db.execute("DELETE FROM stock_concepts")
            db.executemany("INSERT INTO stock_concepts(code, concept) VALUES (?, ?)", memberships)

    def replace_all(self, stocks: list[Stock]) -> None:
        names = [field.name for field in fields(Stock)]
        placeholders = ",".join("?" for _ in names)
        with self.connect() as db:
            db.execute("DELETE FROM stocks")
            db.executemany(f"INSERT INTO stocks ({','.join(names)}) VALUES ({placeholders})",
                           [[getattr(stock, name) for name in names] for stock in stocks])
            db.execute("INSERT OR REPLACE INTO metadata VALUES ('updated_at', ?)",
                       (datetime.now().astimezone().isoformat(timespec="seconds"),))

    def updated_at(self) -> str:
        with self.connect() as db:
            row = db.execute("SELECT value FROM metadata WHERE key='updated_at'").fetchone()
            return row[0] if row else ""

    def metadata(self) -> dict:
        with self.connect() as db:
            rows = db.execute("""
                SELECT industry, COUNT(*) AS stock_count,
                       AVG(momentum_20d) AS momentum_20d,
                       AVG(momentum_120d) AS momentum_120d,
                       AVG(change_pct) AS change_pct,
                       AVG(momentum_120d) * 0.5 + AVG(momentum_20d) * 0.3 + AVG(change_pct) * 0.2 AS heat
                FROM stocks
                GROUP BY industry
                ORDER BY heat DESC, industry ASC
            """).fetchall()
        sectors = [
            {
                "name": row["industry"], "stock_count": row["stock_count"],
                "momentum_20d": round(row["momentum_20d"], 2),
                "momentum_120d": round(row["momentum_120d"], 2),
                "change_pct": round(row["change_pct"], 2), "heat": round(row["heat"], 2),
                "is_hot": index < 6,
            }
            for index, row in enumerate(rows)
        ]
        return {
            "sectors": sectors,
            "industries": [sector["name"] for sector in sectors],  # backward-compatible API
            "count": self.count(), "updated_at": self.updated_at(), "data_mode": "demo",
            "sector_ranking_basis": "20日动量30% + 120日动量50% + 当日涨跌20%",
        }

    def sector_rankings(self) -> dict:
        def rank(rows: list[sqlite3.Row], sector_key: str) -> list[dict]:
            grouped: dict[str, list[sqlite3.Row]] = {}
            for row in rows:
                grouped.setdefault(row[sector_key], []).append(row)
            result = []
            for name, members in grouped.items():
                leader = max(members, key=lambda item: item["change_pct"])
                result.append({
                    "name": name,
                    "change_pct": round(sum(item["change_pct"] for item in members) / len(members), 2),
                    "stock_count": len(members),
                    "leader_name": leader["name"],
                    "leader_change_pct": round(leader["change_pct"], 2),
                })
            return sorted(result, key=lambda item: (-item["change_pct"], item["name"]))

        with self.connect() as db:
            industry_rows = db.execute("SELECT industry, name, change_pct FROM stocks").fetchall()
            concept_rows = db.execute("""
                SELECT c.concept, s.name, s.change_pct
                FROM stock_concepts c JOIN stocks s ON s.code = c.code
            """).fetchall()
        return {
            "concepts": rank(concept_rows, "concept"),
            "industries": rank(industry_rows, "industry"),
            "ranking_basis": "板块内成分股平均涨跌幅",
            "updated_at": self.updated_at(),
        }

    def get_by_codes(self, codes: list[str]) -> list[Stock]:
        if not codes:
            return []
        placeholders = ",".join("?" for _ in codes)
        with self.connect() as db:
            rows = db.execute(
                f"SELECT * FROM stocks WHERE code IN ({placeholders}) ORDER BY change_pct DESC, code ASC",
                codes,
            ).fetchall()
        return [Stock(**dict(row)) for row in rows]

    def screen(self, query: ScreenQuery) -> tuple[list[Stock], int]:
        clauses, params = ["1=1"], []
        if query.keyword:
            clauses.append("(code LIKE ? OR name LIKE ?)")
            keyword = f"%{query.keyword}%"
            params.extend([keyword, keyword])
        if query.industries:
            clauses.append(f"industry IN ({','.join('?' for _ in query.industries)})")
            params.extend(query.industries)
        mapping = {
            "min_market_cap": (">=", query.min_market_cap), "max_market_cap": ("<=", query.max_market_cap),
            "min_pe": (">=", query.min_pe), "max_pe": ("<=", query.max_pe), "min_roe": (">=", query.min_roe),
            "min_revenue_growth": (">=", query.min_revenue_growth),
            "min_profit_growth": (">=", query.min_profit_growth), "max_debt_ratio": ("<=", query.max_debt_ratio),
            "min_turnover_rate": (">=", query.min_turnover_rate), "min_score": (">=", query.min_score),
        }
        columns = {name: name.removeprefix("min_").removeprefix("max_") for name in mapping}
        columns["min_pe"] = columns["max_pe"] = "pe_ttm"
        columns["min_roe"] = "roe_ttm"
        for name, (operator, value) in mapping.items():
            if value is not None:
                clauses.append(f"{columns[name]} {operator} ?")
                params.append(value)
        if query.exclude_st:
            clauses.append("is_st = 0")
        if query.exclude_suspended:
            clauses.append("is_suspended = 0")
        where = " AND ".join(clauses)
        with self.connect() as db:
            total = int(db.execute(f"SELECT COUNT(*) FROM stocks WHERE {where}", params).fetchone()[0])
            sql = f"SELECT * FROM stocks WHERE {where} ORDER BY {query.sort} {query.order.upper()}, code ASC LIMIT ? OFFSET ?"
            rows = db.execute(sql, [*params, query.page_size, (query.page - 1) * query.page_size]).fetchall()
        return [Stock(**dict(row)) for row in rows], total

