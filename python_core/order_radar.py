"""
order_radar.py — Quad-State Decision Engine for Mordu Market Engine.

States: HOLD | OUTBID | EVACUATE | BUYOUT
"""

from __future__ import annotations

import logging
import sqlite3
from enum import Enum
from typing import TypedDict

from init_db import init_db, DB_PATH

logger = logging.getLogger(__name__)


class OrderState(str, Enum):
    HOLD = "HOLD"
    OUTBID = "OUTBID"
    EVACUATE = "EVACUATE"
    BUYOUT = "BUYOUT"


class RadarResult(TypedDict):
    order_id: int
    type_id: int
    type_name: str
    region_id: int
    my_price: float
    best_market_price: float
    state: str
    reason: str
    recommended_price: float
    wall_thickness: int


WALL_THIN_THRESHOLD = 500
WALL_THICK_THRESHOLD = 5000
OUTBID_THRESHOLD = 0.005
EVACUATE_THRESHOLD = 0.02
EVACUATE_MARGIN_FLOOR = 0.02
BUYOUT_COMPETITOR_MAX = 100
PRICE_WALL_BAND = 0.001


class QuadStateEngine:
    def __init__(self, db_path=DB_PATH) -> None:
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = init_db(self.db_path)
        return self._conn

    @staticmethod
    def _wall_thickness(best_price: float, market_orders: list[dict], is_buy: bool) -> int:
        band = best_price * PRICE_WALL_BAND
        total = 0
        for order in market_orders:
            if bool(order.get("is_buy_order")) != is_buy:
                continue
            p = float(order.get("price", 0))
            if is_buy:
                if p >= best_price - band:
                    total += int(order.get("volume_remain", 0))
            else:
                if p <= best_price + band:
                    total += int(order.get("volume_remain", 0))
        return total

    def analyze_order(
        self,
        my_order: dict,
        market_orders: list[dict],
        wallet_balance: float,
    ) -> RadarResult:
        my_price: float = float(my_order.get("price", 0))
        is_buy: bool = bool(my_order.get("is_buy_order", False))
        type_name: str = str(my_order.get("type_name", my_order.get("type_id", "?")))

        same_side = [o for o in market_orders if bool(o.get("is_buy_order")) == is_buy]

        if not same_side:
            return RadarResult(
                order_id=my_order.get("id", 0), type_id=int(my_order.get("type_id", 0)),
                type_name=type_name, region_id=int(my_order.get("region_id", 0)),
                my_price=my_price, best_market_price=my_price,
                state=OrderState.HOLD, reason="No competing orders found.",
                recommended_price=my_price, wall_thickness=0,
            )

        if is_buy:
            best_price = max(float(o.get("price", 0)) for o in same_side)
        else:
            best_price = min(float(o.get("price", 0)) for o in same_side)

        wall = self._wall_thickness(best_price, same_side, is_buy)

        if is_buy:
            undercut_ratio = (best_price - my_price) / my_price if my_price > 0 else 0
        else:
            undercut_ratio = (my_price - best_price) / my_price if my_price > 0 else 0

        i_am_best = undercut_ratio <= 0.0001

        competitor_volume = sum(
            int(o.get("volume_remain", 0))
            for o in same_side
            if abs(float(o.get("price", 0)) - best_price) / max(best_price, 1) < PRICE_WALL_BAND
        )

        if i_am_best and wall < WALL_THIN_THRESHOLD:
            return RadarResult(
                order_id=my_order.get("id", 0), type_id=int(my_order.get("type_id", 0)),
                type_name=type_name, region_id=int(my_order.get("region_id", 0)),
                my_price=my_price, best_market_price=best_price,
                state=OrderState.HOLD, reason="You have the best price with a thin wall. Hold position.",
                recommended_price=my_price, wall_thickness=wall,
            )

        margin_vs_best = (best_price - my_price) / my_price if my_price > 0 else 0
        evacuate_by_undercut = undercut_ratio > EVACUATE_THRESHOLD
        evacuate_by_wall = wall > WALL_THICK_THRESHOLD and margin_vs_best < EVACUATE_MARGIN_FLOOR

        if evacuate_by_undercut or evacuate_by_wall:
            if is_buy:
                recommended = round(best_price * 0.99, 2)
                reason = f"Undercut by {undercut_ratio * 100:.1f}% or thick wall. Cancel and relist below the wall."
            else:
                recommended = round(best_price - 0.01, 2)
                reason = f"Undercut by {undercut_ratio * 100:.1f}% or thick wall. Evacuate: drop price to match market."
            return RadarResult(
                order_id=my_order.get("id", 0), type_id=int(my_order.get("type_id", 0)),
                type_name=type_name, region_id=int(my_order.get("region_id", 0)),
                my_price=my_price, best_market_price=best_price,
                state=OrderState.EVACUATE, reason=reason, recommended_price=recommended, wall_thickness=wall,
            )

        buyout_cost = competitor_volume * best_price
        can_afford = wallet_balance >= buyout_cost and buyout_cost > 0
        if wall < WALL_THIN_THRESHOLD and competitor_volume <= BUYOUT_COMPETITOR_MAX and can_afford:
            return RadarResult(
                order_id=my_order.get("id", 0), type_id=int(my_order.get("type_id", 0)),
                type_name=type_name, region_id=int(my_order.get("region_id", 0)),
                my_price=my_price, best_market_price=best_price,
                state=OrderState.BUYOUT,
                reason=f"Competitor has only {competitor_volume} units at {best_price:,.2f} ISK. Buyout cost ~{buyout_cost:,.0f} ISK. Wallet sufficient.",
                recommended_price=best_price, wall_thickness=wall,
            )

        if is_buy:
            recommended = round(best_price + 0.01, 2)
        else:
            recommended = round(best_price - 0.01, 2)

        return RadarResult(
            order_id=my_order.get("id", 0), type_id=int(my_order.get("type_id", 0)),
            type_name=type_name, region_id=int(my_order.get("region_id", 0)),
            my_price=my_price, best_market_price=best_price,
            state=OrderState.OUTBID,
            reason=f"Undercut by {undercut_ratio * 100:.2f}% (<0.5%). Recommended: undercut by 0.01 ISK.",
            recommended_price=recommended, wall_thickness=wall,
        )

    def run_radar(self, character_id: int, region_id: int) -> list[RadarResult]:
        conn = self.conn
        row = conn.execute("SELECT balance FROM wallet_balance WHERE character_id=?", (character_id,)).fetchone()
        wallet = float(row["balance"]) if row else 0.0
        tracked = conn.execute("SELECT type_id, type_name FROM tracked_items WHERE region_id=? AND active=1", (region_id,)).fetchall()
        results: list[RadarResult] = []
        for item in tracked:
            type_id = item["type_id"]
            type_name = item["type_name"]
            market_orders = [dict(r) for r in conn.execute("SELECT * FROM market_orders WHERE region_id=? AND type_id=?", (region_id, type_id)).fetchall()]
            if not market_orders:
                continue
            buy_orders = [o for o in market_orders if o.get("is_buy_order")]
            sell_orders = [o for o in market_orders if not o.get("is_buy_order")]
            if buy_orders:
                best_buy = max(buy_orders, key=lambda o: float(o.get("price", 0)))
                my_buy = {"id": best_buy.get("id"), "type_id": type_id, "type_name": type_name, "region_id": region_id, "price": float(best_buy.get("price", 0)), "volume_remain": int(best_buy.get("volume_remain", 0)), "is_buy_order": 1}
                results.append(self.analyze_order(my_buy, market_orders, wallet))
            if sell_orders:
                best_sell = min(sell_orders, key=lambda o: float(o.get("price", 0)))
                my_sell = {"id": best_sell.get("id"), "type_id": type_id, "type_name": type_name, "region_id": region_id, "price": float(best_sell.get("price", 0)), "volume_remain": int(best_sell.get("volume_remain", 0)), "is_buy_order": 0}
                results.append(self.analyze_order(my_sell, market_orders, wallet))
        return results

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    engine = QuadStateEngine()
    my_sell_order = {"id": 1, "type_id": 34, "type_name": "Tritanium", "region_id": 10000002, "price": 6.20, "volume_remain": 100_000, "is_buy_order": 0}
    market_book = [
        {"id": 2, "price": 6.19, "volume_remain": 50, "is_buy_order": 0},
        {"id": 1, "price": 6.20, "volume_remain": 100_000, "is_buy_order": 0},
        {"id": 3, "price": 5.50, "volume_remain": 200_000, "is_buy_order": 1},
    ]
    result = engine.analyze_order(my_order=my_sell_order, market_orders=market_book, wallet_balance=500_000_000)
    print("=== Radar Result ===")
    for k, v in result.items():
        print(f"  {k}: {v}")
    engine.close()
