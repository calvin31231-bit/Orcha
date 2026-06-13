"""
sso_auth.py — FastAPI server for EVE Online OAuth2/SSO authentication.

Handles the OAuth2 authorization code flow, JWT validation, token storage,
and refresh token lifecycle. Run on port 5001.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import sqlite3
import time
from pathlib import Path
from typing import Any

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from init_db import init_db, DB_PATH

logger = logging.getLogger(__name__)

EVE_CLIENT_ID: str = os.environ.get("EVE_CLIENT_ID", "")
EVE_CLIENT_SECRET: str = os.environ.get("EVE_CLIENT_SECRET", "")
EVE_CALLBACK_URL: str = os.environ.get("EVE_CALLBACK_URL", "http://localhost:5001/callback")
EVE_TOKEN_URL = "https://login.eveonline.com/v2/oauth/token"
EVE_VERIFY_URL = "https://esi.evetech.net/verify/"
SSO_PORT = 5001

app = FastAPI(title="Mordu SSO", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "tauri://localhost", "http://localhost:5000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_db_conn: sqlite3.Connection | None = None


def get_db() -> sqlite3.Connection:
    global _db_conn
    if _db_conn is None:
        _db_conn = init_db()
    return _db_conn


def _decode_jwt_payload(token: str) -> dict[str, Any]:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Not a JWT")
        payload_b64 = parts[1] + "=" * (4 - len(parts[1]) % 4)
        return json.loads(base64.urlsafe_b64decode(payload_b64))
    except Exception as exc:
        raise ValueError(f"JWT decode failed: {exc}") from exc


def _verify_jwt_via_esi(access_token: str) -> dict[str, Any]:
    resp = httpx.get(EVE_VERIFY_URL, headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
    resp.raise_for_status()
    return resp.json()


def _exchange_code_for_tokens(code: str) -> dict[str, Any]:
    if not EVE_CLIENT_ID or not EVE_CLIENT_SECRET:
        raise RuntimeError("EVE_CLIENT_ID and EVE_CLIENT_SECRET must be set as environment variables")
    credentials = base64.b64encode(f"{EVE_CLIENT_ID}:{EVE_CLIENT_SECRET}".encode()).decode()
    resp = httpx.post(
        EVE_TOKEN_URL,
        headers={"Authorization": f"Basic {credentials}", "Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "authorization_code", "code": code},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def _refresh_access_token(refresh_token: str) -> dict[str, Any]:
    if not EVE_CLIENT_ID or not EVE_CLIENT_SECRET:
        raise RuntimeError("EVE_CLIENT_ID and EVE_CLIENT_SECRET must be set")
    credentials = base64.b64encode(f"{EVE_CLIENT_ID}:{EVE_CLIENT_SECRET}".encode()).decode()
    resp = httpx.post(
        EVE_TOKEN_URL,
        headers={"Authorization": f"Basic {credentials}", "Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def _store_tokens(character_id: int, character_name: str, access_token: str, refresh_token: str, expires_in: int, scope: str) -> None:
    expires_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + expires_in))
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO refresh_tokens (character_id, refresh_token, access_token, expires_at, character_name, updated_at) VALUES (?, ?, ?, ?, ?, datetime('now'))",
        (character_id, refresh_token, access_token, expires_at, character_name),
    )
    conn.commit()


def _load_refresh_token(character_id: int) -> str | None:
    row = get_db().execute("SELECT refresh_token FROM refresh_tokens WHERE character_id=?", (character_id,)).fetchone()
    return row["refresh_token"] if row else None


def _update_access_token(character_id: int, access_token: str, expires_in: int, new_refresh: str) -> None:
    expires_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + expires_in))
    get_db().execute(
        "UPDATE refresh_tokens SET access_token=?, expires_at=?, refresh_token=?, updated_at=datetime('now') WHERE character_id=?",
        (access_token, expires_at, new_refresh, character_id),
    )
    get_db().commit()


@app.get("/callback")
async def oauth_callback(code: str = Query(...)) -> JSONResponse:
    try:
        token_data = _exchange_code_for_tokens(code)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail="Token exchange with EVE SSO failed")
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    access_token: str = token_data.get("access_token", "")
    refresh_token: str = token_data.get("refresh_token", "")
    expires_in: int = int(token_data.get("expires_in", 1200))
    scope: str = token_data.get("scope", "")

    try:
        char_info = _verify_jwt_via_esi(access_token)
    except Exception:
        raise HTTPException(status_code=502, detail="EVE ESI token verification failed")

    character_id: int = int(char_info.get("CharacterID", 0))
    character_name: str = char_info.get("CharacterName", "Unknown")

    if not character_id:
        raise HTTPException(status_code=500, detail="Could not extract character ID from JWT")

    _store_tokens(character_id, character_name, access_token, refresh_token, expires_in, scope)
    return JSONResponse({"status": "ok", "character_id": character_id, "character_name": character_name, "scope": scope, "expires_in": expires_in})


@app.get("/refresh/{character_id}")
async def refresh_token_endpoint(character_id: int) -> JSONResponse:
    stored_refresh = _load_refresh_token(character_id)
    if not stored_refresh:
        raise HTTPException(status_code=404, detail=f"No refresh token found for character {character_id}")
    try:
        token_data = _refresh_access_token(stored_refresh)
    except httpx.HTTPStatusError:
        raise HTTPException(status_code=502, detail="Refresh token exchange failed")
    new_access: str = token_data.get("access_token", "")
    new_refresh: str = token_data.get("refresh_token", stored_refresh)
    expires_in: int = int(token_data.get("expires_in", 1200))
    _update_access_token(character_id, new_access, expires_in, new_refresh)
    return JSONResponse({"status": "ok", "character_id": character_id, "access_token": new_access, "expires_in": expires_in})


@app.get("/characters")
async def list_characters() -> JSONResponse:
    rows = get_db().execute("SELECT character_id, character_name, expires_at, updated_at FROM refresh_tokens").fetchall()
    return JSONResponse([dict(r) for r in rows])


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "mordu-sso"})


def run_sso_server(host: str = "0.0.0.0", port: int = SSO_PORT) -> None:
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if not EVE_CLIENT_ID:
        print("[sso_auth] WARNING: EVE_CLIENT_ID not set — token exchange will fail.")
    print(f"[sso_auth] Starting SSO server on port {SSO_PORT}")
    run_sso_server()
