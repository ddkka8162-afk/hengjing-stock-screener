from __future__ import annotations

import json
import mimetypes
import re
import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from stock_screener.providers import DemoMarketDataProvider
from stock_screener.crypto import CryptoMarketProvider
from stock_screener.repository import StockRepository
from stock_screener.screening import ScreenQuery, parse_screen_query


ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
DB_PATH = ROOT / "data" / "stocks.db"


class Application:
    def __init__(self) -> None:
        DB_PATH.parent.mkdir(exist_ok=True)
        self.repo = StockRepository(DB_PATH)
        self.repo.initialize()
        if self.repo.count() == 0 or not self.repo.has_heat_scores():
            self.repo.replace_all(DemoMarketDataProvider().load_snapshot())
        if self.repo.concept_count() == 0:
            self.repo.replace_concepts(DemoMarketDataProvider().load_concepts())

    def refresh_demo(self) -> int:
        provider = DemoMarketDataProvider()
        stocks = provider.load_snapshot()
        self.repo.replace_all(stocks)
        self.repo.replace_concepts(provider.load_concepts())
        return len(stocks)


APP = Application()
MARKET_PROVIDER = DemoMarketDataProvider()
CRYPTO_PROVIDER = CryptoMarketProvider()


class Handler(BaseHTTPRequestHandler):
    server_version = "StockScreener/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            return self.json_response({"status": "ok", "time": datetime.now(timezone.utc).isoformat()})
        if parsed.path == "/api/meta":
            return self.json_response(APP.repo.metadata())
        if parsed.path == "/api/market-overview":
            return self.json_response({
                "items": MARKET_PROVIDER.load_index_overview(),
                "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "data_mode": "demo",
            })
        if parsed.path == "/api/sector-rankings":
            return self.json_response(APP.repo.sector_rankings())
        if parsed.path == "/api/watchlist":
            raw_codes = parse_qs(parsed.query).get("codes", [""])[0]
            codes = list(dict.fromkeys(code.strip() for code in raw_codes.split(",") if code.strip()))[:200]
            if any(not re.fullmatch(r"\d{6}", code) for code in codes):
                return self.json_response({"error": "股票代码格式无效"}, HTTPStatus.BAD_REQUEST)
            rows = APP.repo.get_by_codes(codes)
            return self.json_response({
                "items": [asdict(row) for row in rows], "total": len(rows),
                "updated_at": APP.repo.updated_at(),
            })
        if parsed.path == "/api/crypto-markets":
            return self.json_response(CRYPTO_PROVIDER.get_markets())
        if parsed.path == "/api/crypto-history":
            query = parse_qs(parsed.query)
            try:
                return self.json_response(CRYPTO_PROVIDER.get_history(
                    query.get("id", [""])[0], query.get("interval", ["1h"])[0]
                ))
            except ValueError as exc:
                return self.json_response({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        if parsed.path == "/api/screen":
            try:
                query = parse_screen_query(parse_qs(parsed.query))
                rows, total = APP.repo.screen(query)
                return self.json_response({
                    "items": [asdict(row) for row in rows],
                    "total": total,
                    "page": query.page,
                    "page_size": query.page_size,
                    "updated_at": APP.repo.updated_at(),
                    "data_mode": "demo",
                })
            except ValueError as exc:
                return self.json_response({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        if parsed.path == "/api/export.csv":
            try:
                query = parse_screen_query(parse_qs(parsed.query), max_page_size=5000)
                rows, _ = APP.repo.screen(query)
                return self.csv_response(rows)
            except ValueError as exc:
                return self.json_response({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        return self.serve_static(parsed.path)

    def do_POST(self) -> None:
        if urlparse(self.path).path == "/api/admin/refresh-demo":
            return self.json_response({"updated": APP.refresh_demo()})
        self.send_error(HTTPStatus.NOT_FOUND)

    def serve_static(self, request_path: str) -> None:
        relative = "index.html" if request_path == "/" else request_path.lstrip("/")
        candidate = (STATIC / relative).resolve()
        if STATIC.resolve() not in candidate.parents and candidate != STATIC.resolve():
            return self.send_error(HTTPStatus.FORBIDDEN)
        if not candidate.is_file():
            return self.send_error(HTTPStatus.NOT_FOUND)
        body = candidate.read_bytes()
        mime, _ = mimetypes.guess_type(candidate.name)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{mime or 'application/octet-stream'}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def json_response(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def csv_response(self, rows: list) -> None:
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["代码", "名称", "行业", "价格", "涨跌幅", "市值(亿)", "PE", "PB", "ROE", "营收增长", "净利增长", "负债率", "综合得分"])
        for row in rows:
            writer.writerow([row.code, row.name, row.industry, row.price, row.change_pct, row.market_cap,
                             row.pe_ttm, row.pb, row.roe_ttm, row.revenue_growth, row.profit_growth,
                             row.debt_ratio, row.score])
        body = ("\ufeff" + output.getvalue()).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", 'attachment; filename="stock-screen.csv"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        print(f"[{self.log_date_time_string()}] {format % args}")


def main() -> None:
    host, port = "127.0.0.1", 8000
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"量化选股器已启动：http://{host}:{port}")
    print("按 Ctrl+C 停止")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

