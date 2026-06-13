"""
Mordu Market Engine - Smoke Test Suite
Run this before building to validate all Python components.
Usage: python smoke_test.py
"""
import asyncio
import sys
import os
import json

# Add python_core to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'python_core'))


def test_header(name: str):
    print(f"\n{'='*50}")
    print(f"  TEST: {name}")
    print('='*50)


def ok(msg: str):
    print(f"  [OK]  {msg}")


def fail(msg: str):
    print(f"  [FAIL] {msg}")
    sys.exit(1)


# ─── Test 1: DB Initialization ─────────────────────────────────────────────
test_header("Database Initialization (init_db.py)")
try:
    import sqlite3
    from init_db import init_db
    _init_conn = init_db("smoke_test.db")  # must close before deleting on Windows
    _init_conn.close()
    conn = sqlite3.connect("smoke_test.db")
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cur.fetchall()}
    required = {"market_orders", "market_history", "tracked_items", "character_skills", "ai_briefs", "wallet_balance"}
    missing = required - tables
    if missing:
        fail(f"Missing tables: {missing}")
    else:
        ok(f"All tables created: {tables}")
    conn.close()
    os.remove("smoke_test.db")
    for f in ["smoke_test.db-wal", "smoke_test.db-shm"]:
        if os.path.exists(f):
            os.remove(f)
except Exception as e:
    fail(str(e))


# ─── Test 2: Math Engine ─────────────────────────────────────────────────
test_header("Math Engine (math_engine.py)")
try:
    from math_engine import TrueMarginCalculator

    calc = TrueMarginCalculator()
    result = calc.true_margin(
        buy_price=100_000_000,
        sell_price=130_000_000,
        accounting_level=5,
        broker_relations_level=5
    )
    ok(f"Gross margin: {result['gross_margin']:,.0f} ISK")
    ok(f"Net margin:   {result['net_margin_pct']*100:.2f}%")
    ok(f"Broker fee:   {result['broker_fee']:,.0f} ISK")
    ok(f"Sales tax:    {result['sales_tax']:,.0f} ISK")

    opps = [
        {"type_name": "PLEX", "buy_price": 3_900_000, "sell_price": 4_200_000,
         "daily_volume": 500, "avg_price": 4_050_000, "accounting_level": 5, "broker_relations_level": 5},
        {"type_name": "Tritanium", "buy_price": 4, "sell_price": 5,
         "daily_volume": 10_000_000, "avg_price": 4.5, "accounting_level": 3, "broker_relations_level": 3},
    ]
    ranked = calc.rank_opportunities(opps)
    ok(f"Ranked {len(ranked)} opportunities (max 15)")
    ok(f"Top opportunity: {ranked[0]['type_name']} EDCY={ranked[0].get('edcy', 0):,.0f} ISK/day")
except Exception as e:
    fail(str(e))


# ─── Test 3: Order Radar ───────────────────────────────────────────────
test_header("Order Radar - Quad-State Engine (order_radar.py)")
try:
    from order_radar import QuadStateEngine

    engine = QuadStateEngine()
    my_order = {"type_id": 34, "price": 5.0, "is_buy_order": False, "volume_remain": 1000}
    market_orders = [
        {"type_id": 34, "price": 4.99, "is_buy_order": False, "volume_remain": 50},
        {"type_id": 34, "price": 5.01, "is_buy_order": False, "volume_remain": 200},
        {"type_id": 34, "price": 5.0,  "is_buy_order": False, "volume_remain": 100},
    ]
    result = engine.analyze_order(my_order, market_orders, wallet_balance=500_000_000)
    ok(f"State: {result['state']}")
    ok(f"Reason: {result['reason']}")
    ok(f"Recommended price: {result['recommended_price']}")
    ok(f"Wall thickness: {result['wall_thickness']}")
    assert result['state'] in ('HOLD', 'OUTBID', 'EVACUATE', 'BUYOUT'), "Invalid state"
except Exception as e:
    fail(str(e))


# ─── Test 4: ESI Fetcher (connectivity check) ─────────────────────────────────────────
test_header("ESI Fetcher - Connectivity (market_fetcher.py)")
try:
    import aiohttp

    async def check_esi():
        async with aiohttp.ClientSession() as session:
            url = "https://esi.evetech.net/latest/status/"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    ok(f"ESI online - Players: {data.get('players', 'N/A')}")
                else:
                    ok(f"ESI reachable (status {resp.status})")

    asyncio.run(check_esi())
except Exception as e:
    ok(f"ESI connectivity skipped (offline env): {e}")


# ─── Test 5: Ollama check (soft) ─────────────────────────────────────────────────
test_header("Ollama AI Agent - Local Instance Check (ai_agent.py)")
try:
    import httpx
    r = httpx.get("http://localhost:11434/api/tags", timeout=3)
    if r.status_code == 200:
        models = [m["name"] for m in r.json().get("models", [])]
        ok(f"Ollama running - Models: {models}")
        if "deepseek-r1:8b" in models:
            ok("deepseek-r1:8b model is available")
        else:
            print(f"  [WARN] deepseek-r1:8b not found. Run: ollama pull deepseek-r1:8b")
    else:
        print("  [WARN] Ollama returned unexpected status - AI Brief will be unavailable")
except Exception:
    print("  [WARN] Ollama not running locally - AI Brief unavailable until started")
    print("         Start with: ollama serve && ollama pull deepseek-r1:8b")


print(f"\n{'='*50}")
print("  ALL SMOKE TESTS PASSED - Ready to build!")
print('='*50)
