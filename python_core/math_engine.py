"""
math_engine.py — Market math calculations for Mordu Market Engine.

Implements broker fee, sales tax, true margin, EDCY, and opportunity ranking.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict


class MarginResult(TypedDict):
    gross_margin: float
    broker_fee: float
    sales_tax: float
    net_margin: float
    net_margin_pct: float


class Opportunity(TypedDict, total=False):
    type_id: int
    type_name: str
    region_id: int
    buy_price: float
    sell_price: float
    daily_volume: float
    avg_price: float
    accounting_level: int
    broker_relations_level: int
    gross_margin: float
    broker_fee: float
    sales_tax: float
    net_margin: float
    net_margin_pct: float
    edcy: float


class TrueMarginCalculator:
    """
    Calculates realistic EVE Online trade margins including broker fees and sales tax.

    Broker fee formula  : 0.03 * (1 - 0.003 * broker_relations_level), floor 0.01
    Sales tax formula   : 0.08 * (1 - 0.11 * accounting_level)
    """

    @staticmethod
    def broker_fee_rate(broker_relations_level: int) -> float:
        rate = 0.03 * (1.0 - 0.003 * broker_relations_level)
        return max(rate, 0.01)

    @staticmethod
    def sales_tax_rate(accounting_level: int) -> float:
        return 0.08 * (1.0 - 0.11 * accounting_level)

    def true_margin(
        self,
        buy_price: float,
        sell_price: float,
        accounting_level: int,
        broker_relations_level: int,
    ) -> MarginResult:
        bf_rate = self.broker_fee_rate(broker_relations_level)
        st_rate = self.sales_tax_rate(accounting_level)

        buy_broker_fee = buy_price * bf_rate
        sell_broker_fee = sell_price * bf_rate
        sales_tax = sell_price * st_rate

        total_broker_fee = buy_broker_fee + sell_broker_fee

        gross_margin = sell_price - buy_price
        net_margin = gross_margin - total_broker_fee - sales_tax
        net_margin_pct = net_margin / buy_price if buy_price > 0 else 0.0

        return MarginResult(
            gross_margin=gross_margin,
            broker_fee=total_broker_fee,
            sales_tax=sales_tax,
            net_margin=net_margin,
            net_margin_pct=net_margin_pct,
        )

    @staticmethod
    def edcy(
        daily_volume: float,
        avg_price: float,
        net_margin_pct: float,
    ) -> float:
        return daily_volume * avg_price * net_margin_pct

    def rank_opportunities(
        self,
        opportunities: list[Opportunity],
    ) -> list[Opportunity]:
        enriched: list[Opportunity] = []

        for opp in opportunities:
            margin = self.true_margin(
                buy_price=float(opp.get("buy_price", 0)),
                sell_price=float(opp.get("sell_price", 0)),
                accounting_level=int(opp.get("accounting_level", 0)),
                broker_relations_level=int(opp.get("broker_relations_level", 0)),
            )

            score = self.edcy(
                daily_volume=float(opp.get("daily_volume", 0)),
                avg_price=float(opp.get("avg_price", 0)),
                net_margin_pct=margin["net_margin_pct"],
            )

            enriched_opp: Opportunity = {
                **opp,  # type: ignore[misc]
                "gross_margin": margin["gross_margin"],
                "broker_fee": margin["broker_fee"],
                "sales_tax": margin["sales_tax"],
                "net_margin": margin["net_margin"],
                "net_margin_pct": margin["net_margin_pct"],
                "edcy": score,
            }
            enriched.append(enriched_opp)

        enriched.sort(key=lambda x: x.get("edcy", 0.0), reverse=True)
        return enriched[:15]


_calculator = TrueMarginCalculator()
calculate_margin = _calculator.true_margin
calculate_edcy = _calculator.edcy
rank_opportunities = _calculator.rank_opportunities


if __name__ == "__main__":
    calc = TrueMarginCalculator()
    result = calc.true_margin(
        buy_price=5.50, sell_price=6.20, accounting_level=4, broker_relations_level=4
    )
    print("=== True Margin ===")
    for k, v in result.items():
        print(f"  {k}: {v:.6f}")

    edcy_val = calc.edcy(daily_volume=1_000_000, avg_price=5.85, net_margin_pct=result["net_margin_pct"])
    print(f"\nEDCY: {edcy_val:,.2f} ISK/day")
