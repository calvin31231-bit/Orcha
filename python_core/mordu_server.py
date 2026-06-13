"""
mordu_server.py — Master orchestrator for the Mordu Market Engine.

Exposes a JSON HTTP API on port 5000 via aiohttp.web.
Runs the FastAPI SSO server (port 5001) in a background thread.
Runs market fetch pipeline every 5 minutes.

API endpoints:
  GET  /api/opportunities
  GET  /api/orders/radar
  GET  /api/brief
  GET  /api/wallet/{character_id}
  GET  /api/status
  POST /api/track
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from datetime import datetime, timezone
from typing import Any

from aiohttp import web

from ai_agent import SmartBriefAgent
from init_db import init_db, DB_PATH
from market_fetcher import MarketFetcher
from math_engine import TrueMarginCalculator, rank_opportunities
from order_radar import QuadStateEngine
from sso_auth import run_sso_server

logger = logging.getLogger(__name__)

API_PORT = 5000
SSO_PORT = 5001
FETCH_INTERVAL_SECONDS = 300

CORS_ORIGINS = [
    "http://localhost",
    "http://localhost:5000",
    "http://localhost:1420",
    "tauri://localhost",
]

_pipeline_state: dict[str, Any] = {
    "last_fetch": None,
    "next_fetch": None,
    "items_tracked": 0,
    "orders_fetched": 0,
    "history_rows_fetched": 0,
    "is_running": False,
}


def _get_db():
    return init_db(DB_PATH)


@web.middleware
async def cors_middleware(request: web.Request, handler) -> web.Response:
    origin = request.headers.get("Origin", "")
    allow_origin = origin if origin in CORS_ORIGINS else CORS_ORIGINS[0]

    if request.method == "OPTIONS":
        return web.Response(
            status=204,
            headers={
                "Access-Control-Allow-Origin": allow_origin,
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization",
                "Access-Control-Max-Age": "86400",
            },
        )

    response = await handler(request)
    response.headers["Access-Control-Allow-Origin"] = allow_origin
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response


def _json_response(data: Any, status: int = 200) -> web.Response:
    return web.Response(text=json.dumps(data, default=str), status=status, content_type="application/json")


async def handle_opportunities(request: web.Request) -> web.Response:
    db = _get_db()
    tracked = db.execute("SELECT type_id, type_name, region_id FROM tracked_items WHERE active=1").fetchall()
    opportunities = []
    for item in tracked:
        type_id = item["type_id"]
        region_id = item["region_id"]
        sell_row = db.execute("SELECT MIN(price) as best_sell FROM market_orders WHERE region_id=? AND type_id=? AND is_buy_order=0", (region_id, type_id)).fetchone()
        buy_row = db.execute("SELECT MAX(price) as best_buy FROM market_orders WHERE region_id=? AND type_id=? AND is_buy_order=1", (region_id, type_id)).fetchone()
        hist_row = db.execute("SELECT AVG(volume) as avg_vol, AVG(average) as avg_price FROM (SELECT volume, average FROM market_history WHERE region_id=? AND type_id=? ORDER BY date DESC LIMIT 30)", (region_id, type_id)).fetchone()
        best_sell = sell_row["best_sell"] if sell_row and sell_row["best_sell"] else None
        best_buy = buy_row["best_buy"] if buy_row and buy_row["best_buy"] else None
        if not best_sell or not best_buy:
            continue
        opportunities.append({
            "type_id": type_id, "type_name": item["type_name"], "region_id": region_id,
            "buy_price": best_buy, "sell_price": best_sell,
            "daily_volume": hist_row["avg_vol"] or 0 if hist_row else 0,
            "avg_price": hist_row["avg_price"] or 0 if hist_row else 0,
            "accounting_level": 4, "broker_relations_level": 4,
        })
    db.close()
    return _json_response(rank_opportunities(opportunities))


async def handle_radar(request: web.Request) -> web.Response:
    engine = QuadStateEngine()
    character_id = int(request.rel_url.query.get("character_id", 0))
    region_id = int(request.rel_url.query.get("region_id", 10000002))
    if character_id == 0:
        db = _get_db()
        row = db.execute("SELECT character_id FROM wallet_balance LIMIT 1").fetchone()
        db.close()
        character_id = row["character_id"] if row else 0
    if not character_id:
        return _json_response({"error": "No authenticated character found"}, status=400)
    results = engine.run_radar(character_id=character_id, region_id=region_id)
    engine.close()
    return _json_response(results)


async def handle_brief(request: web.Request) -> web.Response:
    db = _get_db()
    tracked = db.execute("SELECT type_id, type_name, region_id FROM tracked_items WHERE active=1").fetchall()
    opportunities = []
    for item in tracked:
        type_id = item["type_id"]
        region_id = item["region_id"]
        sell_row = db.execute("SELECT MIN(price) as p FROM market_orders WHERE region_id=? AND type_id=? AND is_buy_order=0", (region_id, type_id)).fetchone()
        buy_row = db.execute("SELECT MAX(price) as p FROM market_orders WHERE region_id=? AND type_id=? AND is_buy_order=1", (region_id, type_id)).fetchone()
        hist_row = db.execute("SELECT AVG(volume) as avg_vol, AVG(average) as avg_price FROM (SELECT volume, average FROM market_history WHERE region_id=? AND type_id=? ORDER BY date DESC LIMIT 30)", (region_id, type_id)).fetchone()
        best_sell = sell_row["p"] if sell_row and sell_row["p"] else None
        best_buy = buy_row["p"] if buy_row and buy_row["p"] else None
        if not best_sell or not best_buy:
            continue
        opportunities.append({
            "type_id": type_id, "type_name": item["type_name"], "region_id": region_id,
            "buy_price": best_buy, "sell_price": best_sell,
            "daily_volume": hist_row["avg_vol"] or 0 if hist_row else 0,
            "avg_price": hist_row["avg_price"] or 0 if hist_row else 0,
            "accounting_level": 4, "broker_relations_level": 4,
        })
    db.close()
    top_opps = rank_opportunities(opportunities)
    agent = SmartBriefAgent()
    loop = asyncio.get_event_loop()
    brief_text = await loop.run_in_executor(None, agent.generate_brief, top_opps)
    db2 = _get_db()
    db2.execute("INSERT INTO ai_briefs (brief_text) VALUES (?)", (brief_text,))
    db2.commit()
    db2.close()
    return _json_response({"brief": brief_text})


async def handle_wallet(request: web.Request) -> web.Response:
    character_id = int(request.match_info["character_id"])
    db = _get_db()
    row = db.execute("SELECT balance, updated_at FROM wallet_balance WHERE character_id=?", (character_id,)).fetchone()
    db.close()
    if not row:
        return _json_response({"error": f"No wallet data for character {character_id}"}, status=404)
    return _json_response({"character_id": character_id, "balance": row["balance"], "updated_at": row["updated_at"]})


async def handle_status(request: web.Request) -> web.Response:
    db = _get_db()
    n = db.execute("SELECT COUNT(*) as n FROM tracked_items WHERE active=1").fetchone()["n"]
    db.close()
    _pipeline_state["items_tracked"] = n
    return _json_response(_pipeline_state)


async def handle_track(request: web.Request) -> web.Response:
    try:
        body = await request.json()
    except Exception:
        return _json_response({"error": "Invalid JSON body"}, status=400)
    type_id = body.get("type_id")
    type_name = body.get("type_name", f"Type_{type_id}")
    region_id = body.get("region_id", 10000002)
    if not type_id:
        return _json_response({"error": "type_id is required"}, status=400)
    db = _get_db()
    try:
        db.execute("INSERT OR REPLACE INTO tracked_items (type_id, type_name, region_id, active) VALUES (?, ?, ?, 1)", (int(type_id), str(type_name), int(region_id)))
        db.commit()
    except Exception as exc:
        db.close()
        return _json_response({"error": str(exc)}, status=500)
    db.close()
    return _json_response({"status": "ok", "type_id": type_id, "type_name": type_name, "region_id": region_id})


async def market_pipeline_loop() -> None:
    fetcher = MarketFetcher()
    while True:
        db = _get_db()
        tracked = db.execute("SELECT DISTINCT type_id, region_id FROM tracked_items WHERE active=1").fetchall()
        db.close()
        region_ids = list({row["region_id"] for row in tracked})
        type_ids = list({row["type_id"] for row in tracked})
        if region_ids:
            _pipeline_state["is_running"] = True
            try:
                summary = await fetcher.run_pipeline(region_ids, type_ids)
                _pipeline_state.update(summary)
                _pipeline_state["last_fetch"] = datetime.now(timezone.utc).isoformat()
            except Exception as exc:
                logger.error("[pipeline] Fetch failed: %s", exc)
            finally:
                _pipeline_state["is_running"] = False
        next_at = datetime.now(timezone.utc).timestamp() + FETCH_INTERVAL_SECONDS
        _pipeline_state["next_fetch"] = datetime.fromtimestamp(next_at, tz=timezone.utc).isoformat()
        await asyncio.sleep(FETCH_INTERVAL_SECONDS)


def _start_sso_thread() -> threading.Thread:
    thread = threading.Thread(target=run_sso_server, kwargs={"host": "0.0.0.0", "port": SSO_PORT}, daemon=True, name="mordu-sso")
    thread.start()
    logger.info("[sso] SSO server thread started on port %d", SSO_PORT)
    return thread


def build_app() -> web.Application:
    app = web.Application(middlewares=[cors_middleware])
    app.router.add_get("/api/opportunities", handle_opportunities)
    app.router.add_get("/api/orders/radar", handle_radar)
    app.router.add_get("/api/brief", handle_brief)
    app.router.add_get("/api/wallet/{character_id}", handle_wallet)
    app.router.add_get("/api/status", handle_status)
    app.router.add_post("/api/track", handle_track)
    for path in ["/api/opportunities", "/api/orders/radar", "/api/brief", "/api/wallet/{character_id}", "/api/status", "/api/track"]:
        app.router.add_route("OPTIONS", path, lambda r: web.Response(status=204))
    return app


async def _async_main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    db = _get_db()
    logger.info("[main] Database initialised at %s", DB_PATH)
    db.close()
    _start_sso_thread()
    pipeline_task = asyncio.create_task(market_pipeline_loop())
    app = build_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=API_PORT)
    await site.start()
    logger.info("[main] Mordu API server listening on port %d", API_PORT)
    try:
        await asyncio.gather(pipeline_task)
    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info("[main] Shutting down...")
    finally:
        pipeline_task.cancel()
        await runner.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(_async_main())
    except KeyboardInterrupt:
        print("\n[main] Stopped by user.")
