"""
market_fetcher.py — Async ESI market data fetcher with ETag caching.
Fetches orders and history from the EVE Online ESI API and stores them in SQLite.
"""

import asyncio
import sqlite3
import logging
from datetime import datetime, timezone
from typing import Any

import aiohttp

from init_db import init_db, DB_PATH

logger = logging.getLogger(__name__)

ESI_BASE = "https://esi.evetech.net/latest"
MAX_CONCURRENT = 10  # asyncio.Semaphore cap


class MarketFetcher:
    """
    Async ESI market data fetcher.

    Uses ETag caching to respect ESI's 5-minute cache windows.
    Writes results directly into the mordu.db SQLite database.
    """

    def __init__(self, db_path=DB_PATH) -> None:
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = init_db(self.db_path)
        return self._conn

    def _get_cached_etag_for_orders(self, region_id: int) -> str | None:
        row = self.conn.execute(
            "SELECT etag FROM market_orders WHERE region_id=? AND etag IS NOT NULL LIMIT 1",
            (region_id,),
        ).fetchone()
        return row["etag"] if row else None

    def _upsert_orders(self, region_id: int, orders: list[dict], etag: str | None) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute("DELETE FROM market_orders WHERE region_id=?", (region_id,))
        self.conn.executemany(
            """
            INSERT INTO market_orders
                (region_id, type_id, price, volume_remain, is_buy_order,
                 location_id, issued, expires, etag, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    region_id,
                    o.get("type_id"),
                    o.get("price", 0.0),
                    o.get("volume_remain", 0),
                    1 if o.get("is_buy_order") else 0,
                    o.get("location_id"),
                    o.get("issued", ""),
                    o.get("expires", ""),
                    etag,
                    now,
                )
                for o in orders
            ],
        )
        self.conn.commit()

    def _upsert_history(self, region_id: int, type_id: int, history: list[dict]) -> None:
        self.conn.executemany(
            """
            INSERT OR REPLACE INTO market_history
                (region_id, type_id, date, average, highest, lowest, order_count, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    region_id,
                    type_id,
                    h.get("date", ""),
                    h.get("average", 0.0),
                    h.get("highest", 0.0),
                    h.get("lowest", 0.0),
                    h.get("order_count", 0),
                    h.get("volume", 0),
                )
                for h in history
            ],
        )
        self.conn.commit()

    async def _fetch_all_pages(
        self,
        session: aiohttp.ClientSession,
        url: str,
        headers: dict[str, str],
    ) -> tuple[list[Any], str | None, str | None]:
        page = 1
        combined: list[Any] = []
        etag_out: str | None = None
        expires_out: str | None = None

        while True:
            paged_url = f"{url}?page={page}" if "?" not in url else f"{url}&page={page}"
            async with self._semaphore:
                async with session.get(paged_url, headers=headers) as resp:
                    if resp.status == 304:
                        logger.debug("304 Not Modified: %s", url)
                        return [], None, None

                    resp.raise_for_status()
                    data = await resp.json()
                    combined.extend(data if isinstance(data, list) else [data])

                    if page == 1:
                        etag_out = resp.headers.get("ETag")
                        expires_out = resp.headers.get("X-Expires")

                    total_pages = int(resp.headers.get("X-Pages", 1))
                    if page >= total_pages:
                        break
                    page += 1

        return combined, etag_out, expires_out

    async def fetch_orders(
        self,
        region_id: int,
        session: aiohttp.ClientSession | None = None,
    ) -> list[dict]:
        url = f"{ESI_BASE}/markets/{region_id}/orders/"
        cached_etag = self._get_cached_etag_for_orders(region_id)
        headers: dict[str, str] = {}
        if cached_etag:
            headers["If-None-Match"] = cached_etag

        own_session = session is None
        if own_session:
            session = aiohttp.ClientSession()

        try:
            orders, etag, _expires = await self._fetch_all_pages(session, url, headers)
        finally:
            if own_session:
                await session.close()

        if orders:
            self._upsert_orders(region_id, orders, etag)
            logger.info("Stored %d orders for region %d", len(orders), region_id)
        else:
            logger.info("Orders cache hit (304) for region %d", region_id)
            rows = self.conn.execute(
                "SELECT * FROM market_orders WHERE region_id=?", (region_id,)
            ).fetchall()
            orders = [dict(r) for r in rows]

        return orders

    async def fetch_history(
        self,
        region_id: int,
        type_id: int,
        session: aiohttp.ClientSession | None = None,
    ) -> list[dict]:
        url = f"{ESI_BASE}/markets/{region_id}/history/?type_id={type_id}"
        headers: dict[str, str] = {}

        own_session = session is None
        if own_session:
            session = aiohttp.ClientSession()

        try:
            async with self._semaphore:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 304:
                        rows = self.conn.execute(
                            "SELECT * FROM market_history WHERE region_id=? AND type_id=?",
                            (region_id, type_id),
                        ).fetchall()
                        return [dict(r) for r in rows]

                    resp.raise_for_status()
                    history: list[dict] = await resp.json()
        finally:
            if own_session:
                await session.close()

        self._upsert_history(region_id, type_id, history)
        logger.info("Stored %d history rows for type %d in region %d", len(history), type_id, region_id)
        return history

    async def run_pipeline(
        self,
        region_ids: list[int],
        type_ids: list[int],
    ) -> dict[str, int]:
        async with aiohttp.ClientSession() as session:
            order_tasks = [self.fetch_orders(rid, session) for rid in region_ids]
            order_results = await asyncio.gather(*order_tasks, return_exceptions=True)

            total_orders = 0
            for rid, result in zip(region_ids, order_results):
                if isinstance(result, Exception):
                    logger.error("Orders fetch failed for region %d: %s", rid, result)
                else:
                    total_orders += len(result)

            history_tasks = [
                self.fetch_history(rid, tid, session)
                for rid in region_ids
                for tid in type_ids
            ]
            history_results = await asyncio.gather(*history_tasks, return_exceptions=True)

            total_history = 0
            for result in history_results:
                if isinstance(result, Exception):
                    logger.error("History fetch failed: %s", result)
                else:
                    total_history += len(result)

        return {"orders_fetched": total_orders, "history_rows_fetched": total_history}

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    fetcher = MarketFetcher()

    async def smoke() -> None:
        result = await fetcher.run_pipeline(region_ids=[10000002], type_ids=[34])
        print("Pipeline result:", result)

    asyncio.run(smoke())
    fetcher.close()
