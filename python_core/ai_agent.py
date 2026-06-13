"""
ai_agent.py — Ollama AI integration for Mordu Smart Briefs.

Uses deepseek-r1:8b via the ollama Python SDK with tool-calling to produce
structured market intelligence briefs from the top 15 opportunities.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import ollama

from math_engine import TrueMarginCalculator

logger = logging.getLogger(__name__)

_calc = TrueMarginCalculator()

SYSTEM_PROMPT = (
    "You are Mordu, a ruthless EVE Online market analyst. Analyze the top market "
    "opportunities and provide a concise strategic brief with specific buy/sell "
    "targets and risk assessment. Use the calculation tools for accuracy. Be direct "
    "and tactical."
)

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "calculate_margin",
            "description": "Calculate true net margin for an EVE Online buy/sell trade, accounting for broker fees and sales tax at the given skill levels.",
            "parameters": {
                "type": "object",
                "properties": {
                    "buy_price": {"type": "number", "description": "Price paid to acquire the item (ISK/unit)."},
                    "sell_price": {"type": "number", "description": "Price the item is listed for sale at (ISK/unit)."},
                    "accounting_level": {"type": "integer", "description": "Character's Accounting skill level (0-5)."},
                    "broker_relations_level": {"type": "integer", "description": "Character's Broker Relations skill level (0-5)."},
                },
                "required": ["buy_price", "sell_price", "accounting_level", "broker_relations_level"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_edcy",
            "description": "Calculate Expected Daily ISK (EDCY) for a trade opportunity. Formula: daily_volume * avg_price * net_margin_pct.",
            "parameters": {
                "type": "object",
                "properties": {
                    "daily_volume": {"type": "number", "description": "Average number of units traded per day."},
                    "avg_price": {"type": "number", "description": "Average market price of the item (ISK/unit)."},
                    "net_margin_pct": {"type": "number", "description": "Net margin as a decimal (e.g. 0.12 for 12%)."},
                },
                "required": ["daily_volume", "avg_price", "net_margin_pct"],
            },
        },
    },
]


def _dispatch_tool(tool_name: str, args: dict[str, Any]) -> str:
    if tool_name == "calculate_margin":
        result = _calc.true_margin(
            buy_price=float(args["buy_price"]),
            sell_price=float(args["sell_price"]),
            accounting_level=int(args["accounting_level"]),
            broker_relations_level=int(args["broker_relations_level"]),
        )
        return json.dumps({k: round(v, 6) for k, v in result.items()})
    if tool_name == "calculate_edcy":
        result = _calc.edcy(
            daily_volume=float(args["daily_volume"]),
            avg_price=float(args["avg_price"]),
            net_margin_pct=float(args["net_margin_pct"]),
        )
        return json.dumps({"edcy": round(result, 2)})
    return json.dumps({"error": f"Unknown tool: {tool_name}"})


class SmartBriefAgent:
    MODEL = "deepseek-r1:8b"
    MAX_TOOL_ROUNDS = 8

    def __init__(self, model: str = MODEL) -> None:
        self.model = model

    @staticmethod
    def _format_opportunities(opportunities: list[dict]) -> str:
        lines = [
            "| # | Item | Region | Buy | Sell | Net Margin % | EDCY (ISK/day) |",
            "|---|------|--------|-----|------|--------------|----------------|]",
        ]
        for i, opp in enumerate(opportunities, 1):
            lines.append(
                f"| {i} | {opp.get('type_name', opp.get('type_id', '?'))} "
                f"| {opp.get('region_id', '?')} "
                f"| {opp.get('buy_price', 0):,.2f} "
                f"| {opp.get('sell_price', 0):,.2f} "
                f"| {opp.get('net_margin_pct', 0) * 100:.2f}% "
                f"| {opp.get('edcy', 0):,.0f} |"
            )
        return "\n".join(lines)

    def generate_brief(self, opportunities: list[dict]) -> str:
        top_opps = opportunities[:15]
        if not top_opps:
            return "## Mordu Market Brief\n\n_No opportunities to analyse._"

        opp_table = self._format_opportunities(top_opps)
        user_message = (
            "Here are the top market opportunities identified by the Mordu scanner:\n\n"
            f"{opp_table}\n\n"
            "Provide a strategic brief covering:\n"
            "1. **Top 3 Priority Trades** — specific buy/sell prices and expected ISK/day\n"
            "2. **Risk Assessment** — which trades have thin walls or high competition\n"
            "3. **Capital Allocation** — suggested order sizing\n"
            "4. **Tactical Notes** — timing, station choices, watch-outs\n\n"
            "Use the calculation tools to verify margins on your top picks. Format the output in clean markdown."
        )

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        for round_num in range(self.MAX_TOOL_ROUNDS):
            logger.debug("AI round %d", round_num + 1)
            response = ollama.chat(model=self.model, messages=messages, tools=TOOLS)
            msg = response.get("message", {})
            tool_calls = msg.get("tool_calls") or []

            if not tool_calls:
                return msg.get("content", "").strip()

            messages.append({"role": "assistant", **msg})
            for tc in tool_calls:
                fn = tc.get("function", {})
                tool_result = _dispatch_tool(fn.get("name", ""), fn.get("arguments", {}))
                messages.append({"role": "tool", "content": tool_result})

        messages.append({"role": "user", "content": "Provide your final brief now without using any more tools."})
        final_response = ollama.chat(model=self.model, messages=messages)
        return final_response.get("message", {}).get("content", "").strip()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sample_opportunities = [
        {"type_id": 34, "type_name": "Tritanium", "region_id": 10000002, "buy_price": 5.50, "sell_price": 6.20, "daily_volume": 1_000_000, "avg_price": 5.85, "net_margin_pct": 0.054, "edcy": 315_900, "accounting_level": 4, "broker_relations_level": 4},
        {"type_id": 35, "type_name": "Pyerite", "region_id": 10000002, "buy_price": 10.00, "sell_price": 12.50, "daily_volume": 500_000, "avg_price": 11.25, "net_margin_pct": 0.14, "edcy": 787_500, "accounting_level": 4, "broker_relations_level": 4},
    ]
    agent = SmartBriefAgent()
    print("[ai_agent] Generating brief (requires local Ollama with deepseek-r1:8b)...\n")
    brief = agent.generate_brief(sample_opportunities)
    print(brief)
